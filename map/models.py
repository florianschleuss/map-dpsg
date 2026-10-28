import secrets
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

def new_token(): return secrets.token_urlsafe(32)

class ScoutGroup(models.Model):
    name = models.CharField('Gruppenname', max_length=160)
    description = models.TextField('Beschreibung', blank=True)
    def __str__(self): return self.name
    class Meta:
        verbose_name = 'Stufe'
        verbose_name_plural = 'Stufen'

class FormTemplate(models.Model):
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='created_form_templates',editable=False,verbose_name='Angelegt von')
    name = models.CharField('Vorlagenname', max_length=160)
    def __str__(self): return self.name
    class Meta:
        verbose_name = 'Formularvorlage'
        verbose_name_plural = 'Formularvorlagen'

class FormModule(models.Model):
    template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField('Modulüberschrift', max_length=160)
    position = models.PositiveIntegerField('Reihenfolge', default=0)
    def __str__(self): return self.title
    class Meta:
        ordering = ['position', 'pk']
        verbose_name = 'Formularmodul'
        verbose_name_plural = 'Formularmodule'

class FormField(models.Model):
    module = models.ForeignKey(FormModule, on_delete=models.CASCADE, related_name='fields', verbose_name='Modul')
    key = models.SlugField('Eindeutiger Schlüssel', max_length=50)
    label = models.CharField('Beschriftung', max_length=200)
    kind = models.CharField('Feldtyp', max_length=12, choices=[('text', 'Text'), ('textarea', 'Mehrzeiliger Text'), ('email', 'E-Mail'), ('integer', 'Ganzzahl'), ('date', 'Datum'), ('checkbox', 'Kontrollkästchen'), ('select', 'Auswahl')])
    required = models.BooleanField('Pflichtfeld', default=False)
    choices = models.TextField('Auswahlwerte (ein Wert pro Zeile)', blank=True)
    help_text = models.CharField('Hilfetext', max_length=300, blank=True)
    position = models.PositiveIntegerField('Reihenfolge', default=0)
    def clean(self):
        import re
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,49}', self.key): raise ValidationError('Schlüssel: a-z, 0-9, _; Beginn mit Buchstabe.')
        if self.module_id and FormField.objects.filter(module__template_id=self.module.template_id, key=self.key).exclude(pk=self.pk).exists():
            raise ValidationError('Schlüssel muss innerhalb der Vorlage eindeutig sein.')
        values = self.choices.splitlines()
        if self.kind == 'select' and (not values or any(not x.strip() for x in values) or len(set(values)) != len(values)):
            raise ValidationError('Bitte eindeutige, nicht leere Auswahlwerte eingeben.')
    class Meta:
        ordering = ['position', 'pk']
        constraints = [models.UniqueConstraint(fields=['module', 'key'], name='unique_module_field')]
        verbose_name = 'Formularfeld'
        verbose_name_plural = 'Formularfelder'

    def __str__(self): return self.label

