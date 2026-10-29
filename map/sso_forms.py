from .widgets import QuickDateWidget
import uuid
from django import forms
from django.utils import timezone
from .sso_models import SSOConfiguration, EntraStageMapping
from .models import ScoutGroup


class SSOSettingsForm(forms.ModelForm):
    client_secret = forms.CharField(label='Wert des Anwendungsgeheimnisses', required=False, strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='Leer lassen, um den gespeicherten Wert zu behalten. Niemals die Geheimnis-ID eintragen. Für SSO eine eigene App verwenden; die Mail-App bleibt unverändert.')
    clear_secret = forms.BooleanField(label='Gespeichertes Geheimnis entfernen', required=False)

    class Meta:
        model = SSOConfiguration
        fields = ['enabled', 'tenant_id', 'client_id', 'secret_expires_on', 'notification_email']
        widgets = {'secret_expires_on': QuickDateWidget()}

    def clean(self):
        data = super().clean()
        if data.get('enabled'):
            for name in ['tenant_id', 'client_id', 'notification_email', 'secret_expires_on']:
                if not data.get(name): self.add_error(name, 'Für die aktive Microsoft-Anmeldung erforderlich.')
            if not data.get('client_secret') and (data.get('clear_secret') or not self.instance.client_secret_encrypted):
                self.add_error('client_secret', 'Bitte den Wert des Anwendungsgeheimnisses eintragen.')
            if data.get('secret_expires_on') and data['secret_expires_on'] < timezone.localdate():
                self.add_error('secret_expires_on', 'Das Geheimnis ist bereits abgelaufen.')
        if any(name in self.changed_data for name in ['tenant_id', 'client_id']) and self.instance.client_secret_encrypted and not data.get('client_secret'):
            self.add_error('client_secret', 'Bei einer anderen App oder einem anderen Mandanten das passende Geheimnis neu eintragen.')
        return data

    def save(self, commit=True):
        from .mailer import encrypt_password
        config = super().save(commit=False)
        if self.cleaned_data['clear_secret']: config.client_secret_encrypted = ''
        if self.cleaned_data['client_secret']: config.client_secret_encrypted = encrypt_password(self.cleaned_data['client_secret'])
        config.revision = uuid.uuid4()
        if commit: config.save()
        return config


class MappingForm(forms.ModelForm):
    class Meta:
        model = EntraStageMapping
        fields = ['stage', 'group_id']
        labels = {'stage': 'MAP-Stufe', 'group_id': 'Entra-Gruppen-Objekt-ID'}


MappingFormSet = forms.modelformset_factory(EntraStageMapping, form=MappingForm, extra=2, can_delete=True, max_num=100, validate_max=True)


class ManualIdentityForm(forms.Form):
    approved = forms.BooleanField(label='Zugang manuell freigeben', required=False)
    blocked = forms.BooleanField(label='Microsoft-Zugang sperren', required=False)
    stages = forms.ModelMultipleChoiceField(label='Zusätzliche manuelle Stufen', queryset=ScoutGroup.objects.all(),
        required=False, widget=forms.CheckboxSelectMultiple,
        help_text='Diese Zuordnung bleibt bei Microsoft-Synchronisierungen erhalten. Rollen und Adminrechte werden unter Benutzer verwaltet.')
