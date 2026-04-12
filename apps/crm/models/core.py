from django.conf import settings
from django.core.validators import MinLengthValidator, URLValidator
from django.db import models

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


class PsiStatus(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Статус ПСИ"
        verbose_name_plural = "Статусы ПСИ"


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
    )
    position = models.CharField(max_length=255, blank=True, verbose_name="Должность")
    last_name = models.CharField(max_length=120, blank=True, verbose_name="Фамилия")
    first_name = models.CharField(max_length=120, blank=True, verbose_name="Имя")
    middle_name = models.CharField(max_length=120, blank=True, verbose_name="Отчество")
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
        indexes = [models.Index(fields=["organization", "last_name"])]

    def __str__(self) -> str:
        fio = " ".join(x for x in [self.last_name, self.first_name, self.middle_name] if x)
        return fio or f"Контакт #{self.pk}"


class Psi(TimeAuditModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="psis",
        verbose_name="Организация",
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
    status = models.ForeignKey(
        PsiStatus,
        on_delete=models.PROTECT,
        related_name="psis",
        verbose_name="Статус",
    )
    protocol_html_url = models.URLField(blank=True, verbose_name="Ссылка на протокол")
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
            )
        ]

    def __str__(self) -> str:
        return f"ПСИ {self.organization.name}"


class Comment(TimeAuditModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Организация",
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

    def __str__(self) -> str:
        return f"Комментарий {self.organization.name}"


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
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="Организация",
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="documents",
        verbose_name="Добавил",
    )
    start_date = models.DateField(null=True, blank=True, verbose_name="Начало действия")
    end_date = models.DateField(null=True, blank=True, verbose_name="Завершение действия")
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name="documents",
        verbose_name="Документ",
    )
    number = models.CharField(max_length=255, blank=True, verbose_name="Номер документа")
    title = models.CharField(max_length=500, verbose_name="Наименование документа")
    html_url = models.URLField(blank=True, verbose_name="Ссылка на HTML документ")
    file = models.FileField(upload_to="documents/%Y/%m/%d/", null=True, blank=True, verbose_name="Файл")
    comment = models.TextField(blank=True, verbose_name="Комментарий")

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="document_dates_valid",
            )
        ]

    def __str__(self) -> str:
        return self.title


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
