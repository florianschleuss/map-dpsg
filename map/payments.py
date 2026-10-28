from io import BytesIO
from uuid import uuid4
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.http import HttpResponse,Http404
from django.shortcuts import get_object_or_404,render,redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods,require_GET,require_POST
from .models import Event,Registration,PaymentBatch,AuditLog,EmailJob
from .payment_rules import cost_label,payment_visible,epc_payload,transfer_data
from .services import require_permission,resolve_token,token_for,throttle


def payment_details(row):
    event=row.event
    details={'cost':cost_label(event),'cash':event.cost_mode!='free' and event.payment_method=='cash','visible':payment_visible(event,row),'received':bool(row.payment_received_at),'due':event.payment_due,'note':event.payment_note}
    if details['visible']:
        details.update(holder=event.bank_account_holder,iban=event.bank_iban,bic=event.bank_bic,reference=event.title+' - '+row.child_name,
            qr_available=True,qr_url=reverse('payment_qr',args=[token_for(row,'manage')]),amount=event.cost_amount if event.cost_mode=='fixed' else None)
        try:details['reference'],payload=transfer_data(event.title,row.child_name,details['holder'],details['iban'],details['bic'],details['amount'])
        except ValueError:details['qr_available']=False
    return details

def payment_text(row):
    info=payment_details(row)
    if row.event.cost_mode=='free':return 'Kosten: Kostenlos.\n'
    text='Kosten: '+info['cost']+'\n'
    if row.status in ['cancelled','expired']:return text+'Diese Anmeldung ist nicht aktiv. Bitte keine Zahlung veranlassen; bei bereits geleisteter Zahlung die Veranstaltungsleitung kontaktieren.\n'
    if info['received']:return text+'Der Zahlungseingang wurde von der Veranstaltungsleitung bestätigt.\n'
    if info['cash']:
        text+='Bei Teilnahme bitte das Geld bar zur Veranstaltung mitbringen.\n'
    elif info['visible']:
        text+='Bitte überweise den Beitrag an:\nKontoinhaber: '+info['holder']+'\nIBAN: '+info['iban']+'\n'
        if info['bic']:text+='BIC: '+info['bic']+'\n'
        text+='Verwendungszweck: '+info['reference']+'\n'
        if row.event.cost_mode=='custom':text+='Den Betrag bitte entsprechend der Kostenbeschreibung selbst eintragen.\n'
        if info['due']:text+='Zahlbar bis: '+info['due'].strftime('%d.%m.%Y')+'\n'
        text+='Die Bankdaten und der Überweisungs-QR-Code stehen auch in deiner persönlichen Anmeldungsverwaltung.\n'
    elif row.status!='confirmed':text+='Bitte noch nicht überweisen. Zahlungsdaten erscheinen erst nach bestätigter Teilnahme.\n'
    else:text+='Die Zahlungsaufforderung wird später durch die Veranstaltungsleitung verschickt. Bitte noch nicht überweisen.\n'
    # Free-text notes may contain bank details, so keep them behind the same gate.
    if info['note'] and (info['cash'] or info['visible']):text+=info['note']+'\n'
    return text

@require_GET
def payment_qr(request,token):
    try:row=resolve_token(token,'manage')
    except ValidationError:raise Http404 from None
    if not payment_visible(row.event,row):raise PermissionDenied
    info=payment_details(row)
    try:reference,payload=transfer_data(row.event.title,row.child_name,info['holder'],info['iban'],info['bic'],info['amount'])
    except ValueError:raise Http404('Der Überweisungs-QR-Code konnte nicht erstellt werden. Bitte die Bankdaten in der Anmeldungsverwaltung verwenden.') from None
    import qrcode
    from qrcode.image.pure import PyPNGImage
    code=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=8,border=4)
    code.add_data(payload);code.make(fit=True)
    if code.version>13:raise Http404
    output=BytesIO();code.make_image(image_factory=PyPNGImage).save(output)
    response=HttpResponse(output.getvalue(),content_type='image/png');response['Content-Disposition']='inline; filename="ueberweisung.png"'
    return response

