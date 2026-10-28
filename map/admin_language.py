from django.contrib import admin
from django.utils import formats, timezone
from django.utils.html import format_html_join
from django.utils.translation import gettext_lazy as _

LABELS={'event_group':'Gruppe','template':'Formularvorlage','module':'Formularmodul','event':'Veranstaltung','user':'Benutzerkonto','actor':'Benutzerkonto','action':'Aktion','identity':'Dublettenkennung','schema_snapshot':'Verwendete Formularfassung','token_nonce':'Interner Linkschlüssel','email_verified':'E-Mail bestätigt','confirmation_deadline':'Bestätigungsfrist','created_at':'Erstellt am','updated_at':'Zuletzt geändert','status':'Status','answers':'Antworten','child_name':'Name des Kindes','email':'E-Mail-Adresse','recipient':'Empfänger','subject':'Betreff','body':'Nachricht','sent_at':'Gesendet am','attempts':'Versuche','next_attempt':'Nächster Versuch','last_error':'Letzter Fehler'}
TYPES={'text':'Text','textarea':'Mehrzeiliger Text','email':'E-Mail','integer':'Ganzzahl','date':'Datum','checkbox':'Kontrollkästchen','select':'Auswahl'}

def label_form(form):
    for key,field in form.base_fields.items():
        if key in LABELS: field.label=LABELS[key]
    return form

class GermanInline(admin.TabularInline):
    def get_formset(self,request,obj=None,**kwargs):
        result=super().get_formset(request,obj,**kwargs)
        label_form(result.form)
        return result

def german_value(obj,key):
    value=getattr(obj,key)
    if key=='event_group': return value.group.name if value else obj.event.group.name
    if key=='status': return obj.get_status_display()
    if isinstance(value,bool): return 'Ja' if value else 'Nein'
    if value is None: return '—'
    if hasattr(value,'utcoffset'):
        if timezone.is_aware(value): value=timezone.localtime(value)
        return formats.date_format(value,'DATETIME_FORMAT')
    if key=='last_error':
        if value.startswith('ms_'):
            from .microsoft_mail import MESSAGES
            return MESSAGES.get(value,'Microsoft-Versandfehler – bitte die E-Mail-Einstellungen prüfen.')
        return {'RoomNotificationObsolete':'Diese Raumbuchungsnachricht ist durch eine spätere Änderung oder Stornierung überholt und wurde nicht versendet.','PaymentRequestObsolete':'Die Zahlungsnachricht ist nicht mehr aktuell, etwa nach Stornierung, Zahlungsmarkierung oder Änderung der Bankdaten. Bitte bei Bedarf eine neue Nachricht erzeugen.','PasswordResetExpired':'Der Passwort-Link ist abgelaufen oder nicht mehr gültig. Bitte in der Benutzerverwaltung einen neuen Link anfordern.','SMTPAuthenticationError':'Anmeldung beim Mailserver fehlgeschlagen','SMTPRecipientsRefused':'Empfänger vom Mailserver abgelehnt','SMTPSenderRefused':'Absender vom Mailserver abgelehnt','SMTPConnectError':'Verbindung zum Mailserver fehlgeschlagen','SMTPServerDisconnected':'Verbindung zum Mailserver unterbrochen','SMTPDataError':'Nachricht vom Mailserver abgelehnt','TimeoutError':'Zeitüberschreitung beim Versand','ConnectionRefusedError':'Verbindung zum Mailserver abgelehnt','OSError':'Verbindungs- oder Systemfehler'}.get(value,'Versandfehler – bitte Serverprotokoll prüfen') if value else 'Kein Fehler'
    if key=='action':
        translations={'edit event settings':'Veranstaltungseinstellungen geändert','export csv':'CSV exportiert'}
        if value in translations: return translations[value]
        for prefix,label in [('edit registration ','Anmeldung bearbeitet: '),('cancel registration ','Anmeldung storniert: ')]:
            if value.startswith(prefix): return label+value[len(prefix):]
        return value
    if key=='answers':
        labels={field['key']:field['label'] for module in obj.schema_snapshot for field in module.get('fields',[])}
        return format_html_join('', '<div><strong>{}</strong>: {}</div>',[(labels.get(k,'Angabe'), 'Ja' if v is True else 'Nein' if v is False else v) for k,v in value.items()]) or 'Keine zusätzlichen Angaben'
    if key=='schema_snapshot':
        return format_html_join('', '<div><strong>{}</strong>: {} ({})</div>',[(module.get('title','Modul'),field.get('label','Feld'),TYPES.get(field.get('type'),'Feld')) for module in value for field in module.get('fields',[])]) or 'Keine zusätzlichen Formularfelder'
    return '—' if value == '' else value

def add_displays(cls,keys):
    for key in keys:
        def display(self,obj,_key=key): return german_value(obj,_key)
        display=admin.display(description=LABELS.get(key,key))(display)
        setattr(cls,'de_'+key,display)
