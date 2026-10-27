from django.utils import timezone
from django import forms
from django.contrib.auth import get_user_model
from .models import ScoutGroup, FormTemplate
from .widgets import QuickDateTimeWidget, BuilderWidget
from .form_schema import validate_builder_schema
from .forms import template_schema

class BasicsForm(forms.Form):
    title=forms.CharField(label='Name der Veranstaltung',max_length=200,help_text='Zum Beispiel: Sommerlager 2027')
    description=forms.CharField(label='Beschreibung',widget=forms.Textarea(attrs={'rows':4}),required=False)
    groups=forms.ModelMultipleChoiceField(label='Teilnehmende Gruppen',queryset=ScoutGroup.objects.none(),widget=forms.CheckboxSelectMultiple,required=False)
    group=forms.ModelChoiceField(queryset=ScoutGroup.objects.none(),required=False,widget=forms.HiddenInput)
    def __init__(self,*args,**kwargs):
        actor=kwargs.pop('actor',None)
        super().__init__(*args,**kwargs)
        available=ScoutGroup.objects.order_by('name')
        if actor is not None:
            from .roles import can_create_any,leader_stage_ids
            if not can_create_any(actor): available=available.filter(pk__in=leader_stage_ids(actor))
        self.fields['groups'].queryset=available
        self.fields['group'].queryset=available
    def clean(self):
        data=super().clean()
        if not data.get('groups') and data.get('group'):
            data['groups']=ScoutGroup.objects.filter(pk=data['group'].pk)
        if self.data.get('new_group_name'):
            raise forms.ValidationError('Stufen können nur durch Admins in der Stufenverwaltung angelegt werden.')
        if not data.get('groups'):
            raise forms.ValidationError('Bitte mindestens eine bestehende Stufe auswählen.')
        return data

def group_entries(basics):
    result=[{'key':str(group.pk),'label':group.name,'group':group} for group in basics.get('groups',[])]
    return result

def quota_values(basics,capacity_data):
    entries=group_entries(basics)
    return {entry['key']:capacity_data['capacity' if len(entries)==1 else 'capacity_'+entry['key']] for entry in entries}

class DatesForm(forms.Form):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        now=timezone.localtime(timezone.now()).replace(second=0,microsecond=0)
        for name in ['starts_at','registration_opens','registration_closes']:
            self.initial.setdefault(name,now)

    starts_at=forms.DateTimeField(label='Beginn der Veranstaltung',widget=QuickDateTimeWidget())
    registration_opens=forms.DateTimeField(label='Anmeldung möglich ab',widget=QuickDateTimeWidget())
    registration_closes=forms.DateTimeField(label='Anmeldung möglich bis',widget=QuickDateTimeWidget())
    def clean(self):
        data=super().clean()
        opens,closes,starts=[data.get(key) for key in ['registration_opens','registration_closes','starts_at']]
        if opens and closes and opens>=closes: self.add_error('registration_closes','Das Anmeldeende muss nach dem Anmeldebeginn liegen.')
        if closes and starts and closes>starts: self.add_error('registration_closes','Die Anmeldung muss spätestens zum Veranstaltungsbeginn enden.')
        return data

