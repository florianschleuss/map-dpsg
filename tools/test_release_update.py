"""Exercise production release ordering and rollback without Docker or real data."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('release_update',Path(__file__).resolve().parent.parent/'scripts/apply_release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

class ReleaseUpdateTests(unittest.TestCase):
    def invoke(self,failure=None,operator_assets=False):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            root=Path(directory)/'prod';source=Path(directory)/'release';root.mkdir();source.mkdir();(source/'deploy').mkdir()
            (root/'.env').write_text('SECRET_KEY=fixture-only');(root/'app.py').write_text('old source')
            (source/'app.py').write_text('new source');(source/'new.py').write_text('new module');(source/'compose.yaml').write_text('fixture')
            manifest={'paths':{'app.py':[hashlib.sha256(b'old source').hexdigest()],'new.py':[None]}}
            (source/'deploy/release-baselines.json').write_text(json.dumps(manifest))
            records={s:{'Config':{'Image':'map-prod:latest'},'Image':'old-image'} for s in ['web','worker','db']}
            calls=[];asset_checks=[]
            if operator_assets:
                (root/'operator-assets').mkdir();(root/'operator-assets/logo.svg').write_text('operator-owned')
            def compose(where,files,project,args,**kwargs):
                calls.append((where==root,project,args))
                if where==root and args[-1]=='check_production' and operator_assets:
                    override=json.loads(Path(files[-1]).read_text())
                    self.assertEqual(override['services']['init']['volumes'][0]['source'],str(root/'operator-assets'))
                    self.assertTrue(override['services']['init']['volumes'][0]['read_only']);asset_checks.append(True)
                if args[0]=='config':
                    return SimpleNamespace(stdout=json.dumps({'services':{'web':{'image':'map-prod:latest'},'test':{'environment':{'POSTGRES_HOST':'db' if failure=='test_isolation' else 'test-db','EMAIL_BACKEND':'django.core.mail.backends.locmem.EmailBackend'},'depends_on':{'test-db':{}}},'test-db':{}},'networks':{'default':{'name':project+'_default'}}}))
                if failure=='build' and args[0]=='build':raise RuntimeError('build failed')
                if args[-1]=='test':
                    if failure=='tests':raise RuntimeError('tests failed')
                    if failure=='operator_edit':(root/'app.py').write_text('operator edit')
                if failure=='production_check' and args[-1]=='check_production':raise RuntimeError('production check failed')
                if args[:3]==['exec','-T','db'] and 'pg_dump' in ' '.join(args):
                    if failure=='backup':raise RuntimeError('backup failed')
                    kwargs['stdout'].write(b'' if failure=='empty_backup' else b'PGDMP-fixture-backup')
                if failure=='verify_backup' and args[-1]=='--list':raise RuntimeError('invalid dump')
                if failure=='migration' and args[-1]=='--noinput':raise RuntimeError('migration failed')
                if failure=='startup' and args[0]=='up' and sum(a[2][0]=='up' for a in calls)==1:raise RuntimeError('startup failed')
                return SimpleNamespace(stdout='')
            if failure=='unknown_source':(root/'app.py').write_text('unknown')
            if failure=='existing_source_env':(source/'.env').write_text('do-not-delete')
            error=None
            with patch.object(release.os,'geteuid',return_value=0,create=True),patch.object(release,'discover',return_value=('map-prod',['compose.yaml'],{},records,'map-prod:latest')),patch.object(release,'compose',side_effect=compose),patch.object(release,'command',return_value=SimpleNamespace(stdout='')),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                try:release.apply(root,source)
                except RuntimeError as caught:error=caught
            if failure is None:
                self.assertIsNone(error);self.assertEqual((root/'app.py').read_text(),'new source');self.assertTrue((root/'new.py').exists())
                backup=next((root/'backups').iterdir());self.assertEqual((backup/'sources/app.py').read_text(),'old source');self.assertTrue((backup/'database.dump').exists())
                actions=[a[2] for a in calls]
                self.assertLess(next(i for i,a in enumerate(actions) if a[-1]=='test'),actions.index(['stop','web','worker']))
                self.assertLess(next(i for i,a in enumerate(actions) if a[-1]=='--list'),next(i for i,a in enumerate(actions) if a[-1]=='--noinput'))
            else:
                self.assertIsNotNone(error)
                self.assertEqual((root/'app.py').read_text(),'unknown' if failure=='unknown_source' else 'operator edit' if failure=='operator_edit' else 'old source')
                self.assertFalse((root/'new.py').exists())
                if failure in ['build','tests','production_check','unknown_source','operator_edit','test_isolation','existing_source_env']:
                    self.assertFalse(any(a[2][0]=='stop' for a in calls))
            if operator_assets:
                self.assertEqual(len(asset_checks),2);self.assertEqual((root/'operator-assets/logo.svg').read_text(),'operator-owned')
                self.assertFalse(list(source.glob('.map-production-check-*')))
            self.assertEqual((root/'.env').read_text(),'SECRET_KEY=fixture-only')
            if failure=='existing_source_env':self.assertEqual((source/'.env').read_text(),'do-not-delete')
            else:self.assertFalse((source/'.env').exists())
            for where,project,args in calls:
                if args[0:2]==['--profile','tools'] and args[-2:]==['down','-v']:self.assertNotEqual(project,'map-prod')
    def test_success(self):self.invoke()
    def test_operator_assets_are_available_to_readiness_checks_but_unchanged(self):self.invoke(operator_assets=True)
    def test_build_failure(self):self.invoke('build')
    def test_test_failure(self):self.invoke('tests')
    def test_production_readiness_failure(self):self.invoke('production_check')
    def test_backup_failure(self):self.invoke('backup')
    def test_empty_backup(self):self.invoke('empty_backup')
    def test_invalid_backup(self):self.invoke('verify_backup')
    def test_migration_failure(self):self.invoke('migration')
    def test_startup_failure(self):self.invoke('startup')
    def test_unknown_source(self):self.invoke('unknown_source')
    def test_concurrent_operator_edit_is_preserved(self):self.invoke('operator_edit')
    def test_test_database_isolation(self):self.invoke('test_isolation')
    def test_existing_release_credentials_are_never_removed(self):self.invoke('existing_source_env')

    def test_discover_rejects_non_production_and_shared_tags(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            root=Path(directory);(root/'compose.yaml').write_text('fixture')
            def record(service):return {'Config':{'Image':'map-prod:latest','Labels':{'com.docker.compose.project.working_dir':str(root),'com.docker.compose.service':service,'com.docker.compose.project':'map-prod','com.docker.compose.project.config_files':str(root/'compose.yaml')}}}
            records=[record(s) for s in ['web','worker','db']]
            config={'services':{s:{'image':'map-prod:latest','environment':{'MAP_PRODUCTION':'0','DEBUG':'0'}} for s in ['web','worker','init']}}
            with patch.object(release,'command',return_value=SimpleNamespace(stdout='ids')),patch.object(release,'docker_json',return_value=records),patch.object(release,'compose',return_value=SimpleNamespace(stdout=json.dumps(config))):
                with self.assertRaisesRegex(RuntimeError,'Produktionskonfiguration'):release.discover(root)
            config['services']['web']['environment']['MAP_PRODUCTION']='1'
            records.append({'Config':{'Image':'map-prod:latest','Labels':{}}})
            with patch.object(release,'command',return_value=SimpleNamespace(stdout='ids')),patch.object(release,'docker_json',return_value=records),patch.object(release,'compose',return_value=SimpleNamespace(stdout=json.dumps(config))):
                with self.assertRaisesRegex(RuntimeError,'anderen Stack'):release.discover(root)

    def test_explicit_obsolete_source_is_removed_and_can_be_restored(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            root=Path(directory);(root/'obsolete.html').write_text('old view')
            values=release.read_sources(root,{'paths':{'obsolete.html':[None]},'remove':['obsolete.html']})
            self.assertIsNone(values['obsolete.html'])
            release.write_files(root,values);self.assertFalse((root/'obsolete.html').exists())
            release.write_files(root,{'obsolete.html':b'old view'});self.assertEqual((root/'obsolete.html').read_bytes(),b'old view')

    def test_manifest_path_escape_is_refused(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            source=Path(directory)/'release';source.mkdir();(Path(directory)/'outside').write_text('private')
            with self.assertRaises(RuntimeError):release.read_sources(source,{'paths':{'../outside':[None]}})

if __name__=='__main__':unittest.main(verbosity=2)
