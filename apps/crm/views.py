from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Prefetch, Q
from django.http import HttpResponseRedirect
from django.utils import timezone
from datetime import date
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, RedirectView, TemplateView, UpdateView

from apps.crm.forms import (
    DataSourceForm,
    OriForm,
    TelecomOperatorForm,
    TelecomOperatorLicenseForm,
    LicenseOrderForm,
    OrgActionCreateForm,
    OrgActionEditForm,
    PsiAssignmentForm,
)
from apps.crm.models import (
    Contact,
    DataSource,
    Ori,
    Comment,
    ActionTemplate,
    OrgAction,
    OrgActionStatus,
    Psi,
    TelecomOperatorLicense,
    TelecomOperator,
    TelecomOperatorAuditEvent,
)
from apps.crm.action_template_utils import (
    action_template_items_from_actions,
    normalize_action_template_items,
)
from apps.crm.psi_utils import (
    annotate_psi_schedule_hints,
    build_psi_busy_ranges,
    build_psi_history_payload,
    partition_psis,
)
from apps.crm.rkn_licenses import RknSyncError, sync_telecom_operator_licenses_from_rkn


TELECOM_OPERATOR_MENU_LABEL = "Операторы связи"


def _is_truthy_mine(value) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class PanelMenuMixin:
    panel_title = "D.3.0"

    def get_panel_menu(self):
        request = self.request
        current_path = request.path.rstrip("/")
        ori_url = reverse("panel:ori_list")
        data_sources_url = reverse("panel:data_source_list")
        telecom_operators_url = reverse("panel:telecom_operator_list")
        telecom_licenses_prefix = reverse("panel:telecom_license_detail", kwargs={"pk": 1}).rsplit("/", 2)[0]

        ori_base = ori_url.rstrip("/")
        data_sources_base = data_sources_url.rstrip("/")
        telecom_base = telecom_operators_url.rstrip("/")
        mine_param = request.GET.get("mine", "")

        is_ori_list = current_path == ori_base
        is_ori_section = current_path == ori_base or current_path.startswith(f"{ori_base}/")
        is_data_sources_section = (
            current_path == data_sources_base or current_path.startswith(f"{data_sources_base}/")
        )
        is_telecom_section = (
            current_path == telecom_base
            or current_path.startswith(f"{telecom_base}/")
            or current_path.startswith(telecom_licenses_prefix)
        )

        org_children = [
            {
                "name": TELECOM_OPERATOR_MENU_LABEL,
                "url": telecom_operators_url,
                "is_active": is_telecom_section,
            },
            {
                "name": "ОРИ",
                "url": ori_url,
                "is_active": is_ori_list and not _is_truthy_mine(mine_param),
            },
            {
                "name": "Источники данных",
                "url": data_sources_url,
                "is_active": is_data_sources_section,
            },
            {
                "name": "Мои дела",
                "url": f"{ori_url}?mine=1",
                "is_active": is_ori_list and _is_truthy_mine(mine_param),
            },
        ]

        implementation_url = reverse("panel:implementation")
        calendar_url = reverse("panel:calendar")
        statistics_url = reverse("panel:statistics")
        contacts_url = reverse("panel:contacts")
        mailings_url = reverse("panel:mailings")
        admin_url = reverse("admin:index")
        org_group_active = is_ori_section or is_data_sources_section or is_telecom_section
        return [
            {
                "name": "Организации",
                "url": ori_url,
                "is_active": org_group_active,
                "children": org_children,
            },
            {"name": "Внедрение", "url": implementation_url, "is_active": current_path.startswith(implementation_url)},
            {"name": "Календарь", "url": calendar_url, "is_active": current_path.startswith(calendar_url)},
            {"name": "Статистика", "url": statistics_url, "is_active": current_path.startswith(statistics_url)},
            {"name": "Контакты", "url": contacts_url, "is_active": current_path.startswith(contacts_url)},
            {"name": "Рассылки", "url": mailings_url, "is_active": current_path.startswith(mailings_url)},
            {"name": "Администрирование", "url": admin_url, "is_active": current_path.startswith("/admin/")},
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["panel_menu"] = self.get_panel_menu()
        context["panel_title"] = self.panel_title
        return context


class PanelAuthMixin(LoginRequiredMixin):
    login_url = reverse_lazy("panel:login")


_ORI_DETAIL_TABS = {"info", "psi", "actions", "contacts", "history"}
_DATA_SOURCE_DETAIL_TABS = {"info", "actions", "contacts", "history"}
_TELECOM_OPERATOR_DETAIL_TABS = {"info", "actions", "contacts", "licenses", "history"}
_ENTITY_ACTION_POST_ACTIONS = {
    "create_action",
    "edit_action",
    "delete_action",
    "cycle_action_status",
    "apply_action_template",
    "save_action_template",
}

def _apply_org_action_overdue_sync(item: OrgAction) -> None:
    if (
        item.deadline
        and item.deadline < timezone.localdate()
        and item.status == OrgActionStatus.PLANNED
    ):
        item.status = OrgActionStatus.OVERDUE


def _is_org_action_overdue(item: OrgAction) -> bool:
    _apply_org_action_overdue_sync(item)
    if item.status == OrgActionStatus.OVERDUE:
        return True
    if item.deadline and item.deadline < timezone.localdate():
        return item.status == OrgActionStatus.DONE
    return False


def _next_org_action_status(item: OrgAction) -> str | None:
    _apply_org_action_overdue_sync(item)
    if _is_org_action_overdue(item):
        if item.status == OrgActionStatus.OVERDUE:
            return OrgActionStatus.DONE
        if item.status == OrgActionStatus.DONE:
            return OrgActionStatus.OVERDUE
        return None
    if item.status == OrgActionStatus.PLANNED:
        return OrgActionStatus.DONE
    if item.status == OrgActionStatus.DONE:
        return OrgActionStatus.PLANNED
    return None


def _sync_org_actions_overdue(actions: list) -> None:
    today = timezone.localdate()
    overdue_pks = [
        item.pk
        for item in actions
        if item.deadline and item.deadline < today and item.status == OrgActionStatus.PLANNED
    ]
    if not overdue_pks:
        return
    OrgAction.objects.filter(pk__in=overdue_pks).update(status=OrgActionStatus.OVERDUE)
    overdue_set = set(overdue_pks)
    for item in actions:
        if item.pk in overdue_set:
            item.status = OrgActionStatus.OVERDUE


class EntityDetailTabsMixin:
    allowed_tabs: set[str] = set()

    def _entity_active_tab(self) -> str:
        tab = self.request.GET.get("tab", "").strip()
        return tab if tab in self.allowed_tabs else "info"

    def _entity_detail_context(self) -> dict:
        return {
            "active_tab": self._entity_active_tab(),
            "audit_events": [],
            "entity_contacts": [],
            "entity_comments": [],
        }


class EntityActionMixin:
    entity_action_scope_field = ""

    def _actions_redirect(self) -> str:
        return f"{self.request.path}?tab=actions"

    def _entity_actions_qs(self):
        return OrgAction.objects.filter(**{self.entity_action_scope_field: self.object})

    def _entity_action_context(self, **kwargs) -> dict:
        actions = list(
            self._entity_actions_qs().order_by(F("deadline").asc(nulls_last=True), "pk")
        )
        _sync_org_actions_overdue(actions)
        return {
            "entity_actions": actions,
            "entity_actions_edit_data": {
                str(item.pk): {
                    "task": item.task,
                    "status": item.status,
                    "comment": item.comment,
                    "deadline": item.deadline.isoformat() if item.deadline else "",
                    "result": item.result,
                }
                for item in actions
            },
            "entity_action_form": kwargs.get("entity_action_form") or OrgActionCreateForm(),
            "entity_action_modal_open": kwargs.get("entity_action_modal_open", False),
            "entity_action_modal_mode": kwargs.get("entity_action_modal_mode", "create"),
            "entity_action_modal_item": kwargs.get("entity_action_modal_item"),
            "entity_action_status_choices": OrgAction._meta.get_field("status").choices,
            "entity_action_today": timezone.localdate(),
            "entity_action_busy_dates": [
                {"date": item.deadline.isoformat(), "task": item.task}
                for item in actions
                if item.deadline
            ],
            "action_templates": list(ActionTemplate.objects.order_by("name")),
            "action_template_list_modal_open": kwargs.get("action_template_list_modal_open", False),
            "action_template_save_modal_open": kwargs.get("action_template_save_modal_open", False),
            "action_template_save_name": kwargs.get("action_template_save_name", ""),
        }

    def _handle_entity_action_post(self, request):
        action = request.POST.get("action", "").strip()
        if action not in _ENTITY_ACTION_POST_ACTIONS:
            return None
        scope_filter = {self.entity_action_scope_field: self.object}
        if action == "create_action":
            form = OrgActionCreateForm(request.POST)
            if form.is_valid():
                item = form.save(commit=False)
                setattr(item, self.entity_action_scope_field, self.object)
                item.status = OrgActionStatus.PLANNED
                item.result = ""
                item.created_by = request.user
                item.updated_by = request.user
                item.save()
                messages.success(request, "Действие добавлено.")
                return HttpResponseRedirect(self._actions_redirect())
            messages.error(request, "Проверьте поля действия.")
            context = self.get_context_data(
                entity_action_form=form,
                entity_action_modal_open=True,
                entity_action_modal_mode="create",
            )
            return self.render_to_response(context)
        if action == "edit_action":
            item_id = request.POST.get("action_id", "").strip()
            item = OrgAction.objects.filter(pk=item_id, **scope_filter).first()
            if not item:
                messages.error(request, "Действие не найдено.")
                return HttpResponseRedirect(self._actions_redirect())
            form = OrgActionEditForm(request.POST, instance=item)
            if form.is_valid():
                updated = form.save(commit=False)
                updated.updated_by = request.user
                updated.save()
                messages.success(request, "Действие обновлено.")
                return HttpResponseRedirect(self._actions_redirect())
            messages.error(request, "Проверьте поля редактирования действия.")
            context = self.get_context_data(
                entity_action_form=form,
                entity_action_modal_open=True,
                entity_action_modal_mode="edit",
                entity_action_modal_item=item,
            )
            return self.render_to_response(context)
        if action == "delete_action":
            item_id = request.POST.get("action_id", "").strip()
            item = OrgAction.objects.filter(pk=item_id, **scope_filter).first()
            if not item:
                messages.error(request, "Действие не найдено.")
                return HttpResponseRedirect(self._actions_redirect())
            item.delete()
            messages.success(request, "Действие удалено.")
            return HttpResponseRedirect(self._actions_redirect())
        if action == "cycle_action_status":
            item_id = request.POST.get("action_id", "").strip()
            item = OrgAction.objects.filter(pk=item_id, **scope_filter).first()
            if not item:
                messages.error(request, "Действие не найдено.")
                return HttpResponseRedirect(self._actions_redirect())
            next_status = _next_org_action_status(item)
            if not next_status:
                messages.error(request, "Не удалось сменить статус действия.")
                return HttpResponseRedirect(self._actions_redirect())
            item.status = next_status
            item.updated_by = request.user
            item.save()
            return HttpResponseRedirect(self._actions_redirect())
        if action == "apply_action_template":
            template_id = request.POST.get("template_id", "").strip()
            template = ActionTemplate.objects.filter(pk=template_id).first()
            if not template:
                messages.error(request, "Шаблон не найден.")
                return HttpResponseRedirect(self._actions_redirect())
            items = normalize_action_template_items(template.items)
            if not items:
                messages.error(request, "Шаблон не содержит действий.")
                return HttpResponseRedirect(self._actions_redirect())
            created_count = 0
            for entry in items:
                OrgAction.objects.create(
                    **scope_filter,
                    task=entry["task"],
                    comment=entry["comment"],
                    status=OrgActionStatus.PLANNED,
                    result="",
                    created_by=request.user,
                    updated_by=request.user,
                )
                created_count += 1
            messages.success(request, f"Добавлено действий из шаблона: {created_count}.")
            return HttpResponseRedirect(self._actions_redirect())
        if action == "save_action_template":
            template_name = request.POST.get("template_name", "").strip()
            if not template_name:
                messages.error(request, "Укажите название шаблона.")
                context = self.get_context_data(
                    action_template_save_modal_open=True,
                    action_template_save_name=template_name,
                )
                return self.render_to_response(context)
            current_actions = list(self._entity_actions_qs().order_by("pk"))
            items = action_template_items_from_actions(current_actions)
            if not items:
                messages.error(request, "Нет действий для сохранения в шаблон.")
                context = self.get_context_data(
                    action_template_save_modal_open=True,
                    action_template_save_name=template_name,
                )
                return self.render_to_response(context)
            template, created = ActionTemplate.objects.update_or_create(
                name=template_name,
                defaults={
                    "items": items,
                    "updated_by": request.user,
                },
            )
            if created:
                template.created_by = request.user
                template.save(update_fields=["created_by"])
            messages.success(
                request,
                "Шаблон создан." if created else "Шаблон обновлён.",
            )
            return HttpResponseRedirect(self._actions_redirect())
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._entity_action_context(**kwargs))
        if (
            kwargs.get("entity_action_modal_open")
            or kwargs.get("action_template_list_modal_open")
            or kwargs.get("action_template_save_modal_open")
        ):
            context["active_tab"] = "actions"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self._handle_entity_action_post(request)
        if response:
            return response
        return super().post(request, *args, **kwargs)


