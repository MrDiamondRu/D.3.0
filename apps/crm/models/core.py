from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinLengthValidator, URLValidator
from django.db import models
from django.utils import timezone

from apps.crm.validators import validate_phone_11_digits, validate_url_list


class TimeAuditModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата изменения")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_created",
        null=True,
        blank=True,
        verbose_name="Кто создал",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_updated",
        null=True,
        blank=True,
        verbose_name="Кто изменил",
    )

    class Meta:
        abstract = True


class NamedReference(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Наименование")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    alias = models.CharField(max_length=255, blank=True, verbose_name="Синоним для импорта")

    class Meta:
        abstract = True
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class OrganizationType(NamedReference):
    icon = models.ImageField(upload_to="organization_types/icons/", null=True, blank=True, verbose_name="Иконка")

    class Meta(NamedReference.Meta):
        verbose_name = "Тип организации"
        verbose_name_plural = "Типы организаций"


class OrganizationStatus(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Статус организации"
        verbose_name_plural = "Статусы организаций"


class InteractionStatus(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Статус взаимодействия"
        verbose_name_plural = "Статусы взаимодействия"


class InteractionObjectType(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Тип объекта взаимодействия"
        verbose_name_plural = "Типы объектов взаимодействия"


class PsiWorkflowStatus(models.TextChoices):
    ASSIGNED = "assigned", "Назначены"
    IN_PROGRESS = "in_progress", "В работе"
    FAILED = "failed", "Провалены"
    OVERDUE = "overdue", "Просрочены"
    SUCCESSFUL = "successful", "Успешны"


class EventType(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Тип события"
        verbose_name_plural = "Типы событий"


class EventStatus(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Статус события"
        verbose_name_plural = "Статусы событий"


class DocumentType(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Тип документа"
        verbose_name_plural = "Типы документов"


class Industry(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Отрасль"
        verbose_name_plural = "Отрасли"


class OrmVendor(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Производитель ТС ОРМ"
        verbose_name_plural = "Производители ТС ОРМ"


class Organization(TimeAuditModel):
    icon = models.ImageField(upload_to="organizations/icons/", null=True, blank=True, verbose_name="Иконка")
    name = models.CharField(max_length=500, verbose_name="Наименование организации")
    inn = models.CharField(
        max_length=12,
        db_index=True,
        validators=[MinLengthValidator(10)],
        verbose_name="ИНН",
    )
    organization_type = models.ForeignKey(
        OrganizationType,
        on_delete=models.PROTECT,
        related_name="organizations",
        verbose_name="Тип организации",
    )
    statuses = models.ManyToManyField(
        OrganizationStatus,
        related_name="organizations_by_statuses",
        blank=True,
        verbose_name="Статусы",
    )
    interaction_status = models.ForeignKey(
        InteractionStatus,
        on_delete=models.PROTECT,
        related_name="organizations",
        null=True,
        blank=True,
        verbose_name="Статус взаимодействия",
    )
    case_number = models.CharField(max_length=128, blank=True, verbose_name="Номер дела")
    responsible_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="responsible_organizations",
        null=True,
        blank=True,
        verbose_name="Ответственное лицо",
    )
    in_registry = models.CharField(max_length=255, blank=True, verbose_name="Наличие в реестре")
    registry_record_url = models.URLField(blank=True, verbose_name="Ссылка на запись в реестре")
    sites = models.JSONField(default=list, blank=True, validators=[validate_url_list], verbose_name="Сайты")
    correspondence_address = models.TextField(blank=True, verbose_name="Адрес для корреспонденции")
    industry = models.ForeignKey(
        Industry,
        on_delete=models.SET_NULL,
        related_name="organizations",
        null=True,
        blank=True,
        verbose_name="Отрасль",
    )
    orm_vendor = models.ForeignKey(
        OrmVendor,
        on_delete=models.SET_NULL,
        related_name="organizations",
        null=True,
        blank=True,
        verbose_name="Производитель ТС ОРМ",
    )
    sorm_owner = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="sorm_children",
        null=True,
        blank=True,
        verbose_name="Владелец СОРМ",
    )

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"
        ordering = ("name",)
        indexes = [
            models.Index(fields=["inn"]),
            models.Index(fields=["name"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["inn", "name"], name="uniq_org_inn_name"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.inn})"


class InteractionObject(TimeAuditModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="interaction_objects",
        verbose_name="Организация",
    )
    start_date = models.DateField(null=True, blank=True, verbose_name="Начало действия")
    end_date = models.DateField(null=True, blank=True, verbose_name="Завершение действия")
    object_type = models.ForeignKey(
        InteractionObjectType,
        on_delete=models.PROTECT,
        related_name="interaction_objects",
        verbose_name="Тип объекта",
    )
    object_value = models.CharField(max_length=500, verbose_name="Объект взаимодействия")
    object_url = models.URLField(blank=True, validators=[URLValidator(schemes=["http", "https"])], verbose_name="Ссылка на объект")

    class Meta:
        verbose_name = "Объект взаимодействия"
        verbose_name_plural = "Объекты взаимодействия"
        indexes = [models.Index(fields=["organization", "object_type"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="interaction_dates_valid",
            )
        ]

    def __str__(self) -> str:
        return self.object_value


class Contact(TimeAuditModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="contacts",
        verbose_name="Организация",
        null=True,
        blank=True,
    )
    telecom_operator = models.ForeignKey(
        "TelecomOperator",
        on_delete=models.CASCADE,
        related_name="operator_contacts",
        verbose_name="Оператор связи",
        null=True,
        blank=True,
    )
    position = models.CharField(max_length=255, blank=True, verbose_name="Должность")
    first_name = models.CharField(max_length=120, blank=True, verbose_name="Имя")
    phone = models.CharField(
        max_length=11,
        blank=True,
        validators=[validate_phone_11_digits],
        verbose_name="Телефонный номер",
    )
    email = models.EmailField(blank=True, verbose_name="Адрес электронной почты")
    extra_info = models.TextField(blank=True, verbose_name="Дополнительная информация")

    class Meta:
        verbose_name = "Контакт"
        verbose_name_plural = "Контакты"
        indexes = [
            models.Index(fields=["organization", "first_name"]),
            models.Index(fields=["telecom_operator", "first_name"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(organization__isnull=False, telecom_operator__isnull=True)
                    | models.Q(organization__isnull=True, telecom_operator__isnull=False)
                ),
                name="contact_org_xor_operator",
            ),
        ]

    def __str__(self) -> str:
        return self.first_name or f"Контакт #{self.pk}"


class Psi(TimeAuditModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="psis",
        verbose_name="Организация",
        null=True,
        blank=True,
    )
    license_order = models.ForeignKey(
        "LicenseOrder",
        on_delete=models.CASCADE,
        related_name="psis",
        verbose_name="Приказ лицензии",
        null=True,
        blank=True,
    )
    assigned_date = models.DateField(null=True, blank=True, verbose_name="Дата назначения")
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="psis",
        verbose_name="Ответственный",
    )
    start_date = models.DateField(null=True, blank=True, verbose_name="Дата начала")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата завершения")
    status = models.CharField(
        max_length=24,
        choices=PsiWorkflowStatus.choices,
        default=PsiWorkflowStatus.ASSIGNED,
        verbose_name="Статус",
    )
    comment = models.TextField(blank=True, verbose_name="Комментарий")

    class Meta:
        verbose_name = "ПСИ"
        verbose_name_plural = "ПСИ"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="psi_dates_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(organization__isnull=False, license_order__isnull=True)
                    | models.Q(organization__isnull=True, license_order__isnull=False)
                ),
                name="psi_single_scope",
            ),
        ]

    def save(self, *args, **kwargs):
        if (
            self.end_date
            and self.end_date < timezone.localdate()
            and self.status not in {PsiWorkflowStatus.FAILED, PsiWorkflowStatus.SUCCESSFUL}
        ):
            self.status = PsiWorkflowStatus.OVERDUE
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        if self.organization_id:
            return f"ПСИ {self.organization.name}"
        if self.license_order_id:
            lic = self.license_order.license
            return f"ПСИ {lic.title} (приказ)"
        return f"ПСИ #{self.pk}"


class Comment(TimeAuditModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Организация",
        null=True,
        blank=True,
    )
    telecom_operator = models.ForeignKey(
        "TelecomOperator",
        on_delete=models.CASCADE,
        related_name="operator_comments",
        verbose_name="Оператор связи",
        null=True,
        blank=True,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organization_comments",
        verbose_name="Автор",
    )
    text = models.TextField(verbose_name="Текст комментария")
    commented_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время комментария")

    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ("-commented_at",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(organization__isnull=False, telecom_operator__isnull=True)
                    | models.Q(organization__isnull=True, telecom_operator__isnull=False)
                ),
                name="comment_org_xor_operator",
            ),
        ]

    def __str__(self) -> str:
        if self.organization_id:
            return f"Комментарий {self.organization.name}"
        return f"Комментарий {self.telecom_operator.name}"


class Event(TimeAuditModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="Организация",
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        related_name="events",
        null=True,
        blank=True,
        verbose_name="Контакт",
    )
    event_type = models.ForeignKey(
        EventType,
        on_delete=models.PROTECT,
        related_name="events",
        verbose_name="Событие",
    )
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="initiated_events",
        verbose_name="Инициатор",
    )
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="responsible_events",
        verbose_name="Ответственный",
    )
    event_date = models.DateField(verbose_name="Дата события")
    status = models.ForeignKey(
        EventStatus,
        on_delete=models.PROTECT,
        related_name="events",
        verbose_name="Статус",
    )
    comment = models.TextField(blank=True, verbose_name="Комментарий")

    class Meta:
        verbose_name = "Событие"
        verbose_name_plural = "События"
        indexes = [models.Index(fields=["organization", "event_date"])]

    def __str__(self) -> str:
        return f"{self.event_type} {self.organization.name}"


class Document(TimeAuditModel):
    start_date = models.DateField(null=True, blank=True, verbose_name="Начало действия")
    end_date = models.DateField(null=True, blank=True, verbose_name="Завершение действия")
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name="documents",
        verbose_name="Документ",
    )
    number = models.CharField(max_length=255, blank=True, verbose_name="Номер документа")
    file = models.FileField(upload_to="documents/%Y/%m/%d/", null=True, blank=True, verbose_name="Файл")

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="document_dates_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.number or f"Документ #{self.pk}"


