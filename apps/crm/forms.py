from django import forms
from django.contrib.auth import get_user_model

from apps.crm.favicon_fetch import maybe_assign_favicon_from_sites
from apps.crm.models import (
    AppSettings,
    DataSource,
    Ori,
    TelecomOperator,
    TelecomOperatorLicense,
    TelecomNetwork,
    TelecomNetworkName,
    LicenseOrder,
    LicenseOrderNumber,
    OrmVendor,
    OrgAction,
    Psi,
    PsiWorkflowStatus,
)


class OriForm(forms.ModelForm):
    responsible_person = forms.ModelChoiceField(
        label="Ответственное лицо",
        required=False,
        queryset=get_user_model().objects.none(),
        widget=forms.Select(
            attrs={
                "class": "panel-input panel-select",
                "data-searchable": "true",
                "data-search-placeholder": "Поиск пользователя...",
            }
        ),
    )
    sites_text = forms.CharField(
        label="Сайты",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "panel-input panel-textarea",
                "rows": 4,
                "placeholder": "https://example.ru\nhttps://example.org",
            }
        ),
        help_text="Укажите по одному URL на строку.",
    )

    class Meta:
        model = Ori
        fields = [
            "icon",
            "name",
            "inn",
            "case_number",
            "responsible_person",
            "outsourcing",
            "in_registry",
            "sites_text",
            "correspondence_address",
            "industry",
            "orm_vendor",
            "sorm_owner",
        ]
        widgets = {
            "icon": forms.ClearableFileInput(attrs={"class": "panel-file-input"}),
            "name": forms.TextInput(attrs={"class": "panel-input"}),
            "inn": forms.TextInput(attrs={"class": "panel-input", "maxlength": 12}),
            "case_number": forms.TextInput(attrs={"class": "panel-input"}),
            "outsourcing": forms.CheckboxInput(attrs={"class": "panel-checkbox"}),
            "in_registry": forms.TextInput(attrs={"class": "panel-input"}),
            "correspondence_address": forms.Textarea(attrs={"class": "panel-input panel-textarea", "rows": 4}),
            "industry": forms.Select(attrs={"class": "panel-input"}),
            "orm_vendor": forms.Select(attrs={"class": "panel-input"}),
            "sorm_owner": forms.Select(
                attrs={
                    "class": "panel-input panel-select",
                    "data-searchable": "true",
                    "data-search-placeholder": "Поиск владельца СОРМ...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user_model = get_user_model()
        users = user_model.objects.all().order_by("first_name", "last_name", "username")
        self.fields["responsible_person"].queryset = users
        self.fields["responsible_person"].label_from_instance = self._user_label

        self.fields["sorm_owner"].queryset = Ori.objects.order_by("name")
        if self.instance and self.instance.pk:
            self.fields["sorm_owner"].queryset = self.fields["sorm_owner"].queryset.exclude(pk=self.instance.pk)

        if self.instance and self.instance.pk:
            self.fields["sites_text"].initial = "\n".join(self.instance.sites or [])

        if self.instance and self.instance.pk and self.instance.outsourcing:
            self.fields["sorm_owner"].disabled = True

    def clean_sites_text(self):
        value = self.cleaned_data.get("sites_text", "")
        return [line.strip() for line in value.splitlines() if line.strip()]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("outsourcing"):
            cleaned["sorm_owner"] = None
        return cleaned

    @staticmethod
    def _user_label(user):
        full_name = user.get_full_name().strip()
        return f"{full_name} ({user.username})" if full_name else user.username

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.sites = self.cleaned_data.get("sites_text", [])
        if self.cleaned_data.get("outsourcing"):
            instance.sorm_owner = None
        if commit:
            instance.save()
            self.save_m2m()
            maybe_assign_favicon_from_sites(instance)
        return instance


class DataSourceForm(forms.ModelForm):
    responsible_person = forms.ModelChoiceField(
        label="Ответственное лицо",
        required=False,
        queryset=get_user_model().objects.none(),
        widget=forms.Select(
            attrs={
                "class": "panel-input panel-select",
                "data-searchable": "true",
                "data-search-placeholder": "Поиск пользователя...",
            }
        ),
    )
    sites_text = forms.CharField(
        label="Сайты",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "panel-input panel-textarea",
                "rows": 4,
                "placeholder": "https://example.ru\nhttps://example.org",
            }
        ),
        help_text="Укажите по одному URL на строку.",
    )

    class Meta:
        model = DataSource
        fields = [
            "icon",
            "name",
            "inn",
            "case_number",
            "responsible_person",
            "sites_text",
            "correspondence_address",
            "industry",
        ]
        widgets = {
            "icon": forms.ClearableFileInput(attrs={"class": "panel-file-input"}),
            "name": forms.TextInput(attrs={"class": "panel-input"}),
            "inn": forms.TextInput(attrs={"class": "panel-input", "maxlength": 12}),
            "case_number": forms.TextInput(attrs={"class": "panel-input"}),
            "correspondence_address": forms.Textarea(attrs={"class": "panel-input panel-textarea", "rows": 4}),
            "industry": forms.Select(attrs={"class": "panel-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user_model = get_user_model()
        users = user_model.objects.all().order_by("first_name", "last_name", "username")
        self.fields["responsible_person"].queryset = users
        self.fields["responsible_person"].label_from_instance = OriForm._user_label
        if self.instance and self.instance.pk:
            self.fields["sites_text"].initial = "\n".join(self.instance.sites or [])

    def clean_sites_text(self):
        value = self.cleaned_data.get("sites_text", "")
        return [line.strip() for line in value.splitlines() if line.strip()]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.sites = self.cleaned_data.get("sites_text", [])
        if commit:
            instance.save()
            self.save_m2m()
            maybe_assign_favicon_from_sites(instance)
        return instance


class TelecomOperatorForm(forms.ModelForm):
    responsible_person = forms.ModelChoiceField(
        label="Ответственное лицо",
        required=False,
        queryset=get_user_model().objects.none(),
        widget=forms.Select(
            attrs={
                "class": "panel-input panel-select",
                "data-searchable": "true",
                "data-search-placeholder": "Поиск пользователя...",
            }
        ),
    )
    sites_text = forms.CharField(
        label="Сайты",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "panel-input panel-textarea",
                "rows": 4,
                "placeholder": "https://example.ru\nhttps://example.org",
            }
        ),
        help_text="Укажите по одному URL на строку.",
    )

    class Meta:
        model = TelecomOperator
        fields = [
            "icon",
            "name",
            "inn",
            "case_number",
            "responsible_person",
            "sites_text",
            "correspondence_address",
        ]
        widgets = {
            "icon": forms.ClearableFileInput(attrs={"class": "panel-file-input"}),
            "name": forms.TextInput(attrs={"class": "panel-input"}),
            "inn": forms.TextInput(attrs={"class": "panel-input", "maxlength": 12}),
            "case_number": forms.TextInput(attrs={"class": "panel-input"}),
            "correspondence_address": forms.Textarea(attrs={"class": "panel-input panel-textarea", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user_model = get_user_model()
        users = user_model.objects.all().order_by("first_name", "last_name", "username")
        self.fields["responsible_person"].queryset = users
        self.fields["responsible_person"].label_from_instance = OriForm._user_label
        if self.instance and self.instance.pk:
            self.fields["sites_text"].initial = "\n".join(self.instance.sites or [])

    def clean_sites_text(self):
        value = self.cleaned_data.get("sites_text", "")
        return [line.strip() for line in value.splitlines() if line.strip()]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.sites = self.cleaned_data.get("sites_text", [])
        if commit:
            instance.save()
            self.save_m2m()
            maybe_assign_favicon_from_sites(instance)
        return instance


class TelecomOperatorLicenseForm(forms.ModelForm):
    class Meta:
        model = TelecomOperatorLicense
        fields = ["telecom_network", "title", "number", "status", "start_date", "end_date", "territory"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "panel-input"}),
            "number": forms.TextInput(attrs={"class": "panel-input"}),
            "status": forms.Select(attrs={"class": "panel-input"}),
            "start_date": forms.DateInput(format="%Y-%m-%d", attrs={"class": "panel-input", "type": "date"}),
            "end_date": forms.DateInput(format="%Y-%m-%d", attrs={"class": "panel-input", "type": "date"}),
            "territory": forms.Textarea(attrs={"class": "panel-input panel-textarea", "rows": 3}),
            "telecom_network": forms.Select(attrs={"class": "panel-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_date"].input_formats = ["%Y-%m-%d"]
        self.fields["end_date"].input_formats = ["%Y-%m-%d"]
        networks = TelecomNetwork.objects.select_related("name").order_by("name__name")
        if self.instance and self.instance.pk and self.instance.telecom_operator_id:
            networks = networks.filter(telecom_operator_id=self.instance.telecom_operator_id)
        self.fields["telecom_network"].queryset = networks
        self.fields["telecom_network"].empty_label = "Не выбрана"


class TelecomNetworkForm(forms.ModelForm):
    class Meta:
        model = TelecomNetwork
        fields = ["name", "comment"]
        labels = {
            "name": "Наименование сети связи",
            "comment": "Комментарий",
        }
        widgets = {
            "name": forms.Select(attrs={"class": "panel-input"}),
            "comment": forms.Textarea(attrs={"class": "panel-input panel-textarea", "rows": 3}),
        }

    def __init__(self, *args, telecom_operator=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.telecom_operator = telecom_operator
        self.fields["name"].queryset = TelecomNetworkName.objects.filter(is_active=True).order_by("name")
        self.fields["name"].required = True


class TelecomNetworkEditForm(forms.ModelForm):
    class Meta:
        model = TelecomNetwork
        fields = ["comment"]
        labels = {
            "comment": "Комментарий",
        }
        widgets = {
            "comment": forms.Textarea(attrs={"class": "panel-input panel-textarea", "rows": 3}),
        }


class PsiAssignmentForm(forms.ModelForm):
    responsible = forms.ModelChoiceField(
        label="Ответственный",
        queryset=get_user_model().objects.none(),
        widget=forms.Select(attrs={"class": "panel-input panel-select"}),
    )

    class Meta:
        model = Psi
        fields = ["responsible", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "panel-input", "type": "date", "autocomplete": "off"},
            ),
            "end_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "panel-input", "type": "date", "autocomplete": "off"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        users = get_user_model().objects.all().order_by("first_name", "last_name", "username")
        self.fields["responsible"].queryset = users
        self.fields["responsible"].label_from_instance = OriForm._user_label
        self.fields["start_date"].input_formats = ["%Y-%m-%d"]
        self.fields["end_date"].input_formats = ["%Y-%m-%d"]

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "Дата окончания не может быть раньше даты начала.")
        return cleaned


class OrgActionCreateForm(forms.ModelForm):
    class Meta:
        model = OrgAction
        fields = ["task", "comment", "deadline"]
        widgets = {
            "task": forms.TextInput(attrs={"class": "panel-input"}),
            "comment": forms.Textarea(attrs={"class": "panel-input panel-textarea", "rows": 3}),
            "deadline": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "panel-input", "type": "date", "autocomplete": "off"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["task"].required = True
        self.fields["deadline"].input_formats = ["%Y-%m-%d"]


class OrgActionEditForm(forms.ModelForm):
    class Meta:
        model = OrgAction
        fields = ["task", "status", "comment", "deadline", "result"]
        widgets = {
            "task": forms.TextInput(attrs={"class": "panel-input"}),
            "status": forms.Select(attrs={"class": "panel-input"}),
            "comment": forms.Textarea(attrs={"class": "panel-input panel-textarea", "rows": 3}),
            "deadline": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "panel-input", "type": "date", "autocomplete": "off"},
            ),
            "result": forms.Textarea(attrs={"class": "panel-input panel-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["task"].required = True
        self.fields["deadline"].input_formats = ["%Y-%m-%d"]


class PsiStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=PsiWorkflowStatus.choices,
        widget=forms.Select(attrs={"class": "panel-input panel-input-compact"}),
    )


class LicenseOrderForm(forms.ModelForm):
    class Meta:
        model = LicenseOrder
        fields = ["order_number", "orm_vendor"]
        widgets = {
            "order_number": forms.Select(attrs={"class": "panel-input"}),
            "orm_vendor": forms.Select(attrs={"class": "panel-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["order_number"].queryset = LicenseOrderNumber.objects.filter(is_active=True).order_by("name")
        self.fields["orm_vendor"].queryset = OrmVendor.objects.filter(is_active=True).order_by("name")


class AppSettingsForm(forms.ModelForm):
    class Meta:
        model = AppSettings
        fields = ["responsibility_region"]
        labels = {
            "responsibility_region": "Регион ответственности",
        }
        widgets = {
            "responsibility_region": forms.TextInput(
                attrs={
                    "class": "panel-input",
                    "placeholder": "Краснодарский край",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsibility_region"].help_text = (
            "Субъект РФ из отчётов РКН, по которому отбираются операторы связи при импорте."
        )
