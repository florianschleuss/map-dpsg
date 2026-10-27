"""Exercise maintenance ordering and failures without Docker or real databases."""
import contextlib, importlib.util, io, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
scripts=Path(__file__).resolve().parent.parent/'scripts'
sys.path.insert(0,str(scripts))
import deploy, backup

class DeploymentTests(unittest.TestCase):
    def invoke(self,bootstrap=False,fail=None,count='0'):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'.env').write_text('SECRET_KEY=test-only')
            commands=[]
            def run(args,capture=False):
                commands.append(args)
                if fail=='tests' and args[-1]=='test':raise RuntimeError('test failure')
                if fail=='migration' and args==['--profile','tools','run','--rm','-T','init']:raise RuntimeError('migration failure')
                return SimpleNamespace(stdout=count)
            with patch.object(deploy,'ROOT',root),patch.object(deploy,'run',side_effect=run),patch.object(backup,'backup',side_effect=RuntimeError('backup') if fail=='backup' else None) as saved,patch.object(sys,'argv',['deploy']+(['--bootstrap'] if bootstrap else [])),contextlib.redirect_stdout(io.StringIO()):
                if fail or bootstrap and count!='0':
                    with self.assertRaises(RuntimeError):deploy.main()
                else:deploy.main()
            return commands,saved.call_count
    def test_tests_fail_before_stopping_or_migrating(self):
        commands,saved=self.invoke(fail='tests');self.assertNotIn(['stop','web','worker'],commands);self.assertEqual(saved,0)
    def test_update_orders_backup_before_migration(self):
        commands,saved=self.invoke();self.assertEqual(saved,1)
        self.assertLess(commands.index(['stop','web','worker']),commands.index(['--profile','tools','run','--rm','-T','init']))
    def test_failed_backup_restarts_old_containers_without_migration(self):
        commands,_=self.invoke(fail='backup');self.assertIn(['start','web','worker'],commands);self.assertNotIn(['--profile','tools','run','--rm','-T','init'],commands)
    def test_failed_migration_stops_without_automatic_database_restore(self):
        commands,_=self.invoke(fail='migration');self.assertEqual(commands[-1],['stop','web','worker']);self.assertFalse(any('pg_restore' in c for c in commands))
    def test_bootstrap_requires_empty_database(self):
        commands,saved=self.invoke(bootstrap=True,count='12');self.assertEqual(saved,0);self.assertNotIn(['--profile','tools','run','--rm','-T','init'],commands)
    def test_bootstrap_starts_without_copying_development_data(self):
        commands,saved=self.invoke(bootstrap=True);self.assertEqual(saved,0);self.assertIn(['up','-d','--no-build','--force-recreate','--wait','web','worker'],commands)
    def test_backup_rejects_empty_dump(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(backup.subprocess,'run'):
            root=Path(folder);(root/'.env').write_text('not-a-real-secret')
            with self.assertRaises(RuntimeError):backup.backup(root)
            self.assertFalse(list((root/'backups').glob('*.dump')))
    def test_backup_saves_dump_and_matching_configuration(self):
        def execute(args,**kwargs):
            if 'pg_dump' in args[-1]:kwargs['stdout'].write(b'fake-custom-dump-for-flow-test')
        with tempfile.TemporaryDirectory() as folder,patch.object(backup.subprocess,'run',side_effect=execute),contextlib.redirect_stdout(io.StringIO()):
            root=Path(folder);(root/'.env').write_text('test-only-config')
            saved=backup.backup(root)
            self.assertEqual(saved.read_bytes(),b'fake-custom-dump-for-flow-test');self.assertEqual(saved.with_suffix('.env').read_text(),'test-only-config')

if __name__=='__main__':unittest.main(verbosity=2)
