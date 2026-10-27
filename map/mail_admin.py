from django.views.decorators.debug import sensitive_post_parameters
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .models import MailConfiguration,EmailJob
from .access import can_mail_settings,can_queue
from .mailer import encrypt_password,send_mail,test_credentials
from .services import throttle

def mail_error_message(error):
    from .microsoft_mail import MicrosoftMailError
    from django.core.exceptions import ValidationError
    if isinstance(error,MicrosoftMailError): return str(error)
    if isinstance(error,ValidationError): return ' '.join(error.messages)
    import smtplib,ssl,socket
    if isinstance(error,smtplib.SMTPAuthenticationError): return 'Die SMTP-Anmeldung wurde abgelehnt. Bitte Benutzername und Passwort prüfen.'
    if isinstance(error,ssl.SSLError): return 'Die verschlüsselte Verbindung ist fehlgeschlagen. Bitte Port, TLS-Art und Serverzertifikat prüfen.'
    if isinstance(error,socket.gaierror): return 'Der SMTP-Servername konnte nicht aufgelöst werden. Bitte die Schreibweise prüfen.'
    if isinstance(error,smtplib.SMTPRecipientsRefused): return 'Der Mailserver hat die Empfängeradresse der Testmail abgelehnt.'
    if isinstance(error,smtplib.SMTPSenderRefused): return 'Der Mailserver hat die Absenderadresse abgelehnt. Bitte die Versandberechtigung prüfen.'
    if isinstance(error,(OSError,TimeoutError)): return 'Der SMTP-Server ist nicht erreichbar oder antwortet nicht rechtzeitig. Bitte Host, Port und Firewall prüfen.'
    return 'Die Testmail konnte nicht gesendet werden. Bitte Server, Verschlüsselung und Zugangsdaten prüfen; bei geändertem Anwendungsschlüssel das SMTP-Passwort erneut eintragen.'

