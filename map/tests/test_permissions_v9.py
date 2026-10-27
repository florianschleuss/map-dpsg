from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group,Permission
from django.core.exceptions import ValidationError
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from map.models import ScoutGroup,StageRole,LeaderProfile,Event,EventGroup,EventPermission,FormTemplate,EmailJob,EmailTemplate
from map.access import GLOBAL_RIGHTS,STAGE_ACTIONS,stage_code,stage_ids,granted,supported_permissions,can_queue,can_templates
from map.roles import can_create_events,can_delete_event,require_creation_stages,visible_events
from map.services import permitted,register,queue_message
from map.people import PersonForm,RoleForm,effective_access

@override_settings(SECURE_SSL_REDIRECT=False)
class PermissionEnforcementTests(TestCase):
    def setUp(self):
        User=get_user_model();self.admin=User.objects.create_superuser(username='admin9',email='admin@example.org',password='Strong-admin-pass-593!')
        self.user=User.objects.create_user(username='user9');self.other=User.objects.create_user(username='other9')
        self.a=ScoutGroup.objects.create(name='Wölflinge');self.b=ScoutGroup.objects.create(name='Jungpfadfinder')
        self.template=FormTemplate.objects.create(name='Formular9')
        now=timezone.now();self.event=Event.objects.create(group=self.a,form_template=self.template,title='Wölflingslager9',slug='woes9',published=False,starts_at=now+timedelta(days=10),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=8),confirmation_required=False)
        EventGroup.objects.create(event=self.event,group=self.a,capacity=20)
        self.foreign=Event.objects.create(group=self.b,form_template=self.template,title='Juffilager9',slug='juffis9',published=False,starts_at=self.event.starts_at,registration_opens=self.event.registration_opens,registration_closes=self.event.registration_closes)
        EventGroup.objects.create(event=self.foreign,group=self.b,capacity=20)
    def permission(self,code):
        app,codename=code.split('.',1);return Permission.objects.get(content_type__app_label=app,codename=codename)
    def grant(self,code,user=None):
        (user or self.user).user_permissions.add(self.permission(code))
    def login(self,user=None):self.client.force_login(user or self.user)
    def test_every_catalogued_global_permission_exists(self):
        for code in GLOBAL_RIGHTS:self.assertIn(self.permission(code),supported_permissions())
    def test_no_rights_denies_every_management_destination(self):
        self.login()
        for name in ['people','roles','mail_settings','mail_queue','email_templates']:
            self.assertEqual(self.client.get(reverse(name)).status_code,403,name)
        self.assertFalse(permitted(self.user,self.event));self.assertFalse(can_create_events(self.user))
    def test_global_read_is_applied_without_builtin_role(self):
        self.grant('map.view_event');self.login()
        self.assertEqual(self.client.get(reverse('event_admin',args=[self.event.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('export_csv',args=[self.event.pk])).status_code,200)
        self.assertFalse(permitted(self.user,self.event,True));self.assertFalse(can_delete_event(self.user,self.event))
    def test_global_edit_does_not_silently_grant_delete_or_create(self):
        self.grant('map.change_event');self.login()
        self.assertEqual(self.client.get(reverse('event_settings',args=[self.event.pk])).status_code,200)
        self.assertEqual(self.client.post(reverse('publish_event',args=[self.event.pk])).status_code,302)
        self.assertEqual(self.client.post(reverse('event_delete',args=[self.event.pk]),{'confirm_delete':'delete'}).status_code,403)
        self.assertFalse(can_create_events(self.user))
    def test_global_delete_is_enforced_independently(self):
        self.grant('map.delete_event');self.login()
        self.assertTrue(permitted(self.user,self.event));self.assertFalse(permitted(self.user,self.event,True))
        self.assertEqual(self.client.post(reverse('event_delete',args=[self.event.pk]),{'confirm_delete':'delete'}).status_code,302)
        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())
    def test_global_create_allows_both_stages(self):
        self.grant('map.add_event');self.assertTrue(can_create_events(self.user));require_creation_stages(self.user,[self.a,self.b]);self.login()
        self.assertEqual(self.client.get('/admin/veranstaltung-anlegen/').status_code,302)
    def test_create_only_user_gets_personal_rights_on_new_own_event(self):
        from map.event_wizard import create_event
        self.grant('map.add_event')
        data=[{'title':'Selbst angelegt9','description':'','groups':ScoutGroup.objects.filter(pk=self.a.pk)}, {'starts_at':self.event.starts_at,'registration_opens':self.event.registration_opens,'registration_closes':self.event.registration_closes}, {'capacity':20,'waitlist_enabled':True,'confirmation_required':False,'confirmation_hours':48}, {'form_template':self.template}, {'viewers':[],'editors':[]}]
        created=create_event(data,False,'only-create9',self.user)
        self.assertTrue(EventPermission.objects.filter(event=created,user=self.user,role='editor').exists())
        self.assertTrue(permitted(self.user,created,True));self.assertFalse(permitted(self.user,self.event,True))
    def test_each_management_permission_unlocks_only_its_destination(self):
        cases={'auth.change_user':'people','auth.change_group':'roles','map.change_scoutgroup':None,'map.change_mailconfiguration':'mail_settings','map.view_emailjob':'mail_queue','map.change_emailjob':'mail_queue','map.delete_emailjob':'mail_queue','map.change_emailtemplate':'email_templates'}
        for code,name in cases.items():
            with self.subTest(code=code):
                self.user.user_permissions.clear();self.grant(code);self.login()
                if name:self.assertEqual(self.client.get(reverse(name)).status_code,200)
                else:self.assertEqual(self.client.get('/admin/map/scoutgroup/').status_code,200)
                self.assertFalse(permitted(self.user,self.event));self.assertFalse(can_create_events(self.user))
                self.assertFalse(granted(self.user,'map.change_event'))
    def test_global_template_permission_controls_builder(self):
        self.grant('map.change_formtemplate');self.login()
        self.assertEqual(self.client.get(reverse('map_form_builder',args=[self.template.pk])).status_code,200)
        self.assertFalse(permitted(self.user,self.event,True))
    def test_stage_roles_are_created_immediately_with_all_four_permissions(self):
        stage=ScoutGroup.objects.create(name='Rover9');binding=StageRole.objects.get(stage=stage)
        self.assertEqual(set(binding.group.permissions.values_list('codename',flat=True)),{stage_code(stage.pk,action) for action in STAGE_ACTIONS})
    def test_automatic_stage_role_grants_additional_stage_to_leader(self):
        profile=LeaderProfile.objects.create(user=self.user,is_leader=True);profile.stages.add(self.a)
        self.user.groups.add(StageRole.objects.get(stage=self.b).group)
        self.assertTrue(permitted(self.user,self.event,True));self.assertTrue(permitted(self.user,self.foreign,True));self.assertTrue(can_delete_event(self.user,self.foreign))
        self.user.groups.remove(StageRole.objects.get(stage=self.b).group)
        self.assertFalse(permitted(self.user,self.foreign));self.assertTrue(permitted(self.user,self.event,True))
    def test_leader_automatic_rights_do_not_require_duplicate_checkboxes(self):
        profile=LeaderProfile.objects.create(user=self.user,is_leader=True);profile.stages.add(self.a)
        self.assertFalse(self.user.user_permissions.exists())
        for action in STAGE_ACTIONS:self.assertIn(self.a.pk,stage_ids(self.user,action))
        self.assertTrue(permitted(self.user,self.event,True));self.assertTrue(can_delete_event(self.user,self.event));require_creation_stages(self.user,[self.a])
    def test_direct_stage_read_cannot_create_edit_or_delete(self):
        self.grant('map.'+stage_code(self.a.pk,'view'));self.login()
        self.assertTrue(permitted(self.user,self.event));self.assertFalse(permitted(self.user,self.event,True));self.assertFalse(can_delete_event(self.user,self.event));self.assertFalse(can_create_events(self.user))
        self.assertEqual(self.client.get(reverse('export_csv',args=[self.event.pk])).status_code,200)
        self.assertFalse(permitted(self.user,self.foreign))
    def test_direct_stage_create_cannot_create_foreign_stage(self):
        self.grant('map.'+stage_code(self.a.pk,'add'));require_creation_stages(self.user,[self.a])
        with self.assertRaises(ValidationError):require_creation_stages(self.user,[self.b])
        self.assertTrue(can_create_events(self.user));self.assertFalse(permitted(self.user,self.event,True))
    def test_direct_stage_edit_cannot_delete_or_edit_foreign_stage(self):
        self.grant('map.'+stage_code(self.a.pk,'change'));self.assertTrue(permitted(self.user,self.event,True))
        self.assertFalse(can_delete_event(self.user,self.event));self.assertFalse(permitted(self.user,self.foreign,True))
    def test_direct_stage_delete_does_not_grant_edit(self):
        self.grant('map.'+stage_code(self.a.pk,'delete'));self.assertTrue(can_delete_event(self.user,self.event));self.assertFalse(permitted(self.user,self.event,True));self.assertFalse(can_delete_event(self.user,self.foreign))
    def test_mixed_event_needs_all_stages_for_edit_and_delete(self):
        EventGroup.objects.create(event=self.event,group=self.b,capacity=10)
        for action in STAGE_ACTIONS:self.grant('map.'+stage_code(self.a.pk,action))
        self.assertTrue(permitted(self.user,self.event));self.assertFalse(permitted(self.user,self.event,True));self.assertFalse(can_delete_event(self.user,self.event))
        for action in ['change','delete']:self.grant('map.'+stage_code(self.b.pk,action))
        self.assertTrue(permitted(self.user,self.event,True));self.assertTrue(can_delete_event(self.user,self.event))
    def test_inactive_account_denies_all_sources(self):
        self.user.groups.add(Group.objects.get(name='Admin'));self.user.is_active=False;self.user.save()
        for action in STAGE_ACTIONS:self.assertEqual(stage_ids(self.user,action),set())
        self.assertFalse(permitted(self.user,self.event));self.assertFalse(can_delete_event(self.user,self.event));self.assertFalse(granted(self.user,'auth.change_user'))
    def test_readonly_blocks_stage_and_global_event_writes(self):
        self.user.groups.add(Group.objects.get(name='Read-Only'),StageRole.objects.get(stage=self.a).group)
        for code in ['map.add_event','map.change_event','map.delete_event','map.change_formtemplate']:self.grant(code)
        self.assertFalse(permitted(self.user,self.event,True));self.assertFalse(can_delete_event(self.user,self.event));self.assertFalse(can_create_events(self.user));self.assertFalse(can_templates(self.user))
    def test_renaming_stage_preserves_role_membership_and_codes(self):
        binding=StageRole.objects.get(stage=self.a);self.user.groups.add(binding.group)
        before=set(binding.group.permissions.values_list('pk',flat=True));self.a.name='Wös umbenannt';self.a.save();binding.group.refresh_from_db()
        self.assertIn('Wös umbenannt',binding.group.name);self.assertEqual(before,set(binding.group.permissions.values_list('pk',flat=True)));self.assertTrue(self.user.groups.filter(pk=binding.group.pk).exists())
    def test_deleting_unused_stage_removes_its_role_and_permissions(self):
        stage=ScoutGroup.objects.create(name='Vorübergehend9');role=StageRole.objects.get(stage=stage);group_id=role.group_id;permission_ids=list(role.group.permissions.values_list('pk',flat=True));stage.delete()
        self.assertFalse(Group.objects.filter(pk=group_id).exists());self.assertFalse(Permission.objects.filter(pk__in=permission_ids).exists())
    def test_stage_role_never_adopts_a_colliding_custom_group(self):
        self.a.name='Kollision';Group.objects.create(name='Stufe: Kollision ['+str(self.a.pk)+']');self.a.save()
        role=StageRole.objects.get(stage=self.a);self.assertTrue(permitted(self.admin,self.event));self.assertEqual(role.group.permissions.count(),4)
        self.assertEqual(Group.objects.get(name='Stufe: Kollision ['+str(self.a.pk)+']').permissions.count(),0)
    def test_role_editor_saves_permissions_that_really_apply(self):
        form=RoleForm({'name':'Lesen nur Wös','stage_'+str(self.a.pk):[self.permission('map.'+stage_code(self.a.pk,'view')).pk]})
        self.assertTrue(form.is_valid(),form.errors);role=form.save();self.user.groups.add(role)
        self.assertTrue(permitted(self.user,self.event));self.assertFalse(permitted(self.user,self.foreign));self.assertFalse(permitted(self.user,self.event,True))
    def test_person_editor_saves_roles_stages_and_direct_rights(self):
        form=PersonForm({'username':self.user.username,'is_active':'on','is_leader':'on','leader_stages':[self.a.pk],'roles':[StageRole.objects.get(stage=self.b).group_id]},instance=self.user)
        self.assertTrue(form.is_valid(),form.errors);form.save()
        self.assertTrue(permitted(self.user,self.event,True));self.assertTrue(permitted(self.user,self.foreign,True))
    def test_person_editor_keeps_existing_password_when_empty(self):
        self.user.set_password('Old-password-593!');self.user.save();old=self.user.password
        form=PersonForm({'username':self.user.username,'is_active':'on'},instance=self.user);self.assertTrue(form.is_valid(),form.errors);form.save();self.user.refresh_from_db();self.assertEqual(self.user.password,old)
    def test_unsupported_technical_permissions_are_not_silently_removed(self):
        technical=self.permission('map.view_auditlog');self.user.user_permissions.add(technical)
        form=PersonForm({'username':self.user.username,'is_active':'on'},instance=self.user);self.assertTrue(form.is_valid(),form.errors);form.save();self.assertTrue(self.user.user_permissions.filter(pk=technical.pk).exists())
    def test_last_active_admin_cannot_be_disabled(self):
        form=PersonForm({'username':self.admin.username},instance=self.admin);self.assertTrue(form.is_valid(),form.errors)
        with self.assertRaises(ValidationError):form.save()
        self.admin.refresh_from_db();self.assertTrue(self.admin.is_active)
    def test_builtin_and_stage_roles_cannot_be_changed(self):
        self.login(self.admin)
        for group in [Group.objects.get(name='Manager'),StageRole.objects.get(stage=self.a).group]:
            self.assertEqual(self.client.get(reverse('role_edit',args=[group.pk])).status_code,200)
            self.assertEqual(self.client.post(reverse('role_edit',args=[group.pk]),{'name':'Unzulässig'}).status_code,403)
    def test_modern_user_ui_works_on_old_and_new_urls(self):
        self.login(self.admin)
        for url in [reverse('people'),reverse('person_edit',args=[self.user.pk]),reverse('admin:auth_user_changelist'),reverse('admin:auth_user_change',args=[self.user.pk])]:
            response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertTemplateUsed(response,'base.html');self.assertNotContains(response,'name="is_staff"')
        self.assertContains(self.client.get(reverse('person_edit',args=[self.user.pk])),'Tatsächlich wirksamer Stufenzugriff')
    def test_effective_access_matches_saved_direct_rights(self):
        self.grant('map.'+stage_code(self.a.pk,'change'));rows={row['name']:row for row in effective_access(self.user)}
        self.assertEqual([right['allowed'] for right in rows[self.a.name]['rights']],[True,False,True,False])
    def test_new_management_posts_require_csrf(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        for name in ['person_new','role_new']:self.assertEqual(client.post(reverse(name),{}).status_code,403)