class OriContactCommentMixin(EntityDetailTabsMixin):
    allowed_tabs = _ORI_DETAIL_TABS

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._entity_detail_context())
        context["entity_contacts"] = (
            self.object.contacts.select_related("created_by").order_by("-updated_at", "-id")
        )
        context["entity_comments"] = (
            self.object.comments.select_related("author").order_by("commented_at", "id")
        )
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action", "").strip()

        if action in {"save_contact", "delete_contact"}:
            redirect_to_contacts = f"{self.request.path}?tab=contacts"
            contact_id = request.POST.get("contact_id", "").strip()
            contact = self.object.contacts.filter(pk=contact_id).first() if contact_id else None

            if action == "delete_contact":
                if contact:
                    contact.delete()
                else:
                    messages.error(request, "Контакт не найден.")
                return HttpResponseRedirect(redirect_to_contacts)

            first_name = request.POST.get("first_name", "").strip()
            if not first_name:
                messages.error(request, "Поле «Имя» обязательно.")
                return HttpResponseRedirect(redirect_to_contacts)

            payload = {
                "position": request.POST.get("position", "").strip(),
                "first_name": first_name,
                "phone": request.POST.get("phone", "").strip(),
                "email": request.POST.get("email", "").strip(),
                "extra_info": request.POST.get("extra_info", "").strip(),
            }
            if contact:
                for key, value in payload.items():
                    setattr(contact, key, value)
                contact.updated_by = request.user
                contact.save()
            else:
                Contact.objects.create(
                    organization=self.object,
                    created_by=request.user,
                    updated_by=request.user,
                    **payload,
                )
            return HttpResponseRedirect(redirect_to_contacts)

        text = request.POST.get("comment_text", "").strip()
        if text:
            Comment.objects.create(
                organization=self.object,
                author=request.user,
                text=text,
                created_by=request.user,
                updated_by=request.user,
            )
        else:
            messages.error(request, "Комментарий пустой, нечего сохранять.")
        return HttpResponseRedirect(self.request.path)