class Event(models.Model):
    cost_mode=models.CharField('Kostenart',max_length=10,choices=[('free','Kostenlos'),('fixed','Fester Betrag pro Person'),('custom','Kosten als Freitext')],default='free')
    cost_amount=models.DecimalField('Beitrag pro Person in Euro',max_digits=8,decimal_places=2,null=True,blank=True)
    cost_text=models.TextField('Kostenbeschreibung',blank=True,max_length=2000)
    costs_configured=models.BooleanField(default=False,editable=False)
    payment_method=models.CharField('Bezahlungsvorgang',max_length=10,choices=[('none','Keine Zahlung'),('cash','Bargeld zur Veranstaltung mitbringen'),('transfer','Überweisung nach bestätigter Anmeldung'),('reminder','Zahlungsaufforderung später per E-Mail')],default='none')
    bank_account_holder=models.CharField('Kontoinhaber',max_length=70,blank=True)
    bank_iban=models.CharField('IBAN',max_length=34,blank=True)
    bank_bic=models.CharField('BIC',max_length=11,blank=True)
    payment_note=models.TextField('Zusätzlicher Zahlungshinweis',max_length=2000,blank=True)
    payment_due=models.DateField('Zahlbar bis',null=True,blank=True)
    payment_released_at=models.DateTimeField(null=True,blank=True,editable=False)
    group = models.ForeignKey(ScoutGroup, on_delete=models.PROTECT, verbose_name='Gruppe')
    groups = models.ManyToManyField(ScoutGroup, through='EventGroup', related_name='participating_events', verbose_name='Gruppen')
    title = models.CharField('Titel', max_length=200)
    slug = models.SlugField('URL-Kürzel', unique=True)
    description = models.TextField('Beschreibung', blank=True)
    starts_at = models.DateTimeField('Beginn')
    registration_opens = models.DateTimeField('Anmeldung ab')
    registration_closes = models.DateTimeField('Anmeldung bis')
    capacity = models.PositiveIntegerField('Plätze', default=20)
    published = models.BooleanField('Veröffentlicht', default=False)
    waitlist_enabled = models.BooleanField('Warteliste erlauben', default=True)
    capacity_mode = models.CharField('Platzverteilung', max_length=12, choices=[('per_group','Eigene Plätze je Stufe'),('shared','Gemeinsamer Gesamtpool')], default='per_group')
    waitlist_mode = models.CharField('Wartelistenverteilung', max_length=12, choices=[('per_group','Warteliste je Stufe'),('shared','Gemeinsame Warteliste')], default='per_group')
    show_availability = models.BooleanField('Verfügbare Plätze in der Anmeldung anzeigen', default=True)
    confirmation_required = models.BooleanField('E-Mail-Bestätigung erforderlich', default=True)
    confirmation_hours = models.PositiveIntegerField('Bestätigungsfrist (Stunden)', default=48)
    form_template = models.ForeignKey(FormTemplate, on_delete=models.PROTECT, verbose_name='Formularvorlage')
    privacy_text = models.TextField('Datenschutzhinweis', blank=True, default='')
    def clean(self):
        from .payment_rules import normalized_costs,FROZEN_FIELDS,COST_FIELDS
        try:
            normalized=normalized_costs({name:getattr(self,name) for name in COST_FIELDS})
        except ValueError as error:raise ValidationError(str(error))
        for name,value in normalized.items():setattr(self,name,value)
        if self.pk:
            previous=type(self).objects.get(pk=self.pk)
            if previous.costs_configured and self.registrations.exists() and any(getattr(previous,name)!=getattr(self,name) for name in FROZEN_FIELDS):
                raise ValidationError('Kostenart, Beitrag und Bezahlungsvorgang können nach der ersten Anmeldung nicht mehr geändert werden. Bankdaten und zusätzliche Hinweise bleiben korrigierbar.')
        if self.registration_opens and self.registration_closes and self.registration_opens >= self.registration_closes:
            raise ValidationError('Das Anmeldeende muss nach dem Anmeldebeginn liegen.')
        if self.confirmation_hours is not None and not 1<=self.confirmation_hours<=8760: raise ValidationError({'confirmation_hours':'Die Bestätigungsfrist muss zwischen 1 und 8760 Stunden liegen.'})
        if self.registration_closes and self.starts_at and self.registration_closes>self.starts_at:
            raise ValidationError({'registration_closes':'Die Anmeldung muss spätestens zum Veranstaltungsbeginn enden.'})
        if self.pk and self.capacity is not None and self.capacity < self.registrations.filter(status__in=['pending', 'confirmed']).count():
            raise ValidationError('Kapazität darf nicht unter die belegten Plätze sinken.')
    @property
    def group_names(self):
        names=[slot.group.name for slot in self.group_slots.all() if slot.enabled]
        return ', '.join(names) if names else str(self.group)
    def __str__(self): return self.title
    class Meta:
        verbose_name = 'Veranstaltung'
        verbose_name_plural = 'Veranstaltungen'

