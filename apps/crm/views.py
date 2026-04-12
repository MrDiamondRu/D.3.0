from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, RedirectView, TemplateView, UpdateView

from apps.crm.forms import OrganizationForm
from apps.crm.models import Organization, OrganizationStatus, OrganizationType


def _is_truthy_mine(value) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class PanelMenuMixin:
    panel_title = "D.3.0"

    def get_panel_menu(self):
        request = self.request
        current_path = request.path
        organizations_url = reverse("panel:organization_list")
        org_list_path = organizations_url.rstrip("/")
        is_org_list = request.path.rstrip("/") == org_list_path
        is_org_section = current_path.rstrip("/").startswith(org_list_path)
        mine_param = request.GET.get("mine", "")
        org_type_param = request.GET.get("organization_type", "").strip()

        org_children = []
        # Все
        all_active = (is_org_list and not _is_truthy_mine(mine_param) and not org_type_param) or (
            is_org_section and not is_org_list
        )
        org_children.append({"name": "Все", "url": organizations_url, "is_active": all_active})
        # По типу организации
        for org_type in OrganizationType.objects.filter(is_active=True).order_by("name"):
            type_url = f"{organizations_url}?organization_type={org_type.pk}"
            org_children.append(
                {
                    "name": org_type.name,
                    "url": type_url,
                    "is_active": is_org_list and org_type_param == str(org_type.pk) and not _is_truthy_mine(mine_param),
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
        documents_url = reverse("panel:documents")
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
            {"name": "Документы", "url": documents_url, "is_active": current_path.startswith(documents_url)},
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


class OrganizationListView(PanelAuthMixin, PanelMenuMixin, ListView):
    template_name = "panel/organization_list.html"
    context_object_name = "organizations"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            Organization.objects.select_related(
                "organization_type",
                "interaction_status",
            )
            .prefetch_related("statuses")
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
        organization_type_id = self.request.GET.get("organization_type", "").strip()
        status_id = self.request.GET.get("status", "").strip()
        if organization_type_id:
            qs = qs.filter(organization_type_id=organization_type_id)
        if status_id:
            qs = qs.filter(statuses__id=status_id)
        if _is_truthy_mine(self.request.GET.get("mine", "")):
            qs = qs.filter(responsible_person_id=self.request.user.pk)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["selected_organization_type"] = self.request.GET.get("organization_type", "").strip()
        context["selected_status"] = self.request.GET.get("status", "").strip()
        context["selected_mine"] = _is_truthy_mine(self.request.GET.get("mine", ""))
        context["organization_types"] = OrganizationType.objects.filter(is_active=True).order_by("name")
        context["organization_statuses"] = OrganizationStatus.objects.filter(is_active=True).order_by("name")
        return context


class OrganizationDetailView(PanelAuthMixin, PanelMenuMixin, DetailView):
    template_name = "panel/organization_detail.html"
    context_object_name = "organization"

    def get_queryset(self):
        return Organization.objects.select_related(
            "organization_type",
            "interaction_status",
            "industry",
            "orm_vendor",
            "sorm_owner",
            "created_by",
            "updated_by",
        ).prefetch_related("statuses")


class OrganizationCreateView(PanelAuthMixin, PanelMenuMixin, CreateView):
    template_name = "panel/organization_form.html"
    form_class = OrganizationForm

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Организация успешно добавлена.")
        return response

    def get_success_url(self):
        return reverse_lazy("panel:organization_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Добавление организации"
        context["submit_label"] = "Создать организацию"
        return context


class OrganizationUpdateView(PanelAuthMixin, PanelMenuMixin, UpdateView):
    template_name = "panel/organization_form.html"
    form_class = OrganizationForm

    def get_queryset(self):
        return Organization.objects.all()

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Изменения сохранены.")
        return response

    def get_success_url(self):
        return reverse("panel:organization_detail", kwargs={"pk": self.object.pk})

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


class ContactsPlaceholderView(PanelPlaceholderView):
    page_title = "Контакты"


class MailingsPlaceholderView(PanelPlaceholderView):
    page_title = "Рассылки"


class DocumentsPlaceholderView(PanelPlaceholderView):
    page_title = "Документы"


# Legacy placeholder aliases for backward-compatible URLs.
class PsiPlaceholderView(ImplementationPlaceholderView):
    pass


class LicensesPlaceholderView(PanelPlaceholderView):
    page_title = "Лицензии"


class ReportsPlaceholderView(StatisticsPlaceholderView):
    pass


class UsersPlaceholderView(ContactsPlaceholderView):
    pass
