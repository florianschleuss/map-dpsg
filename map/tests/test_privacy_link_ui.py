from django.test import SimpleTestCase
from map.forms import RegistrationForm
from map.mail_presentation import html_message

class PrivacyAndMailUiTests(SimpleTestCase):
    def test_free_text_hints_preserve_existing_help(self):
        form=RegistrationForm(modules=[{'title':'Angaben','fields':[{'key':'notes','label':'Hinweis','type':'textarea','help':'Kurz halten.'},{'key':'phone','label':'Telefon','type':'text'}]}])
        for name in ['child_name','answer_notes','answer_phone']:
            self.assertIn('keine medizinischen Daten',form.fields[name].help_text)
        self.assertIn('Kurz halten.',form.fields['answer_notes'].help_text)
        self.assertNotIn('medizinischen',form.fields['email'].help_text)
    def test_html_links_have_labels_and_keep_exact_targets(self):
        from html.parser import HTMLParser
        class Links(HTMLParser):
            def __init__(self):super().__init__();self.links=[]
            def handle_starttag(self,tag,attrs):
                if tag=='a':self.links.append(dict(attrs)['href'])
        urls=['https://example.org/confirm/secret/?a=1&b=2','https://example.org/manage/secret/','https://example.org/konto/passwort/secret/']
        rendered=html_message('\n'.join(urls));parser=Links();parser.feed(rendered)
        self.assertEqual(parser.links,urls)
        self.assertIn('>E-Mail-Adresse bestätigen</a>',rendered)
        self.assertIn('>Anmeldung öffnen und verwalten</a>',rendered)
        self.assertIn('>Neues Passwort festlegen</a>',rendered)
        self.assertNotIn('>https://',rendered)
    def test_malformed_link_does_not_break_mail_rendering(self):
        self.assertIn('Link öffnen',html_message('https://[invalid'))