class EventPermission(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, verbose_name='Veranstaltung')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Benutzer')
    role = models.CharField('Rolle', max_length=10, choices=[('viewer', 'Lesen und Export'), ('editor', 'Lesen, Export und Bearbeiten')])
    class Meta:
        constraints = [models.UniqueConstraint(fields=['event', 'user'], name='unique_event_permission')]
        verbose_name = 'Veranstaltungsrecht'
        verbose_name_plural = 'Veranstaltungsrechte'

    def __str__(self): return f'{self.user} – {self.event}: {self.get_role_display()}'

class Registration(models.Model):
    payment_received_at=models.DateTimeField('Zahlungseingang manuell bestätigt',null=True,blank=True)
    payment_received_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='recorded_payments')
    STATUS = [('pending', 'Bestätigung ausstehend'), ('confirmed', 'Bestätigt'), ('waitlisted', 'Warteliste'), ('cancelled', 'Storniert'), ('expired', 'Abgelaufen')]
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='registrations', verbose_name='Veranstaltung')
    event_group = models.ForeignKey('EventGroup', null=True, blank=True, on_delete=models.PROTECT, related_name='registrations', verbose_name='Veranstaltungsgruppe')
    child_name = models.CharField('Name des Kindes', max_length=160)
    email = models.EmailField('E-Mail der erziehungsberechtigten Person')
    identity = models.CharField(max_length=500, editable=False)
    status = models.CharField('Status', max_length=12, choices=STATUS)
    answers = models.JSONField('Antworten', default=dict)
    schema_snapshot = models.JSONField(default=list)
    token_nonce = models.CharField(max_length=64, default=new_token, editable=False)
    email_verified = models.BooleanField(default=False)
    confirmation_deadline = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField('Angemeldet am', auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['event', 'identity'], condition=Q(status__in=['pending', 'confirmed', 'waitlisted']), name='unique_active_registration')]
        ordering = ['created_at', 'pk']
        verbose_name = 'Anmeldung'
        verbose_name_plural = 'Anmeldungen'
    def __str__(self): return f'{self.child_name} – {self.event}'

class EmailJob(models.Model):
    room_booking=models.ForeignKey('rooms.RoomBooking',null=True,blank=True,on_delete=models.CASCADE,related_name='mail_jobs')
    room_change=models.ForeignKey('rooms.BookingChange',null=True,blank=True,on_delete=models.SET_NULL)
    room_expected_status=models.CharField(max_length=12,blank=True)
    room_expected_change_status=models.CharField(max_length=12,blank=True)
    room_expected_version=models.PositiveIntegerField(null=True,blank=True)
    registration=models.ForeignKey(Registration,null=True,blank=True,on_delete=models.CASCADE,related_name='email_jobs',editable=False)
    payment_request=models.BooleanField(default=False,editable=False)
    payment_fingerprint=models.CharField(max_length=64,blank=True,editable=False)
    reset_user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.CASCADE,related_name='password_reset_jobs',editable=False)
    body_encrypted=models.TextField(blank=True,editable=False)
    reset_token_encrypted=models.TextField(blank=True,editable=False)
    event = models.ForeignKey(Event,null=True,blank=True,on_delete=models.CASCADE,related_name='email_jobs',verbose_name='Veranstaltung')
    recipient = models.EmailField('Empfänger')
    subject = models.CharField('Betreff', max_length=250)
    body = models.TextField('Inhalt')
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField('Gesendet', null=True, blank=True)
    attempts = models.PositiveIntegerField('Versuche', default=0)
    next_attempt = models.DateTimeField('Nächster Versuch')
    last_error = models.TextField('Letzter Fehler', blank=True)
    class Meta:
        verbose_name = 'E-Mail-Auftrag'
        verbose_name_plural = 'E-Mail-Warteschlange'

    def __str__(self): return self.subject

