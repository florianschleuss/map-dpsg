from .roles import can_manage,can_create_events,require_creation_stages,is_admin
import secrets
from datetime import datetime
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from .models import ScoutGroup, FormTemplate, FormModule, FormField, Event, EventPermission, AuditLog
from .forms import template_schema

SESSION_KEY = 'map_event_drafts_v10'
STEPS = ['Grundlagen', 'Termine', 'Plätze und Bestätigung', 'Anmeldeformular', 'Zugänge', 'Kosten und Bezahlung', 'Prüfen und anlegen']
TIPS = [
('Gemeinsam veranstalten','Wähle eine oder mehrere bestehende Stufen. Neue Stufen legt ausschließlich ein Admin über das Profilmenü an.'),
('Termine bequem auswählen','Wähle ein Datum im Kalender. Mit „0 Uhr“, „9 Uhr“ oder „17 Uhr“ setzt du die Uhrzeit schneller. „Jetzt“ setzt Datum und Uhrzeit. Alle Zeiten beziehen sich auf Deutschland.'),
('Eigene Plätze für jede Gruppe','Jede Gruppe hat ein eigenes Platzlimit. Warteliste und Nachrücken laufen getrennt. Die Gesamtzahl ergibt sich aus allen Gruppenkontingenten.'),
('Fragen aus Bausteinen zusammenstellen','Rechts findest du Standardbausteine und einzelne Fragetypen. Alle Fragen kannst du bearbeiten, verschieben und in der Vorschau prüfen.'),
('Zugriff gezielt vergeben','Wähle Personen per Kontrollkästchen aus. Bei Auswahl in einer Rolle wird die andere Rolle für dieselbe Person gesperrt. Bearbeitungsrechte enthalten bereits Leserechte.'),
('Kosten transparent machen','Wähle kostenlos, einen festen Eurobetrag pro Person oder Freitext. MAP verarbeitet keine Zahlungen. Überweisungsdaten erscheinen erst bei bestätigter Teilnahme; bei Zahlungsaufforderung zusätzlich erst nach manueller Freigabe.'),
('Prüfen und speichern','Erst jetzt werden die Veranstaltung und gegebenenfalls das Formular angelegt. Standardmäßig wird ein unveröffentlichter Entwurf gespeichert. Eltern erhalten später den direkten Anmeldelink.')
]

from .setup_forms import BasicsForm, DatesForm, CapacityForm, TemplateForm, AccessForm, ReviewForm, group_entries, quota_values
from .form_schema import STANDARD_SCHEMA, persist_schema
from .group_limits import apply_limits

from .cost_forms import CostForm
FORMS=[BasicsForm,DatesForm,CapacityForm,TemplateForm,AccessForm,CostForm,ReviewForm]

def serialize(value):
    if isinstance(value,datetime): return value.isoformat()
    from decimal import Decimal
    from datetime import date
    if isinstance(value,Decimal):return str(value).replace('.',',')
    if isinstance(value,date):return str(value)
    if hasattr(value,'values_list'): return list(value.values_list('pk',flat=True))
    if hasattr(value,'pk'): return value.pk
    return value

def initial_values(step,data):
    result=dict(data)
    if step==1:
        for key,value in result.items():
            if isinstance(value,str):
                parsed=parse_datetime(value)
                if parsed: result[key]=timezone.localtime(parsed) if timezone.is_aware(parsed) else parsed
    return result

def make_form(index,state,data=None,initial=None,actor=None):
    kwargs={'initial':initial or {}}
    if index in [0,3,4]: kwargs['actor']=actor
    if index==2:
        basics=BasicsForm(state.get('data',{}).get('0',{}),actor=actor)
        kwargs['entries']=group_entries(basics.cleaned_data) if basics.is_valid() else []
    return FORMS[index](data,**kwargs)

def validate_draft(state,actor=None):
    cleaned=[]
    for index,form_class in enumerate(FORMS[:-1]):
        form=make_form(index,state,state.get('data',{}).get(str(index),{}),actor=actor)
        if not form.is_valid(): return cleaned,index,form
        cleaned.append(form.cleaned_data)
    return cleaned,None,None

