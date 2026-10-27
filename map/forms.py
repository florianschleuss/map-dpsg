from .text_labels import question_label
from .roles import is_admin
from django import forms
from django.contrib.auth import get_user_model
from .models import Event, ScoutGroup, EventPermission
from .schema import validate_schema
from .widgets import QuickDateTimeWidget, GroupLimitsWidget

def template_schema(template):
    modules = [{'title': module.title, 'fields': [
        {'key': field.key, 'label': question_label(field.label), 'type': field.kind, 'required': field.required,
         'choices': field.choices.splitlines(), 'help': field.help_text} for field in module.fields.all()]
        } for module in template.modules.all()]
    validate_schema(modules)
    return modules

class RegistrationForm(forms.Form):
    child_name = forms.CharField(label='Vor- und Nachname des Kindes', max_length=160)
    email = forms.EmailField(label='E-Mail der erziehungsberechtigten Person')
    consent = forms.BooleanField(label='Ich bin zur Anmeldung dieses Kindes berechtigt und melde das Kind verbindlich an.')
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    def __init__(self, *args, modules=None, answers=None, editing=False, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.modules = modules or []
        validate_schema(self.modules)
        if event is not None and not editing:
            slots=list(event.group_slots.filter(enabled=True).select_related('group'))
            options=[(str(slot.group_id),slot.group.name) for slot in slots] or [(str(event.group_id),event.group.name)]
            self.fields['group_id']=forms.ChoiceField(label='Gruppe des Kindes',choices=([('', 'Bitte auswählen')]+options) if len(options)>1 else options,required=len(options)>1,initial=options[0][0] if len(options)==1 else '')
            if len(options)==1: self.fields['group_id'].widget=forms.HiddenInput()
        if editing:
            self.fields['child_name'].disabled = True
            self.fields['email'].disabled = True
            self.fields.pop('consent')
        for module in self.modules:
            for spec in module['fields']:
                options = {'label': question_label(spec['label']), 'required': spec.get('required', False),
                           'initial': (answers or {}).get(spec['key']), 'help_text': spec.get('help', '')}
                kind = spec['type']
                if kind == 'select':
                    binary=spec['choices']==['Ja','Nein']
                    field = forms.ChoiceField(choices=[(x,x) for x in spec['choices']] if binary else [('', 'Bitte wählen')] + [(x,x) for x in spec['choices']],widget=forms.RadioSelect if binary else forms.Select, **options)
                elif kind == 'checkbox': field = forms.BooleanField(**options)
                elif kind == 'integer': field = forms.IntegerField(**options)
                elif kind == 'date': field = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'), **options)
                elif kind == 'email': field = forms.EmailField(**options)
                else: field = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows':1,'data-autogrow':''}) if kind == 'textarea' else forms.TextInput, **options)
                self.fields['answer_' + spec['key']] = field
        for field in self.fields.values():
            if isinstance(field.widget, (forms.TextInput, forms.Textarea)) and not isinstance(field.widget, (forms.EmailInput, forms.HiddenInput)):
                field.help_text = (str(field.help_text) + ' ' if field.help_text else '') + 'Bitte keine medizinischen Daten eingeben (z. B. Diagnosen, Allergien oder Medikamente).'
        self.order_fields(['child_name','email','group_id']+[key for key in self.fields if key.startswith('answer_')]+['consent','website'])
    @property
    def sections(self):
        sections=[{'title':'Zur teilnehmenden Person','fields':[self[name] for name in ['child_name','email','group_id'] if name in self.fields and not self[name].is_hidden]}]
        for module in self.modules:
            sections.append({'title':module['title'],'fields':[self['answer_'+spec['key']] for spec in module['fields']]})
        if 'consent' in self.fields: sections.append({'title':'Anmeldung abschließen','fields':[self['consent']]})
        return sections
    def clean_website(self):
        if self.cleaned_data.get('website'): raise forms.ValidationError('Ungültige Eingabe.')
        return ''
    def answers(self):
        return {key[7:]: value.isoformat() if hasattr(value, 'isoformat') else value for key, value in self.cleaned_data.items() if key.startswith('answer_')}

from .cost_forms import CostFieldsMixin

class EventSettingsForm(CostFieldsMixin,forms.ModelForm):
    from .widgets import GroupLimitsWidget
    viewers=forms.ModelMultipleChoiceField(label='Personen mit Leserechten',queryset=get_user_model().objects.none(),required=False,widget=forms.CheckboxSelectMultiple,help_text='Diese Personen dürfen Anmeldedaten nur lesen und als CSV exportieren.')
    editors=forms.ModelMultipleChoiceField(label='Personen, die die Veranstaltung bearbeiten dürfen',queryset=get_user_model().objects.none(),required=False,widget=forms.CheckboxSelectMultiple,help_text='Bearbeitungsrechte enthalten bereits Leserechte.')
    group_limits=forms.JSONField(label='Teilnehmende Stufen und Platzkontingente',widget=GroupLimitsWidget,help_text='Wähle die Stufen aus. Im gemeinsamen Gesamtpool gilt die Gesamtzahl statt einzelner Stufenlimits.')
    shared_capacity=forms.IntegerField(label='Plätze im gemeinsamen Gesamtpool',min_value=1,max_value=2147483647,required=False)
    class Meta:
        model=Event
        fields=['title','description','starts_at','registration_opens','registration_closes','published','capacity_mode','waitlist_mode','show_availability','waitlist_enabled','confirmation_required','confirmation_hours','form_template']
        from .widgets import QuickDateTimeWidget
        widgets={key:QuickDateTimeWidget() for key in ['starts_at','registration_opens','registration_closes']}
    def __init__(self,*args,**kwargs):
        actor=kwargs.pop('actor',None)
        self.actor=actor
        super().__init__(*args,**kwargs)
        from .widgets import TemplatePickerWidget
        from .roles import can_manage,can_create_events,leader_stage_ids,event_stage_ids
        self.fields['form_template'].widget=TemplatePickerWidget(event_id=self.instance.pk,can_create=bool(actor and can_create_events(actor)))
        self.fields['form_template'].widget.choices=self.fields['form_template'].choices
        if actor and is_admin(actor):
            people=get_user_model().objects.filter(is_active=True,is_superuser=False).order_by('username')
            self.fields['viewers'].queryset=people;self.fields['editors'].queryset=people
            if self.instance.pk:
                for role,key in [('viewer','viewers'),('editor','editors')]:
                    self.initial[key]=list(self.instance.eventpermission_set.filter(role=role,user__is_active=True,user__is_superuser=False).values_list('user_id',flat=True))
        else:
            self.fields.pop('viewers');self.fields.pop('editors')
        self.allowed_stage_ids=None
        from .access import granted
        if actor is not None and not (can_manage(actor) or granted(actor,'map.change_event')):
            from .access import stage_ids
            self.allowed_stage_ids=stage_ids(actor,'change') | (event_stage_ids(self.instance) if self.instance.pk else set())
            self.fields['group_limits'].widget.allowed_ids=self.allowed_stage_ids
        self.fields['confirmation_hours'].min_value=1;self.fields['confirmation_hours'].max_value=8760
        from django.core.validators import MinValueValidator,MaxValueValidator
        self.fields['confirmation_hours'].validators.extend([MinValueValidator(1),MaxValueValidator(8760)])
        self.fields['confirmation_hours'].widget.attrs.update(min=1,max=8760)
        if actor is not None:
            from .template_access import available_templates
            self.fields['form_template'].queryset=available_templates(actor).order_by('name')
        self.fields['capacity_mode'].required=False;self.fields['waitlist_mode'].required=False
        if self.instance.pk and self.instance.capacity_mode=='shared': self.initial['shared_capacity']=self.instance.capacity
        if self.instance.pk:
            slots=list(self.instance.group_slots.filter(enabled=True))
            self.initial['group_limits']={str(slot.group_id):slot.capacity for slot in slots} or {str(self.instance.group_id):self.instance.capacity}
        from .payment_rules import COST_FIELDS
        self.add_cost_fields({name:getattr(self.instance,name) for name in COST_FIELDS})
        self.fields['confirm_existing_costs']=forms.BooleanField(label='Ich bestätige, dass die erstmalige Kostenfestlegung mit bereits angemeldeten Personen abgestimmt wurde.',required=False)
        self.fields['confirm_existing_costs'].widget.attrs['data-existing-costs']='yes' if self.instance.pk and not self.instance.costs_configured and self.instance.registrations.exists() else 'no'
        if self.instance.pk and self.instance.costs_configured and self.instance.registrations.exists():
            from .payment_rules import FROZEN_FIELDS
            for name in FROZEN_FIELDS:self.fields[name].disabled=True
            self.fields['cost_mode'].help_text='Nach der ersten Anmeldung sind Kosten und Bezahlungsvorgang festgelegt. Bankdaten und Zusatzhinweise bleiben korrigierbar.'
        for field in self.fields.values():
            if isinstance(field.widget, (forms.TextInput, forms.Textarea)) and not isinstance(field.widget, (forms.EmailInput, forms.HiddenInput)):
                field.help_text = (str(field.help_text) + ' ' if field.help_text else '') + 'Bitte keine medizinischen Daten eingeben (z. B. Diagnosen, Allergien oder Medikamente).'
        self.order_fields(['title','description']+COST_FIELDS+['confirm_existing_costs','capacity_mode','shared_capacity','group_limits','waitlist_mode','show_availability','starts_at','registration_opens','registration_closes','waitlist_enabled','confirmation_required','confirmation_hours','form_template','viewers','editors','published'])
    def clean_group_limits(self):
        from .group_limits import validate_limits
        limits=self.cleaned_data['group_limits']
        if not isinstance(limits,dict): raise forms.ValidationError('Die Gruppenauswahl ist ungültig.')
        from .security_rules import numeric_pk
        keys=[str(key) for key in limits]
        if any(numeric_pk(key) is None for key in keys):raise forms.ValidationError('Bitte gültige Stufen auswählen.')
        self.selected_groups=list(ScoutGroup.objects.filter(pk__in=[int(key) for key in keys if key.isdigit()]).order_by('name'))
        if len(self.selected_groups)!=len(limits): raise forms.ValidationError('Eine ausgewählte Gruppe existiert nicht mehr.')
        limits={str(int(key)):value for key,value in limits.items()}
        if self.allowed_stage_ids is not None and not {group.pk for group in self.selected_groups}.issubset(self.allowed_stage_ids):
            raise forms.ValidationError('Du kannst hier nur bisherige oder dir zugeordnete Stufen auswählen.')
        validate_limits(self.instance,limits,pooled=self.cleaned_data.get('capacity_mode')=='shared')
        return limits
    def clean(self):
        data=self.clean_costs(super().clean())
        if self.instance.pk and not self.instance.costs_configured and self.instance.registrations.exists() and data.get('cost_mode') not in [None,'free'] and not data.get('confirm_existing_costs'):
            self.add_error('confirm_existing_costs','Bitte die Kosten mit den bereits angemeldeten Personen abstimmen und dies bestätigen.')
        from .payment_rules import COST_FIELDS
        for name in COST_FIELDS:
            if name in data:setattr(self.instance,name,data[name])
        if 'cost_mode' in self.data and (data.get('cost_mode')!='free' or not self.instance.pk or not self.instance.registrations.exists()):self.instance.costs_configured=True
        data['capacity_mode']=data.get('capacity_mode') or 'per_group'
        data['waitlist_mode']=data.get('waitlist_mode') or 'per_group'
        if data['capacity_mode']=='shared' and not data.get('shared_capacity'):
            self.add_error('shared_capacity','Bitte die Gesamtzahl der Plätze eintragen.')
        if 'viewers' in self.fields and data.get('viewers') is not None and data.get('editors') is not None:
            if set(data['viewers'].values_list('pk',flat=True)) & set(data['editors'].values_list('pk',flat=True)):
                raise forms.ValidationError('Eine Person bitte entweder zum Lesen oder zum Bearbeiten auswählen.')
        if data.get('group_limits') and getattr(self,'selected_groups',None):
            self.instance.group=self.selected_groups[0]
            self.instance.capacity=(data.get('shared_capacity') or 1) if data['capacity_mode']=='shared' else sum(data['group_limits'].values())
        return data
    def _save_m2m(self):
        # The explicit through model is saved atomically by save_allocations().
        pass
    def save_allocations(self):
        from .group_limits import apply_limits
        apply_limits(self.instance,self.selected_groups,self.cleaned_data['group_limits'])
        if 'viewers' in self.fields:
            desired={person.pk:role for role,key in [('viewer','viewers'),('editor','editors')] for person in self.cleaned_data[key]}
            self.instance.eventpermission_set.exclude(user_id__in=desired).delete()
            for user_id,role in desired.items(): EventPermission.objects.update_or_create(event=self.instance,user_id=user_id,defaults={'role':role})
    def save(self,commit=True):
        from django.db import transaction
        if not commit: return super().save(commit=False)
        with transaction.atomic():
            instance=super().save(commit=True)
            self.save_allocations()
            return instance


class ResendForm(forms.Form):
    child_name = forms.CharField(label='Name des Kindes', max_length=160)
    email = forms.EmailField(label='E-Mail-Adresse')
