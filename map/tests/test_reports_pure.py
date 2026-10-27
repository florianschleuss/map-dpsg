import unittest,zipfile
from io import BytesIO
from types import SimpleNamespace as Obj
from datetime import datetime,timezone
from xml.etree import ElementTree as ET
from map.registration_reports import categories,export_grid
from map.excel_export import workbook_bytes,column_name

def row(value='Vegan',label='Essen',choices=None,key='food',kind='select',included=True):
    field={'key':key,'label':label,'type':kind,'choices':choices or ['Vegan','Vegetarisch']}
    return Obj(pk=1,child_name='Alex',email='eltern@example.org',event_group_id=None,event=Obj(group=Obj(name='Wös')),get_status_display=lambda:'Bestätigt',email_verified=True,created_at=datetime(2026,10,27,10,tzinfo=timezone.utc),payment_received_at=None,schema_snapshot=[{'title':'Verpflegung','fields':[field]}],answers={key:value} if included else {})

class ReportTests(unittest.TestCase):
    def test_only_known_legacy_privacy_labels_are_normalized(self):
        from map.text_labels import question_label
        self.assertEqual(question_label('Veröffentlichung auf den Homepages'),'Veröffentlichung auf der Homepage')
        self.assertEqual(question_label('Eigene individuelle Fotoentscheidung'),'Eigene individuelle Fotoentscheidung')
        self.assertEqual(question_label('Meine eigene Frage'),'Meine eigene Frage')
    def test_food_counts_and_percentages(self):
        result=categories([row(),row(),row('Vegetarisch')])[0]
        self.assertEqual([(x['label'],x['count']) for x in result['options']],[('Vegan',2),('Vegetarisch',1)])
        self.assertEqual(result['total'],3);self.assertEqual(result['options'][0]['percent'],67)
    def test_missing_is_distinct_from_no(self):
        result=categories([row(False,kind='checkbox'),row(included=False,kind='checkbox')])[0]
        self.assertEqual(result['missing'],1)
        self.assertEqual(result['options'][1]['count'],1)
    def test_form_versions_with_different_choices_are_separate(self):
        self.assertEqual(len(categories([row(),row(choices=['Vegan','Fleisch'])])),2)
    def test_renamed_questions_are_separate(self):
        self.assertEqual(len(categories([row(),row(label='Allergien')])),2)
    def test_unasked_question_is_not_missing(self):
        other=row();other.schema_snapshot=[]
        self.assertEqual(categories([row(),other])[0]['total'],1)
    def test_free_text_and_contact_data_are_not_aggregated(self):
        self.assertEqual(categories([row('Geheime Angabe',kind='text'),row(kind='email')]),[])
    def test_zero_count_choices_are_kept(self):
        self.assertEqual(categories([row()])[0]['options'][1]['count'],0)
    def test_unknown_choice_is_not_silently_dropped(self):
        self.assertEqual(categories([row('Andere')])[0]['options'][-1]['label'],'Andere')
    def test_export_keeps_form_versions_in_separate_columns(self):
        grid=export_grid([row(),row(label='Andere Frage')])
        self.assertEqual(grid[1][-2:],['Vegan','']);self.assertEqual(grid[2][-2:],['','Vegan'])
    def test_export_boolean_is_german_and_integer_is_numeric(self):
        self.assertEqual(export_grid([row(False,kind='checkbox')])[1][-1],'Nein')
        self.assertEqual(export_grid([row(3,kind='integer')])[1][-1],3)

    def test_export_retains_legacy_answers_without_snapshot(self):
        legacy=row();legacy.schema_snapshot=[]
        self.assertEqual(export_grid([legacy])[1][-1],'Vegan')

class ExcelTests(unittest.TestCase):
    def read(self,grid):
        archive=zipfile.ZipFile(BytesIO(workbook_bytes(grid)))
        self.assertIsNone(archive.testzip())
        for name in archive.namelist():ET.fromstring(archive.read(name))
        return ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
    def test_xlsx_contains_valid_xml_and_required_parts(self):
        self.assertTrue(self.read([['Kind','Stufe'],['Alex','Wölflinge']]) is not None)
    def test_formula_like_text_remains_string(self):
        root=self.read([['Antwort'],['=HYPERLINK("https://evil.invalid")'],['+1'],['@SUM(A1)']])
        self.assertFalse(root.findall('.//{*}f'))
        self.assertTrue(all(c.get('t')=='inlineStr' for c in root.findall('.//{*}c')))
    def test_numbers_are_typed_and_emails_remain_text(self):
        root=self.read([['Zahl','E-Mail'],[12,'0012@example.org']]);cells=root.findall('.//{*}row')[1].findall('{*}c')
        self.assertIsNone(cells[0].get('t'));self.assertEqual(cells[1].get('t'),'inlineStr')
    def test_date_is_excel_serial_in_berlin_time(self):
        root=self.read([['Datum'],[datetime(2026,10,27,10,tzinfo=timezone.utc)]])
        cell=root.findall('.//{*}row')[1][0]
        self.assertEqual(cell.get('s'),'2')
        self.assertAlmostEqual(float(cell[0].text)%1,11/24,places=5)
    def test_header_frozen_and_filter_enabled(self):
        root=self.read([['Kind'],['Alex']]);self.assertIsNotNone(root.find('.//{*}pane'));self.assertEqual(root.find('{*}autoFilter').get('ref'),'A1:A2')
    def test_invalid_xml_controls_are_removed(self):
        root=self.read([['Text'],['A\x00B & <test>']]);self.assertIn('AB & <test>',''.join(root.itertext()))
    def test_empty_and_long_column_names(self):
        self.assertEqual(column_name(27),'AA');self.assertEqual(column_name(16384),'XFD')
        with self.assertRaises(ValueError):workbook_bytes([])
    def test_noncharacters_cannot_break_workbook_xml(self):
        root=self.read([['Antwort'],['A\ufffeB\uffffC']])
        self.assertIn('ABC',''.join(root.itertext()))
    def test_very_large_integers_are_safe_text_without_float_overflow(self):
        root=self.read([['Zahl'],[10**400]])
        cell=root.findall('.//{*}row')[1][0]
        self.assertEqual(cell.get('t'),'inlineStr')
        self.assertEqual(''.join(cell.itertext()),str(10**400))
    def test_no_external_links_macros_or_formulas(self):
        archive=zipfile.ZipFile(BytesIO(workbook_bytes([['Text'],['https://example.org']])))
        self.assertFalse(any('externalLink' in n or 'vba' in n for n in archive.namelist()))

if __name__=='__main__':unittest.main()
