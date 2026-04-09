from django.contrib import admin

from .models import (
    Comment,
    Contact,
    Document,
    DocumentType,
    Event,
    EventDocumentTemplate,
    EventStatus,
    EventType,
    Industry,
    InteractionObject,
    InteractionObjectType,
    InteractionStatus,
    Organization,
    OrganizationStatus,
    OrganizationType,
    OrmVendor,
    Psi,
    PsiStatus,
)


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0


class InteractionObjectInline(admin.TabularInline):
    model = InteractionObject
    extra = 0


class EventInline(admin.TabularInline):
    model = Event
    extra = 0
    autocomplete_fields = ("contact", "initiator", "responsible", "event_type", "status")


class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    autocomplete_fields = ("added_by", "document_type")


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    autocomplete_fields = ("author",)


class PsiInline(admin.TabularInline):
    model = Psi
    extra = 0
    autocomplete_fields = ("responsible", "status")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "inn",
        "organization_type",
        "status",
        "interaction_status",
        "responsible_person",
        "updated_at",
    )
    list_filter = ("organization_type", "status", "interaction_status", "industry", "responsible_person")
    search_fields = ("name", "inn", "case_number", "responsible_person__username", "responsible_person__first_name", "responsible_person__last_name")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = (
        "organization_type",
        "status",
        "interaction_status",
        "industry",
        "orm_vendor",
        "sorm_owner",
        "created_by",
        "updated_by",
    )
    inlines = (ContactInline, InteractionObjectInline, EventInline, DocumentInline, CommentInline, PsiInline)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("organization", "last_name", "first_name", "phone", "email", "updated_at")
    search_fields = ("organization__name", "last_name", "first_name", "middle_name", "phone", "email")
    list_filter = ("organization",)
    autocomplete_fields = ("organization", "created_by", "updated_by")


@admin.register(InteractionObject)
class InteractionObjectAdmin(admin.ModelAdmin):
    list_display = ("organization", "object_type", "object_value", "start_date", "end_date")
    search_fields = ("organization__name", "object_value", "object_url")
    list_filter = ("object_type",)
    autocomplete_fields = ("organization", "object_type", "created_by", "updated_by")


@admin.register(Psi)
class PsiAdmin(admin.ModelAdmin):
    list_display = ("organization", "responsible", "status", "assigned_date", "start_date", "end_date")
    list_filter = ("status", "responsible")
    search_fields = ("organization__name", "comment")
    autocomplete_fields = ("organization", "responsible", "status", "created_by", "updated_by")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("organization", "author", "commented_at")
    search_fields = ("organization__name", "author__username", "text")
    list_filter = ("author",)
    autocomplete_fields = ("organization", "author", "created_by", "updated_by")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("organization", "event_type", "event_date", "status", "responsible")
    search_fields = ("organization__name", "comment", "contact__last_name")
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
    list_display = ("organization", "document_type", "number", "title", "start_date", "end_date")
    search_fields = ("organization__name", "number", "title", "comment")
    list_filter = ("document_type",)
    autocomplete_fields = ("organization", "added_by", "document_type", "created_by", "updated_by")


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
@admin.register(PsiStatus)
@admin.register(EventType)
@admin.register(EventStatus)
@admin.register(DocumentType)
@admin.register(Industry)
@admin.register(OrmVendor)
class ReferenceAdmin(admin.ModelAdmin):
    list_display = ("name", "alias", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "alias")
