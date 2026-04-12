from django.urls import path

from apps.crm import views

app_name = "panel"

urlpatterns = [
    path("login/", views.PanelLoginView.as_view(), name="login"),
    path("logout/", views.PanelLogoutView.as_view(), name="logout"),
    path("", views.PanelHomeRedirectView.as_view(), name="home"),
    path("loading/", views.PanelLoadingView.as_view(), name="loading"),
    path("organizations/", views.OrganizationListView.as_view(), name="organization_list"),
    path("organizations/add/", views.OrganizationCreateView.as_view(), name="organization_add"),
    path("organizations/<int:pk>/", views.OrganizationDetailView.as_view(), name="organization_detail"),
    path("organizations/<int:pk>/edit/", views.OrganizationUpdateView.as_view(), name="organization_edit"),
    path("implementation/", views.ImplementationPlaceholderView.as_view(), name="implementation"),
    path("calendar/", views.CalendarPlaceholderView.as_view(), name="calendar"),
    path("statistics/", views.StatisticsPlaceholderView.as_view(), name="statistics"),
    path("contacts/", views.ContactsPlaceholderView.as_view(), name="contacts"),
    path("mailings/", views.MailingsPlaceholderView.as_view(), name="mailings"),
    path("documents/", views.DocumentsPlaceholderView.as_view(), name="documents"),
    path("psi/", views.PsiPlaceholderView.as_view(), name="psi"),
    path("licenses/", views.LicensesPlaceholderView.as_view(), name="licenses"),
    path("reports/", views.ReportsPlaceholderView.as_view(), name="reports"),
    path("users/", views.UsersPlaceholderView.as_view(), name="users"),
]