class CapacityForm(forms.Form):
    capacity_mode=forms.ChoiceField(label='Platzverteilung',choices=[('per_group','Eigene Plätze je Stufe'),('shared','Gemeinsamer Gesamtpool')],required=False,initial='per_group')
    shared_capacity=forms.IntegerField(label='Plätze im gemeinsamen Gesamtpool',min_value=1,max_value=2147483647,required=False)
    waitlist_mode=forms.ChoiceField(label='Wartelistenverteilung',choices=[('per_group','Warteliste je Stufe'),('shared','Gemeinsame Warteliste')],required=False,initial='per_group',help_text='Gemeinsame Warteliste: Nachrücken nach Anmeldezeitpunkt, bei Stufenkontingenten nur auf einen freien Platz der eigenen Stufe.')
    show_availability=forms.BooleanField(label='Verfügbare Plätze in der Anmeldung anzeigen',required=False,initial=True)
    capacity=forms.IntegerField(label='Plätze für die Gruppe',min_value=1,max_value=2147483647,initial=20)
    waitlist_enabled=forms.BooleanField(label='Warteliste anbieten',required=False,initial=True,help_text='Warteliste und Nachrücken werden für jede Gruppe getrennt geführt.')
    confirmation_required=forms.BooleanField(label='E-Mail-Bestätigung verlangen',required=False,initial=True,help_text='Die Anmeldung bleibt bis zur Bestätigung vorläufig reserviert.')
    confirmation_hours=forms.IntegerField(label='Bestätigungsfrist in Stunden',min_value=1,max_value=8760,initial=48)
    def __init__(self,*args,entries=None,**kwargs):
        super().__init__(*args,**kwargs)
        entries=entries or []
        names=['capacity']
        if len(entries)>1:
            self.fields.pop('capacity');names=[]
            for entry in entries:
                key='capacity_'+entry['key'];names.append(key)
                self.fields[key]=forms.IntegerField(label='Plätze für '+entry['label'],min_value=1,max_value=2147483647,initial=20)
        elif entries: self.fields['capacity'].label='Plätze für '+entries[0]['label']
        for name in names: self.fields[name].required=False
        self.order_fields(['capacity_mode','shared_capacity']+names+['waitlist_mode','show_availability']+['waitlist_enabled','confirmation_required','confirmation_hours'])

    def clean(self):
        data=super().clean()
        data['capacity_mode']=data.get('capacity_mode') or 'per_group'
        data['waitlist_mode']=data.get('waitlist_mode') or 'per_group'
        if data['capacity_mode']=='shared' and not data.get('shared_capacity'):
            self.add_error('shared_capacity','Bitte die Gesamtzahl der Plätze eintragen.')
        for name in self.fields:
            if name=='capacity' or name.startswith('capacity_') and name!='capacity_mode':
                if not data.get(name):
                    if data['capacity_mode']=='shared': data[name]=20
                    elif name not in self.errors: self.add_error(name,'Bitte ein Platzlimit ab 1 eintragen.')
        return data

class TemplateForm(forms.Form):
    form_template=forms.ModelChoiceField(label='Vorlage als Ausgangspunkt',queryset=FormTemplate.objects.none(),required=False,empty_label='Mit Standardbausteinen beginnen')
    schema_json=forms.JSONField(label='Anmeldeformular zusammenstellen',required=False,widget=BuilderWidget,validators=[validate_builder_schema])
    def __init__(self,*args,**kwargs):
        self.actor=kwargs.pop('actor',None)
        super().__init__(*args,**kwargs)
        actor=self.actor
        from .template_access import available_templates
        self.fields['form_template'].queryset=(available_templates(actor) if actor is not None else FormTemplate.objects.all()).order_by('name')
        self.fields['schema_json'].widget.allowed_template_ids=list(self.fields['form_template'].queryset.values_list('pk',flat=True))
    def clean_form_template(self):
        template=self.cleaned_data.get('form_template')
        if template: template_schema(template)
        return template

class AccessForm(forms.Form):
    viewers=forms.ModelMultipleChoiceField(label='Personen mit Leserechten',queryset=get_user_model().objects.none(),required=False,widget=forms.CheckboxSelectMultiple,help_text='Diese Personen dürfen Anmeldedaten nur lesen und als CSV exportieren.')
    editors=forms.ModelMultipleChoiceField(label='Personen, die die Veranstaltung bearbeiten dürfen',queryset=get_user_model().objects.none(),required=False,widget=forms.CheckboxSelectMultiple,help_text='Diese Personen dürfen Daten lesen sowie Einstellungen und Anmeldungen bearbeiten.')
    def __init__(self,*args,**kwargs):
        actor=kwargs.pop('actor',None)
        super().__init__(*args,**kwargs)
        people=get_user_model().objects.filter(is_active=True,is_superuser=False).order_by('username')
        self.fields['viewers'].queryset=people
        self.fields['editors'].queryset=people
        if actor is not None:
            from .roles import is_admin
            if not is_admin(actor):
                for name in ['viewers','editors']:
                    self.fields[name].queryset=people.none()
                    self.fields[name].widget=forms.MultipleHiddenInput()
    def clean(self):
        data=super().clean()
        if data.get('viewers') is not None and data.get('editors') is not None and set(data['viewers'].values_list('pk',flat=True)) & set(data['editors'].values_list('pk',flat=True)):
            raise forms.ValidationError('Eine Person bitte entweder zum Lesen oder zum Bearbeiten auswählen.')
        return data

class ReviewForm(forms.Form):
    published=forms.BooleanField(label='Veranstaltung direkt veröffentlichen',required=False,help_text='Ohne Häkchen wird ein unveröffentlichter Entwurf angelegt.')
    acknowledge=forms.BooleanField(label='Ich habe die Angaben und die Zugriffsrechte geprüft.')
