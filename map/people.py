from django.views.decorators.debug import sensitive_post_parameters
"""Account and role editors with a curated, enforced permission catalogue."""
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group,Permission
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404,render,redirect
from django.views.decorators.http import require_http_methods
from .models import ScoutGroup,LeaderProfile,StageRole,EventPermission
from .access import GLOBAL_RIGHTS,STAGE_ACTIONS,BUILTIN_ROLES,supported_permissions,stage_code,stage_ids,can_users,can_roles
from .roles import is_admin,can_manage,can_read_all,can_create_any,is_read_only

class PermissionFields:
    def add_permission_fields(self,selected):
        allowed=list(supported_permissions());self.supported_ids={p.pk for p in allowed}
        labels={}
        for permission in allowed:
            code=permission.content_type.app_label+'.'+permission.codename
            if code in GLOBAL_RIGHTS:labels[permission.pk]=' — '.join(GLOBAL_RIGHTS[code])
        stages=list(ScoutGroup.objects.order_by('name'));self.stage_rows=stages
        for stage in stages:
            for action,(label,help_text) in STAGE_ACTIONS.items():
                for permission in allowed:
                    if permission.codename==stage_code(stage.pk,action) and permission.content_type.app_label=='map':labels[permission.pk]=label+' — '+help_text
        def field(ids,label,help_text):
            result=forms.ModelMultipleChoiceField(queryset=Permission.objects.filter(pk__in=ids).select_related('content_type').order_by('codename'),label=label,required=False,widget=forms.CheckboxSelectMultiple,help_text=help_text)
            result.label_from_instance=lambda permission:labels[permission.pk]
            return result
        global_ids=[p.pk for p in allowed if p.content_type.app_label!='rooms' and p.content_type.app_label+'.'+p.codename in GLOBAL_RIGHTS]
        self.fields['global_rights']=field(global_ids,'Übergreifende Rechte','Diese Rechte gelten unabhängig von der Stufenzuordnung. Nicht benötigte Rechte frei lassen.')
        self.initial['global_rights']=list(set(selected)&set(global_ids))
        room_ids=[p.pk for p in allowed if p.content_type.app_label=='rooms']
        self.fields['room_rights']=field(room_ids,'Raumbuchung','Eigenständige Rechte für Räume. Sie vergeben keine Veranstaltungs-, Stufen- oder technischen Adminrechte.')
        self.initial['room_rights']=list(set(selected)&set(room_ids))
        for stage in stages:
            name='stage_'+str(stage.pk);ids=[p.pk for p in allowed if p.content_type.app_label=='map' and p.codename in [stage_code(stage.pk,action) for action in STAGE_ACTIONS]]
            self.fields[name]=field(ids,stage.name,'Zusätzliche Rechte für diese Stufe. Automatische Leitendenrechte müssen hier nicht nochmals gesetzt werden.')
            self.initial[name]=list(set(selected)&set(ids))
    @property
    def permission_sections(self):
        return [{'title':'Übergreifende Rechte','field':self['global_rights']},{'title':'Raumbuchung','field':self['room_rights']}]+[{'title':stage.name,'field':self['stage_'+str(stage.pk)]} for stage in self.stage_rows]
    def save_permissions(self,relation):
        # Preserve unrelated technical permissions; the editor never silently removes them.
        selected=set(relation.exclude(pk__in=self.supported_ids).values_list('pk',flat=True))
        for name in ['global_rights','room_rights']+['stage_'+str(stage.pk) for stage in self.stage_rows]:selected.update(p.pk for p in self.cleaned_data[name])
        relation.set(selected)