class MailConfigurationForm(forms.ModelForm):
    password=forms.CharField(label='Neues SMTP-Passwort',required=False,strip=False,widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}),help_text='Leer lassen, um das gespeicherte Passwort zu behalten. Es wird verschlüsselt gespeichert und nicht wieder angezeigt.')
    clear_password=forms.BooleanField(label='Gespeichertes SMTP-Passwort entfernen',required=False)
    client_secret=forms.CharField(label='Neues Anwendungsgeheimnis (Wert)',required=False,strip=False,widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}),help_text='Den Wert aus Microsoft Entra verwenden, nicht die Geheimnis-ID. Leer lassen, um den gespeicherten Wert zu behalten.')
    clear_client_secret=forms.BooleanField(label='Gespeichertes Anwendungsgeheimnis entfernen',required=False)
    test_recipient=forms.EmailField(label='Empfängeradresse für die Testmail',required=False)
    class Meta:
        model=MailConfiguration
        fields=['enabled','provider','from_email','tenant_id','client_id','client_secret_expires_on','host','port','security','username']
        widgets={'client_secret_expires_on':forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d')}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['enabled'].label='Eigene E-Mail-Einstellungen verwenden'
        self.fields['provider'].required=False;self.fields['port'].required=False;self.fields['security'].required=False
        self.fields['from_email'].label='Absenderpostfach / Absenderadresse'
        self.fields['from_email'].help_text='Für Microsoft 365 die primäre Adresse oder den Benutzeranmeldenamen des freigegebenen Versandpostfachs verwenden.'
        self.order_fields(['enabled','provider','from_email','tenant_id','client_id','client_secret','clear_client_secret','client_secret_expires_on','host','port','security','username','password','clear_password','test_recipient'])
    def clean_port(self):
        value=self.cleaned_data.get('port')
        if self.cleaned_data.get('provider')=='microsoft_graph': return value or 587
        if value is None: return 587
        if not 1<=value<=65535: raise forms.ValidationError('Bitte einen Port zwischen 1 und 65535 eingeben.')
        return value
    def clean(self):
        data=super().clean()
        data['provider']=data.get('provider') or 'smtp'
        data['security']=data.get('security') or 'starttls'
        if data.get('enabled'):
            if not data.get('from_email'): self.add_error('from_email','Bitte das Absenderpostfach eintragen.')
            if data['provider']=='microsoft_graph':
                for name in ['tenant_id','client_id']:
                    if not data.get(name): self.add_error(name,'Bitte die entsprechende ID aus Microsoft Entra eintragen.')
                if not data.get('client_secret') and (data.get('clear_client_secret') or not self.instance.client_secret_encrypted):
                    self.add_error('client_secret','Bitte den Wert eines gültigen Anwendungsgeheimnisses eintragen.')
            else:
                if not data.get('host'): self.add_error('host','Bitte den SMTP-Server eintragen.')
                if data.get('security')=='plain' and data.get('host') not in ['localhost','127.0.0.1','::1','mailpit']:
                    self.add_error('security','Für externe SMTP-Server bitte STARTTLS oder SSL/TLS verwenden.')
        for field,clear in [('password','clear_password'),('client_secret','clear_client_secret')]:
            if data.get(field) and data.get(clear): self.add_error(field,'Bitte entweder einen neuen Wert eintragen oder den bisherigen entfernen.')
        return data
    def save(self,commit=True):
        instance=super().save(commit=False);instance.pk=1
        if self.cleaned_data.get('clear_password'): instance.password_encrypted=''
        elif self.cleaned_data.get('password'): instance.password_encrypted=encrypt_password(self.cleaned_data['password'])
        if self.cleaned_data.get('clear_client_secret'): instance.client_secret_encrypted=''
        elif self.cleaned_data.get('client_secret'): instance.client_secret_encrypted=encrypt_password(self.cleaned_data['client_secret'])
        if commit: instance.save()
        return instance

@login_required
@require_http_methods(['GET','POST'])
@sensitive_post_parameters('password','client_secret')
def mail_settings(request):
    if not can_mail_settings(request.user): raise PermissionDenied
    config=MailConfiguration.objects.filter(pk=1).first() or MailConfiguration(pk=1)
    form=MailConfigurationForm(request.POST if request.method=='POST' else None,instance=config)
    if request.method=='POST' and form.is_valid():
        action=request.POST.get('action','save')
        testing=action in ['check','test']
        if action=='test' and not form.cleaned_data.get('test_recipient'): form.add_error('test_recipient','Bitte eine Empfängeradresse für die Testmail eingeben.')
        elif testing and not throttle('smtp-test:'+str(request.user.pk),limit=5,seconds=300): form.add_error(None,'Zu viele Testversuche. Bitte fünf Minuten warten.')
        else:
            config=form.save()
            if testing:
                try:
                    if action=='check':
                        result=test_credentials(config)
                        messages.info(request,'Einstellungen gespeichert. '+result)
                    else:
                        from .mail_templates import system_content
                        subject,body=system_content('test',{})
                        send_mail(subject,body,settings.DEFAULT_FROM_EMAIL,[form.cleaned_data['test_recipient']],fail_silently=False)
                        messages.success(request,'Die Einstellungen wurden gespeichert. Der Versanddienst hat die Testmail angenommen. Bitte Empfänger- und Spamordner bzw. Mailpit prüfen; die Annahme ist noch keine Zustellbestätigung.')
                except Exception as error:
                    messages.error(request,'Die Einstellungen wurden gespeichert. '+mail_error_message(error))
            else: messages.success(request,'Die E-Mail-Einstellungen wurden gespeichert. Der Worker verwendet sie für den nächsten Versand.')
            return redirect('mail_settings')
    expires=config.client_secret_expires_on
    expiry_days=(expires-timezone.localdate()).days if expires else None
    return render(request,'mail_settings.html',{'form':form,'password_saved':bool(config.password_encrypted),'client_secret_saved':bool(config.client_secret_encrypted),'mailpit_mode':not config.enabled,'expiry_days':expiry_days})


def filtered_jobs(status):
    jobs=EmailJob.objects.all()
    if status=='pending':jobs=jobs.filter(sent_at__isnull=True,attempts__lt=8)
    elif status=='failed':jobs=jobs.filter(sent_at__isnull=True,attempts__gte=8)
    elif status=='sent':jobs=jobs.filter(sent_at__isnull=False)
    return jobs

@login_required
@require_http_methods(['GET','POST'])
def mail_queue(request):
    if not can_queue(request.user): raise PermissionDenied
    from django.db import transaction
    def reject(text):
        from django.urls import reverse
        return render(request,'message.html',{'title':'Aktion nicht ausgeführt','text':text,'return_url':reverse('mail_queue')},status=400)
    status=request.GET.get('status','all')
    if status not in ['all','pending','failed','sent']:status='all'
    if request.method=='POST':
        action=request.POST.get('action','retry')
        if action not in ['retry','delete','delete_filtered']:return reject('Unbekannte Aktion.')
        if not can_queue(request.user,'change' if action=='retry' else 'delete'):raise PermissionDenied
        if action!='retry' and request.POST.get('confirm_delete')!='yes':return reject('Bitte die endgültige Löschung ausdrücklich bestätigen.')
        with transaction.atomic():
            jobs=filtered_jobs(status)
            if action!='delete_filtered':
                ids=request.POST.getlist('job_ids') or [request.POST.get('job_id','')]
                from .security_rules import numeric_pk
                if len(ids)>500 or not ids or any(numeric_pk(value) is None for value in ids):return reject('Bitte gültige E-Mail-Aufträge auswählen.')
                jobs=jobs.filter(pk__in=[int(value) for value in ids])
            locked=list(jobs.select_for_update().values_list('pk',flat=True))
            jobs=EmailJob.objects.filter(pk__in=locked)
            if action=='retry':
                count=jobs.filter(sent_at__isnull=True).update(attempts=0,next_attempt=timezone.now(),last_error='')
                messages.success(request,str(count)+' ausstehende E-Mail-Aufträge wurden zum erneuten Versand freigegeben. Bereits gesendete Nachrichten bleiben unverändert.')
            else:
                count=jobs.count();jobs.delete()
                messages.success(request,str(count)+' E-Mail-Aufträge wurden endgültig gelöscht. Bereits zugestellte Nachrichten wurden nicht zurückgerufen.')
        from django.urls import reverse
        return redirect(reverse('mail_queue')+'?status='+status)
    page=Paginator(filtered_jobs(status).select_related('event').order_by('-pk'),30).get_page(request.GET.get('page'))
    from .admin_language import german_value
    for job in page.object_list:job.error_display=german_value(job,'last_error')
    return render(request,'mail_queue.html',{'page_obj':page,'status_filter':status,'filtered_count':page.paginator.count,
        'can_retry':can_queue(request.user,'change'),'can_delete_jobs':can_queue(request.user,'delete'),
        'pending_count':filtered_jobs('pending').count(),'failed_count':filtered_jobs('failed').count()})
