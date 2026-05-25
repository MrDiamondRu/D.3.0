from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.db.models import Count

from apps.crm.favicon_fetch import maybe_assign_favicon_from_sites

from .models import (
    Comment,
    Contact,
    Event,
    EventStatus,
    EventType,
    Industry,
    InteractionObject,
    InteractionObjectType,
    InteractionStatus,
    LicenseOrder,
    LicenseOrderNumber,
    Ori,
    OrganizationStatus,
    OrmVendor,
    Psi,
    PsiWorkflowStatus,
    TelecomOperatorAuditEvent,
    TelecomOperator,
    TelecomOperatorLicense,
)


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0
    exclude = ("telecom_operator",)


class InteractionObjectInline(admin.TabularInline):
    model = InteractionObject
    extra = 0


class EventInline(admin.TabularInline):
    model = Event
    extra = 0
    autocomplete_fields = ("contact", "initiator", "responsible", "event_type", "status")


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    exclude = ("telecom_operator",)
    autocomplete_fields = ("author",)


class PsiInline(admin.TabularInline):
    model = Psi
    extra = 0
    exclude = ("license_order",)
    autocomplete_fields = ("responsible",)


class TelecomOperatorContactInline(admin.TabularInline):
    model = Contact
    fk_name = "telecom_operator"
    extra = 0
    exclude = ("organization",)
    autocomplete_fields = ("created_by", "updated_by")


class TelecomOperatorCommentInline(admin.TabularInline):
    model = Comment
    fk_name = "telecom_operator"
    extra = 0
    exclude = ("organization",)
    autocomplete_fields = ("author", "created_by", "updated_by")


class TelecomOperatorLicenseInline(admin.TabularInline):
    model = TelecomOperatorLicense
    extra = 0
    autocomplete_fields = ("created_by", "updated_by")


class LicenseOrderInline(admin.TabularInline):
    model = LicenseOrder
    extra = 0
    autocomplete_fields = ("order_number", "orm_vendor", "created_by", "updated_by")


class LicenseOrderPsiInline(admin.TabularInline):
    model = Psi
    fk_name = "license_order"
    extra = 0
    exclude = ("organization",)
    autocomplete_fields = ("responsible", "created_by", "updated_by")


@admin.register(Ori)
class OriAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "inn",
        "statuses_display",
        "interaction_status",
        "responsible_person",
        "updated_at",
    )
    list_filter = ("statuses", "interaction_status", "industry", "responsible_person")
    search_fields = ("name", "inn", "case_number", "responsible_person__username", "responsible_person__first_name", "responsible_person__last_name")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = (
        "interaction_status",
        "industry",
        "orm_vendor",
        "sorm_owner",
        "created_by",
        "updated_by",
    )
    filter_horizontal = ("statuses",)
    inlines = (ContactInline, InteractionObjectInline, EventInline, CommentInline, PsiInline)

    @admin.display(description="Статусы")
    def statuses_display(self, obj):
        return ", ".join(obj.statuses.values_list("name", flat=True)) or "-"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        maybe_assign_favicon_from_sites(obj)


@admin.register(TelecomOperator)
class TelecomOperatorAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "inn",
        "statuses_display",
        "responsible_person",
        "updated_at",
    )
    list_filter = ("statuses", "responsible_person")
    search_fields = (
        "name",
        "inn",
        "case_number",
        "responsible_person__username",
        "responsible_person__first_name",
        "responsible_person__last_name",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = (
        "responsible_person",
        "created_by",
        "updated_by",
    )
    filter_horizontal = ("statuses",)
    inlines = (
        TelecomOperatorContactInline,
        TelecomOperatorCommentInline,
        TelecomOperatorLicenseInline,
    )

    @admin.display(description="Статусы")
    def statuses_display(self, obj):
        return ", ".join(obj.statuses.values_list("name", flat=True)) or "-"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        maybe_assign_favicon_from_sites(obj)


@admin.register(TelecomOperatorAuditEvent)
class TelecomOperatorAuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "telecom_operator", "operator_name", "user")
    list_filter = ("event_type", "user")
    search_fields = ("operator_name", "telecom_operator__name", "user__username")
    readonly_fields = ("created_at", "event_type", "telecom_operator", "operator_name", "user")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TelecomOperatorLicense)
class TelecomOperatorLicenseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "telecom_operator",
        "number",
        "status",
        "start_date",
        "end_date",
        "updated_at",
    )
    list_filter = ("status", "telecom_operator")
    search_fields = ("title", "number", "territory", "telecom_operator__name")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("telecom_operator", "created_by", "updated_by")
    inlines = (LicenseOrderInline,)


