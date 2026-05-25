from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.http import HttpResponseRedirect
from django.utils import timezone
from datetime import date
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, RedirectView, TemplateView, UpdateView

from apps.crm.forms import OriForm, TelecomOperatorForm, TelecomOperatorLicenseForm, LicenseOrderForm, PsiAssignmentForm
from apps.crm.models import (
    Contact,
    Ori,
    OrganizationStatus,
    Comment,
    Psi,
    TelecomOperatorLicense,
    TelecomOperator,
    TelecomOperatorAuditEvent,
)
from apps.crm.rkn_licenses import RknSyncError, sync_telecom_operator_licenses_from_rkn


TELECOM_OPERATOR_MENU_LABEL = "Операторы связи"
TELECOM_DEFAULT_ICON_REL = "organization_types/icons/free-icon-smartphone-4179839.png"


def telecom_default_icon_url() -> str:
    return f"{settings.MEDIA_URL.rstrip('/')}/{TELECOM_DEFAULT_ICON_REL}"


def _is_truthy_mine(value) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class PanelMenuMixin:
    panel_title = "D.3.0"

    def get_panel_menu(self):
        request = self.request
        current_path = request.path
        organizations_url = reverse("panel:ori_list")
        telecom_operators_url = reverse("panel:telecom_operator_list")
        org_list_path = organizations_url.rstrip("/")
        telecom_base_path = telecom_operators_url.rstrip("/")
        is_org_list = request.path.rstrip("/") == org_list_path
        is_telecom_section = current_path.rstrip("/").startswith(telecom_base_path)
        is_org_section = current_path.rstrip("/").startswith(org_list_path)
        mine_param = request.GET.get("mine", "")

        org_children = []
        ori_active = is_org_list and not _is_truthy_mine(mine_param)
        org_children.append({"name": "ОРИ", "url": organizations_url, "is_active": ori_active})
        org_children.append(
            {
                "name": TELECOM_OPERATOR_MENU_LABEL,
                "url": telecom_operators_url,
                "is_active": is_telecom_section,
            }
        )
        # Мои дела
        mine_url = f"{organizations_url}?mine=1"
        org_children.append(
            {
                "name": "Мои дела",
                "url": mine_url,
                "is_active": is_org_list and _is_truthy_mine(mine_param),
            }
        )

        implementation_url = reverse("panel:implementation")
        calendar_url = reverse("panel:calendar")
        statistics_url = reverse("panel:statistics")
        contacts_url = reverse("panel:contacts")
        mailings_url = reverse("panel:mailings")
        admin_url = reverse("admin:index")
        org_group_active = is_org_section or any(c["is_active"] for c in org_children)
        return [
            {
                "name": "Организации",
                "url": organizations_url,
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
            Ori.objects.select_related("interaction_status")
            .prefetch_related(
                "statuses",
                Prefetch(
                    "psis",
                    queryset=Psi.objects.select_related("responsible").order_by("-assigned_date", "-pk"),
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
        status_id = self.request.GET.get("status", "").strip()
        if status_id:
            qs = qs.filter(statuses__id=status_id)
        if _is_truthy_mine(self.request.GET.get("mine", "")):
            qs = qs.filter(responsible_person_id=self.request.user.pk)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["selected_status"] = self.request.GET.get("status", "").strip()
        context["selected_mine"] = _is_truthy_mine(self.request.GET.get("mine", ""))
        context["organization_statuses"] = OrganizationStatus.objects.filter(is_active=True).order_by("name")
        return context


class TelecomOperatorListView(PanelAuthMixin, PanelMenuMixin, ListView):
    template_name = "panel/telecom_operator_list.html"
    context_object_name = "telecom_operators"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            TelecomOperator.objects.select_related("responsible_person")
            .prefetch_related("statuses")
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
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["telecom_default_icon_url"] = telecom_default_icon_url()
        return context


class TelecomOperatorDetailView(PanelAuthMixin, PanelMenuMixin, DetailView):
    template_name = "panel/telecom_operator_detail.html"
    context_object_name = "telecom_operator"

    def get_queryset(self):
        return TelecomOperator.objects.select_related(
            "responsible_person",
            "created_by",
            "updated_by",
        ).prefetch_related("statuses")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tab = self.request.GET.get("tab", "").strip()
        context["active_tab"] = tab if tab in {"info", "contacts", "licenses", "history"} else "info"
        context["rkn_unavailable"] = self.request.GET.get("rkn_unavailable", "").strip() == "1"
        context["telecom_default_icon_url"] = telecom_default_icon_url()
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
        context["telecom_default_icon_url"] = telecom_default_icon_url()
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


class OriDetailView(PanelAuthMixin, PanelMenuMixin, DetailView):
    template_name = "panel/organization_detail.html"
    context_object_name = "ori"

    def get_queryset(self):
        return Ori.objects.select_related(
            "interaction_status",
            "industry",
            "orm_vendor",
            "sorm_owner",
            "created_by",
            "updated_by",
        ).prefetch_related("statuses")


class OriCreateView(PanelAuthMixin, PanelMenuMixin, CreateView):
    template_name = "panel/organization_form.html"
    form_class = OriForm

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
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
        form.instance.updated_by = self.request.user
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