def review_rows(cleaned):
    basics,dates,places,template,access=cleaned[:5]
    costs=cleaned[5] if len(cleaned)>5 else {'cost_mode':'free'}
    yes=lambda value:'Ja' if value else 'Nein'
    date=lambda value:timezone.localtime(value).strftime('%d.%m.%Y, %H:%M Uhr')
    names=lambda users:', '.join(user.get_username() for user in users) or 'Keine zusätzlichen Personen'
    quotas=quota_values(basics,places)
    return [('Veranstaltung',basics['title']),('Gruppen und Plätze',' · '.join(entry['label']+(': ohne Limit' if places.get('capacity_mode')=='unlimited' else ': '+str(quotas[entry['key']])+' Plätze') for entry in group_entries(basics))),('Beginn',date(dates['starts_at'])),('Anmeldezeitraum',date(dates['registration_opens'])+' bis '+date(dates['registration_closes'])),('Platzverteilung',('Gemeinsamer Gesamtpool: '+str(places.get('shared_capacity'))+' Plätze') if places.get('capacity_mode')=='shared' else ('Ohne Limit' if places.get('capacity_mode')=='unlimited' else 'Eigene Kontingente je Stufe')),('Warteliste',('Gemeinsam' if places.get('waitlist_mode')=='shared' or places.get('capacity_mode')=='shared' else 'Je Stufe') if places['waitlist_enabled'] else 'Keine'),('Platzzahlen für Eltern sichtbar',yes(places.get('show_availability',True))),('E-Mail-Bestätigung',yes(places['confirmation_required'])),('Bestätigungsfrist',str(places['confirmation_hours'])+' Stunden'),('Formular',str(template['form_template'] or 'Eigenes Formular mit Standardbausteinen')),('Personen mit Leserechten',names(access['viewers'])),('Personen mit Bearbeitungsrechten',names(access['editors'])),('Kosten',('Kostenlos' if costs.get('cost_mode')=='free' else str(costs.get('cost_amount')).replace('.',',')+' Euro pro Person' if costs.get('cost_mode')=='fixed' else costs.get('cost_text',''))),('Bezahlung',dict(CostForm().fields['payment_method'].choices).get(costs.get('payment_method'),'Keine Zahlung'))]+([('Kontoinhaber',costs.get('bank_account_holder','')),('IBAN',costs.get('bank_iban','')),('BIC',costs.get('bank_bic') or 'Nicht erforderlich')] if costs.get('payment_method') in ['transfer','reminder'] else [])

@transaction.atomic
def create_event(cleaned,published,draft_id,actor):
    get_user_model().objects.select_for_update().get(pk=actor.pk)
    basics,dates,places,template_data,access=cleaned[:5]
    cost_form=CostForm(cleaned[5] if len(cleaned)>5 else {'cost_mode':'free'})
    if not cost_form.is_valid():raise ValidationError(cost_form.errors.as_text())
    costs=cost_form.cleaned_data
    if not can_create_events(actor): raise ValidationError('Du hast keine Berechtigung, eine Veranstaltung anzulegen.')
    require_creation_stages(actor,list(basics.get('groups',[])))
    if not is_admin(actor) and (access.get('viewers') or access.get('editors')):
        raise ValidationError('Zusätzliche personenbezogene Veranstaltungsrechte vergibt ein Admin.')
    slug=(slugify(basics['title']) or 'veranstaltung')[:24]+'-'+draft_id[:20]
    existing=Event.objects.filter(slug=slug).first()
    if existing:
        from .services import permitted
        if not permitted(actor,existing,True):raise ValidationError('Dieser Entwurf gehört nicht zu deinem Verwaltungsbereich.')
        return existing
    if basics.get('new_group_name'):
        raise ValidationError('Neue Stufen bitte in der Administration anlegen.')
    entries=group_entries(basics)
    if not entries: raise ValidationError('Mindestens eine bestehende Stufe ist erforderlich.')
    quotas=quota_values(basics,places)
    groups=[];limits={}
    for entry in entries:
        group=entry['group']
        groups.append(group);limits[str(group.pk)]=quotas[entry['key']]
    template=template_data['form_template']
    if template is not None:
        from .template_access import available_templates
        if not available_templates(actor).filter(pk=template.pk).exists():raise ValidationError('Diese Formularvorlage ist für dich nicht verfügbar.')
    schema=template_data.get('schema_json')
    if schema is None: schema=template_schema(template) if template else STANDARD_SCHEMA
    if template is None or schema!=template_schema(template):
        template=persist_schema(schema,('Anmeldeformular – '+basics['title'])[:160])
        template.created_by=actor;template.save(update_fields=['created_by'])
    event=Event(group=groups[0],form_template=template,title=basics['title'],description=basics['description'],slug=slug,privacy_text='',published=published,capacity=(places['shared_capacity'] if places.get('capacity_mode')=='shared' else sum(limits.values())),capacity_mode=places.get('capacity_mode') or 'per_group',waitlist_mode=places.get('waitlist_mode') or 'per_group',show_availability=places.get('show_availability',True),**dates,**{key:places[key] for key in ['waitlist_enabled','confirmation_required','confirmation_hours']})
    from .payment_rules import COST_FIELDS
    for name in COST_FIELDS:setattr(event,name,costs[name])
    event.costs_configured=True
    event.full_clean();event.save()
    apply_limits(event,groups,limits)
    from .services import permitted
    if not permitted(actor,event,True): EventPermission.objects.create(event=event,user=actor,role='editor')
    for role,key in [('viewer','viewers'),('editor','editors')]:
        for user in access[key]: EventPermission.objects.create(event=event,user=user,role=role)
    AuditLog.objects.create(actor=actor,event=event,action='Veranstaltung mit dem Assistenten angelegt')
    return event

