from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.db.models import Count

from apps.crm.favicon_fetch import maybe_assign_favicon_from_sites

from .models import (
    Comment,
    Contact,
    Document,
    DocumentLink,
    DocumentType,
    Event,
    EventDocumentTemplate,
    EventStatus,
    EventType,
    Industry,
    InteractionObject,
    InteractionObjectType,
    InteractionStatus,
    LicenseOrder,
    LicenseOrderNumber,
    Organization,
    OrganizationStatus,
    OrganizationType,
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


class OrganizationDocumentLinkInline(GenericTabularInline):
    model = DocumentLink
    extra = 0
    autocomplete_fields = ("document", "created_by", "updated_by")
    ct_field = "content_type"
    ct_fk_field = "object_id"


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


class LicenseOrderDocumentLinkInline(GenericTabularInline):
    model = DocumentLink
    extra = 0
    autocomplete_fields = ("document", "created_by", "updated_by")
    ct_field = "content_type"
    ct_fk_field = "object_id"


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "inn",
        "organization_type",
        "statuses_display",
        "interaction_status",
        "responsible_person",
        "updated_at",
    )
    list_filter = ("organization_type", "statuses", "interaction_status", "industry", "responsible_person")
    search_fields = ("name", "inn", "case_number", "responsible_person__username", "responsible_person__first_name", "responsible_person__last_name")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = (
        "organization_type",
        "interaction_status",
        "industry",
        "orm_vendor",
        "sorm_owner",
        "created_by",
        "updated_by",
    )
    filter_horizontal = ("statuses",)
    inlines = (ContactInline, InteractionObjectInline, EventInline, OrganizationDocumentLinkInline, CommentInline, PsiInline)

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
    inlines = (LicenseOrderPsiInline, LicenseOrderDocumentLinkInline)

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


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("document_type", "number", "start_date", "end_date", "links_count")
    search_fields = ("number",)
    list_filter = ("document_type",)
    autocomplete_fields = ("document_type", "created_by", "updated_by")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_links_count=Count("links"))

    @admin.display(description="Связей")
    def links_count(self, obj):
        return getattr(obj, "_links_count", obj.links.count())


@admin.register(DocumentLink)
class DocumentLinkAdmin(admin.ModelAdmin):
    list_display = ("document", "content_type", "object_id", "created_at")
    list_filter = ("content_type",)
    search_fields = ("document__number",)
    autocomplete_fields = ("document", "created_by", "updated_by")


@admin.register(EventDocumentTemplate)
class EventDocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "event_type", "template_path", "is_active")
    search_fields = ("name", "event_type__name", "template_path")
    list_filter = ("event_type", "is_active")
    autocomplete_fields = ("event_type", "created_by", "updated_by")


@admin.register(OrganizationType)
@admin.register(OrganizationStatus)
@admin.register(InteractionStatus)
@admin.register(InteractionObjectType)
@admin.register(EventType)
@admin.register(EventStatus)
@admin.register(DocumentType)
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
