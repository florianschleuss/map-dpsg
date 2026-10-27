import unittest
from types import SimpleNamespace
from email.utils import parseaddr
from email.header import decode_header,make_header
from map.email_content import TEMPLATES,DEFAULT_BODY,default_content,effective_content,render_content,example_context,status_explanation
from map.mail_presentation import FOOTER,SENDER_NAME,with_footer,html_message,sender_address

class MailPresentationTests(unittest.TestCase):
    def test_notification_templates_are_distinct(self):
        values=[default_content(k) for k in TEMPLATES]
        self.assertEqual(len(set(s for s,b in values)),len(values))
        self.assertEqual(len(set(b for s,b in values)),len(values))
    def test_footer_is_always_present_once(self):
        for key in TEMPLATES:
            _,body=render_content(*default_content(key),key,example_context(key))
            self.assertTrue(body.endswith(FOOTER));self.assertEqual(with_footer(body),body)
    def test_html_footer_is_small_and_escaped(self):
        html=html_message('<script>alert(1)</script>\nhttps://example.org/manage/abc/')
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
        self.assertIn('font-size:12px',html);self.assertIn('href="https://example.org/manage/abc/"',html)
    def test_injected_html_attributes_are_escaped(self):
        html=html_message('https://example.org/" onclick="alert(1)')
        self.assertNotIn('href="https://example.org/"',html);self.assertNotIn(' onclick="',html)
    def test_sender_keeps_real_address(self):
        name,address=parseaddr(sender_address('No Reply <anmeldung@example.org>'))
        self.assertEqual(str(make_header(decode_header(name))),SENDER_NAME);self.assertEqual(address,'anmeldung@example.org')
    def test_sender_rejects_header_injection(self):
        with self.assertRaises(ValueError):sender_address('a@example.org\nBcc: secret@example.org')
    def test_legacy_shipped_template_is_upgraded(self):
        saved=SimpleNamespace(subject='{notification}: {event_title}',body=DEFAULT_BODY)
        self.assertEqual(effective_content('registration',saved),default_content('registration'))
    def test_old_special_defaults_are_updated_without_overwriting_custom_text(self):
        from map.email_content import LEGACY_SPECIAL
        for key,(subject,body) in LEGACY_SPECIAL.items():
            self.assertEqual(effective_content(key,SimpleNamespace(subject=subject,body=body)),default_content(key))
            self.assertEqual(effective_content(key,SimpleNamespace(subject=subject,body=body+' Zusatz')), (subject,body+' Zusatz'))
    def test_custom_template_is_preserved(self):
        saved=SimpleNamespace(subject='Unser Lager',body=DEFAULT_BODY)
        self.assertEqual(effective_content('registration',saved),('Unser Lager',DEFAULT_BODY))
    def test_waitlist_message_does_not_promise_place(self):
        body=render_content(*default_content('confirmed'),'confirmed',example_context('confirmed','waitlisted'))[1]
        self.assertIn('keine Platzzusage',body);self.assertNotIn('Die Teilnahme ist bestätigt.',body)
    def test_pending_explains_confirmation(self):
        self.assertIn('bestätige deine E-Mail-Adresse',status_explanation('pending',False))
    def test_expired_and_cancelled_do_not_contain_active_confirmation_links(self):
        for key in ['expired','cancelled']:
            body=render_content(*default_content(key),key,example_context(key))[1]
            self.assertNotIn('/confirm/',body);self.assertIn('keine',body)
    def test_maximum_valid_custom_body_can_receive_automatic_sections(self):
        body='{confirmation_section} {manage_url}'
        body+='x'*(20000-len(body))
        rendered=render_content('Eigene Vorlage',body,'registration',example_context())[1]
        self.assertIn('Bitte noch nicht überweisen',rendered)
        self.assertTrue(rendered.endswith(FOOTER))
    def test_custom_mail_gets_status_and_footer(self):
        body=render_content('Eigener Betreff','{confirmation_section}\n{manage_url}','changed',example_context('changed','waitlisted'))[1]
        self.assertIn('Warteliste',body);self.assertTrue(body.endswith(FOOTER))

if __name__=='__main__':unittest.main()

class MailHtmlLayoutTests(unittest.TestCase):
    def test_paragraphs_and_lines_do_not_depend_on_whitespace_css(self):
        result=html_message('Hallo,\n\nVeranstaltung: Lager\nKind: Beispiel\n\nDanke!')
        self.assertIn('Veranstaltung: Lager<br>Kind: Beispiel',result)
        self.assertIn('Hallo,</p><p ',result)
        self.assertNotIn('white-space:',result)
    def test_windows_and_mac_line_breaks_are_preserved(self):
        for newline in ['\r\n','\r','\n']:
            result=html_message('Erste'+newline+'Zweite'+newline+newline+'Dritte')
            self.assertIn('Erste<br>Zweite</p>',result)
            self.assertIn('Dritte</p>',result)
    def test_links_and_user_input_remain_escaped(self):
        result=html_message('<img src=x onerror="alert(1)">\nhttps://example.org/manage/token/?a=1&b=2')
        self.assertNotIn('<img ',result)
        self.assertIn('&lt;img',result)
        self.assertIn('href="https://example.org/manage/token/?a=1&amp;b=2"',result)
    def test_all_system_templates_have_structural_paragraphs(self):
        for key in TEMPLATES:
            subject,body=render_content(*default_content(key),key,example_context(key))
            result=html_message(body)
            self.assertGreaterEqual(result.count('<p '),3)
            self.assertEqual(result.count(FOOTER),1)
    def test_footer_is_outside_body_paragraphs_and_smaller(self):
        result=html_message('Text')
        self.assertLess(result.index('Text</p>'),result.index('<hr '))
        self.assertIn('font-size:12px;line-height:18px',result)
