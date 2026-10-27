from .roles import is_admin
from django import forms
from django.db import models
from django.shortcuts import redirect
from .forms import EventSettingsForm
from .widgets import QuickDateTimeWidget
from .admin_language import label_form, GermanInline, add_displays
from django.contrib import admin
from django.db import transaction
from .models import ScoutGroup, Event, FormTemplate, FormModule, FormField, EventPermission, Registration, EmailJob, AuditLog
from .services import rebalance

class LocalAdmin(admin.ModelAdmin):
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.DateTimeField):
            return db_field.formfield(widget=QuickDateTimeWidget())
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    def get_form(self, request, obj=None, **kwargs):
        result=label_form(super().get_form(request, obj, **kwargs))
        for field in result.base_fields.values():
            for key in ['can_add_related','can_change_related','can_delete_related']:
                if hasattr(field.widget,key): setattr(field.widget,key,False)
        return result
    def has_module_permission(self, request): return is_admin(request.user)
    def has_view_permission(self, request, obj=None): return is_admin(request.user)
    def has_add_permission(self, request): return is_admin(request.user)
    def has_change_permission(self, request, obj=None): return is_admin(request.user)
    def has_delete_permission(self, request, obj=None): return is_admin(request.user)

class FieldInline(GermanInline):
    model = FormField
    extra = 0

class ModuleInline(GermanInline):
    model = FormModule
    extra = 0
    show_change_link = True

@admin.register(FormTemplate)
class TemplateAdmin(LocalAdmin):
    inlines = []
    def add_view(self, request, form_url='', extra_context=None):
        if not is_admin(request.user): return super().add_view(request,form_url,extra_context)
        return redirect('map_form_builder_new')
    def change_view(self, request, object_id, form_url='', extra_context=None):
        if not is_admin(request.user): return super().change_view(request,object_id,form_url,extra_context)
        return redirect('map_form_builder',pk=native_pk(object_id))
    list_display = ['name']

@admin.register(FormModule)
class ModuleAdmin(LocalAdmin):
    def has_module_permission(self, request): return False
    inlines = [FieldInline]
    list_display = ['title', 'template', 'position']
    list_filter = ['template']

class PermissionInline(GermanInline):
    model = EventPermission
    extra = 0

@admin.register(Event)
class EventAdmin(LocalAdmin):
    change_form_template = 'admin/map_event_change_form.html'
    form = EventSettingsForm
    fields = ['title','description','capacity_mode','shared_capacity','group_limits','waitlist_mode','show_availability','starts_at','registration_opens','registration_closes','waitlist_enabled','confirmation_required','confirmation_hours','form_template','viewers','editors','published']
    list_display = ['title', 'group_summary', 'capacity', 'published', 'starts_at']
    @admin.display(description='Teilnehmende Gruppen')
    def group_summary(self,obj): return obj.group_names
    def add_view(self,request,form_url='',extra_context=None):
        if not is_admin(request.user): return super().add_view(request,form_url,extra_context)
        return redirect('map_event_wizard')
    inlines = []
    def get_form(self, request, obj=None, **kwargs):
        base=super().get_form(request,obj,**kwargs)
        class ScopedEventForm(base):
            def __init__(self,*args,**form_kwargs):
                form_kwargs['actor']=request.user
                super().__init__(*args,**form_kwargs)
        return ScopedEventForm
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        with transaction.atomic():
            if object_id: Event.objects.select_for_update().filter(pk=native_pk(object_id)).first()
            return super().changeform_view(request, object_id, form_url, extra_context)
    def delete_view(self,request,object_id,extra_context=None):
        return redirect('event_delete',pk=native_pk(object_id))
    def get_actions(self,request):
        actions=super().get_actions(request);actions.pop('delete_selected',None);return actions
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
    def save_related(self,request,form,formsets,change):
        super().save_related(request,form,formsets,change)
        form.save_allocations()
        rebalance(form.instance.pk)

@admin.register(EmailJob)
class EmailAdmin(LocalAdmin):
    fields = ['de_recipient', 'de_subject', 'de_body', 'de_attempts', 'de_sent_at', 'de_next_attempt', 'de_last_error', 'de_created_at']
    list_display = ['de_recipient', 'de_subject', 'de_attempts', 'de_sent_at', 'de_next_attempt']
    readonly_fields = ['de_recipient', 'de_subject', 'de_body', 'de_attempts', 'de_sent_at', 'de_next_attempt', 'de_last_error', 'de_created_at']
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
    actions = ['retry']
    @admin.action(description='Fehlgeschlagene Aufträge erneut freigeben')
    def retry(self, request, queryset):
        from django.utils import timezone
        queryset.filter(sent_at__isnull=True).update(attempts=0, next_attempt=timezone.now(), last_error='')