class Throttle(models.Model):
    key = models.CharField(max_length=64, unique=True)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)

class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = 'Änderungsprotokoll'
        verbose_name_plural = 'Änderungsprotokoll'

    def __str__(self): return f'Änderung zu {self.event}'


class EventGroup(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='group_slots', verbose_name='Veranstaltung')
    group = models.ForeignKey(ScoutGroup, on_delete=models.PROTECT, related_name='event_slots', verbose_name='Gruppe')
    capacity = models.PositiveIntegerField('Plätze dieser Gruppe', default=20)
    enabled = models.BooleanField('Aktiv', default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['event', 'group'], name='unique_event_group')]
        ordering = ['group__name', 'pk']
        verbose_name = 'Veranstaltungsgruppe'
        verbose_name_plural = 'Veranstaltungsgruppen'
    def __str__(self): return f'{self.group} – {self.event}'


class MailConfiguration(models.Model):
    provider=models.CharField('Versandweg',max_length=20,choices=[('smtp','SMTP mit Benutzername und Passwort'),('microsoft_graph','Microsoft 365 / Exchange Online (OAuth)')],default='smtp')
    tenant_id=models.UUIDField('Mandanten-ID (Tenant-ID)',null=True,blank=True)
    client_id=models.UUIDField('Anwendungs-ID (Client-ID)',null=True,blank=True)
    client_secret_encrypted=models.TextField(blank=True,editable=False)
    client_secret_expires_on=models.DateField('Ablaufdatum des Anwendungsgeheimnisses',null=True,blank=True)
    enabled=models.BooleanField('Eigene SMTP-Einstellungen verwenden',default=False)
    host=models.CharField('SMTP-Server',max_length=250,blank=True)
    port=models.PositiveIntegerField('Port',default=587)
    username=models.CharField('Benutzername',max_length=250,blank=True)
    password_encrypted=models.TextField(blank=True,editable=False)
    security=models.CharField('Verschlüsselung',max_length=12,choices=[('starttls','STARTTLS (meist Port 587)'),('ssl','SSL/TLS (meist Port 465)'),('plain','Unverschlüsselt (nur lokaler Testbetrieb)')],default='starttls')
    from_email=models.EmailField('Absenderadresse',blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name='SMTP-Einstellung'
        verbose_name_plural='SMTP-Einstellungen'


class LeaderProfile(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='leadership',verbose_name='Benutzerkonto')
    is_leader=models.BooleanField('Leitendenstatus',default=False)
    stages=models.ManyToManyField(ScoutGroup,blank=True,related_name='leader_profiles',verbose_name='Zugeordnete Stufen')
    class Meta:
        verbose_name='Leitendenprofil'
        verbose_name_plural='Leitendenprofile'


class StageRole(models.Model):
    stage=models.OneToOneField(ScoutGroup,on_delete=models.CASCADE,related_name='access_role')
    group=models.OneToOneField('auth.Group',on_delete=models.CASCADE,related_name='stage_role')
    class Meta:
        verbose_name='Automatische Stufenrolle'
        verbose_name_plural='Automatische Stufenrollen'

class EmailTemplate(models.Model):
    key=models.SlugField(unique=True,max_length=32)
    subject=models.CharField('Betreffvorlage',max_length=200)
    body=models.TextField('Nachrichtenvorlage')
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name='E-Mail-Vorlage'
        verbose_name_plural='E-Mail-Vorlagen'


class PaymentBatch(models.Model):
    event=models.ForeignKey(Event,on_delete=models.CASCADE,related_name='payment_batches')
    nonce=models.UUIDField(unique=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    created_at=models.DateTimeField(auto_now_add=True)
    recipient_count=models.PositiveIntegerField(default=0)
    class Meta:
        verbose_name='Zahlungsaufforderung'
        verbose_name_plural='Zahlungsaufforderungen'

from .sso_models import SSOConfiguration, EntraStageMapping, EntraIdentity, SSOAudit