@admin.register(LicenseOrder)
class LicenseOrderAdmin(admin.ModelAdmin):
    list_display = ("license", "order_number", "orm_vendor", "psis_count", "updated_at")
    search_fields = (
        "license__title",
        "license__telecom_operator__name",
        "order_number__name",
    )
    list_filter = ("orm_vendor", "order_number")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = (
        "license",
        "order_number",
        "orm_vendor",
        "created_by",
        "updated_by",
    )
    inlines = (LicenseOrderPsiInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_psi_count=Count("psis"))

    @admin.display(description="ПСИ")
    def psis_count(self, obj):
        return getattr(obj, "_psi_count", obj.psis.count())


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("organization", "telecom_operator", "first_name", "phone", "email", "updated_at")
    search_fields = (
        "organization__name",
        "telecom_operator__name",
        "first_name",
        "phone",
        "email",
    )
    list_filter = ("organization", "telecom_operator")
    autocomplete_fields = ("organization", "telecom_operator", "created_by", "updated_by")


@admin.register(InteractionObject)
class InteractionObjectAdmin(admin.ModelAdmin):
    list_display = ("organization", "object_type", "object_value", "start_date", "end_date")
    search_fields = ("organization__name", "object_value", "object_url")
    list_filter = ("object_type",)
    autocomplete_fields = ("organization", "object_type", "created_by", "updated_by")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("organization", "telecom_operator", "author", "commented_at")
    search_fields = ("organization__name", "telecom_operator__name", "author__username", "text")
    list_filter = ("author", "organization", "telecom_operator")
    autocomplete_fields = ("organization", "telecom_operator", "author", "created_by", "updated_by")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("organization", "event_type", "event_date", "status", "responsible")
    search_fields = ("organization__name", "comment", "contact__first_name", "contact__phone", "contact__email")
    list_filter = ("event_type", "status", "event_date")
    date_hierarchy = "event_date"
    autocomplete_fields = (
        "organization",
        "contact",
        "event_type",
        "initiator",
        "responsible",
        "status",
        "created_by",
        "updated_by",
    )


@admin.register(OrganizationStatus)
@admin.register(InteractionStatus)
@admin.register(InteractionObjectType)
@admin.register(EventType)
@admin.register(EventStatus)
@admin.register(Industry)
@admin.register(OrmVendor)
@admin.register(LicenseOrderNumber)
class ReferenceAdmin(admin.ModelAdmin):
    list_display = ("name", "alias", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "alias")


@admin.register(Psi)
class PsiAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "license_order",
        "responsible",
        "status_display",
        "assigned_date",
        "start_date",
        "end_date",
    )
    list_filter = ("status", "responsible")
    search_fields = (
        "organization__name",
        "license_order__license__title",
        "license_order__license__telecom_operator__name",
        "comment",
    )
    autocomplete_fields = ("organization", "license_order", "responsible", "created_by", "updated_by")

    @admin.display(description="Статус")
    def status_display(self, obj):
        return dict(PsiWorkflowStatus.choices).get(obj.status, obj.status)


# --- Группировка моделей CRM в админке (главная и /admin/crm/) ---

_CRM_TELECOM_MODELS = (
    "TelecomOperator",
    "TelecomOperatorLicense",
    "LicenseOrder",
    "LicenseOrderNumber",
)
_CRM_COMMON_MODELS = (
    "OrganizationStatus",
    "OrmVendor",
    "Psi",
)


def _split_crm_admin_app(app: dict) -> list[dict]:
    """Разбивает один блок приложения crm на «Операторы связи», «Общее» и остальные модели."""
    models = list(app.get("models") or [])
    by_object_name = {m["object_name"]: m for m in models}
    used = set(_CRM_TELECOM_MODELS) | set(_CRM_COMMON_MODELS)
    telecom = [by_object_name[name] for name in _CRM_TELECOM_MODELS if name in by_object_name]
    common = [by_object_name[name] for name in _CRM_COMMON_MODELS if name in by_object_name]
    other = [m for m in models if m["object_name"] not in used]
    orig_name = app.get("name") or "CRM"
    out: list[dict] = []
    if telecom:
        block = dict(app)
        block["name"] = "Операторы связи"
        block["models"] = telecom
        out.append(block)
    if common:
        block = dict(app)
        block["name"] = "Общее"
        block["models"] = common
        out.append(block)
    if other:
        block = dict(app)
        block["name"] = orig_name
        block["models"] = other
        out.append(block)
    return out


_original_admin_get_app_list = AdminSite.get_app_list


def _patched_admin_get_app_list(self, request, app_label=None):
    app_list = _original_admin_get_app_list(self, request, app_label)
    if app_label is not None and app_label != "crm":
        return app_list
    new_list: list[dict] = []
    for app in app_list:
        if app.get("app_label") == "crm":
            new_list.extend(_split_crm_admin_app(app))
        else:
            new_list.append(app)
    return new_list


if not getattr(AdminSite, "_crm_admin_app_list_grouped", False):
    AdminSite._crm_admin_app_list_grouped = True
    AdminSite.get_app_list = _patched_admin_get_app_list