@login_required
@require_http_methods(['GET','POST'])
def request_payments(request,pk):
    event=get_object_or_404(Event,pk=pk);require_permission(request.user,event,True)
    if event.cost_mode=='free' or event.payment_method not in ['transfer','reminder']:raise PermissionDenied('Für diese Veranstaltung ist keine Zahlungsaufforderung per Überweisung vorgesehen.')
    if request.method=='POST':
        if request.POST.get('confirm_send')!='yes':
            messages.error(request,'Bitte den Versand der Zahlungsaufforderungen ausdrücklich bestätigen.');return redirect('request_payments',pk=pk)
        try:data=signing.loads(request.POST.get('batch_token',''),salt='map-payment-batch',max_age=3600)
        except (signing.BadSignature,TypeError):
            messages.error(request,'Die Versandbestätigung ist abgelaufen oder ungültig. Bitte erneut prüfen.');return redirect('request_payments',pk=pk)
        if data.get('event')!=pk:raise PermissionDenied
        with transaction.atomic():
            event=Event.objects.select_for_update().get(pk=pk);require_permission(request.user,event,True)
            if event.cost_mode=='free' or event.payment_method not in ['transfer','reminder']:raise PermissionDenied
            if PaymentBatch.objects.filter(nonce=data['nonce']).exists():
                messages.info(request,'Diese Zahlungsaufforderung wurde bereits ausgelöst. Es wurden keine doppelten Nachrichten erzeugt.');return redirect('event_admin',pk=pk)
            if not throttle('payment-batch:'+str(pk)+':'+str(request.user.pk),limit=3,seconds=600):
                messages.error(request,'Zu viele Zahlungsaufforderungen. Bitte zehn Minuten warten.');return redirect('request_payments',pk=pk)
            rows=list(event.registrations.filter(status='confirmed',payment_received_at__isnull=True).select_related('event','event_group__group'))
            if not rows:
                messages.info(request,'Es gibt keine bestätigten, noch offenen Anmeldungen. Es wurde nichts versendet.');return redirect('event_admin',pk=pk)
            event.full_clean()
            event.payment_released_at=event.payment_released_at or timezone.now();event.save(update_fields=['payment_released_at'])
            from .mail_templates import system_content
            from .services import registration_message_context
            batch=PaymentBatch.objects.create(event=event,nonce=data['nonce'],created_by=request.user)
            for row in rows:
                row.event=event
                subject,body=system_content('payment_request',registration_message_context(row,'Zahlungsaufforderung'))
                EmailJob.objects.create(template_scope='map',template_key='payment_request',event=event,registration=row,payment_request=True,payment_fingerprint=payment_fingerprint(event),recipient=row.email,subject=subject,body=body,next_attempt=timezone.now())
            batch.recipient_count=len(rows);batch.save(update_fields=['recipient_count'])
            AuditLog.objects.create(actor=request.user,event=event,action='Zahlungsaufforderung an '+str(len(rows))+' bestätigte Anmeldungen erzeugt')
        messages.success(request,str(len(rows))+' Zahlungsaufforderungen wurden in die E-Mail-Warteschlange gestellt. Warteliste, unbestätigte und als bezahlt markierte Anmeldungen wurden ausgelassen.')
        return redirect('event_admin',pk=pk)
    eligible=event.registrations.filter(status='confirmed',payment_received_at__isnull=True).count()
    token=signing.dumps({'event':pk,'nonce':str(uuid4())},salt='map-payment-batch')
    return render(request,'request_payments.html',{'event':event,'eligible_count':eligible,'batch_token':token,'cost_label':cost_label(event)})

@login_required
@require_POST
def record_payment(request,pk):
    initial=get_object_or_404(Registration,pk=pk)
    with transaction.atomic():
        event=Event.objects.select_for_update().get(pk=initial.event_id);require_permission(request.user,event,True)
        row=Registration.objects.select_for_update().get(pk=pk)
        if event.cost_mode=='free' or row.status!='confirmed':raise PermissionDenied
        action=request.POST.get('action')
        if action not in ['received','undo']:raise PermissionDenied
        row.payment_received_at=timezone.now() if action=='received' else None
        row.payment_received_by=request.user if action=='received' else None
        row.save(update_fields=['payment_received_at','payment_received_by'])
        AuditLog.objects.create(actor=request.user,event=event,action=('Zahlungseingang bestätigt: ' if action=='received' else 'Zahlungsmarkierung aufgehoben: ')+str(row.pk))
    messages.success(request,'Der manuelle Zahlungsstatus wurde gespeichert. MAP hat keine Bankbuchung geprüft.')
    return redirect('event_admin',pk=event.pk)


def payment_fingerprint(event):
    import hashlib,json
    from .payment_rules import COST_FIELDS
    values={name:str(getattr(event,name) or '') for name in COST_FIELDS}
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()

def payment_job_is_current(job):
    if not job.registration_id:return not job.payment_request and not job.payment_fingerprint
    row=job.registration
    if job.payment_request or job.payment_fingerprint:
        if row.status!='confirmed' or row.payment_received_at is not None or not payment_visible(row.event,row):return False
        if job.payment_fingerprint!=payment_fingerprint(row.event):return False
    return True