class PanelHomeRedirectView(PanelAuthMixin, RedirectView):
    permanent = False
    pattern_name = "panel:loading"


class PanelLoginView(LoginView):
    template_name = "panel/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        return reverse("panel:loading")


class PanelLogoutView(LogoutView):
    next_page = reverse_lazy("panel:login")


class PanelLoadingView(PanelAuthMixin, TemplateView):
    template_name = "panel/loading.html"


class OriListView(PanelAuthMixin, PanelMenuMixin, ListView):
    template_name = "panel/organization_list.html"
    context_object_name = "oris"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            Ori.objects.select_related("responsible_person")
            .prefetch_related(
                Prefetch(
                    "org_actions",
                    queryset=OrgAction.objects.order_by("deadline", "pk"),
                ),
            )
            .all()
            .order_by("name")
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(inn__icontains=query)
                | Q(case_number__icontains=query)
                | Q(responsible_person__username__icontains=query)
                | Q(responsible_person__first_name__icontains=query)
                | Q(responsible_person__last_name__icontains=query)
            )
        if _is_truthy_mine(self.request.GET.get("mine", "")):
            qs = qs.filter(responsible_person_id=self.request.user.pk)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["selected_mine"] = _is_truthy_mine(self.request.GET.get("mine", ""))
        for ori in context.get("oris", []):
            _sync_org_actions_overdue(list(ori.org_actions.all()))
        return context


