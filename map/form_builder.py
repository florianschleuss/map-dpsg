from .access import can_templates
from django import forms
from django.contrib import admin, messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode
from .models import FormTemplate, AuditLog
from .forms import template_schema
from .form_schema import STANDARD_SCHEMA, persist_schema, validate_builder_schema
from .widgets import BuilderWidget

class SchemaForm(forms.Form):
    name=forms.CharField(label='Name der Formularvorlage',max_length=160)
    schema_json=forms.JSONField(label='Fragen und Bausteine',widget=BuilderWidget,required=False,validators=[validate_builder_schema])
    def clean_schema_json(self): return self.cleaned_data.get('schema_json') or []

@login_required
@require_http_methods(['GET','POST'])
def form_builder(request,pk=None):
    if not can_templates(request.user):
        from .services import permitted
        from .roles import can_create_events
        from .models import Event
        if not pk:
            event=get_object_or_404(Event,pk=request.GET.get('event') if request.GET.get('event','').isdigit() else 0)
            if not can_create_events(request.user) or not permitted(request.user,event,True): raise PermissionDenied
        else:
            candidate=get_object_or_404(FormTemplate,pk=pk)
            linked=list(candidate.event_set.all())
            if linked:
                if not all(permitted(request.user,event,True) for event in linked): raise PermissionDenied
            elif candidate.created_by_id!=request.user.pk or not can_create_events(request.user): raise PermissionDenied
    return_url=request.GET.get('zurueck','')
    if not return_url.startswith('/') or return_url.startswith('//') or not url_has_allowed_host_and_scheme(return_url,{request.get_host()},require_https=request.is_secure()): return_url=''
    if not return_url:
        from django.urls import reverse
        from .roles import is_admin
        from .models import Event
        from .services import permitted
        event=Event.objects.filter(pk=request.GET['event']).first() if request.GET.get('event','').isdigit() else None
        if event and permitted(request.user,event): return_url=reverse('event_admin',args=[event.pk])
        elif not is_admin(request.user): return_url=reverse('dashboard')
    template=get_object_or_404(FormTemplate,pk=pk) if pk else None
    form=SchemaForm(request.POST if request.method=='POST' else None,initial={'name':template.name if template else '', 'schema_json':template_schema(template) if template else STANDARD_SCHEMA})
    from .template_access import available_templates
    form.fields['schema_json'].widget.allowed_template_ids=list(available_templates(request.user).values_list('pk',flat=True))
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            saved=persist_schema(form.cleaned_data['schema_json'],form.cleaned_data['name'],template)
            if template is None:
                saved.created_by=request.user;saved.save(update_fields=['created_by'])
            for event in saved.event_set.all(): AuditLog.objects.create(actor=request.user,event=event,action='Formularvorlage über den Baukasten geändert')
        messages.success(request,'Die Formularvorlage wurde gespeichert. Bereits eingegangene Anmeldungen bleiben unverändert.')
        from django.urls import reverse
        return redirect(reverse('map_form_builder',kwargs={'pk':saved.pk})+('?' + urlencode({**({'zurueck':return_url} if return_url else {}),**({'event':request.GET['event']} if request.GET.get('event','').isdigit() else {})}) if return_url or request.GET.get('event','').isdigit() else ''))
    context=admin.site.each_context(request)
    context.update(title='Formularbaukasten',form=form,template_object=template,return_url=return_url)
    return render(request,'admin/map_form_builder.html',context)


@login_required
@require_http_methods(['GET'])
def template_options(request,pk):
    from django.http import JsonResponse
    from .models import Event
    from .services import require_permission
    event=get_object_or_404(Event,pk=pk)
    require_permission(request.user,event,True)
    from .template_access import available_templates
    return JsonResponse({'templates':list(available_templates(request.user).order_by('name').values('id','name'))})
