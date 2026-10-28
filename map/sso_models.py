"""Tenant-bound Microsoft identities; automatic grants never modify manual roles."""
import uuid
from django.conf import settings
from django.db import models


class SSOConfiguration(models.Model):
    enabled = models.BooleanField('Microsoft-Anmeldung aktivieren', default=False)
    tenant_id = models.UUIDField('Mandanten-ID (Tenant-ID)', null=True, blank=True)
    client_id = models.UUIDField('Anwendungs-ID (Client-ID)', null=True, blank=True)
    client_secret_encrypted = models.TextField(blank=True, editable=False)
    secret_expires_on = models.DateField('Ablaufdatum des Geheimnisses', null=True, blank=True)
    notification_email = models.EmailField('E-Mail für neue Freigabeanfragen', blank=True)
    revision = models.UUIDField(default=uuid.uuid4, editable=False)
    updated_at = models.DateTimeField(auto_now=True)


class EntraStageMapping(models.Model):
    group_id = models.UUIDField('Entra-Gruppen-Objekt-ID')
    stage = models.ForeignKey('map.ScoutGroup', on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['group_id', 'stage'], name='unique_entra_stage_mapping')]


class EntraIdentity(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='entra_identity')
    tenant_id = models.UUIDField()
    object_id = models.UUIDField()
    approved = models.BooleanField('Manuell freigegeben', default=False)
    blocked = models.BooleanField('Microsoft-Zugang gesperrt', default=False)
    automatic_stages = models.ManyToManyField('map.ScoutGroup', blank=True, related_name='entra_leaders')
    group_ids = models.JSONField(default=list, editable=False)
    groups_complete = models.BooleanField(default=False)
    last_login_at = models.DateTimeField(null=True, blank=True)
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant_id', 'object_id'], name='unique_entra_identity')]


class SSOAudit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
