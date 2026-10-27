import ast,hashlib,json,sys,unittest,importlib.util
from pathlib import Path
from types import SimpleNamespace
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT.resolve()))
from map.payment_rules import normalized_costs,payment_visible,COST_FIELDS
ns={'hashlib':hashlib,'json':json,'COST_FIELDS':COST_FIELDS,'payment_visible':payment_visible}
source=ast.parse((ROOT/'map/payments.py').read_text(encoding='utf-8'));functions=[]
for node in source.body:
 if isinstance(node,ast.FunctionDef) and node.name in ['payment_fingerprint','payment_job_is_current']:
  node.body=[item for item in node.body if not isinstance(item,ast.ImportFrom)];functions.append(node)
exec(compile(ast.Module(body=functions,type_ignores=[]),'payment guards','exec'),ns)
spec=importlib.util.spec_from_file_location('policy_checks',ROOT/'checks/permission_checks.py');policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
ns['can_users']=policy.ns['can_users']
functions=[n for n in ast.parse((ROOT/'map/account_security.py').read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name in ['technical_admin','can_edit_person']]
exec(compile(ast.Module(body=functions,type_ignores=[]),'account gates','exec'),ns)
class SecurityGateTests(unittest.TestCase):
 def event(self):
  event=SimpleNamespace(**normalized_costs({'cost_mode':'fixed','cost_amount':'25.50','payment_method':'transfer','bank_account_holder':'Stamm','bank_iban':'DE89370400440532013000'}));event.payment_released_at=None;return event
 def job(self):
  event=self.event();row=SimpleNamespace(status='confirmed',payment_received_at=None,event=event)
  return SimpleNamespace(registration_id=1,registration=row,payment_request=True,payment_fingerprint=ns['payment_fingerprint'](event))
 def test_current_confirmed_payment_job_is_allowed(self):self.assertTrue(ns['payment_job_is_current'](self.job()))
 def test_cancelled_pending_waitlisted_and_expired_payment_jobs_are_denied(self):
  for status in ['cancelled','pending','waitlisted','expired']:
   job=self.job();job.registration.status=status;self.assertFalse(ns['payment_job_is_current'](job),status)
 def test_received_payment_is_not_requested_again(self):
  job=self.job();job.registration.payment_received_at='received';self.assertFalse(ns['payment_job_is_current'](job))
 def test_changed_bank_or_fee_data_invalidates_queued_request(self):
  for name,value in [('bank_account_holder','Neu'),('bank_iban','DE12500105170648489890'),('payment_note','Neue Anweisung'),('cost_amount','26.00')]:
   job=self.job();setattr(job.registration.event,name,value);self.assertFalse(ns['payment_job_is_current'](job),name)
 def test_unreleased_reminder_does_not_leave_queue(self):
  job=self.job();job.registration.event.payment_method='reminder';job.payment_fingerprint=ns['payment_fingerprint'](job.registration.event);self.assertFalse(ns['payment_job_is_current'](job))
 def test_orphaned_payment_job_cannot_send(self):
  job=self.job();job.registration_id=None;self.assertFalse(ns['payment_job_is_current'](job))
 def test_non_payment_legacy_job_still_sends(self):self.assertTrue(ns['payment_job_is_current'](SimpleNamespace(registration_id=None,payment_request=False,payment_fingerprint='')))
 def test_business_admin_cannot_modify_technical_user(self):
  admin=policy.actor('Admin');target=policy.actor();target.is_superuser=True;self.assertFalse(ns['can_edit_person'](admin,target))
 def test_technical_admin_can_modify_technical_user(self):
  admin=policy.actor();admin.is_superuser=True;target=policy.actor();target.is_superuser=True;self.assertTrue(ns['can_edit_person'](admin,target))
 def test_delegated_user_manager_can_modify_regular_user(self):self.assertTrue(ns['can_edit_person'](policy.actor(direct=['auth.change_user']),policy.actor()))
 def test_inactive_technical_admin_has_no_authority(self):
  admin=policy.actor(active=False);admin.is_superuser=True;self.assertFalse(ns['technical_admin'](admin));self.assertFalse(ns['can_edit_person'](admin,policy.actor()))

if __name__=='__main__':unittest.main(verbosity=2)
