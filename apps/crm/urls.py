from django.urls import path

from apps.crm import views

app_name = "panel"

urlpatterns = [
    path("", views.PanelHomeRedirectView.as_view(), name="home"),
    path("organizations/", views.OrganizationListView.as_view(), name="organization_list"),
    path("organizations/add/", views.OrganizationCreateView.as_view(), name="organization_add"),
    path("organizations/<int:pk>/", views.OrganizationDetailView.as_view(), name="organization_detail"),
    path("organizations/<int:pk>/edit/", views.OrganizationUpdateView.as_view(), name="organization_edit"),
    path("psi/", views.PsiPlaceholderView.as_view(), name="psi"),
    path("calendar/", views.CalendarPlaceholderView.as_view(), name="calendar"),
    path("licenses/", views.LicensesPlaceholderView.as_view(), name="licenses"),
    path("reports/", views.ReportsPlaceholderView.as_view(), name="reports"),
    path("users/", views.UsersPlaceholderView.as_view(), name="users"),
]
