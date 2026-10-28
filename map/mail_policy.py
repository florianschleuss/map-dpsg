"""Delivery switches are independent of editable content and cannot disable essential flows."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import MailTemplatePolicy

PROTECTED={'password_reset','registration','resend','promotion','payment_request','test'}

def protected(scope,key):return scope=='map' and key in PROTECTED

def enabled(scope,key):
    if not scope or not key or protected(scope,key):return True
    return not MailTemplatePolicy.objects.filter(scope=scope,key=key,enabled=False).exists()

def state(scope,key):return {'enabled':enabled(scope,key),'protected':protected(scope,key),'scope':scope}

@login_required
@require_POST
def set_template_state(request,scope,key):
    if scope=='map':
        from .access import can_mail_templates
        from .email_content import TEMPLATES
        if not can_mail_templates(request.user):raise PermissionDenied
        if key not in TEMPLATES:raise Http404
    elif scope=='rooms':
        from rooms.access import can_configure
        from rooms.notifications import EVENTS
        if not can_configure(request.user):raise PermissionDenied
        if key not in EVENTS:raise Http404
    else:raise Http404
    if protected(scope,key):raise PermissionDenied('Diese Nachricht ist für den sicheren Ablauf erforderlich und bleibt aktiviert.')
    value=request.POST.get('enabled')
    if value not in ['0','1']:raise PermissionDenied
    with transaction.atomic():
        row,_=MailTemplatePolicy.objects.get_or_create(scope=scope,key=key)
        row=MailTemplatePolicy.objects.select_for_update().get(pk=row.pk)
        row.enabled=value=='1';row.updated_by=request.user;row.save(update_fields=['enabled','updated_by','updated_at'])
    messages.success(request,'Mailvorlage aktiviert.' if row.enabled else 'Mailvorlage deaktiviert. Neue Nachrichten dieses Typs werden nicht erzeugt; noch nicht versendete Aufträge mit Vorlagenkennung werden beim Versand gestoppt.')
    if scope=='rooms':return redirect('rooms:templates')
    return redirect(reverse('email_templates')+'?section='+('system' if key in ['password_reset','test'] else 'events'))
