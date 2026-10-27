"""Execute the actual permission functions with lightweight database doubles."""
import ast,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent.parent
ns={}
class ValidationError(Exception):pass
ns['ValidationError']=ValidationError
class Q:
 def __init__(self,**kwargs):self.users=list(kwargs.values())
 def __or__(self,other):obj=Q();obj.users=self.users+other.users;return obj
ns['Q']=Q
class ValueRows:
 def __init__(self,values):self.values=values
 def values_list(self,*args,**kwargs):return self
 def distinct(self):return self
 def __iter__(self):return iter(self.values)
class PermissionManager:
 def filter(self,query):
  actor=query.users[0];return ValueRows([tuple(code.split('.',1)) for code in actor.direct|actor.role_codes])
ns['Permission']=SimpleNamespace(objects=PermissionManager())
class ProfileManager:
 def filter(self,**kwargs):
  actor=kwargs['user'];self.ids=actor.stages if actor.is_leader else set();return self
 def exclude(self,**kwargs):return self
 def values_list(self,*args,**kwargs):return list(self.ids)
ns['LeaderProfile']=SimpleNamespace(objects=ProfileManager())
ns['ScoutGroup']=SimpleNamespace(objects=SimpleNamespace(values_list=lambda *args,**kwargs:[1,2,3]))
class Names:
 def __init__(self,names):self.names=set(names)
 def filter(self,**kwargs):return SimpleNamespace(exists=lambda:kwargs['name'] in self.names)
class EventPermissions:
 def __init__(self,roles):self.roles=set(roles)
 def filter(self,**kwargs):return SimpleNamespace(exists=lambda:bool(self.roles & set(kwargs.get('role__in',[kwargs.get('role')]))))
class Slots:
 def __init__(self,ids):self.ids=set(ids)
 def filter(self,**kwargs):return self
 def values_list(self,*args,**kwargs):return self.ids

def actor(*roles,direct=(),stages=(),leader=False,active=True,authenticated=True):return SimpleNamespace(is_superuser=False,is_active=active,is_authenticated=authenticated,groups=Names(roles),direct=set(direct),role_codes=set(),stages=set(stages),is_leader=leader)
def event(*stages,explicit=()):return SimpleNamespace(group_slots=Slots(stages),group_id=1,eventpermission_set=EventPermissions(explicit))
for path in ['map/access.py','map/roles.py','map/services.py']:
 tree=ast.parse((ROOT/path).read_text(encoding='utf-8'))
 selected=[]
 for node in tree.body:
  if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id in ['GLOBAL_RIGHTS','STAGE_ACTIONS'] for target in node.targets):selected.append(node)
  if not isinstance(node,ast.FunctionDef):continue
  if path.endswith('services.py') and node.name!='permitted':continue
  if node.name in ['supported_permissions','visible_events','portal_context']:continue
  node.body=[item for item in node.body if not isinstance(item,(ast.Import,ast.ImportFrom))]
  selected.append(node)
 exec(compile(ast.Module(body=selected,type_ignores=[]),path,'exec'),ns)