class PersonForm(PermissionFields,forms.ModelForm):
    roles=forms.ModelMultipleChoiceField(queryset=Group.objects.none(),required=False,label='Zusätzliche Rollen',widget=forms.CheckboxSelectMultiple,help_text='Rollen addieren Rechte. Stufenrollen geben vollständigen Zugriff auf ihre Stufe. Read-Only sperrt Veranstaltungsänderungen; Admin und Manager haben Vorrang.')
    is_leader=forms.BooleanField(label='Leitendenstatus',required=False,help_text='Mit aktiver Stufenzuordnung entstehen Lese-, Anlege-, Bearbeitungs- und Löschrechte für diese Stufen automatisch.')
    leader_stages=forms.ModelMultipleChoiceField(queryset=ScoutGroup.objects.none(),required=False,label='Eigene Stufen als leitende Person',widget=forms.CheckboxSelectMultiple)
    new_password=forms.CharField(label='Neues Passwort',required=False,strip=False,widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}),help_text='Bei bestehenden Konten leer lassen, um das Passwort zu behalten. Bei neuen Konten erforderlich. Nach Änderung deines eigenen Passworts ist eine erneute Anmeldung nötig.')
    class Meta:
        model=get_user_model();fields=['username','first_name','last_name','email','is_active']
    def __init__(self,*args,**kwargs):
        self.actor=kwargs.pop('actor',None)
        super().__init__(*args,**kwargs)
        from django.contrib.auth.validators import UnicodeUsernameValidator
        from .sso_names import validate_portal_username
        self.fields['username'].validators=[v for v in self.fields['username'].validators if not isinstance(v,UnicodeUsernameValidator)]+[validate_portal_username]
        from .account_security import technical_admin
        if self.actor and technical_admin(self.actor):
            self.fields['technical_admin']=forms.BooleanField(label='Technisches Admin-Konto',required=False,help_text='Vollständiger technischer Django-Adminzugang. Nur bestehende technische Admins dürfen diesen Status vergeben oder entfernen.')
            self.initial['technical_admin']=bool(self.instance.is_superuser)
        self.fields['roles'].queryset=Group.objects.order_by('name')
        stage_names={row.group_id:row.stage.name for row in StageRole.objects.select_related('stage')}
        self.fields['roles'].label_from_instance=lambda group:('Stufe: '+stage_names[group.pk]+' — Lesen, Anlegen, Bearbeiten und Löschen' if group.pk in stage_names else group.name+(' — '+BUILTIN_ROLES[group.name] if group.name in BUILTIN_ROLES else ''))
        self.fields['leader_stages'].queryset=ScoutGroup.objects.order_by('name')
        self.fields['is_active'].label='Konto aktiv';self.fields['is_active'].help_text='Gesperrte Konten erhalten keinerlei Zugriff, auch nicht über Rollen oder persönliche Veranstaltungsrechte.'
        profile=LeaderProfile.objects.filter(user=self.instance).first() if self.instance.pk else None
        if profile:self.initial.update(is_leader=profile.is_leader,leader_stages=list(profile.stages.values_list('pk',flat=True)))
        self.initial['roles']=list(self.instance.groups.values_list('pk',flat=True)) if self.instance.pk else []
        self.add_permission_fields(list(self.instance.user_permissions.values_list('pk',flat=True)) if self.instance.pk else [])
    def clean_username(self):
        value=self.cleaned_data['username']
        if get_user_model().objects.filter(username__iexact=value).exclude(pk=self.instance.pk).exists():raise ValidationError('Dieser Benutzername wird bereits verwendet.')
        return value
    def _get_validation_exclusions(self):
        exclude=super()._get_validation_exclusions()
        # Django's stock username regex excludes #; our form validates the controlled #SSO suffix.
        if self.cleaned_data.get('username','').endswith('#SSO'):exclude.add('username')
        return exclude
    def clean_new_password(self):
        value=self.cleaned_data.get('new_password','')
        if not self.instance.pk and not value:raise ValidationError('Für ein neues Konto bitte ein Passwort festlegen.')
        return value
    def clean(self):
        data=super().clean()
        if 'technical_admin' in self.data and 'technical_admin' not in self.fields:
            raise forms.ValidationError('Den technischen Adminstatus dürfen nur bestehende technische Admins ändern.')
        if data.get('new_password'):
            candidate=get_user_model()(**{name:data.get(name,'') for name in ['username','email','first_name','last_name']})
            try:validate_password(data['new_password'],candidate)
            except ValidationError as error:self.add_error('new_password',error)
        if not data.get('is_leader') and data.get('leader_stages'):
            self.add_error('is_leader','Bitte den Leitendenstatus aktivieren oder die Zuordnung eigener Stufen entfernen. Zusätzlicher Zugriff ist über Rollen und Einzelrechte möglich.')
        return data
    @transaction.atomic
    def save(self,commit=True):
        user=super().save(commit=False)
        if 'technical_admin' in self.fields:
            user.is_superuser=bool(self.cleaned_data['technical_admin'])
            user.is_staff=user.is_superuser
        if self.cleaned_data.get('new_password'):user.set_password(self.cleaned_data['new_password'])
        user.save();user.groups.set(self.cleaned_data['roles']);self.save_permissions(user.user_permissions)
        profile,_=LeaderProfile.objects.get_or_create(user=user)
        profile.is_leader=self.cleaned_data['is_leader'];profile.save(update_fields=['is_leader']);profile.stages.set(self.cleaned_data['leader_stages'])
        User=get_user_model()
        # Serialize editor changes and retain at least one active administrator.
        if not User.objects.filter(is_active=True).filter(Q(is_superuser=True)|Q(groups__name='Admin')).exists():
            raise ValidationError('Mindestens ein aktives Admin-Konto muss erhalten bleiben. Die Änderung wurde nicht gespeichert.')
        if 'technical_admin' in self.fields and not User.objects.filter(is_active=True,is_superuser=True).exists():
            raise ValidationError('Mindestens ein aktives technisches Admin-Konto muss erhalten bleiben. Die Änderung wurde nicht gespeichert.')
        return user

