from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, RedirectView, TemplateView, UpdateView

from apps.crm.forms import OrganizationForm
from apps.crm.models import Organization, OrganizationStatus, OrganizationType


class PanelMenuMixin:
    panel_title = "Панель организаций"

    def get_panel_menu(self):
        current_path = self.request.path
        organization_url = reverse("panel:organization_list")
        psi_url = reverse("panel:psi")
        calendar_url = reverse("panel:calendar")
        licenses_url = reverse("panel:licenses")
        reports_url = reverse("panel:reports")
        users_url = reverse("panel:users")
        return [
            {
                "name": "Организации",
                "url": organization_url,
                "is_active": current_path.startswith(organization_url),
            },
            {"name": "ПСИ", "url": psi_url, "is_active": current_path.startswith(psi_url)},
            {"name": "Календарь", "url": calendar_url, "is_active": current_path.startswith(calendar_url)},
            {"name": "Лицензии", "url": licenses_url, "is_active": current_path.startswith(licenses_url)},
            {"name": "Отчеты", "url": reports_url, "is_active": current_path.startswith(reports_url)},
            {"name": "Пользователи", "url": users_url, "is_active": current_path.startswith(users_url)},
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["panel_menu"] = self.get_panel_menu()
        context["panel_title"] = self.panel_title
        return context


class PanelAuthMixin(LoginRequiredMixin):
    login_url = reverse_lazy("admin:login")


class PanelHomeRedirectView(PanelAuthMixin, RedirectView):
    permanent = False
    pattern_name = "panel:organization_list"


class OrganizationListView(PanelAuthMixin, PanelMenuMixin, ListView):
    template_name = "panel/organization_list.html"
    context_object_name = "organizations"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            Organization.objects.select_related(
                "organization_type",
                "status",
                "interaction_status",
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
                | Q(responsible_person__icontains=query)
            )
        organization_type_id = self.request.GET.get("organization_type", "").strip()
        status_id = self.request.GET.get("status", "").strip()
        if organization_type_id:
            qs = qs.filter(organization_type_id=organization_type_id)
        if status_id:
            qs = qs.filter(status_id=status_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["selected_organization_type"] = self.request.GET.get("organization_type", "").strip()
        context["selected_status"] = self.request.GET.get("status", "").strip()
        context["organization_types"] = OrganizationType.objects.filter(is_active=True).order_by("name")
        context["organization_statuses"] = OrganizationStatus.objects.filter(is_active=True).order_by("name")
        return context


class OrganizationDetailView(PanelAuthMixin, PanelMenuMixin, DetailView):
    template_name = "panel/organization_detail.html"
    context_object_name = "organization"

    def get_queryset(self):
        return Organization.objects.select_related(
            "organization_type",
            "status",
            "interaction_status",
            "industry",
            "orm_vendor",
            "sorm_owner",
            "created_by",
            "updated_by",
        )


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


class PsiPlaceholderView(PanelPlaceholderView):
    page_title = "ПСИ"


class CalendarPlaceholderView(PanelPlaceholderView):
    page_title = "Календарь"


class LicensesPlaceholderView(PanelPlaceholderView):
    page_title = "Лицензии"


class ReportsPlaceholderView(PanelPlaceholderView):
    page_title = "Отчеты"


class UsersPlaceholderView(PanelPlaceholderView):
    page_title = "Пользователи"