@admin.register(Registration)
class RegistrationAdmin(LocalAdmin):
    fields = ['de_event', 'de_event_group', 'de_child_name', 'de_email', 'de_status', 'de_answers', 'de_schema_snapshot', 'de_email_verified', 'de_confirmation_deadline', 'de_created_at', 'de_updated_at']
    list_display = ['child_name', 'event', 'de_event_group', 'status', 'created_at']
    list_filter = ['event', 'status']
    readonly_fields = ['de_event', 'de_event_group', 'de_child_name', 'de_email', 'de_status', 'de_answers', 'de_schema_snapshot', 'de_email_verified', 'de_confirmation_deadline', 'de_created_at', 'de_updated_at']
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(AuditLog)
class AuditAdmin(LocalAdmin):
    fields = ['de_created_at', 'de_actor', 'de_event', 'de_action']
    list_display = ['de_created_at', 'de_actor', 'de_event', 'de_action']
    readonly_fields = ['de_created_at', 'de_actor', 'de_event', 'de_action']
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

admin.site.register(ScoutGroup, LocalAdmin)
@admin.register(EventPermission)
class PermissionAdmin(LocalAdmin):
    def has_module_permission(self,request): return False
    list_display = ['event', 'user', 'role']
    list_filter = ['event', 'role']

# MAP: German readonly labels without changes to database field definitions.
add_displays(EmailAdmin, ['recipient', 'subject', 'body', 'attempts', 'sent_at', 'next_attempt', 'last_error', 'created_at'])
add_displays(RegistrationAdmin, ['event', 'event_group', 'child_name', 'email', 'status', 'answers', 'schema_snapshot', 'email_verified', 'confirmation_deadline', 'created_at', 'updated_at'])
add_displays(AuditAdmin, ['created_at', 'actor', 'event', 'action'])

# The administration is a profile destination, never a second homepage.
from types import MethodType
admin.site.enable_nav_sidebar = False
admin.site.has_permission = MethodType(lambda self, request: is_admin(request.user), admin.site)
admin.site.index = MethodType(lambda self, request, extra_context=None: redirect('dashboard'), admin.site)

from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import GroupAdmin, UserAdmin

def permission_label(permission):
    action=permission.codename.split('_',1)[0]
    model=permission.content_type.model_class()
    label=str(model._meta.verbose_name) if model else permission.content_type.model
    return {'add':'Anlegen','change':'Bearbeiten','delete':'Löschen','view':'Ansehen'}.get(action,action)+' · '+label

class GermanPermissionMixin:
    def formfield_for_manytomany(self,db_field,request,**kwargs):
        field=super().formfield_for_manytomany(db_field,request,**kwargs)
        if db_field.name in ['permissions','user_permissions'] and field:
            field.label_from_instance=permission_label
        return field

for model in [Group,User]:
    if admin.site.is_registered(model): admin.site.unregister(model)
admin.site.register(Group,type('GermanGroupAdmin',(GermanPermissionMixin,GroupAdmin),{}))
from django.contrib.auth.forms import UserChangeForm,UserCreationForm
from .models import LeaderProfile

def leader_user_form(base):
    class LeaderUserForm(base):
        is_leader=forms.BooleanField(label='Leitendenstatus',required=False,help_text='Erlaubt Zugriff über die unten zugeordneten Stufen. Ohne Stufenzuordnung entstehen keine zusätzlichen Stufenrechte.')
        leader_stages=forms.ModelMultipleChoiceField(label='Zugeordnete Stufen',queryset=ScoutGroup.objects.none(),required=False,widget=forms.CheckboxSelectMultiple,help_text='Leitende sehen Veranstaltungen mit einer dieser Stufen und können Veranstaltungen für ihre zugeordneten Stufen anlegen. Zusätzliche individuelle Veranstaltungsrechte bleiben unabhängig davon bestehen.')
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.fields['leader_stages'].queryset=ScoutGroup.objects.order_by('name')
            if self.instance.pk:
                profile=LeaderProfile.objects.filter(user=self.instance).first()
                if profile:
                    self.initial['is_leader']=profile.is_leader
                    self.initial['leader_stages']=list(profile.stages.values_list('pk',flat=True))
    return LeaderUserForm