class PermissionPolicyTests(unittest.TestCase):
 def test_every_global_permission_is_recognized_and_not_broader(self):
  targets={'auth.change_user':'can_users','auth.change_group':'can_roles','map.change_scoutgroup':'can_stages','map.change_mailconfiguration':'can_mail_settings','map.change_emailtemplate':'can_mail_templates','map.change_formtemplate':'can_templates'}
  for code,helper in targets.items():
   user=actor(direct=[code]);self.assertTrue(ns[helper](user),code)
   for other in targets.values():
    if other!=helper:self.assertFalse(ns[other](user),(code,other))
   self.assertFalse(ns['permitted'](user,event(1)),code)
 def test_global_event_read_add_change_delete_remain_separate(self):
  expected={'view':(True,False,False,False),'add':(False,True,False,False),'change':(True,False,True,False),'delete':(True,False,False,True)}
  for action,values in expected.items():
   user=actor(direct=['map.'+action+'_event']);target=event(1)
   self.assertEqual((ns['permitted'](user,target),ns['can_create_events'](user),ns['permitted'](user,target,True),ns['can_delete_event'](user,target)),values,action)
 def test_queue_rights_are_independent(self):
  for action in ['view','change','delete']:
   user=actor(direct=['map.'+action+'_emailjob']);self.assertTrue(ns['can_queue'](user))
   self.assertEqual(ns['can_queue'](user,'change'),action=='change');self.assertEqual(ns['can_queue'](user,'delete'),action=='delete')
 def test_each_stage_permission_applies_only_to_its_stage_and_action(self):
  for stage in [1,2,3]:
   for action in ['view','add','change','delete']:
    user=actor(direct=['map.'+ns['stage_code'](stage,action)])
    self.assertTrue(ns['permitted'](user,event(stage)))
    self.assertEqual(ns['can_create_events'](user),action=='add')
    self.assertEqual(ns['permitted'](user,event(stage),True),action=='change')
    self.assertEqual(ns['can_delete_event'](user,event(stage)),action=='delete')
    for foreign in {1,2,3}-{stage}:
     self.assertFalse(ns['permitted'](user,event(foreign)));self.assertFalse(ns['can_delete_event'](user,event(foreign)))
 def test_leader_gets_automatic_own_stage_rights(self):
  user=actor(stages=[1],leader=True)
  for action in ['view','add','change','delete']:self.assertEqual(ns['stage_ids'](user,action),{1})
  self.assertTrue(ns['permitted'](user,event(1),True));self.assertFalse(ns['permitted'](user,event(2)))
 def test_additional_role_codes_extend_but_do_not_replace_own_stage(self):
  user=actor(stages=[1],leader=True);user.role_codes={"map."+ns['stage_code'](2,action) for action in ['view','add','change','delete']}
  self.assertTrue(ns['permitted'](user,event(1),True));self.assertTrue(ns['permitted'](user,event(2),True));self.assertTrue(ns['can_delete_event'](user,event(1,2)))
  user.role_codes.clear();self.assertFalse(ns['permitted'](user,event(2)));self.assertTrue(ns['permitted'](user,event(1)))
 def test_shared_events_require_all_stages_for_edit_and_delete(self):
  user=actor(stages=[1],leader=True);target=event(1,2)
  self.assertTrue(ns['permitted'](user,target));self.assertFalse(ns['permitted'](user,target,True));self.assertFalse(ns['can_delete_event'](user,target))
  user.direct.add('map.change_stage_2');self.assertTrue(ns['permitted'](user,target,True));self.assertFalse(ns['can_delete_event'](user,target))
  user.direct.add('map.delete_stage_2');self.assertTrue(ns['can_delete_event'](user,target))
 def test_revoked_leader_status_removes_automatic_rights_immediately(self):
  user=actor(stages=[1],leader=True);user.is_leader=False
  self.assertFalse(ns['permitted'](user,event(1)));self.assertFalse(ns['can_create_events'](user))
 def test_readonly_blocks_all_event_writes_even_with_additional_grants(self):
  user=actor('Read-Only',stages=[1],leader=True,direct=['map.add_event','map.change_event','map.delete_event','map.change_formtemplate'])
  self.assertTrue(ns['permitted'](user,event(2)));self.assertFalse(ns['permitted'](user,event(1),True));self.assertFalse(ns['can_delete_event'](user,event(1)));self.assertFalse(ns['can_create_events'](user));self.assertFalse(ns['can_templates'](user))
 def test_admin_and_manager_precede_readonly(self):
  for role in ['Admin','Manager']:
   user=actor(role,'Read-Only');self.assertTrue(ns['permitted'](user,event(2),True));self.assertTrue(ns['can_delete_event'](user,event(2)));self.assertTrue(ns['can_create_events'](user))
 def test_inactive_and_anonymous_have_no_access_from_any_source(self):
  for user in [actor('Admin',active=False,leader=True,stages=[1]),actor('Admin',authenticated=False,leader=True,stages=[1])]:
   for helper in ['can_users','can_roles','can_stages','can_mail_settings','can_mail_templates','can_templates','can_create_events']:self.assertFalse(ns[helper](user),helper)
   self.assertFalse(ns['permitted'](user,event(1),True));self.assertFalse(ns['can_delete_event'](user,event(1)))
 def test_explicit_event_editor_remains_independent_of_stage(self):
  user=actor();target=event(2,explicit=['editor'])
  self.assertTrue(ns['permitted'](user,target));self.assertTrue(ns['permitted'](user,target,True));self.assertTrue(ns['can_delete_event'](user,target))
 def test_explicit_event_viewer_does_not_gain_writes(self):
  user=actor();target=event(2,explicit=['viewer'])
  self.assertTrue(ns['permitted'](user,target));self.assertFalse(ns['permitted'](user,target,True));self.assertFalse(ns['can_delete_event'](user,target))
 def test_creation_checks_each_requested_stage(self):
  user=actor(direct=['map.add_stage_1']);ns['require_creation_stages'](user,[SimpleNamespace(pk=1)])
  with self.assertRaises(ValidationError):ns['require_creation_stages'](user,[SimpleNamespace(pk=1),SimpleNamespace(pk=2)])
 def test_group_permission_revocation_is_not_masked_by_django_cache(self):
  user=actor();user.role_codes={'map.change_event'};self.assertTrue(ns['permitted'](user,event(2),True))
  user.role_codes.clear();self.assertFalse(ns['permitted'](user,event(2),True))
 def test_unsupported_technical_rights_do_not_grant_supported_portal_actions(self):
  user=actor(direct=['map.change_registration','auth.view_user','map.view_auditlog'])
  self.assertFalse(ns['permitted'](user,event(1)));self.assertFalse(ns['can_users'](user));self.assertFalse(ns['can_queue'](user))

if __name__=='__main__':unittest.main(verbosity=2)
