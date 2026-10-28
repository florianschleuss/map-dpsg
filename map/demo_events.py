"""One-click Dev fixtures through the same forms and service as the event wizard."""
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from .roles import can_create_events,can_create_any,is_admin,leader_stage_ids


def can_create_dummy(user):
    return not settings.MAP_PRODUCTION and can_create_events(user)


def validated(form):
    if not form.is_valid():raise ValidationError('Die Dummy-Vorlage passt nicht zu den aktuellen Formularregeln: '+form.errors.as_text())
    return form.cleaned_data


@transaction.atomic
def create_dummy_event(actor,nonce):
    if not can_create_dummy(actor):raise PermissionDenied
    from .models import ScoutGroup
    from .setup_forms import BasicsForm,DatesForm,CapacityForm,TemplateForm,AccessForm,group_entries
    from .cost_forms import CostForm
    from .event_wizard import create_event
    from .form_schema import STANDARD_SCHEMA
    groups=ScoutGroup.objects.order_by('pk')
    if not can_create_any(actor):groups=groups.filter(pk__in=leader_stage_ids(actor))
    stage=groups.first()
    if stage is None:
        if not is_admin(actor):raise ValidationError('Bitte zuerst eine Stufe durch die Administration anlegen und zuordnen lassen.')
        stage=ScoutGroup.objects.create(name='Teststufe',description='Für die erste Dummy-Veranstaltung in Dev angelegt.')
    basics=validated(BasicsForm({'title':'[TEST] Dummy-Veranstaltung','description':'Automatisch erzeugte, unveröffentlichte Testveranstaltung. Keine echten Teilnehmendendaten enthalten.','groups':[stage.pk]},actor=actor))
    now=timezone.localtime().replace(second=0,microsecond=0)
    dates=validated(DatesForm({key:value.strftime('%Y-%m-%dT%H:%M') for key,value in {
        'starts_at':now+timedelta(days=30),'registration_opens':now-timedelta(days=1),'registration_closes':now+timedelta(days=20)}.items()}))
    entries=group_entries(basics)
    places=validated(CapacityForm({'capacity_mode':'per_group','capacity':20,'confirmation_required':'on','waitlist_mode':'per_group','show_availability':'on','waitlist_enabled':'on','confirmation_hours':48},entries=entries))
    import json
    template=validated(TemplateForm({'form_template':'','schema_json':json.dumps(demo_schema(STANDARD_SCHEMA))},actor=actor))
    access=validated(AccessForm({'viewers':[],'editors':[]},actor=actor))
    cost=validated(CostForm({'cost_mode':'fixed','cost_amount':'25.00','payment_method':'cash','payment_note':'TESTDATEN – kein echtes Geld bezahlen.'}))
    event=create_event([basics,dates,places,template,access,cost],False,'dummy-'+nonce,actor)
    populate_registrations(event,actor)
    return event


@login_required
@require_POST
def dummy_event(request):
    if not can_create_dummy(request.user):raise PermissionDenied
    nonce=request.POST.get('nonce','')
    if not nonce or not secrets.compare_digest(nonce,request.session.get('dummy_event_nonce','')):
        messages.error(request,'Bitte die Seite neu laden und die Dummy-Veranstaltung über das Profilmenü erneut erstellen.')
        return redirect('dashboard')
    try:event=create_dummy_event(request.user,nonce)
    except ValidationError as error:
        messages.error(request,' '.join(error.messages));return redirect('dashboard')
    request.session['dummy_event_nonce']=secrets.token_hex(16)
    messages.success(request,'Dummy-Veranstaltung mit 29 erfundenen Anmeldungen in allen fünf Zuständen erstellt. Sie bleibt unveröffentlicht und versendet keine E-Mails.')
    return redirect('event_admin',pk=event.pk)


def demo_schema(standard):
    from copy import deepcopy
    schema=deepcopy(standard)
    schema.extend([
        {'title':'Weitere Kontaktdaten','fields':[
            {'key':'demo_birth_date','label':'Geburtsdatum','type':'date','required':True},
            {'key':'demo_contact_email','label':'Zusätzliche Kontaktadresse','type':'email','required':False},
            {'key':'demo_emergency_name','label':'Notfallkontakt: Name','type':'text','required':True},
            {'key':'demo_emergency_relation','label':'Verhältnis zur teilnehmenden Person','type':'text','required':True},
            {'key':'demo_emergency_phone','label':'Notfallkontakt: Telefon','type':'text','required':True}]},
        {'title':'Organisation','fields':[
            {'key':'demo_arrival','label':'Anreise','type':'select','required':True,'choices':['Bus','Fahrgemeinschaft','Eigene Anreise']},
            {'key':'demo_tents','label':'Mitgebrachte Zeltplätze','type':'integer','required':False},
            {'key':'demo_help','label':'Ich kann beim Aufbau helfen','type':'checkbox','required':False}]},
        {'title':'Datenschutz','fields':[{'key':'demo_photo_'+str(i),'label':label,'type':'select','required':True,'choices':['Ja','Nein']} for i,label in enumerate([
            'Zeigen von Fotos im Rahmen eines Fotoabends','Veröffentlichung in Medien des Verbandes','Veröffentlichung in der Presse','Veröffentlichung auf der Homepage','Veröffentlichung auf Social-Media-Kanälen des Stamms','Aushang von Bildern in den Veranstaltungsräumen'])]}
    ])
    return schema


def populate_registrations(event,actor):
    """Validate fixtures against today's real registration form; never enqueue mail."""
    if event.registrations.exists():return
    from .forms import RegistrationForm,template_schema
    from .models import Registration
    from .services import identity
    schema=template_schema(event.form_template);slot=event.group_slots.first();now=timezone.now()
    statuses=['confirmed']*12+['pending']*8+['waitlisted']*4+['cancelled']*3+['expired']*2
    for index,status in enumerate(statuses,1):
        name='Testkind '+str(index).zfill(2)+' Muster';email='test-eltern-'+str(index).zfill(2)+'@example.invalid'
        data={'child_name':name,'email':email,'consent':'on','group_id':str(slot.group_id)}
        for module in schema:
            for spec in module['fields']:
                key=spec['key'];kind=spec['type']
                value=({'select':lambda:spec['choices'][(index-1)%len(spec['choices'])],
                    'email':lambda:email,'date':lambda:'2015-04-15','integer':lambda:index%4,
                    'checkbox':lambda:index%2==0,'textarea':lambda:'Erfundene Testangaben. Keine medizinischen Daten.',
                    'text':lambda:'Testkontakt Muster' if 'name' in key else 'Elternteil' if 'relation' in key else '0000 000000'}.get(kind,lambda:None))()
                data['answer_'+key]=value
        form=RegistrationForm(data,modules=schema,event=event)
        validated(form)
        verified=status=='confirmed' or (status=='waitlisted' and index%2==0) or status=='cancelled'
        row=Registration(event=event,event_group=slot,child_name=name,email=email,identity=identity(name,email),
            status=status,answers=form.answers(),schema_snapshot=schema,email_verified=verified,
            confirmation_deadline=now-timedelta(days=1) if status=='expired' else now+timedelta(hours=48) if not verified else None,
            payment_received_at=now if status=='confirmed' and index<=6 else None,
            payment_received_by=actor if status=='confirmed' and index<=6 else None)
        row.full_clean();row.save()