class TelecomLicenseStatus(models.TextChoices):
    ACTIVE = "active", "Действующая"
    INACTIVE = "inactive", "Недействующая"


class LicenseOrderNumber(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Номер приказа"
        verbose_name_plural = "Номера приказов"


class TelecomOperator(TimeAuditModel):
    icon = models.ImageField(upload_to="telecom_operators/icons/", null=True, blank=True, verbose_name="Иконка")
    name = models.CharField(max_length=500, verbose_name="Наименование организации")
    inn = models.CharField(
        max_length=12,
        db_index=True,
        validators=[MinLengthValidator(10)],
        verbose_name="ИНН",
    )
    statuses = models.ManyToManyField(
        OrganizationStatus,
        related_name="telecom_operators_by_statuses",
        blank=True,
        verbose_name="Статусы",
    )
    case_number = models.CharField(max_length=128, blank=True, verbose_name="Номер дела")
    responsible_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="responsible_telecom_operators",
        null=True,
        blank=True,
        verbose_name="Ответственное лицо",
    )
    sites = models.JSONField(default=list, blank=True, validators=[validate_url_list], verbose_name="Сайты")
    correspondence_address = models.TextField(blank=True, verbose_name="Адрес для корреспонденции")

    class Meta:
        verbose_name = "Оператор связи"
        verbose_name_plural = "Операторы связи"
        ordering = ("name",)
        indexes = [
            models.Index(fields=["inn"]),
            models.Index(fields=["name"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["inn", "name"], name="uniq_telecom_operator_inn_name"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.inn})"


class TelecomOperatorLicense(TimeAuditModel):
    telecom_operator = models.ForeignKey(
        TelecomOperator,
        on_delete=models.CASCADE,
        related_name="licenses",
        verbose_name="Оператор связи",
    )
    title = models.CharField(max_length=500, verbose_name="Наименование")
    number = models.CharField(max_length=255, blank=True, verbose_name="Номер")
    start_date = models.DateField(null=True, blank=True, verbose_name="Начало действия")
    end_date = models.DateField(null=True, blank=True, verbose_name="Окончание действия")
    territory = models.TextField(blank=True, verbose_name="Территория действия")
    status = models.CharField(
        max_length=16,
        choices=TelecomLicenseStatus.choices,
        default=TelecomLicenseStatus.ACTIVE,
        verbose_name="Статус",
    )

    class Meta:
        verbose_name = "Лицензия"
        verbose_name_plural = "Лицензии"
        ordering = ("telecom_operator", "start_date", "title")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="telecom_license_dates_valid",
            )
        ]

    def __str__(self) -> str:
        return self.title


