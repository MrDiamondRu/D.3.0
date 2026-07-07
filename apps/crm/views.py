from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models import F, Prefetch, Q
from django.http import HttpResponseRedirect, JsonResponse
from django.utils import timezone
from datetime import date
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, RedirectView, TemplateView, UpdateView

from apps.crm.forms import (
    AppSettingsForm,
    DataSourceForm,
    OriForm,
    TelecomOperatorForm,
    TelecomOperatorLicenseForm,
    TelecomNetworkForm,
    TelecomNetworkEditForm,
    LicenseOrderForm,
    OrgActionCreateForm,
    OrgActionEditForm,
    PsiAssignmentForm,
)
from apps.crm.models import (
    AppSettings,
    Contact,
    DataSource,
    Event,
    Ori,
    Comment,
    ActionTemplate,
    OrgAction,
    OrgActionStatus,
    Psi,
    LicenseOrder,
    TelecomOperatorLicense,
    TelecomOperator,
    TelecomNetwork,
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
from apps.crm.organization_list_utils import (
    annotate_data_source_list,
    annotate_ori_list,
    annotate_telecom_list,
    org_actions_prefetch,
    status_links_prefetch,
)
from apps.crm.rkn_licenses import RknSyncError, sync_telecom_operator_licenses_from_rkn
from apps.crm.telecom_operator_import import import_telecom_operator_from_docx


TELECOM_OPERATOR_MENU_LABEL = "Операторы связи"


def _operator_licenses_url(operator_pk: int) -> str:
    return f"{reverse('panel:telecom_operator_detail', kwargs={'pk': operator_pk})}?tab=licenses"


def _orders_qs_for_network(network: TelecomNetwork):
    return LicenseOrder.objects.filter(telecom_network_id=network.pk)


def _psi_scope_for_network(network: TelecomNetwork) -> Q:
    return Q(license_order__telecom_network_id=network.pk)


def _populate_orders_psi_context(orders_qs) -> dict:
    orders = list(
        orders_qs.select_related("order_number", "orm_vendor", "telecom_network", "telecom_operator")
        .prefetch_related(
            Prefetch(
                "psis",
                queryset=Psi.objects.select_related("responsible", "created_by").order_by("-assigned_date", "-pk"),
            )
        )
        .order_by("pk")
    )
    order_number_ids = {order.order_number_id for order in orders if order.order_number_id}
    busy_ranges_by_order_number = {}
    if order_number_ids:
        related_psis = (
            Psi.objects.select_related(
                "license_order__order_number",
                "license_order__telecom_network__telecom_operator",
                "license_order__telecom_operator",
            )
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
            if psi.license_order_id:
                order = psi.license_order
                if order.telecom_network_id:
                    operator_name = order.telecom_network.telecom_operator.name
                elif order.telecom_operator_id:
                    operator_name = order.telecom_operator.name
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
    return {
        "network_orders": orders,
        "psi_busy_ranges_by_order": busy_ranges_by_order,
        "psi_history_by_order": history_payload_by_order,
    }


def _panel_nav_state(request) -> dict:
    current_path = request.path.rstrip("/")
    ori_url = reverse("panel:ori_list")
    data_sources_url = reverse("panel:data_source_list")
    telecom_operators_url = reverse("panel:telecom_operator_list")
    telecom_licenses_prefix = reverse("panel:telecom_license_detail", kwargs={"pk": 1}).rsplit("/", 2)[0]
    telecom_networks_prefix = reverse("panel:telecom_network_detail", kwargs={"pk": 1}).rsplit("/", 2)[0]
    implementation_url = reverse("panel:implementation")
    calendar_url = reverse("panel:calendar")
    statistics_url = reverse("panel:statistics")
    contacts_url = reverse("panel:contacts")
    mailings_url = reverse("panel:mailings")
    settings_url = reverse("panel:app_settings")

    ori_base = ori_url.rstrip("/")
    data_sources_base = data_sources_url.rstrip("/")
    telecom_base = telecom_operators_url.rstrip("/")
    settings_base = settings_url.rstrip("/")
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
        or current_path.startswith(telecom_networks_prefix)
    )

    return {
        "current_path": current_path,
        "mine_param": mine_param,
        "is_ori_list": is_ori_list,
        "is_ori_section": is_ori_section,
        "is_data_sources_section": is_data_sources_section,
        "is_telecom_section": is_telecom_section,
        "ori_url": ori_url,
        "data_sources_url": data_sources_url,
        "telecom_operators_url": telecom_operators_url,
        "implementation_url": implementation_url,
        "calendar_url": calendar_url,
        "statistics_url": statistics_url,
        "contacts_url": contacts_url,
        "mailings_url": mailings_url,
        "settings_url": settings_url,
        "is_settings_section": current_path == settings_base,
    }


def _panel_section_title(nav: dict) -> str:
    if nav["is_telecom_section"]:
        return TELECOM_OPERATOR_MENU_LABEL
    if nav["is_data_sources_section"]:
        return "Источники данных"
    if nav["is_ori_list"] and _is_truthy_mine(nav["mine_param"]):
        return "Мои дела"
    if nav["is_ori_section"]:
        return "ОРИ"
    current_path = nav["current_path"]
    if current_path.startswith(nav["implementation_url"].rstrip("/")):
        return "Внедрение"
    if current_path.startswith(nav["calendar_url"].rstrip("/")):
        return "Календарь"
    if current_path.startswith(nav["statistics_url"].rstrip("/")):
        return "Статистика"
    if current_path.startswith(nav["contacts_url"].rstrip("/")):
        return "Контакты"
    if current_path.startswith(nav["mailings_url"].rstrip("/")):
        return "Рассылки"
    if nav["is_settings_section"]:
        return "Настройки приложения"
    if current_path.startswith("/admin"):
        return "Администрирование"
    return ""


def _is_truthy_mine(value) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _archive_filter_value(request) -> str:
    value = request.GET.get("archive", "").strip().lower()
    if value in {"archived", "all"}:
        return value
    return "active"


def _apply_archive_filter(queryset, archive_filter: str):
    if archive_filter == "archived":
        return queryset.filter(is_archived=True)
    if archive_filter == "all":
        return queryset
    return queryset.filter(is_archived=False)


def _transfer_ori_to_data_source(source: Ori) -> DataSource:
    target = DataSource.objects.create(
        icon=source.icon.name if source.icon else None,
        name=source.name,
        is_archived=source.is_archived,
        inn=source.inn,
        case_number=source.case_number,
        responsible_person=source.responsible_person,
        sites=list(source.sites or []),
        correspondence_address=source.correspondence_address,
        industry=source.industry,
    )

    Contact.objects.filter(organization=source).update(
        organization=None,
        data_source=target,
    )
    Comment.objects.filter(organization=source).update(
        organization=None,
        data_source=target,
    )
    OrgAction.objects.filter(organization=source).update(
        organization=None,
        data_source=target,
    )

    Event.objects.filter(organization=source).delete()
    Psi.objects.filter(organization=source).delete()
    source.delete()
    return target


def _transfer_data_source_to_ori(source: DataSource) -> Ori:
    target = Ori.objects.create(
        icon=source.icon.name if source.icon else None,
        name=source.name,
        is_archived=source.is_archived,
        inn=source.inn,
        case_number=source.case_number,
        responsible_person=source.responsible_person,
        sites=list(source.sites or []),
        correspondence_address=source.correspondence_address,
        industry=source.industry,
    )

    Contact.objects.filter(data_source=source).update(
        data_source=None,
        organization=target,
    )
    Comment.objects.filter(data_source=source).update(
        data_source=None,
        organization=target,
    )
    OrgAction.objects.filter(data_source=source).update(
        data_source=None,
        organization=target,
    )

    source.delete()
    return target


class PanelMenuMixin:
    panel_title = "D.3.0"

    def get_panel_menu(self):
        nav = _panel_nav_state(self.request)
        current_path = nav["current_path"]
        mine_param = nav["mine_param"]
        org_children = [
            {
                "name": TELECOM_OPERATOR_MENU_LABEL,
                "url": nav["telecom_operators_url"],
                "is_active": nav["is_telecom_section"],
            },
            {
                "name": "ОРИ",
                "url": nav["ori_url"],
                "is_active": nav["is_ori_list"] and not _is_truthy_mine(mine_param),
            },
            {
                "name": "Источники данных",
                "url": nav["data_sources_url"],
                "is_active": nav["is_data_sources_section"],
            },
            {
                "name": "Мои дела",
                "url": f"{nav['ori_url']}?mine=1",
                "is_active": nav["is_ori_list"] and _is_truthy_mine(mine_param),
            },
        ]

        admin_url = reverse("admin:index")
        org_group_active = (
            nav["is_ori_section"] or nav["is_data_sources_section"] or nav["is_telecom_section"]
        )
        return [
            {
                "name": "Организации",
                "url": nav["ori_url"],
                "is_active": org_group_active,
                "children": org_children,
            },
            {
                "name": "Внедрение",
                "url": nav["implementation_url"],
                "is_active": current_path.startswith(nav["implementation_url"].rstrip("/")),
            },
            {
                "name": "Календарь",
                "url": nav["calendar_url"],
                "is_active": current_path.startswith(nav["calendar_url"].rstrip("/")),
            },
            {
                "name": "Статистика",
                "url": nav["statistics_url"],
                "is_active": current_path.startswith(nav["statistics_url"].rstrip("/")),
            },
            {
                "name": "Контакты",
                "url": nav["contacts_url"],
                "is_active": current_path.startswith(nav["contacts_url"].rstrip("/")),
            },
            {
                "name": "Рассылки",
                "url": nav["mailings_url"],
                "is_active": current_path.startswith(nav["mailings_url"].rstrip("/")),
            },
            {
                "name": "Настройки",
                "url": nav["settings_url"],
                "is_active": nav["is_settings_section"],
            },
            {"name": "Администрирование", "url": admin_url, "is_active": current_path.startswith("/admin/")},
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        nav = _panel_nav_state(self.request)
        context["panel_menu"] = self.get_panel_menu()
        context["panel_title"] = self.panel_title
        context["panel_section_title"] = _panel_section_title(nav)
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

    def _actions_redirect(self, action_id=None) -> str:
        url = f"{self.request.path}?tab=actions"
        if action_id:
            url += f"#entity-action-{action_id}"
        return url

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
                return HttpResponseRedirect(self._actions_redirect(item.pk))
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
                return HttpResponseRedirect(self._actions_redirect(item.pk))
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
            return HttpResponseRedirect(self._actions_redirect(item_id))
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
        archive_filter = _archive_filter_value(self.request)
        qs = annotate_ori_list(
            Ori.objects.select_related("responsible_person", "orm_vendor")
            .prefetch_related(org_actions_prefetch(), status_links_prefetch())
            .order_by("name")
        )
        qs = _apply_archive_filter(qs, archive_filter)
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
        context["selected_archive"] = _archive_filter_value(self.request)
        for ori in context.get("oris", []):
            _sync_org_actions_overdue(list(ori.org_actions.all()))
        return context


class TelecomOperatorListView(PanelAuthMixin, PanelMenuMixin, ListView):
    template_name = "panel/telecom_operator_list.html"
    context_object_name = "telecom_operators"
    paginate_by = 20

    def get_queryset(self):
        archive_filter = _archive_filter_value(self.request)
        qs = annotate_telecom_list(
            TelecomOperator.objects.select_related("responsible_person")
            .prefetch_related(org_actions_prefetch(), status_links_prefetch())
            .order_by("name")
        )
        qs = _apply_archive_filter(qs, archive_filter)
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
        context["selected_archive"] = _archive_filter_value(self.request)
        for operator in context.get("telecom_operators", []):
            _sync_org_actions_overdue(list(operator.org_actions.all()))
        return context


class TelecomOperatorImportView(PanelAuthMixin, View):
    def post(self, request, *args, **kwargs):
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return JsonResponse({"error": "Файл не выбран"}, status=400)
        if not uploaded.name.lower().endswith(".docx"):
            return JsonResponse({"error": "Допустимы только файлы .docx"}, status=400)

        result = import_telecom_operator_from_docx(uploaded, created_by=request.user)
        return JsonResponse(result.as_dict())


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
        licenses_qs = TelecomOperatorLicense.objects.filter(telecom_operator_id=self.object.pk)
        context["operator_networks"] = list(
            TelecomNetwork.objects.filter(telecom_operator_id=self.object.pk)
            .select_related("name")
            .prefetch_related(
                Prefetch(
                    "licenses",
                    queryset=licenses_qs.order_by("title", "pk"),
                ),
                Prefetch(
                    "orders",
                    queryset=LicenseOrder.objects.select_related("order_number"),
                ),
            )
            .order_by("name__name")
        )
        context["unlinked_operator_licenses"] = list(
            licenses_qs.filter(telecom_network__isnull=True).order_by("title", "pk")
        )
        context["telecom_network_form"] = kwargs.get("telecom_network_form") or TelecomNetworkForm(
            telecom_operator=self.object,
        )
        context["network_modal_open"] = kwargs.get("network_modal_open", False)
        if kwargs.get("force_licenses_tab"):
            context["active_tab"] = "licenses"
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
                        f"пропущено по территории: {result['skipped_territory']}, "
                        f"ошибок: {result['errors']}."
                    ),
                )
                return HttpResponseRedirect(redirect_to_licenses)

        if action == "create_network":
            redirect_to_licenses = f"{self.request.path}?tab=licenses"
            form = TelecomNetworkForm(request.POST, telecom_operator=self.object)
            if form.is_valid():
                network = form.save(commit=False)
                network.telecom_operator = self.object
                network.created_by = request.user
                network.updated_by = request.user
                network.save()
                messages.success(request, "Сеть связи добавлена.")
                return HttpResponseRedirect(redirect_to_licenses)
            messages.error(request, "Выберите наименование сети связи.")
            context = self.get_context_data(
                telecom_network_form=form,
                network_modal_open=True,
                force_licenses_tab=True,
            )
            return self.render_to_response(context)

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


