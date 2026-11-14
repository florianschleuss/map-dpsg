"""Check public brand-name configuration using dummy files and mocked Docker calls."""
import contextlib,io,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'scripts'))
import configure_brand as brand

class BrandConfigurationTests(unittest.TestCase):
    def invoke(self,fail=False):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();env=root/'.env'
            previous=b'SECRET_KEY=fictional-only\r\nMAP_ORGANIZATION="Formal operator"\r\nMAP_BRAND_ORGANIZATION="Old"\r\n'
            env.write_bytes(previous)
            with patch.object(brand,'discover',return_value=('prod',['compose.yaml'],{}, {},'image')),patch.object(brand,'compose',side_effect=[RuntimeError('restart failed'),None] if fail else None) as compose,contextlib.redirect_stdout(io.StringIO()):
                if fail:
                    with self.assertRaisesRegex(RuntimeError,'restart failed'):brand.configure(root,'Display name')
                    self.assertEqual(env.read_bytes(),previous);self.assertEqual(compose.call_count,2)
                else:
                    brand.configure(root,'Display name');brand.configure(root,'Display name')
                    data=env.read_bytes();self.assertIn(b'SECRET_KEY=fictional-only\r\n',data)
                    self.assertIn(b'MAP_ORGANIZATION="Formal operator"',data)
                    self.assertEqual(data.count(b'MAP_BRAND_ORGANIZATION='),1)
                    self.assertIn(b'MAP_BRAND_ORGANIZATION="Display name"',data)
                    self.assertEqual(compose.call_count,1);self.assertEqual(compose.call_args.args[3][-1],'web')
                self.assertEqual(next((root/'backups').glob('brand-env-*.env')).read_bytes(),previous)
    def test_preserve_settings_and_idempotent_configuration(self):self.invoke()
    def test_restart_failure_restores_original_configuration(self):self.invoke(fail=True)
    def test_invalid_name_does_not_touch_files_or_docker(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();(root/'.env').write_bytes(b'UNCHANGED=yes\n')
            for name in ['', 'x\nSECRET=changed', '${SECRET_KEY}']:
                with patch.object(brand,'discover') as discover,self.assertRaises(RuntimeError):brand.configure(root,name)
                discover.assert_not_called();self.assertEqual((root/'.env').read_bytes(),b'UNCHANGED=yes\n')
if __name__=='__main__':unittest.main(verbosity=2)