class LicenseOrder(TimeAuditModel):
    license = models.ForeignKey(
        TelecomOperatorLicense,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="Лицензия",
    )
    order_number = models.ForeignKey(
        LicenseOrderNumber,
        on_delete=models.PROTECT,
        related_name="license_orders",
        verbose_name="Номер приказа",
    )
    orm_vendor = models.ForeignKey(
        OrmVendor,
        on_delete=models.PROTECT,
        related_name="license_orders",
        verbose_name="Производитель ТС (ИС) ОРМ",
    )
    class Meta:
        verbose_name = "Приказ лицензии"
        verbose_name_plural = "Приказы лицензий"
        ordering = ("license", "pk")

    def __str__(self) -> str:
        return f"{self.order_number} — {self.license.title}"


class DocumentLink(TimeAuditModel):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="links",
        verbose_name="Документ",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="crm_document_links",
        verbose_name="Тип сущности",
    )
    object_id = models.PositiveBigIntegerField(verbose_name="ID сущности")
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        verbose_name = "Связь документа"
        verbose_name_plural = "Связи документов"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "content_type", "object_id"],
                name="uniq_document_link_target",
            )
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["document"]),
        ]

    def __str__(self) -> str:
        return f"{self.document} -> {self.content_type}#{self.object_id}"