class TelecomOperatorCreateView(PanelAuthMixin, PanelMenuMixin, CreateView):
    template_name = "panel/telecom_operator_form.html"
    form_class = TelecomOperatorForm

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Оператор связи успешно добавлен.")
        return response

    def get_success_url(self):
        return reverse_lazy("panel:telecom_operator_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Добавление оператора связи"
        context["submit_label"] = "Создать оператора связи"
        return context


class TelecomOperatorUpdateView(PanelAuthMixin, PanelMenuMixin, UpdateView):
    template_name = "panel/telecom_operator_form.html"
    form_class = TelecomOperatorForm
    context_object_name = "telecom_operator"

    def get_queryset(self):
        return TelecomOperator.objects.all()

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.POST.get("action", "").strip() == "toggle_archive":
            self.object.is_archived = not self.object.is_archived
            self.object.updated_by = request.user
            self.object.save(update_fields=["is_archived", "updated_by", "updated_at"])
            state = "в архив" if self.object.is_archived else "из архива"
            messages.success(request, f"Оператор связи перемещен {state}.")
            return HttpResponseRedirect(self.request.path)
        return super().post(request, *args, **kwargs)

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
        context["archive_toggle_label"] = "Вернуть из архива" if self.object.is_archived else "Переместить в архив"
        return context


class TelecomOperatorLicenseDetailView(PanelAuthMixin, PanelMenuMixin, DetailView):
    template_name = "panel/telecom_license_detail.html"
    context_object_name = "license"

    def get_queryset(self):
        return TelecomOperatorLicense.objects.select_related("telecom_operator", "telecom_network__name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["license_form"] = kwargs.get("license_form") or TelecomOperatorLicenseForm(instance=self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action", "").strip()
        if action == "save_license_info":
            redirect_to_licenses = _operator_licenses_url(self.object.telecom_operator_id)
            form = TelecomOperatorLicenseForm(request.POST, instance=self.object)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.updated_by = request.user
                obj.save()
                messages.success(request, "Информация по лицензии обновлена.")
                return HttpResponseRedirect(redirect_to_licenses)
            messages.error(request, "Проверьте корректность заполненных полей.")
            context = self.get_context_data(license_form=form)
            return self.render_to_response(context)
        if action == "delete_license":
            operator_pk = self.object.telecom_operator_id
            self.object.delete()
            messages.success(request, "Лицензия удалена.")
            return HttpResponseRedirect(_operator_licenses_url(operator_pk))
        return HttpResponseRedirect(self.request.path)


class TelecomNetworkDetailView(PanelAuthMixin, PanelMenuMixin, DetailView):
    template_name = "panel/telecom_network_detail.html"
    context_object_name = "network"

    def get_queryset(self):
        return TelecomNetwork.objects.select_related("name", "telecom_operator")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["network_form"] = kwargs.get("network_form") or TelecomNetworkEditForm(instance=self.object)
        context["psi_form"] = kwargs.get("psi_form") or PsiAssignmentForm()
        context["order_form"] = kwargs.get("order_form") or LicenseOrderForm()
        context["order_modal_open"] = kwargs.get("order_modal_open", False)
        context["psi_modal_open"] = kwargs.get("psi_modal_open", False)
        context["psi_modal_order"] = kwargs.get("psi_modal_order")
        context["psi_modal_mode"] = kwargs.get("psi_modal_mode", "create")
        context["psi_modal_psi"] = kwargs.get("psi_modal_psi")
        context["psi_status_choices"] = Psi._meta.get_field("status").choices
        context["psi_assigned_today"] = timezone.localdate()
        context.update(_populate_orders_psi_context(_orders_qs_for_network(self.object)))
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action", "").strip()
        orders_qs = _orders_qs_for_network(self.object)
        psi_scope = _psi_scope_for_network(self.object)

        if action == "save_network_info":
            form = TelecomNetworkEditForm(request.POST, instance=self.object)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.updated_by = request.user
                obj.save()
                messages.success(request, "Информация по сети связи обновлена.")
                return HttpResponseRedirect(self.request.path)
            messages.error(request, "Проверьте корректность заполненных полей.")
            context = self.get_context_data(network_form=form)
            return self.render_to_response(context)
        if action == "update_order_vendor":
            order_id = request.POST.get("order_id", "").strip()
            orm_vendor_id = request.POST.get("orm_vendor", "").strip()
            order = orders_qs.filter(pk=order_id).first()
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
                order.telecom_operator_id = self.object.telecom_operator_id
                order.telecom_network_id = self.object.pk
                order.created_by = request.user
                order.updated_by = request.user
                order.save()
                messages.success(request, "Приказ добавлен.")
                return HttpResponseRedirect(self.request.path)
            messages.error(request, "Проверьте поля нового приказа.")
            context = self.get_context_data(order_form=form, order_modal_open=True)
            return self.render_to_response(context)
        if action == "create_psi":
            order_id = request.POST.get("license_order_id", "").strip()
            order = (
                orders_qs.filter(pk=order_id).select_related("order_number").first()
                if order_id
                else None
            )
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
                Psi.objects.filter(pk=psi_id)
                .filter(psi_scope)
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
            psi = Psi.objects.filter(pk=psi_id).filter(psi_scope).first()
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
                Psi.objects.filter(pk=psi_id)
                .filter(psi_scope)
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
        if action == "change_interaction_type":
            try:
                with transaction.atomic():
                    source_name = self.object.name
                    target = _transfer_ori_to_data_source(self.object)
            except IntegrityError:
                messages.error(
                    request,
                    "Перенос не выполнен: в «Источниках данных» уже есть запись с таким ИНН и наименованием.",
                )
                return HttpResponseRedirect(self.request.path)

            messages.success(
                request,
                f"Объект «{source_name}» перенесен в группу «Источники данных».",
            )
            return HttpResponseRedirect(reverse("panel:data_source_detail", kwargs={"pk": target.pk}))

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

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.POST.get("action", "").strip() == "toggle_archive":
            self.object.is_archived = not self.object.is_archived
            self.object.save(update_fields=["is_archived"])
            state = "в архив" if self.object.is_archived else "из архива"
            messages.success(request, f"ОРИ перемещена {state}.")
            return HttpResponseRedirect(self.request.path)
        return super().post(request, *args, **kwargs)

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
        context["archive_toggle_label"] = "Вернуть из архива" if self.object.is_archived else "Переместить в архив"
        return context


class DataSourceListView(PanelAuthMixin, PanelMenuMixin, ListView):
    template_name = "panel/data_source_list.html"
    context_object_name = "data_sources"
    paginate_by = 20

    def get_queryset(self):
        archive_filter = _archive_filter_value(self.request)
        qs = annotate_data_source_list(
            DataSource.objects.select_related("responsible_person", "industry")
            .prefetch_related(org_actions_prefetch(), status_links_prefetch())
            .order_by("name")
        )
        qs = _apply_archive_filter(qs, archive_filter)
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
        context["selected_archive"] = _archive_filter_value(self.request)
        for data_source in context.get("data_sources", []):
            _sync_org_actions_overdue(list(data_source.org_actions.all()))
        return context


class DataSourceCommentMixin(EntityDetailTabsMixin):
    allowed_tabs = _DATA_SOURCE_DETAIL_TABS

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
                    data_source=self.object,
                    created_by=request.user,
                    updated_by=request.user,
                    **payload,
                )
            return HttpResponseRedirect(redirect_to_contacts)

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

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.POST.get("action", "").strip() == "change_interaction_type":
            try:
                with transaction.atomic():
                    source_name = self.object.name
                    target = _transfer_data_source_to_ori(self.object)
            except IntegrityError:
                messages.error(
                    request,
                    "Перенос не выполнен: в группе «ОРИ» уже есть запись с таким ИНН и наименованием.",
                )
                return HttpResponseRedirect(self.request.path)

            messages.success(
                request,
                f"Объект «{source_name}» перенесен в группу «ОРИ».",
            )
            return HttpResponseRedirect(reverse("panel:ori_detail", kwargs={"pk": target.pk}))

        return super().post(request, *args, **kwargs)


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

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.POST.get("action", "").strip() == "toggle_archive":
            self.object.is_archived = not self.object.is_archived
            self.object.save(update_fields=["is_archived"])
            state = "в архив" if self.object.is_archived else "из архива"
            messages.success(request, f"Источник данных перемещен {state}.")
            return HttpResponseRedirect(self.request.path)
        return super().post(request, *args, **kwargs)

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
        context["archive_toggle_label"] = "Вернуть из архива" if self.object.is_archived else "Переместить в архив"
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


