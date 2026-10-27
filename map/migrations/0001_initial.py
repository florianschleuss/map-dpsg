from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import map.models
from map.models import new_token
class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
migrations.CreateModel(name='ScoutGroup', fields=[
('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
('name', models.CharField('Gruppenname', max_length=160)),
('description', models.TextField('Beschreibung', blank=True))
], options={'verbose_name': 'Gruppe','verbose_name_plural': 'Gruppen'}),
migrations.CreateModel(name='FormTemplate', fields=[
('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
('name', models.CharField('Vorlagenname', max_length=160))
], options={'verbose_name': 'Formularvorlage','verbose_name_plural': 'Formularvorlagen'}),
migrations.CreateModel(name='FormModule', fields=[
('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
('template', models.ForeignKey('map.formtemplate', on_delete=models.CASCADE, related_name='modules')),
('title', models.CharField('Modulüberschrift', max_length=160)),
('position', models.PositiveIntegerField('Reihenfolge', default=0))
], options={'ordering': ['position', 'pk'],'verbose_name': 'Formularmodul','verbose_name_plural': 'Formularmodule'}),
migrations.CreateModel(name='FormField', fields=[
('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
('module', models.ForeignKey('map.formmodule', on_delete=models.CASCADE, related_name='fields', verbose_name='Modul')),
('key', models.SlugField('Eindeutiger Schlüssel', max_length=50)),
('label', models.CharField('Beschriftung', max_length=200)),
('kind', models.CharField('Feldtyp', max_length=12, choices=[('text', 'Text'), ('textarea', 'Mehrzeiliger Text'), ('email', 'E-Mail'), ('integer', 'Ganzzahl'), ('date', 'Datum'), ('checkbox', 'Kontrollkästchen'), ('select', 'Auswahl')])),
('required', models.BooleanField('Pflichtfeld', default=False)),
('choices', models.TextField('Auswahlwerte (ein Wert pro Zeile)', blank=True)),
('help_text', models.CharField('Hilfetext', max_length=300, blank=True)),
('position', models.PositiveIntegerField('Reihenfolge', default=0))
], options={'ordering': ['position', 'pk'],'constraints': [models.UniqueConstraint(fields=['module', 'key'], name='unique_module_field')],'verbose_name': 'Formularfeld','verbose_name_plural': 'Formularfelder'}),
migrations.CreateModel(name='Event', fields=[
('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
('group', models.ForeignKey('map.scoutgroup', on_delete=models.PROTECT, verbose_name='Gruppe')),
('title', models.CharField('Titel', max_length=200)),
('slug', models.SlugField('URL-Kürzel', unique=True)),
('description', models.TextField('Beschreibung', blank=True)),
('starts_at', models.DateTimeField('Beginn')),
('registration_opens', models.DateTimeField('Anmeldung ab')),
('registration_closes', models.DateTimeField('Anmeldung bis')),
('capacity', models.PositiveIntegerField('Plätze', default=20)),
('published', models.BooleanField('Veröffentlicht', default=False)),
('waitlist_enabled', models.BooleanField('Warteliste erlauben', default=True)),
('confirmation_required', models.BooleanField('E-Mail-Bestätigung erforderlich', default=True)),
('confirmation_hours', models.PositiveIntegerField('Bestätigungsfrist (Stunden)', default=48)),
('form_template', models.ForeignKey('map.formtemplate', on_delete=models.PROTECT, verbose_name='Formularvorlage')),
('privacy_text', models.TextField('Datenschutzhinweis', default='Bitte hier den Datenschutzhinweis des Veranstalters eintragen.'))
], options={'verbose_name': 'Veranstaltung','verbose_name_plural': 'Veranstaltungen'}),
migrations.CreateModel(name='EventPermission', fields=[
('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
('event', models.ForeignKey('map.event', on_delete=models.CASCADE, verbose_name='Veranstaltung')),
('user', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Benutzer')),
('role', models.CharField('Rolle', max_length=10, choices=[('viewer', 'Lesen und Export'), ('editor', 'Lesen, Export und Bearbeiten')]))
], options={'constraints': [models.UniqueConstraint(fields=['event', 'user'], name='unique_event_permission')],'verbose_name': 'Veranstaltungsrecht','verbose_name_plural': 'Veranstaltungsrechte'}),
migrations.CreateModel(name='Registration', fields=[
('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
('event', models.ForeignKey('map.event', on_delete=models.PROTECT, related_name='registrations', verbose_name='Veranstaltung')),
('child_name', models.CharField('Name des Kindes', max_length=160)),
('email', models.EmailField('E-Mail der erziehungsberechtigten Person')),
('identity', models.CharField(max_length=500, editable=False)),
('status', models.CharField('Status', max_length=12, choices=[('pending', 'Bestätigung ausstehend'), ('confirmed', 'Bestätigt'), ('waitlisted', 'Warteliste'), ('cancelled', 'Storniert'), ('expired', 'Abgelaufen')])),
('answers', models.JSONField('Antworten', default=dict)),
('schema_snapshot', models.JSONField(default=list)),
('token_nonce', models.CharField(max_length=64, default=new_token, editable=False)),
('email_verified', models.BooleanField(default=False)),
('confirmation_deadline', models.DateTimeField(null=True, blank=True)),
('created_at', models.DateTimeField('Angemeldet am', auto_now_add=True)),
('updated_at', models.DateTimeField(auto_now=True))
], options={'constraints': [models.UniqueConstraint(fields=['event', 'identity'], condition=Q(status__in=['pending', 'confirmed', 'waitlisted']), name='unique_active_registration')],'ordering': ['created_at', 'pk'],'verbose_name': 'Anmeldung','verbose_name_plural': 'Anmeldungen'}),
migrations.CreateModel(name='EmailJob', fields=[
('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
('recipient', models.EmailField('Empfänger')),
('subject', models.CharField('Betreff', max_length=250)),
('body', models.TextField('Inhalt')),
('created_at', models.DateTimeField(auto_now_add=True)),
('sent_at', models.DateTimeField('Gesendet', null=True, blank=True)),
('attempts', models.PositiveIntegerField('Versuche', default=0)),
('next_attempt', models.DateTimeField('Nächster Versuch')),
('last_error', models.TextField('Letzter Fehler', blank=True))
], options={'verbose_name': 'E-Mail-Auftrag','verbose_name_plural': 'E-Mail-Warteschlange'}),
migrations.CreateModel(name='Throttle', fields=[
('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
('key', models.CharField(max_length=64, unique=True)),
('window_start', models.DateTimeField()),
('count', models.PositiveIntegerField(default=0))
], options={}),
migrations.CreateModel(name='AuditLog', fields=[
('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
('actor', models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)),
('event', models.ForeignKey('map.event', on_delete=models.CASCADE)),
('action', models.CharField(max_length=100)),
('created_at', models.DateTimeField(auto_now_add=True))
], options={'verbose_name': 'Änderungsprotokoll','verbose_name_plural': 'Änderungsprotokoll'})
]