class TelecomOperatorListView(PanelAuthMixin, PanelMenuMixin, ListView):
    template_name = "panel/telecom_operator_list.html"
    context_object_name = "telecom_operators"
    paginate_by = 20

    def get_queryset(self):
        qs = TelecomOperator.objects.select_related("responsible_person").order_by("name")
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(inn__icontains=query)
                | Q(case_number__icontains=query)
                | Q(responsible_person__username__icontains=query)
                | Q(responsible_person__first_name__icontains=query)
                | Q(responsible_person__last_name__icontains=query)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        return context


class TelecomOperatorDetailView(PanelAuthMixin, PanelMenuMixin, EntityActionMixin, DetailView):
    entity_action_scope_field = "telecom_operator"
    template_name = "panel/telecom_operator_detail.html"
    context_object_name = "telecom_operator"

    def get_queryset(self):
        return TelecomOperator.objects.select_related(
            "responsible_person",
            "created_by",
            "updated_by",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tab = self.request.GET.get("tab", "").strip()
        context["active_tab"] = tab if tab in _TELECOM_OPERATOR_DETAIL_TABS else "info"
        context["rkn_unavailable"] = self.request.GET.get("rkn_unavailable", "").strip() == "1"
        context["audit_events"] = (
            TelecomOperatorAuditEvent.objects.select_related("user")
            .filter(telecom_operator_id=self.object.pk)
            .order_by("-created_at", "-id")
        )
        context["operator_comments"] = self.object.operator_comments.select_related("author").order_by("commented_at", "id")
        context["operator_contacts"] = (
            self.object.operator_contacts.select_related("created_by")
            .order_by("-updated_at", "-id")
        )
        licenses = list(
            TelecomOperatorLicense.objects.filter(telecom_operator_id=self.object.pk)
            .prefetch_related("orders__order_number")
            .order_by("title", "pk")
        )
        context["operator_licenses"] = licenses
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action_response = self._handle_entity_action_post(request)
        if action_response:
            return action_response
        action = request.POST.get("action", "").strip()
        if action == "sync_licenses_rkn":
            redirect_to_licenses = f"{self.request.path}?tab=licenses"
            redirect_to_licenses_with_error = f"{redirect_to_licenses}&rkn_unavailable=1"
            try:
                result = sync_telecom_operator_licenses_from_rkn(self.object)
            except RknSyncError as exc:
                messages.error(request, f"Не удалось обновить лицензии из РКН: {exc}")
                return HttpResponseRedirect(redirect_to_licenses_with_error)
            else:
                messages.success(
                    request,
                    (
                        "Лицензии обновлены из РКН. "
                        f"Найдено: {result['parsed_from_list']}, "
                        f"создано: {result['created']}, "
                        f"обновлено: {result['updated']}, "
                        f"ошибок: {result['errors']}."
                    ),
                )
                return HttpResponseRedirect(redirect_to_licenses)

        if action in {"save_contact", "delete_contact"}:
            redirect_to_contacts = f"{self.request.path}?tab=contacts"
            contact_id = request.POST.get("contact_id", "").strip()
            contact = None
            if contact_id:
                contact = self.object.operator_contacts.filter(pk=contact_id).first()

            if action == "delete_contact":
                if contact:
                    contact.delete()
                else:
                    messages.error(request, "Контакт не найден.")
                return HttpResponseRedirect(redirect_to_contacts)

            # save_contact
            first_name = request.POST.get("first_name", "").strip()
            if not first_name:
                messages.error(request, "Поле «Имя» обязательно.")
                return HttpResponseRedirect(redirect_to_contacts)

            payload = {
                "position": request.POST.get("position", "").strip(),
                "first_name": first_name,
                "phone": request.POST.get("phone", "").strip(),
                "email": request.POST.get("email", "").strip(),
                "extra_info": request.POST.get("extra_info", "").strip(),
            }
            if contact:
                for key, value in payload.items():
                    setattr(contact, key, value)
                contact.updated_by = request.user
                contact.save()
            else:
                Contact.objects.create(
                    telecom_operator=self.object,
                    created_by=request.user,
                    updated_by=request.user,
                    **payload,
                )
            return HttpResponseRedirect(redirect_to_contacts)

        text = request.POST.get("comment_text", "").strip()
        if text:
            Comment.objects.create(
                telecom_operator=self.object,
                author=request.user,
                text=text,
                created_by=request.user,
                updated_by=request.user,
            )
        else:
            messages.error(request, "Комментарий пустой, нечего сохранять.")
        return HttpResponseRedirect(self.request.path)


class TelecomOperatorUpdateView(PanelAuthMixin, PanelMenuMixin, UpdateView):
    template_name = "panel/telecom_operator_form.html"
    form_class = TelecomOperatorForm
    context_object_name = "telecom_operator"

    def get_queryset(self):
        return TelecomOperator.objects.all()

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Изменения сохранены.")
        return response

    def get_success_url(self):
        return reverse("panel:telecom_operator_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = f"Редактирование: {self.object.name}"
        context["submit_label"] = "Сохранить изменения"
        return context


class TelecomOperatorLicenseDetailView(PanelAuthMixin, PanelMenuMixin, DetailView):
    template_name = "panel/telecom_license_detail.html"
    context_object_name = "license"

    def get_queryset(self):
        return TelecomOperatorLicense.objects.select_related("telecom_operator")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["license_form"] = kwargs.get("license_form") or TelecomOperatorLicenseForm(instance=self.object)
        context["license_edit_mode"] = kwargs.get("license_edit_mode", False)
        context["psi_form"] = kwargs.get("psi_form") or PsiAssignmentForm()
        context["license_order_form"] = kwargs.get("license_order_form") or LicenseOrderForm()
        context["license_order_modal_open"] = kwargs.get("license_order_modal_open", False)
        context["psi_modal_open"] = kwargs.get("psi_modal_open", False)
        context["psi_modal_order"] = kwargs.get("psi_modal_order")
        context["psi_modal_mode"] = kwargs.get("psi_modal_mode", "create")
        context["psi_modal_psi"] = kwargs.get("psi_modal_psi")
        context["psi_status_choices"] = Psi._meta.get_field("status").choices
        context["psi_assigned_today"] = timezone.localdate()
        orders = list(
            self.object.orders.select_related("order_number", "orm_vendor").prefetch_related(
                Prefetch(
                    "psis",
                    queryset=Psi.objects.select_related("responsible", "created_by").order_by("-assigned_date", "-pk"),
                )
            ).order_by("pk")
        )
        order_number_ids = {order.order_number_id for order in orders if order.order_number_id}
        busy_ranges_by_order_number = {}
        if order_number_ids:
            related_psis = (
                Psi.objects.select_related("license_order__order_number", "license_order__license__telecom_operator")
                .filter(license_order__order_number_id__in=order_number_ids)
                .exclude(start_date__isnull=True, end_date__isnull=True)
            )
            for psi in related_psis:
                start_date = psi.start_date or psi.end_date
                end_date = psi.end_date or psi.start_date
                if not start_date or not end_date:
                    continue
                if end_date < start_date:
                    start_date, end_date = end_date, start_date
                operator_name = "—"
                if psi.license_order_id and psi.license_order.license_id:
                    operator_name = psi.license_order.license.telecom_operator.name
                busy_ranges_by_order_number.setdefault(psi.license_order.order_number_id, []).append(
                    {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat(),
                        "operator_name": operator_name,
                    }
                )
        busy_ranges_by_order = {}
        history_payload_by_order = {}
        for order in orders:
            all_psis = list(order.psis.all())
            all_psis.sort(
                key=lambda psi: (
                    psi.end_date is None,
                    -(psi.end_date.toordinal() if psi.end_date else date.min.toordinal()),
                    -psi.pk,
                )
            )
            active_statuses = {"assigned", "overdue", "in_progress"}
            visible_psis = [psi for psi in all_psis if psi.status in active_statuses]
            latest_success = next((psi for psi in all_psis if psi.status == "successful"), None)
            latest_failed = next((psi for psi in all_psis if psi.status == "failed"), None)
            for candidate in (latest_success, latest_failed):
                if candidate and candidate not in visible_psis:
                    visible_psis.append(candidate)
            order.linked_psis = visible_psis
            order.history_psis = [psi for psi in all_psis if psi not in visible_psis]
            history_payload_by_order[str(order.pk)] = [
                {
                    "id": psi.pk,
                    "status": psi.get_status_display(),
                    "status_value": psi.status,
                    "responsible": str(psi.responsible) if psi.responsible_id else "—",
                    "responsible_id": psi.responsible_id or "",
                    "start_date": psi.start_date.strftime("%d.%m.%Y") if psi.start_date else "—",
                    "start_iso": psi.start_date.isoformat() if psi.start_date else "",
                    "end_date": psi.end_date.strftime("%d.%m.%Y") if psi.end_date else "—",
                    "end_iso": psi.end_date.isoformat() if psi.end_date else "",
                    "created_by": (
                        psi.created_by.get_full_name().strip() or psi.created_by.username
                        if psi.created_by_id
                        else "—"
                    ),
                    "created_at": psi.created_at.strftime("%d.%m.%Y %H:%M") if psi.created_at else "—",
                    "order_id": order.pk,
                    "order_name": order.order_number.name,
                }
                for psi in order.history_psis
            ]
            busy_ranges_by_order[str(order.pk)] = busy_ranges_by_order_number.get(order.order_number_id, [])
            today = timezone.localdate()
            for psi in all_psis:
                if psi.end_date:
                    delta_days = (psi.end_date - today).days
                    if delta_days > 0:
                        psi.schedule_hint = f"до завершения {delta_days} дн."
                    elif delta_days == 0:
                        psi.schedule_hint = "завершается сегодня"
                    else:
                        psi.schedule_hint = f"просрочено на {abs(delta_days)} дн."
                elif psi.start_date and psi.start_date > today:
                    psi.schedule_hint = f"старт через {(psi.start_date - today).days} дн."
                else:
                    psi.schedule_hint = "сроки не заданы"
        context["license_orders"] = orders
        context["psi_busy_ranges_by_order"] = busy_ranges_by_order
        context["psi_history_by_order"] = history_payload_by_order
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action", "").strip()
        if action == "save_license_info":
            form = TelecomOperatorLicenseForm(request.POST, instance=self.object)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.updated_by = request.user
                obj.save()
                messages.success(request, "Информация по лицензии обновлена.")
                return HttpResponseRedirect(self.request.path)
            messages.error(request, "Проверьте корректность заполненных полей.")
            context = self.get_context_data(license_form=form, license_edit_mode=True)
            return self.render_to_response(context)
        if action == "update_order_vendor":
            order_id = request.POST.get("order_id", "").strip()
            orm_vendor_id = request.POST.get("orm_vendor", "").strip()
            order = self.object.orders.filter(pk=order_id).first()
            if not order:
                messages.error(request, "Приказ не найден.")
                return HttpResponseRedirect(self.request.path)
            if not orm_vendor_id:
                messages.error(request, "Выберите производителя ТС-ОРМ.")
                return HttpResponseRedirect(self.request.path)
            order.orm_vendor_id = orm_vendor_id
            order.updated_by = request.user
            order.save(update_fields=["orm_vendor", "updated_by", "updated_at"])
            messages.success(request, "Производитель ТС-ОРМ обновлен.")
            return HttpResponseRedirect(self.request.path)
        if action == "create_license_order":
            form = LicenseOrderForm(request.POST)
            if form.is_valid():
                order = form.save(commit=False)
                order.license = self.object
                order.created_by = request.user
                order.updated_by = request.user
                order.save()
                messages.success(request, "Приказ лицензии добавлен.")
                return HttpResponseRedirect(self.request.path)
            messages.error(request, "Проверьте поля нового приказа.")
            context = self.get_context_data(license_order_form=form, license_order_modal_open=True)
            return self.render_to_response(context)
        if action == "create_psi":
            order_id = request.POST.get("license_order_id", "").strip()
            order = self.object.orders.filter(pk=order_id).select_related("order_number").first() if order_id else None
            if not order:
                messages.error(request, "Приказ для назначения ПСИ не найден.")
                return HttpResponseRedirect(self.request.path)
            form = PsiAssignmentForm(request.POST)
            if form.is_valid():
                psi = form.save(commit=False)
                psi.license_order = order
                psi.assigned_date = timezone.localdate()
                psi.created_by = request.user
                psi.updated_by = request.user
                psi.save()
                messages.success(request, "ПСИ назначено.")
                return HttpResponseRedirect(self.request.path)
            messages.error(request, "Проверьте поля назначения ПСИ.")
            context = self.get_context_data(
                psi_form=form,
                psi_modal_open=True,
                psi_modal_order=order,
                psi_modal_mode="create",
            )
            return self.render_to_response(context)
        if action == "edit_psi":
            psi_id = request.POST.get("psi_id", "").strip()
            psi = (
                Psi.objects.filter(pk=psi_id, license_order__license_id=self.object.pk)
                .select_related("license_order__order_number")
                .first()
            )
            if not psi:
                messages.error(request, "ПСИ не найдено.")
                return HttpResponseRedirect(self.request.path)
            form = PsiAssignmentForm(request.POST, instance=psi)
            if form.is_valid():
                updated = form.save(commit=False)
                updated.updated_by = request.user
                updated.save()
                messages.success(request, "ПСИ обновлено.")
                return HttpResponseRedirect(self.request.path)
            messages.error(request, "Проверьте поля редактирования ПСИ.")
            context = self.get_context_data(
                psi_form=form,
                psi_modal_open=True,
                psi_modal_order=psi.license_order,
                psi_modal_mode="edit",
                psi_modal_psi=psi,
            )
            return self.render_to_response(context)
        if action == "delete_psi":
            psi_id = request.POST.get("psi_id", "").strip()
            psi = Psi.objects.filter(pk=psi_id, license_order__license_id=self.object.pk).first()
            if not psi:
                messages.error(request, "ПСИ не найдено.")
                return HttpResponseRedirect(self.request.path)
            psi.delete()
            messages.success(request, "ПСИ удалено.")
            return HttpResponseRedirect(self.request.path)
        if action == "update_psi_status":
            psi_id = request.POST.get("psi_id", "").strip()
            new_status = request.POST.get("status", "").strip()
            psi = (
                Psi.objects.filter(pk=psi_id, license_order__license_id=self.object.pk)
                .select_related("license_order")
                .first()
            )
            valid_statuses = {choice[0] for choice in Psi._meta.get_field("status").choices}
            if not psi:
                messages.error(request, "ПСИ не найдено.")
                return HttpResponseRedirect(self.request.path)
            if new_status not in valid_statuses:
                messages.error(request, "Выбран некорректный статус ПСИ.")
                return HttpResponseRedirect(self.request.path)
            psi.status = new_status
            psi.updated_by = request.user
            psi.save()
            messages.success(request, "Статус ПСИ обновлен.")
            return HttpResponseRedirect(self.request.path)
        return HttpResponseRedirect(self.request.path)


class OriDetailView(PanelAuthMixin, PanelMenuMixin, EntityActionMixin, OriContactCommentMixin, DetailView):
    entity_action_scope_field = "organization"
    template_name = "panel/organization_detail.html"
    context_object_name = "ori"

    def get_queryset(self):
        return Ori.objects.select_related(
            "industry",
            "orm_vendor",
            "sorm_owner",
            "responsible_person",
        )

    def _psi_redirect(self) -> str:
        return f"{self.request.path}?tab=psi"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["psi_form"] = kwargs.get("psi_form") or PsiAssignmentForm()
        context["psi_modal_open"] = kwargs.get("psi_modal_open", False)
        context["psi_modal_mode"] = kwargs.get("psi_modal_mode", "create")
        context["psi_modal_psi"] = kwargs.get("psi_modal_psi")
        context["psi_status_choices"] = Psi._meta.get_field("status").choices
        context["psi_assigned_today"] = timezone.localdate()
        all_psis = list(
            self.object.psis.select_related("responsible", "created_by").order_by("-assigned_date", "-pk")
        )
        linked_psis, history_psis = partition_psis(all_psis)
        annotate_psi_schedule_hints(all_psis)
        context["linked_psis"] = linked_psis
        context["history_psis"] = history_psis
        context["psi_history_items"] = build_psi_history_payload(history_psis)
        context["psi_busy_ranges"] = build_psi_busy_ranges(
            self.object.psis.exclude(start_date__isnull=True, end_date__isnull=True),
            self.object.name,
        )
        if kwargs.get("psi_modal_open"):
            context["active_tab"] = "psi"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action", "").strip()
        psi_actions = {"create_psi", "edit_psi", "delete_psi", "update_psi_status"}
        if action in psi_actions:
            if action == "create_psi":
                form = PsiAssignmentForm(request.POST)
                if form.is_valid():
                    psi = form.save(commit=False)
                    psi.organization = self.object
                    psi.assigned_date = timezone.localdate()
                    psi.created_by = request.user
                    psi.updated_by = request.user
                    psi.save()
                    messages.success(request, "ПСИ назначено.")
                    return HttpResponseRedirect(self._psi_redirect())
                messages.error(request, "Проверьте поля назначения ПСИ.")
                context = self.get_context_data(
                    psi_form=form,
                    psi_modal_open=True,
                    psi_modal_mode="create",
                )
                return self.render_to_response(context)
            if action == "edit_psi":
                psi_id = request.POST.get("psi_id", "").strip()
                psi = Psi.objects.filter(pk=psi_id, organization_id=self.object.pk).first()
                if not psi:
                    messages.error(request, "ПСИ не найдено.")
                    return HttpResponseRedirect(self._psi_redirect())
                form = PsiAssignmentForm(request.POST, instance=psi)
                if form.is_valid():
                    updated = form.save(commit=False)
                    updated.updated_by = request.user
                    updated.save()
                    messages.success(request, "ПСИ обновлено.")
                    return HttpResponseRedirect(self._psi_redirect())
                messages.error(request, "Проверьте поля редактирования ПСИ.")
                context = self.get_context_data(
                    psi_form=form,
                    psi_modal_open=True,
                    psi_modal_mode="edit",
                    psi_modal_psi=psi,
                )
                return self.render_to_response(context)
            if action == "delete_psi":
                psi_id = request.POST.get("psi_id", "").strip()
                psi = Psi.objects.filter(pk=psi_id, organization_id=self.object.pk).first()
                if not psi:
                    messages.error(request, "ПСИ не найдено.")
                    return HttpResponseRedirect(self._psi_redirect())
                psi.delete()
                messages.success(request, "ПСИ удалено.")
                return HttpResponseRedirect(self._psi_redirect())
            if action == "update_psi_status":
                psi_id = request.POST.get("psi_id", "").strip()
                new_status = request.POST.get("status", "").strip()
                psi = Psi.objects.filter(pk=psi_id, organization_id=self.object.pk).first()
                valid_statuses = {choice[0] for choice in Psi._meta.get_field("status").choices}
                if not psi:
                    messages.error(request, "ПСИ не найдено.")
                    return HttpResponseRedirect(self._psi_redirect())
                if new_status not in valid_statuses:
                    messages.error(request, "Выбран некорректный статус ПСИ.")
                    return HttpResponseRedirect(self._psi_redirect())
                psi.status = new_status
                psi.updated_by = request.user
                psi.save()
                messages.success(request, "Статус ПСИ обновлен.")
                return HttpResponseRedirect(self._psi_redirect())
        action_response = self._handle_entity_action_post(request)
        if action_response:
            return action_response
        return super().post(request, *args, **kwargs)


class OriCreateView(PanelAuthMixin, PanelMenuMixin, CreateView):
    template_name = "panel/organization_form.html"
    form_class = OriForm

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "ОРИ успешно добавлена.")
        return response

    def get_success_url(self):
        return reverse_lazy("panel:ori_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Добавление ОРИ"
        context["submit_label"] = "Создать ОРИ"
        return context


class OriUpdateView(PanelAuthMixin, PanelMenuMixin, UpdateView):
    template_name = "panel/organization_form.html"
    form_class = OriForm

    def get_queryset(self):
        return Ori.objects.all()

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Изменения сохранены.")
        return response

    def get_success_url(self):
        return reverse("panel:ori_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = f"Редактирование: {self.object.name}"
        context["submit_label"] = "Сохранить изменения"
        return context


class DataSourceListView(PanelAuthMixin, PanelMenuMixin, ListView):
    template_name = "panel/data_source_list.html"
    context_object_name = "data_sources"
    paginate_by = 20

    def get_queryset(self):
        qs = DataSource.objects.select_related("responsible_person", "industry").order_by("name")
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(inn__icontains=query)
                | Q(case_number__icontains=query)
                | Q(responsible_person__username__icontains=query)
                | Q(responsible_person__first_name__icontains=query)
                | Q(responsible_person__last_name__icontains=query)
            )
        if _is_truthy_mine(self.request.GET.get("mine", "")):
            qs = qs.filter(responsible_person_id=self.request.user.pk)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["selected_mine"] = _is_truthy_mine(self.request.GET.get("mine", ""))
        return context


class DataSourceCommentMixin(EntityDetailTabsMixin):
    allowed_tabs = _DATA_SOURCE_DETAIL_TABS

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._entity_detail_context())
        context["entity_comments"] = (
            self.object.comments.select_related("author").order_by("commented_at", "id")
        )
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        text = request.POST.get("comment_text", "").strip()
        if text:
            Comment.objects.create(
                data_source=self.object,
                author=request.user,
                text=text,
                created_by=request.user,
                updated_by=request.user,
            )
        else:
            messages.error(request, "Комментарий пустой, нечего сохранять.")
        return HttpResponseRedirect(self.request.path)


class DataSourceDetailView(PanelAuthMixin, PanelMenuMixin, EntityActionMixin, DataSourceCommentMixin, DetailView):
    entity_action_scope_field = "data_source"
    template_name = "panel/data_source_detail.html"
    context_object_name = "data_source"

    def get_queryset(self):
        return DataSource.objects.select_related("industry", "responsible_person")


class DataSourceCreateView(PanelAuthMixin, PanelMenuMixin, CreateView):
    template_name = "panel/data_source_form.html"
    form_class = DataSourceForm

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Источник данных успешно добавлен.")
        return response

    def get_success_url(self):
        return reverse_lazy("panel:data_source_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Добавление источника данных"
        context["submit_label"] = "Создать источник данных"
        return context


class DataSourceUpdateView(PanelAuthMixin, PanelMenuMixin, UpdateView):
    template_name = "panel/data_source_form.html"
    form_class = DataSourceForm

    def get_queryset(self):
        return DataSource.objects.all()

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Изменения сохранены.")
        return response

    def get_success_url(self):
        return reverse("panel:data_source_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = f"Редактирование: {self.object.name}"
        context["submit_label"] = "Сохранить изменения"
        return context


class PanelPlaceholderView(PanelAuthMixin, PanelMenuMixin, TemplateView):
    template_name = "panel/placeholder.html"
    page_title = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title
        return context


class ImplementationPlaceholderView(PanelPlaceholderView):
    page_title = "Внедрение"


class CalendarPlaceholderView(PanelPlaceholderView):
    page_title = "Календарь"


class StatisticsPlaceholderView(PanelPlaceholderView):
    page_title = "Статистика"


class ContactsListView(PanelAuthMixin, PanelMenuMixin, ListView):
    template_name = "panel/contacts_list.html"
    context_object_name = "contacts"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Contact.objects.select_related("created_by", "updated_by")
            .prefetch_related("organization", "telecom_operator")
            .order_by("-updated_at", "-id")
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(first_name__icontains=query)
                | Q(position__icontains=query)
                | Q(phone__icontains=query)
                | Q(email__icontains=query)
                | Q(organization__name__icontains=query)
                | Q(telecom_operator__name__icontains=query)
                | Q(created_by__username__icontains=query)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        return context


class MailingsPlaceholderView(PanelPlaceholderView):
    page_title = "Рассылки"


# Legacy placeholder aliases for backward-compatible URLs.
class PsiPlaceholderView(ImplementationPlaceholderView):
    pass


class LicensesPlaceholderView(PanelPlaceholderView):
    page_title = "Лицензии"


class ReportsPlaceholderView(StatisticsPlaceholderView):
    pass


class UsersPlaceholderView(PanelPlaceholderView):
    page_title = "Пользователи"
    pass
