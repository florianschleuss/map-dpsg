from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_http_methods
from .models import EmailTemplate
from .access import can_mail_templates
from .email_content import TEMPLATES,PLACEHOLDERS,default_content,effective_content,validate_content,render_content,example_context

def system_content(key,context):
    saved=EmailTemplate.objects.filter(key=key).first()
    subject,body=effective_content(key,saved)
    try:return render_content(subject,body,key,context)
    except ValueError:
        if saved is None:raise
        import logging
        logging.getLogger('map.mail').warning('Invalid stored email template; using default for key %s',key)
        return render_content(*default_content(key),key,context)

class EmailTemplateForm(forms.Form):
    preview_status=forms.ChoiceField(label='Beispielstatus für die Vorschau',required=False,choices=[('', 'Passend zum Anlass'),('pending','E-Mail-Bestätigung ausstehend'),('confirmed','Teilnahme bestätigt'),('waitlisted','Warteliste')],help_text='Nur Beispieldaten für die Vorschau; verändert keine Anmeldung und wird nicht in der Vorlage gespeichert.')
    subject=forms.CharField(label='Betreffvorlage',max_length=200,strip=False)
    body=forms.CharField(label='Nachrichtentext',max_length=20000,strip=False,widget=forms.Textarea(attrs={'rows':15}))
    def __init__(self,*args,key,**kwargs):self.key=key;super().__init__(*args,**kwargs)
    def clean(self):
        data=super().clean()
        if 'subject' in data and 'body' in data:
            try:validate_content(data['subject'],data['body'],self.key)
            except ValueError as error:raise forms.ValidationError(str(error))
        return data

@login_required
@require_http_methods(['GET'])
def email_templates(request):
    if not can_mail_templates(request.user):raise PermissionDenied
    custom={saved.key for saved in EmailTemplate.objects.all() if saved.key in TEMPLATES and effective_content(saved.key,saved)!=default_content(saved.key)}
    from .account_security import technical_admin
    rows=[{'key':key,'title':title,'description':description,'custom':key in custom,'can_edit':key!='password_reset' or technical_admin(request.user)} for key,(title,description) in TEMPLATES.items()]
    return render(request,'email_templates.html',{'templates':rows})

@login_required
@require_http_methods(['GET','POST'])
def email_template_edit(request,key):
    if not can_mail_templates(request.user):raise PermissionDenied
    from .account_security import technical_admin
    if key=='password_reset' and not technical_admin(request.user):raise PermissionDenied
    if key not in TEMPLATES:
        from django.http import Http404
        raise Http404
    saved=EmailTemplate.objects.filter(key=key).first()
    initial=dict(zip(['subject','body'],effective_content(key,saved)))
    form=EmailTemplateForm(request.POST if request.method=='POST' else None,key=key,initial=initial)
    preview=None
    if request.method=='POST' and request.POST.get('action')=='reset':
        if request.POST.get('confirm_reset')!='yes':form.add_error(None,'Bitte das Zurücksetzen auf den Standard ausdrücklich bestätigen.')
        else:
            EmailTemplate.objects.filter(key=key).delete();messages.success(request,'Die Standardvorlage wird wieder verwendet. Vorhandene E-Mail-Aufträge wurden nicht verändert.');return redirect('email_template_edit',key=key)
    elif request.method=='POST' and form.is_valid():
        preview=render_content(form.cleaned_data['subject'],form.cleaned_data['body'],key,example_context(key,form.cleaned_data.get('preview_status') or None) if key!='test' else {})
        if request.POST.get('action')=='save':
            EmailTemplate.objects.update_or_create(key=key,defaults={name:form.cleaned_data[name] for name in ['subject','body']})
            messages.success(request,'Die E-Mail-Vorlage wurde gespeichert. Sie gilt für neu erzeugte Nachrichten; vorhandene Aufträge behalten ihren bisherigen Inhalt.');return redirect('email_template_edit',key=key)
    if preview is None and request.method=='GET':
        try:preview=render_content(initial['subject'],initial['body'],key,example_context(key) if key!='test' else {})
        except ValueError:
            messages.error(request,'Die gespeicherte Vorlage ist ungültig. Beim Versand wird vorübergehend der Standard verwendet. Bitte korrigieren oder ausdrücklich zurücksetzen.')
            preview=render_content(*default_content(key),key,example_context(key) if key!='test' else {})
    return render(request,'email_template_edit.html',{'form':form,'key':key,'template_title':TEMPLATES[key][0],'description':TEMPLATES[key][1],'preview':preview,'placeholders':PLACEHOLDERS.items(),'custom':bool(saved and effective_content(key,saved)!=default_content(key))})
