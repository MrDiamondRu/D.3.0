from django.conf import settings
from django.core.validators import MinLengthValidator
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


class PsiWorkflowStatus(models.TextChoices):
    ASSIGNED = "assigned", "Назначены"
    IN_PROGRESS = "in_progress", "В работе"
    FAILED = "failed", "Провалены"
    OVERDUE = "overdue", "Просрочены"
    SUCCESSFUL = "successful", "Успешны"


class EntityStatusKind(models.TextChoices):
    STATUS = "status", "Статус"
    MESSAGE = "message", "Сообщение"
    WARNING = "warning", "Предупреждение"


class EventType(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Тип события"
        verbose_name_plural = "Типы событий"


class EventStatus(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Статус события"
        verbose_name_plural = "Статусы событий"


class Industry(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Отрасль"
        verbose_name_plural = "Отрасли"


class OrmVendor(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Производитель ТС ОРМ"
        verbose_name_plural = "Производители ТС ОРМ"


class Ori(models.Model):
    icon = models.ImageField(upload_to="organizations/icons/", null=True, blank=True, verbose_name="Иконка")
    name = models.CharField(max_length=500, verbose_name="Наименование организации")
    is_archived = models.BooleanField(default=False, verbose_name="Архив")
    inn = models.CharField(
        max_length=12,
        db_index=True,
        validators=[MinLengthValidator(10)],
        verbose_name="ИНН",
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
    outsourcing = models.BooleanField(default=False, verbose_name="Аутсорминг")
    in_registry = models.CharField(max_length=255, blank=True, verbose_name="Номер в реестре")
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
    statuses = models.ManyToManyField(
        "EntityStatus",
        through="EntityStatusLink",
        through_fields=("organization", "status"),
        related_name="organizations",
        blank=True,
        verbose_name="Статусы",
    )

    class Meta:
        verbose_name = "ОРИ"
        verbose_name_plural = "ОРИ"
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


class DataSource(models.Model):
    icon = models.ImageField(upload_to="data_sources/icons/", null=True, blank=True, verbose_name="Иконка")
    name = models.CharField(max_length=500, verbose_name="Наименование")
    is_archived = models.BooleanField(default=False, verbose_name="Архив")
    inn = models.CharField(
        max_length=12,
        db_index=True,
        validators=[MinLengthValidator(10)],
        verbose_name="ИНН",
    )
    case_number = models.CharField(max_length=128, blank=True, verbose_name="Номер дела")
    responsible_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="responsible_data_sources",
        null=True,
        blank=True,
        verbose_name="Ответственное лицо",
    )
    sites = models.JSONField(default=list, blank=True, validators=[validate_url_list], verbose_name="Сайты")
    correspondence_address = models.TextField(blank=True, verbose_name="Адрес для корреспонденции")
    industry = models.ForeignKey(
        Industry,
        on_delete=models.SET_NULL,
        related_name="data_sources",
        null=True,
        blank=True,
        verbose_name="Отрасль",
    )
    statuses = models.ManyToManyField(
        "EntityStatus",
        through="EntityStatusLink",
        through_fields=("data_source", "status"),
        related_name="data_sources",
        blank=True,
        verbose_name="Статусы",
    )

    class Meta:
        verbose_name = "Источник данных"
        verbose_name_plural = "Источники данных"
        ordering = ("name",)
        indexes = [
            models.Index(fields=["inn"]),
            models.Index(fields=["name"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["inn", "name"], name="uniq_data_source_inn_name"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.inn})"


class Contact(TimeAuditModel):
    organization = models.ForeignKey(
        Ori,
        on_delete=models.CASCADE,
        related_name="contacts",
        verbose_name="ОРИ",
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
    data_source = models.ForeignKey(
        "DataSource",
        on_delete=models.CASCADE,
        related_name="contacts",
        verbose_name="Источник данных",
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
            models.Index(fields=["data_source", "first_name"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(organization__isnull=False, telecom_operator__isnull=True, data_source__isnull=True)
                    | models.Q(organization__isnull=True, telecom_operator__isnull=False, data_source__isnull=True)
                    | models.Q(organization__isnull=True, telecom_operator__isnull=True, data_source__isnull=False)
                ),
                name="contact_org_xor_operator",
            ),
        ]

    def __str__(self) -> str:
        return self.first_name or f"Контакт #{self.pk}"


class Psi(TimeAuditModel):
    organization = models.ForeignKey(
        Ori,
        on_delete=models.CASCADE,
        related_name="psis",
        verbose_name="ОРИ",
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
            order = self.license_order
            if order.telecom_network_id:
                return f"ПСИ {order.telecom_network.name} (приказ)"
            if order.telecom_operator_id:
                return f"ПСИ {order.telecom_operator.name} (приказ)"
            return f"ПСИ (приказ #{order.pk})"
        return f"ПСИ #{self.pk}"


class Comment(TimeAuditModel):
    organization = models.ForeignKey(
        Ori,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="ОРИ",
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
    data_source = models.ForeignKey(
        "DataSource",
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Источник данных",
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
                    models.Q(organization__isnull=False, telecom_operator__isnull=True, data_source__isnull=True)
                    | models.Q(organization__isnull=True, telecom_operator__isnull=False, data_source__isnull=True)
                    | models.Q(organization__isnull=True, telecom_operator__isnull=True, data_source__isnull=False)
                ),
                name="comment_single_scope",
            ),
        ]

    def __str__(self) -> str:
        if self.organization_id:
            return f"Комментарий {self.organization.name}"
        if self.data_source_id:
            return f"Комментарий {self.data_source.name}"
        return f"Комментарий {self.telecom_operator.name}"


class Event(TimeAuditModel):
    organization = models.ForeignKey(
        Ori,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="ОРИ",
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


class TelecomLicenseStatus(models.TextChoices):
    ACTIVE = "active", "Действующая"
    INACTIVE = "inactive", "Недействующая"


class LicenseOrderNumber(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Номер приказа"
        verbose_name_plural = "Номера приказов"


class TelecomNetworkName(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "Наименование сети связи"
        verbose_name_plural = "Наименования сетей связи"


class TelecomOperator(TimeAuditModel):
    icon = models.ImageField(upload_to="telecom_operators/icons/", null=True, blank=True, verbose_name="Иконка")
    name = models.CharField(max_length=500, verbose_name="Наименование организации")
    is_archived = models.BooleanField(default=False, verbose_name="Архив")
    inn = models.CharField(
        max_length=12,
        db_index=True,
        validators=[MinLengthValidator(10)],
        verbose_name="ИНН",
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
    statuses = models.ManyToManyField(
        "EntityStatus",
        through="EntityStatusLink",
        through_fields=("telecom_operator", "status"),
        related_name="telecom_operators",
        blank=True,
        verbose_name="Статусы",
    )

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


class TelecomNetwork(TimeAuditModel):
    name = models.ForeignKey(
        TelecomNetworkName,
        on_delete=models.PROTECT,
        related_name="networks",
        verbose_name="Наименование",
    )
    telecom_operator = models.ForeignKey(
        TelecomOperator,
        on_delete=models.CASCADE,
        related_name="networks",
        verbose_name="Оператор связи",
    )
    comment = models.TextField(blank=True, verbose_name="Комментарий")

    class Meta:
        verbose_name = "Сеть связи"
        verbose_name_plural = "Сети связи"
        ordering = ("telecom_operator", "name__name")

    def __str__(self) -> str:
        return str(self.name)


class EntityStatus(models.Model):
    text = models.CharField(max_length=500, verbose_name="Текст")
    kind = models.CharField(
        max_length=16,
        choices=EntityStatusKind.choices,
        default=EntityStatusKind.STATUS,
        verbose_name="Тип",
    )

    class Meta:
        verbose_name = "Статус"
        verbose_name_plural = "Статусы"
        ordering = ("kind", "text")

    def __str__(self) -> str:
        return self.text


class EntityStatusLink(models.Model):
    status = models.ForeignKey(
        EntityStatus,
        on_delete=models.CASCADE,
        related_name="links",
        verbose_name="Статус",
    )
    organization = models.ForeignKey(
        Ori,
        on_delete=models.CASCADE,
        related_name="status_links",
        verbose_name="ОРИ",
        null=True,
        blank=True,
    )
    telecom_operator = models.ForeignKey(
        TelecomOperator,
        on_delete=models.CASCADE,
        related_name="status_links",
        verbose_name="Оператор связи",
        null=True,
        blank=True,
    )
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="status_links",
        verbose_name="Источник данных",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Привязка статуса"
        verbose_name_plural = "Привязки статусов"
        ordering = ("status", "pk")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(organization__isnull=False, telecom_operator__isnull=True, data_source__isnull=True)
                    | models.Q(organization__isnull=True, telecom_operator__isnull=False, data_source__isnull=True)
                    | models.Q(organization__isnull=True, telecom_operator__isnull=True, data_source__isnull=False)
                ),
                name="entity_status_link_single_scope",
            ),
            models.UniqueConstraint(
                fields=("status", "organization"),
                condition=models.Q(organization__isnull=False),
                name="uniq_entity_status_org",
            ),
            models.UniqueConstraint(
                fields=("status", "telecom_operator"),
                condition=models.Q(telecom_operator__isnull=False),
                name="uniq_entity_status_telecom",
            ),
            models.UniqueConstraint(
                fields=("status", "data_source"),
                condition=models.Q(data_source__isnull=False),
                name="uniq_entity_status_data_source",
            ),
        ]

    @property
    def entity(self):
        if self.organization_id:
            return self.organization
        if self.telecom_operator_id:
            return self.telecom_operator
        if self.data_source_id:
            return self.data_source
        return None

    def __str__(self) -> str:
        entity = self.entity
        if entity is not None:
            return f"{self.status} → {entity}"
        return str(self.status)


class TelecomOperatorLicense(TimeAuditModel):
    telecom_operator = models.ForeignKey(
        TelecomOperator,
        on_delete=models.CASCADE,
        related_name="licenses",
        verbose_name="Оператор связи",
    )
    telecom_network = models.ForeignKey(
        TelecomNetwork,
        on_delete=models.SET_NULL,
        related_name="licenses",
        verbose_name="Сеть связи",
        null=True,
        blank=True,
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
    telecom_operator = models.ForeignKey(
        TelecomOperator,
        on_delete=models.CASCADE,
        related_name="license_orders",
        verbose_name="Оператор связи",
        null=True,
        blank=True,
    )
    telecom_network = models.ForeignKey(
        TelecomNetwork,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="Сеть связи",
        null=True,
        blank=True,
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
        ordering = ("telecom_network", "pk")

    def __str__(self) -> str:
        if self.telecom_network_id:
            return f"{self.order_number} — {self.telecom_network.name}"
        if self.telecom_operator_id:
            return f"{self.order_number} — {self.telecom_operator.name}"
        return str(self.order_number)


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


class OrgActionStatus(models.TextChoices):
    PLANNED = "planned", "Запланировано"
    DONE = "done", "Готово"
    OVERDUE = "overdue", "Просрочено"


class OrgAction(TimeAuditModel):
    organization = models.ForeignKey(
        Ori,
        on_delete=models.CASCADE,
        related_name="org_actions",
        verbose_name="ОРИ",
        null=True,
        blank=True,
    )
    telecom_operator = models.ForeignKey(
        "TelecomOperator",
        on_delete=models.CASCADE,
        related_name="org_actions",
        verbose_name="Оператор связи",
        null=True,
        blank=True,
    )
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="org_actions",
        verbose_name="Источник данных",
        null=True,
        blank=True,
    )
    task = models.CharField(max_length=500, verbose_name="Задача")
    status = models.CharField(
        max_length=16,
        choices=OrgActionStatus.choices,
        default=OrgActionStatus.PLANNED,
        verbose_name="Статус",
    )
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    deadline = models.DateField(null=True, blank=True, verbose_name="Срок")
    result = models.TextField(blank=True, verbose_name="Результат")

    class Meta:
        verbose_name = "Действие"
        verbose_name_plural = "Действия"
        ordering = ("deadline", "pk")
        indexes = [
            models.Index(fields=["organization", "deadline"]),
            models.Index(fields=["telecom_operator", "deadline"]),
            models.Index(fields=["data_source", "deadline"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(organization__isnull=False, telecom_operator__isnull=True, data_source__isnull=True)
                    | models.Q(organization__isnull=True, telecom_operator__isnull=False, data_source__isnull=True)
                    | models.Q(organization__isnull=True, telecom_operator__isnull=True, data_source__isnull=False)
                ),
                name="org_action_single_scope",
            ),
        ]

    def save(self, *args, **kwargs):
        if (
            self.deadline
            and self.deadline < timezone.localdate()
            and self.status == OrgActionStatus.PLANNED
        ):
            self.status = OrgActionStatus.OVERDUE
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        if self.organization_id:
            return f"{self.task} ({self.organization.name})"
        if self.data_source_id:
            return f"{self.task} ({self.data_source.name})"
        if self.telecom_operator_id:
            return f"{self.task} ({self.telecom_operator.name})"
        return self.task


class ActionTemplate(TimeAuditModel):
    name = models.CharField(max_length=255, unique=True, verbose_name="Название")
    items = models.JSONField(default=list, verbose_name="Действия")

    class Meta:
        verbose_name = "Шаблон действий"
        verbose_name_plural = "Шаблоны действий"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    @property
    def items_count(self) -> int:
        return len(self.items) if isinstance(self.items, list) else 0


class AppSettings(models.Model):
    SINGLETON_PK = 1

    responsibility_region = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Регион ответственности",
    )

    class Meta:
        verbose_name = "Настройки приложения"
        verbose_name_plural = "Настройки приложения"

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return

    @classmethod
    def load(cls) -> "AppSettings":
        settings, _ = cls.objects.get_or_create(
            pk=cls.SINGLETON_PK,
            defaults={"responsibility_region": "Краснодарский край"},
        )
        return settings

    def __str__(self) -> str:
        return "Настройки приложения"