class TelecomOperatorAuditEventType(models.TextChoices):
    CREATE = "create", "Создание"
    UPDATE = "update", "Изменение"
    DELETE = "delete", "Удаление"


class TelecomOperatorAuditEvent(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата события")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="telecom_operator_audit_events",
        null=True,
        blank=True,
        verbose_name="Пользователь",
    )
    event_type = models.CharField(
        max_length=16,
        choices=TelecomOperatorAuditEventType.choices,
        verbose_name="Тип события",
    )
    telecom_operator = models.ForeignKey(
        TelecomOperator,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
        verbose_name="Оператор связи",
    )
    operator_name = models.CharField(max_length=500, blank=True, verbose_name="Наименование оператора")

    class Meta:
        verbose_name = "Событие аудита оператора связи"
        verbose_name_plural = "События аудита операторов связи"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["event_type"]),
        ]

    def __str__(self) -> str:
        label = self.operator_name or (self.telecom_operator.name if self.telecom_operator_id else "—")
        return f"{self.get_event_type_display()}: {label}"


class EventDocumentTemplate(TimeAuditModel):
    event_type = models.ForeignKey(
        EventType,
        on_delete=models.CASCADE,
        related_name="document_templates",
        verbose_name="Тип события",
    )
    name = models.CharField(max_length=255, verbose_name="Наименование шаблона")
    template_path = models.CharField(max_length=500, blank=True, verbose_name="Путь к шаблону .docx")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Шаблон документа события"
        verbose_name_plural = "Шаблоны документов событий"
        constraints = [models.UniqueConstraint(fields=["event_type", "name"], name="uniq_event_template_name")]

    def __str__(self) -> str:
        return self.name