class GermanUserAdmin(GermanPermissionMixin,UserAdmin):
    form=leader_user_form(UserChangeForm)
    add_form=leader_user_form(UserCreationForm)
    fieldsets=(
        (None,{'fields':('username','password')}),
        ('Persönliche Angaben',{'fields':('first_name','last_name','email')}),
        ('Leitendenstatus und Stufen',{'fields':('is_leader','leader_stages')}),
        ('Kontozugang und zusätzliche Rechte',{'fields':('is_active','is_superuser','groups','user_permissions')}),
        ('Zeitpunkte',{'fields':('last_login','date_joined')}),
    )
    add_fieldsets=((None,{'classes':('wide',),'fields':('username','email','password1','password2','is_leader','leader_stages','is_active','groups')}),)
    list_display=('username','email','first_name','last_name','leader_flag','stage_names','is_active')
    list_filter=('is_active','is_superuser','groups','leadership__is_leader')
    def get_queryset(self,request):
        return super().get_queryset(request).select_related('leadership').prefetch_related('leadership__stages')
    @admin.display(description='Leitendenstatus',boolean=True)
    def leader_flag(self,obj):
        try:return obj.leadership.is_leader
        except LeaderProfile.DoesNotExist:return False
    @admin.display(description='Zugeordnete Stufen')
    def stage_names(self,obj):
        try:return ', '.join(stage.name for stage in obj.leadership.stages.all()) or '—'
        except LeaderProfile.DoesNotExist:return '—'
    def save_model(self,request,obj,form,change):
        super().save_model(request,obj,form,change)
        profile,_=LeaderProfile.objects.get_or_create(user=obj)
        profile.is_leader=bool(form.cleaned_data.get('is_leader'));profile.save(update_fields=['is_leader'])
        profile.stages.set(form.cleaned_data.get('leader_stages',[]))

admin.site.register(User,GermanUserAdmin)


# Account/role routes use the same responsive portal UI, including old bookmarks.
from .access import can_users,can_roles,can_stages
from .people import people,person_edit,role_list,role_edit
GermanUserAdmin.changelist_view=lambda self,request,extra_context=None:people(request)
GermanUserAdmin.add_view=lambda self,request,form_url='',extra_context=None:person_edit(request)
GermanUserAdmin.change_view=lambda self,request,object_id,form_url='',extra_context=None:person_edit(request,pk=native_pk(object_id))
for method in ['has_module_permission','has_view_permission','has_add_permission','has_change_permission']:
    setattr(GermanUserAdmin,method,lambda self,request,obj=None:can_users(request.user))
group_admin=admin.site._registry[Group]
group_admin.changelist_view=MethodType(lambda self,request,extra_context=None:role_list(request),group_admin)
group_admin.add_view=MethodType(lambda self,request,form_url='',extra_context=None:role_edit(request),group_admin)
group_admin.change_view=MethodType(lambda self,request,object_id,form_url='',extra_context=None:role_edit(request,pk=native_pk(object_id)),group_admin)
group_admin.has_delete_permission=MethodType(lambda self,request,obj=None:False,group_admin)
GermanUserAdmin.has_delete_permission=lambda self,request,obj=None:False
stage_admin=admin.site._registry[ScoutGroup]
for method in ['has_module_permission','has_view_permission','has_add_permission','has_change_permission','has_delete_permission']:
    setattr(stage_admin,method,MethodType(lambda self,request,obj=None:can_stages(request.user),stage_admin))
admin.site.has_permission=MethodType(lambda self,request:is_admin(request.user) or can_users(request.user) or can_roles(request.user) or can_stages(request.user),admin.site)

# Existing native password endpoints must honor technical-account protection too.
from .account_security import can_edit_person
GermanUserAdmin.has_change_permission=lambda self,request,obj=None:can_edit_person(request.user,obj) if obj is not None else can_users(request.user)
# Serve legacy event URLs through the shared editor without discarding POST data.
from .views import event_settings as shared_event_settings
EventAdmin.change_view=lambda self,request,object_id,form_url='',extra_context=None:shared_event_settings(request,pk=native_pk(object_id))


# Native admin URLs use path converters; reject malformed and oversized IDs early.
def native_pk(value):
    from .security_rules import numeric_pk
    from django.http import Http404
    result=numeric_pk(value)
    if result is None:raise Http404
    return result