class RoleForm(PermissionFields,forms.ModelForm):
    class Meta:model=Group;fields=['name'];labels={'name':'Name der Rolle'}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.add_permission_fields(list(self.instance.permissions.values_list('pk',flat=True)) if self.instance.pk else [])
    def clean_name(self):
        value=self.cleaned_data['name'].strip()
        if value in BUILTIN_ROLES or value.startswith('Stufe:'):raise ValidationError('Dieser Name ist für feste System- und Stufenrollen reserviert.')
        return value
    @transaction.atomic
    def save(self,commit=True):
        group=super().save(commit=True);self.save_permissions(group.permissions);return group

def effective_access(user):
    automatic=set(LeaderProfile.objects.filter(user=user,is_leader=True).values_list('stages__pk',flat=True))
    from .sso import automatic_stage_ids
    automatic |= automatic_stage_ids(user)
    actions={action:stage_ids(user,action) for action in STAGE_ACTIONS}
    from .access import granted
    rows=[]
    for stage in ScoutGroup.objects.order_by('name'):
        row={'name':stage.name,'automatic':stage.pk in automatic and user.is_active,'rights':[]}
        for action in STAGE_ACTIONS:
            global_right=(can_read_all(user) if action=='view' else can_create_any(user) if action=='add' else can_manage(user) or granted(user,'map.'+action+'_event'))
            value=bool(user.is_active and (action=='view' or not is_read_only(user)) and (global_right or stage.pk in actions[action]))
            row['rights'].append({'label':STAGE_ACTIONS[action][0],'allowed':value})
        rows.append(row)
    return rows

@login_required
@require_http_methods(['GET'])
def people(request):
    if not can_users(request.user):raise PermissionDenied
    users=get_user_model().objects.prefetch_related('groups','leadership__stages').order_by('username')
    stage_names={row.group_id:row.stage.name for row in StageRole.objects.select_related('stage')}
    from .account_security import can_edit_person
    for person in users:
        person.can_edit_account=can_edit_person(request.user,person)
        for group in person.groups.all():group.display_name='Stufe: '+stage_names[group.pk] if group.pk in stage_names else group.name
    return render(request,'people.html',{'people':users})