class StatisticsView(PanelAuthMixin, PanelMenuMixin, TemplateView):
    template_name = "panel/statistics.html"
    page_title = "Статистика"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title
        context["statistics_cards"] = [
            {
                "label": "Операторы связи",
                "count": TelecomOperator.objects.count(),
                "url": reverse("panel:telecom_operator_list"),
                "variant": "telecom",
            },
            {
                "label": "ОРИ",
                "count": Ori.objects.count(),
                "url": reverse("panel:ori_list"),
                "variant": "ori",
            },
            {
                "label": "Источники данных",
                "count": DataSource.objects.count(),
                "url": reverse("panel:data_source_list"),
                "variant": "data_source",
            },
        ]
        return context


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


class ReportsPlaceholderView(PanelPlaceholderView):
    page_title = "Отчёты"


class UsersPlaceholderView(PanelPlaceholderView):
    page_title = "Пользователи"


class AppSettingsView(PanelAuthMixin, PanelMenuMixin, UpdateView):
    model = AppSettings
    form_class = AppSettingsForm
    template_name = "panel/app_settings.html"
    success_url = reverse_lazy("panel:app_settings")

    def get_object(self, queryset=None):
        return AppSettings.load()

    def form_valid(self, form):
        messages.success(self.request, "Настройки сохранены.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Настройки приложения"
        context["submit_label"] = "Сохранить"
        return context
    pass
