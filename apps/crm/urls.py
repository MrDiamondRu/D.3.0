from django.urls import path
from django.views.generic import RedirectView

from apps.crm import views

app_name = "panel"

urlpatterns = [
    path("login/", views.PanelLoginView.as_view(), name="login"),
    path("logout/", views.PanelLogoutView.as_view(), name="logout"),
    path("", views.PanelHomeRedirectView.as_view(), name="home"),
    path("loading/", views.PanelLoadingView.as_view(), name="loading"),
    # ОРИ
    path("ori/", views.OriListView.as_view(), name="ori_list"),
    path("ori/add/", views.OriCreateView.as_view(), name="ori_add"),
    path("ori/<int:pk>/edit/", views.OriUpdateView.as_view(), name="ori_edit"),
    path("ori/<int:pk>/", views.OriDetailView.as_view(), name="ori_detail"),
    # Источники данных
    path("data-sources/", views.DataSourceListView.as_view(), name="data_source_list"),
    path("data-sources/add/", views.DataSourceCreateView.as_view(), name="data_source_add"),
    path("data-sources/<int:pk>/edit/", views.DataSourceUpdateView.as_view(), name="data_source_edit"),
    path("data-sources/<int:pk>/", views.DataSourceDetailView.as_view(), name="data_source_detail"),
    # Операторы связи
    path("telecom-operators/", views.TelecomOperatorListView.as_view(), name="telecom_operator_list"),
    path("telecom-operators/<int:pk>/edit/", views.TelecomOperatorUpdateView.as_view(), name="telecom_operator_edit"),
    path("telecom-operators/<int:pk>/", views.TelecomOperatorDetailView.as_view(), name="telecom_operator_detail"),
    path("telecom-licenses/<int:pk>/", views.TelecomOperatorLicenseDetailView.as_view(), name="telecom_license_detail"),
    # Прочие разделы
    path("implementation/", views.ImplementationPlaceholderView.as_view(), name="implementation"),
    path("calendar/", views.CalendarPlaceholderView.as_view(), name="calendar"),
    path("statistics/", views.StatisticsPlaceholderView.as_view(), name="statistics"),
    path("contacts/", views.ContactsListView.as_view(), name="contacts"),
    path("mailings/", views.MailingsPlaceholderView.as_view(), name="mailings"),
    path("psi/", views.PsiPlaceholderView.as_view(), name="psi"),
    path("licenses/", views.LicensesPlaceholderView.as_view(), name="licenses"),
    path("reports/", views.ReportsPlaceholderView.as_view(), name="reports"),
    path("users/", views.UsersPlaceholderView.as_view(), name="users"),
    # Старые URL (organizations/*) → новые
    path(
        "organizations/",
        RedirectView.as_view(pattern_name="panel:ori_list", permanent=True),
    ),
    path(
        "organizations/add/",
        RedirectView.as_view(pattern_name="panel:ori_add", permanent=True),
    ),
    path(
        "organizations/<int:pk>/edit/",
        RedirectView.as_view(pattern_name="panel:ori_edit", permanent=True),
    ),
    path(
        "organizations/<int:pk>/",
        RedirectView.as_view(pattern_name="panel:ori_detail", permanent=True),
    ),
    path(
        "organizations/data-sources/",
        RedirectView.as_view(pattern_name="panel:data_source_list", permanent=True),
    ),
    path(
        "organizations/data-sources/add/",
        RedirectView.as_view(pattern_name="panel:data_source_add", permanent=True),
    ),
    path(
        "organizations/data-sources/<int:pk>/edit/",
        RedirectView.as_view(pattern_name="panel:data_source_edit", permanent=True),
    ),
    path(
        "organizations/data-sources/<int:pk>/",
        RedirectView.as_view(pattern_name="panel:data_source_detail", permanent=True),
    ),
    path(
        "organizations/telecom-operators/",
        RedirectView.as_view(pattern_name="panel:telecom_operator_list", permanent=True),
    ),
    path(
        "organizations/telecom-operators/<int:pk>/edit/",
        RedirectView.as_view(pattern_name="panel:telecom_operator_edit", permanent=True),
    ),
    path(
        "organizations/telecom-operators/<int:pk>/",
        RedirectView.as_view(pattern_name="panel:telecom_operator_detail", permanent=True),
    ),
    path(
        "organizations/telecom-licenses/<int:pk>/",
        RedirectView.as_view(pattern_name="panel:telecom_license_detail", permanent=True),
    ),
]
