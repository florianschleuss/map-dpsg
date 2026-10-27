"""Dependency-free source/unit checks; does not import or start Django.
Run: python checks/static_checks.py
These checks do NOT replace the Django/PostgreSQL integration test suite.
"""
import ast
import hashlib
import json
import re
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class ValidationError(Exception):
    pass

def load_pure(path, name, extra=None):
    tree = ast.parse((ROOT/path).read_text(encoding='utf-8'))
    node = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == name)
    namespace = {'hashlib': hashlib, 'json': json, 'unicodedata': unicodedata, 're': re, 'ValidationError': ValidationError}
    namespace.update(extra or {})
    exec(compile(ast.Module(body=[node], type_ignores=[]), path, 'exec'), namespace)
    return namespace[name]

identity = load_pure('map/services.py', 'identity')
csv_safe = load_pure('map/views.py', 'csv_safe')
validate_schema = load_pure('map/schema.py', 'validate_schema', {'FIELD_TYPES': {'text','textarea','email','integer','date','checkbox','select'}})

class StaticAndPureUnitTests(unittest.TestCase):
    def test_map_rename_is_consistent(self):
        self.assertTrue((ROOT/'map/models.py').is_file())
        self.assertEqual(ROOT.name, 'map')
        forbidden = ['scout' + '-registration', 'scout' + 's', 'scout' + '-link', 'Pfadfinder' + '-Anmeldung']
        for path in ROOT.rglob('*'):
            if not path.is_file() or path.name == 'MANIFEST.sha256' or path.suffix not in ['.py','.html','.js','.cjs','.md','.yaml','.yml','.txt','.svg'] or '__pycache__' in path.parts or '.rendered' in path.parts: continue
            content = path.read_text(encoding='utf-8-sig')
            for old in forbidden:
                self.assertNotIn(old, content, str(path))
        settings = (ROOT/'config/settings.py').read_text(encoding='utf-8')
        self.assertIn("'map'", settings)
        migration = (ROOT/'map/migrations/0001_initial.py').read_text(encoding='utf-8')
        self.assertIn("'map.event'", migration)
        self.assertIn('from map.models import new_token', migration)
        self.assertIn('COMPOSE_PROJECT_NAME', (ROOT/'compose.yaml').read_text(encoding='utf-8'))

    def test_all_python_sources_compile(self):
        sources=list(ROOT.rglob('*.py'))
        self.assertGreaterEqual(len(sources),20)
        for path in sources:
            with self.subTest(file=str(path.relative_to(ROOT))):
                compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec')
    def test_duplicate_normalization(self):
        self.assertEqual(identity('  ANNA   Kind ','PARENT@EXAMPLE.ORG'),identity('Anna Kind','parent@example.org'))
        self.assertEqual(identity('Ａｎｎａ Kind','p@example.org'),identity('Anna Kind','p@example.org'))
    def test_duplicate_distinguishes_children_and_emails(self):
        self.assertNotEqual(identity('Anna','p@example.org'),identity('Ben','p@example.org'))
        self.assertNotEqual(identity('Anna','p@example.org'),identity('Anna','q@example.org'))
    def test_identity_has_bounded_length(self):
        self.assertEqual(len(identity('ß'*160,'long@example.org')),64)
    def test_identity_delimiter_collision(self):
        self.assertNotEqual(identity('a|b','c@example.org'),identity('a','b|c@example.org'))
    def test_csv_formula_prefixes(self):
        for value in ['=1+1','+SUM(A1)','-1+1','@SUM(A1)','  =1','\ttext','\rtext','\ntext']:
            with self.subTest(value=value): self.assertTrue(csv_safe(value).startswith("'"))
    def test_csv_plain_values(self):
        for value in ['Anna Müller','01234','',42]: self.assertEqual(csv_safe(value),str(value))
    def test_valid_modular_schema(self):
        validate_schema([{'title':'Kontakt','fields':[{'key':'phone','type':'text','label':'Telefon','required':True}]}])
        validate_schema([])
    def test_duplicate_schema_keys_rejected_across_modules(self):
        spec={'key':'phone','type':'text','label':'Telefon'}
        with self.assertRaises(ValidationError): validate_schema([{'title':'A','fields':[spec]},{'title':'B','fields':[spec]}])
    def test_invalid_schema_types_and_keys(self):
        for key,kind in [('bad-key','text'),('1key','text'),('valid','file')]:
            with self.assertRaises(ValidationError): validate_schema([{'title':'A','fields':[{'key':key,'type':kind,'label':'Field'}]}])
    def test_invalid_select_choices(self):
        for values in [[],['a','a'],None]:
            with self.assertRaises(ValidationError): validate_schema([{'title':'A','fields':[{'key':'choice','type':'select','label':'Auswahl','choices':values}]}])
    def test_schema_required_must_be_boolean(self):
        with self.assertRaises(ValidationError): validate_schema([{'title':'A','fields':[{'key':'x','type':'text','label':'X','required':'yes'}]}])
    def test_migration_models_and_fields_match_source(self):
        modeltree=ast.parse((ROOT/'map/models.py').read_text(encoding='utf-8'))
        model_fields={}
        for cls in [x for x in modeltree.body if isinstance(x,ast.ClassDef)]:
            model_fields[cls.name]={'id'}
            for item in cls.body:
                if isinstance(item,ast.Assign) and isinstance(item.value,ast.Call) and isinstance(item.value.func,ast.Attribute) and isinstance(item.value.func.value,ast.Name) and item.value.func.value.id=='models':
                    model_fields[cls.name].add(item.targets[0].id)
        migrated={}
        for migration in sorted((ROOT/'map/migrations').glob('[0-9]*.py')):
            tree=ast.parse(migration.read_text(encoding='utf-8'))
            for call in [x for x in ast.walk(tree) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='CreateModel']:
                args={item.arg:item.value for item in call.keywords}
                migrated[ast.literal_eval(args['name'])]={ast.literal_eval(item.elts[0]) for item in args['fields'].elts}
            for call in [x for x in ast.walk(tree) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='AddField']:
                args={item.arg:item.value for item in call.keywords}
                name=next(name for name in migrated if name.lower()==ast.literal_eval(args['model_name']))
                migrated[name].add(ast.literal_eval(args['name']))
        self.assertEqual(model_fields,migrated)
        self.assertNotIn('choices=STATUS',(ROOT/'map/migrations/0001_initial.py').read_text(encoding='utf-8'))
    def test_no_live_env_or_database_in_deliverable(self):
        self.assertFalse((ROOT/'.env').exists())
        self.assertEqual(list(ROOT.rglob('*.sqlite3')),[])
    def test_no_mutation_on_get_in_link_views(self):
        tree=ast.parse((ROOT/'map/views.py').read_text(encoding='utf-8'))
        confirm=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='confirm_link')
        condition=next(x for x in ast.walk(confirm) if isinstance(x,ast.If) and "request.method == 'POST'"==ast.unparse(x.test))
        self.assertTrue(any(isinstance(x,ast.Call) and ast.unparse(x.func)=='svc.confirm' for x in ast.walk(condition)))
    def test_security_and_worker_files_included(self):
        for filename in ['deploy/Caddyfile.example','compose.yaml','compose.dev.yaml','compose.production.yaml','Dockerfile','map/management/commands/process_queue.py','map/tests/test_concurrency.py','scripts/backup.sh','scripts/restore.sh']:
            self.assertTrue((ROOT/filename).is_file(),filename)

if __name__=='__main__':
    unittest.main(verbosity=2)
