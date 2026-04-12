from django import forms
from django.contrib.auth import get_user_model

from apps.crm.models import Organization, OrganizationStatus


class OrganizationForm(forms.ModelForm):
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
    statuses = forms.ModelMultipleChoiceField(
        label="Статусы организации",
        required=False,
        queryset=OrganizationStatus.objects.none(),
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
        model = Organization
        fields = [
            "icon",
            "name",
            "inn",
            "organization_type",
            "statuses",
            "interaction_status",
            "case_number",
            "responsible_person",
            "in_registry",
            "registry_record_url",
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
            "organization_type": forms.Select(attrs={"class": "panel-input"}),
            "interaction_status": forms.Select(attrs={"class": "panel-input"}),
            "case_number": forms.TextInput(attrs={"class": "panel-input"}),
            "in_registry": forms.TextInput(attrs={"class": "panel-input"}),
            "registry_record_url": forms.URLInput(attrs={"class": "panel-input"}),
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
        self.fields["statuses"].queryset = OrganizationStatus.objects.filter(is_active=True).order_by("name")

        self.fields["sorm_owner"].queryset = Organization.objects.order_by("name")
        if self.instance and self.instance.pk:
            self.fields["sorm_owner"].queryset = self.fields["sorm_owner"].queryset.exclude(pk=self.instance.pk)

        if self.instance and self.instance.pk:
            self.fields["sites_text"].initial = "\n".join(self.instance.sites or [])

    def clean_sites_text(self):
        value = self.cleaned_data.get("sites_text", "")
        return [line.strip() for line in value.splitlines() if line.strip()]

    @staticmethod
    def _user_label(user):
        full_name = user.get_full_name().strip()
        return f"{full_name} ({user.username})" if full_name else user.username

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.sites = self.cleaned_data.get("sites_text", [])
        if commit:
            instance.save()
            self.save_m2m()
        return instance