def wizard_context(request,state,draft_id,form,cleaned=None):
    step=state['step']
    tip_text=TIPS[step][1]
    if step==4 and not is_admin(request.user): tip_text='Leitende der ausgewählten Stufen erhalten ihre Rechte automatisch. Zusätzliche persönliche Veranstaltungsrechte kann ein Admin in den Einstellungen vergeben.'
    context=admin.site.each_context(request)
    context.update(title='Veranstaltung anlegen',step=step+1,total_steps=len(STEPS),step_title=STEPS[step],
        steps=[{'number':i+1,'label':label,'current':i==step,'done':i<step} for i,label in enumerate(STEPS)],
        form=form,draft_id=draft_id,tip_title=TIPS[step][0],tip_text=tip_text,
        review=review_rows(cleaned) if cleaned and step==6 else [],is_review=step==6,is_form_step=step==3)
    return context

@login_required
@require_http_methods(['GET','POST'])
def event_wizard(request):
    if not can_create_events(request.user):
        raise PermissionDenied
    drafts=request.session.get(SESSION_KEY,{})
    draft_id=request.POST.get('draft_id') if request.method=='POST' else request.GET.get('entwurf')
    if not draft_id or draft_id not in drafts:
        if request.method=='POST':
            messages.error(request,'Dieser Entwurf ist abgelaufen. Bitte die Veranstaltung erneut anlegen.')
        draft_id=secrets.token_hex(16)
        while len(drafts)>=5: drafts.pop(next(iter(drafts)))
        drafts[draft_id]={'step':0,'data':{}}
        request.session[SESSION_KEY]=drafts
        return redirect(request.path+'?entwurf='+draft_id)
    state=drafts[draft_id]
    if state.get('created_event'):
        return redirect('event_admin',state['created_event'])
    step=state['step']
    if request.method=='POST' and request.POST.get('step')!=str(step+1):
        messages.warning(request,'Der Schritt wurde bereits bearbeitet. Bitte nutze die aktuelle Seite.')
        return redirect(request.path+'?entwurf='+draft_id)
    form=make_form(step,state,request.POST if request.method=='POST' else None,initial=initial_values(step,state['data'].get(str(step),{})),actor=request.user)
    cleaned=None
    if step==6:
        cleaned,invalid,invalid_form=validate_draft(state,actor=request.user)
        if invalid is not None:
            state['step']=invalid
            drafts[draft_id]=state
            request.session[SESSION_KEY]=drafts
            messages.error(request,'Bitte prüfe diesen Schritt erneut. Ein gespeicherter Wert ist nicht mehr gültig.')
            return render(request,'admin/map_event_wizard.html',wizard_context(request,state,draft_id,invalid_form))
    if request.method=='POST':
        action=request.POST.get('action','next')
        if action=='back' and step>0:
            if form.is_valid(): state['data'][str(step)]={key:serialize(value) for key,value in form.cleaned_data.items()}
            state['step']=step-1
        elif form.is_valid():
            if step<6:
                state['data'][str(step)]={key:serialize(value) for key,value in form.cleaned_data.items()}
                state['step']=step+1
            else:
                try: event=create_event(cleaned,form.cleaned_data['published'],draft_id,request.user)
                except ValidationError as exc: form.add_error(None,forms.ValidationError(exc.messages))
                else:
                    state['created_event']=event.pk
                    drafts[draft_id]=state
                    request.session[SESSION_KEY]=drafts
                    messages.success(request,'Die Veranstaltung wurde angelegt.' if event.published else 'Die Veranstaltung wurde als unveröffentlichter Entwurf angelegt.')
                    return redirect('event_admin',event.pk)
        if state['step']!=step:
            drafts[draft_id]=state
            request.session[SESSION_KEY]=drafts
            return redirect(request.path+'?entwurf='+draft_id)
    return render(request,'admin/map_event_wizard.html',wizard_context(request,state,draft_id,form,cleaned))