@login_required
@require_http_methods(['GET','POST'])
@sensitive_post_parameters('new_password')
def person_edit(request,pk=None):
    if not can_users(request.user):raise PermissionDenied
    user=get_object_or_404(get_user_model(),pk=pk) if pk else get_user_model()()
    from .account_security import can_edit_person
    if user.pk and not can_edit_person(request.user,user):raise PermissionDenied
    form=PersonForm(request.POST if request.method=='POST' else None,instance=user,actor=request.user)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                list(get_user_model().objects.select_for_update(of=('self',)).filter(Q(is_superuser=True)|Q(groups__name='Admin')).order_by('pk').values_list('pk',flat=True))
                if user.pk:
                    current=get_user_model().objects.select_for_update().get(pk=user.pk)
                    if not can_edit_person(request.user,current):raise PermissionDenied
                    form.instance.password=current.password
                    form.instance.last_login=current.last_login
                    form.instance.date_joined=current.date_joined
                    if 'technical_admin' not in form.fields:
                        form.instance.is_superuser=current.is_superuser
                        form.instance.is_staff=current.is_staff
                saved=form.save()
        except ValidationError as error:form.add_error(None,error)
        else:
            messages.success(request,'Benutzerkonto, Stufenzuordnung und Rechte wurden gespeichert. Änderungen wirken bei der nächsten Anfrage.')
            return redirect('person_edit',pk=saved.pk)
    stored=get_user_model().objects.get(pk=user.pk) if user.pk else user
    from .user_deletion import deletion_context
    delete_context=deletion_context(request.user,stored) if stored.pk else {}
    return render(request,'person_edit.html',{**delete_context,'form':form,'person':stored,'effective_rows':effective_access(stored) if stored.pk else [],'is_person':True,'personal_permissions':list(EventPermission.objects.filter(user=stored).select_related('event')) if stored.pk else []})

@login_required
@require_http_methods(['GET'])
def role_list(request):
    if not can_roles(request.user):raise PermissionDenied
    groups=list(Group.objects.annotate().order_by('name'))
    stage_map={row.group_id:row.stage.name for row in StageRole.objects.select_related('stage')}
    for group in groups:
        group.fixed=group.name in BUILTIN_ROLES or group.pk in stage_map
        group.display_name='Stufe: '+stage_map[group.pk] if group.pk in stage_map else group.name
        group.explanation=BUILTIN_ROLES.get(group.name) or ('Vollständiger Zugriff auf die Stufe '+stage_map[group.pk] if group.pk in stage_map else 'Eigene Rolle mit individuell gewählten Rechten.');group.member_count=group.user_set.count()
    return render(request,'roles.html',{'roles':groups})

@login_required
@require_http_methods(['GET','POST'])
def role_edit(request,pk=None):
    if not can_roles(request.user):raise PermissionDenied
    group=get_object_or_404(Group,pk=pk) if pk else Group()
    binding=StageRole.objects.select_related('stage').filter(group=group).first() if group.pk else None
    group.display_name='Stufe: '+binding.stage.name if binding else group.name
    locked=bool(group.name in BUILTIN_ROLES or group.pk and StageRole.objects.filter(group=group).exists())
    form=RoleForm(request.POST if request.method=='POST' else None,instance=group)
    if locked:
        for field in form.fields.values():field.disabled=True
        if request.method=='POST':raise PermissionDenied('System- und automatische Stufenrollen sind feste Vorgaben. Für andere Rechte bitte eine eigene Rolle anlegen.')
    if request.method=='POST' and form.is_valid():
        group=form.save();messages.success(request,'Die Rolle wurde gespeichert. Ihre Rechte gelten für alle zugeordneten Personen.');return redirect('role_edit',pk=group.pk)
    return render(request,'person_edit.html',{'form':form,'role':group,'locked':locked,'is_person':False,'role_description':BUILTIN_ROLES.get(group.name) or ('Lesen, Anlegen, Bearbeiten und Löschen für die Stufe '+binding.stage.name+'. Diese Rolle gibt keinen globalen Verwaltungszugriff.' if binding else 'Eigene Rolle mit den unten gewählten Rechten.')})
