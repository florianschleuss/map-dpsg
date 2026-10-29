"""Independent room reservations with a separate proposed revision."""
from django.conf import settings
from django.db import models
from django.db.models import Q,F

STATUSES=[('pending','Schwebend'),('approved','Genehmigt'),('rejected','Abgelehnt'),('cancelled','Storniert')]


class Room(models.Model):
    active=models.BooleanField('Aktiv',default=True)
    name=models.CharField('Raum',max_length=60,unique=True)
    position=models.PositiveSmallIntegerField(default=0)
    class Meta:ordering=['position','pk']
    def __str__(self):return self.name


class Occupancy(models.Model):
    starts_at=models.DateTimeField('Von')
    ends_at=models.DateTimeField('Bis (exklusiv)')
    recurring=models.BooleanField('Wöchentlich wiederholen',default=False)
    all_day=models.BooleanField('Ganztägig',default=False)
    rooms=models.ManyToManyField(Room,related_name='%(class)s_entries')
    grouping=models.CharField('Gruppierung',max_length=160)
    purpose=models.CharField('Veranstaltung / Zweck',max_length=250)
    class Meta:abstract=True


class RoomBooking(Occupancy):
    creator=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name='room_bookings')
    contact_person=models.CharField('Ansprechperson',max_length=160)
    contact=models.CharField('Kontakt',max_length=500)
    status=models.CharField('Status',max_length=12,choices=STATUSES,default='pending')
    version=models.PositiveIntegerField(default=1)
    decision_reason=models.TextField('Begründung',blank=True,max_length=2000)
    decided_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='+')
    decided_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['starts_at','pk']
        permissions=[('manage_bookings','Alle Raumbuchungen genehmigen und verwalten'),('configure_rooms','Raumbuchungs-Einstellungen und Mailvorlagen verwalten')]
        constraints=[models.CheckConstraint(condition=Q(ends_at__gt=F('starts_at')),name='room_booking_positive_duration')]
        indexes=[models.Index(fields=['status','starts_at','ends_at'])]
    def __str__(self):return self.purpose


class BookingChange(Occupancy):
    booking=models.ForeignKey(RoomBooking,on_delete=models.CASCADE,related_name='changes')
    requested_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name='+')
    status=models.CharField(max_length=12,choices=STATUSES,default='pending')
    decision_reason=models.TextField(blank=True,max_length=2000)
    decided_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='+')
    decided_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-created_at','-pk']
        constraints=[models.UniqueConstraint(fields=['booking'],condition=Q(status='pending'),name='one_pending_room_change'),models.CheckConstraint(condition=Q(ends_at__gt=F('starts_at')),name='room_change_positive_duration')]


class RoomSettings(models.Model):
    defaults_seeded=models.BooleanField(default=False,editable=False)
    public_api_enabled=models.BooleanField('Öffentliche Belegungs-API aktivieren',default=False,help_text='Veröffentlicht Tage, aggregierte Belegungsstatus und die Namen betroffener Räume; keine Veranstaltungs- oder Kontaktdaten.')
    notification_emails=models.TextField('E-Mail-Adressen für Anfragen und Stornierungen',blank=True,
        help_text='Eine Adresse pro Zeile. Diese Empfänger erhalten Informationen zum Genehmigungsworkflow.')
    watchers=models.ManyToManyField(settings.AUTH_USER_MODEL,blank=True,related_name='room_watch_settings',verbose_name='Zusätzlich intern benachrichtigen')


class RoomNotification(models.Model):
    recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='room_notifications')
    booking=models.ForeignKey(RoomBooking,on_delete=models.CASCADE)
    title=models.CharField(max_length=250)
    created_at=models.DateTimeField(auto_now_add=True)
    read_at=models.DateTimeField(null=True,blank=True)
    class Meta:ordering=['-created_at','-pk']


class RoomAudit(models.Model):
    booking=models.ForeignKey(RoomBooking,on_delete=models.CASCADE,related_name='history')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    action=models.CharField(max_length=160)
    before=models.JSONField(default=dict)
    after=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=['-created_at','-pk']


class RoomEmailTemplate(models.Model):
    key=models.SlugField(max_length=40,unique=True)
    subject=models.CharField(max_length=200)
    body=models.TextField(max_length=20000)
