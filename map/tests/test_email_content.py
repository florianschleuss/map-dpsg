import unittest
from map.email_content import TEMPLATES,PLACEHOLDERS,DEFAULT_BODY,default_content,validate_content,render_content,example_context

class EmailContentTests(unittest.TestCase):
    def test_all_defaults_validate_and_render(self):
        for key in TEMPLATES:
            subject,body=default_content(key);validate_content(subject,body,key)
            rendered=render_content(subject,body,key,example_context())
            self.assertTrue(rendered[0]);self.assertTrue(rendered[1])
    def test_all_registration_notifications_keep_required_links(self):
        for key in TEMPLATES:
            if key in ['test','password_reset','payment_request']:continue
            subject,body=render_content(*default_content(key),key,example_context())
            self.assertIn('/manage/BEISPIEL/',body);self.assertIn('/confirm/BEISPIEL/',body)
    def test_unknown_attributes_indexes_conversions_and_specs_are_rejected(self):
        for field in ['secret','child_name.__class__','child_name[0]','child_name!r','child_name:>200','child_name:{status}']:
            with self.subTest(field=field),self.assertRaises(ValueError):validate_content('Betreff','{'+field+'}'+DEFAULT_BODY,'registration')
    def test_confirmation_and_manage_placeholders_are_mandatory_in_body(self):
        for removed in ['{manage_url}','{confirmation_section}']:
            with self.assertRaises(ValueError):validate_content('Betreff',DEFAULT_BODY.replace(removed,''),'registration')
    def test_secure_placeholders_in_subject_are_rejected(self):
        for subject in ['{manage_url}','{confirmation_section}','{reset_url}','{payment_section}']:
            with self.assertRaises(ValueError):validate_content(subject,DEFAULT_BODY,'registration')
    def test_malformed_braces_are_reported(self):
        for body in ['{','}', '{child_name']:
            with self.assertRaises(ValueError):validate_content('Betreff',body+DEFAULT_BODY,'registration')
    def test_subject_newlines_and_oversize_input_are_rejected(self):
        for subject,body in [('Hallo\nWelt',DEFAULT_BODY),('Hallo\rWelt',DEFAULT_BODY),('x'*201,DEFAULT_BODY),('Hallo','x'*20001)]:
            with self.assertRaises(ValueError):validate_content(subject,body,'registration')
    def test_subject_is_bounded_after_expansion_and_cannot_inject_headers(self):
        data=example_context();data['event_title']='x'*300+'\r\nBCC: secret@example.org'
        subject,body=render_content('{event_title}',DEFAULT_BODY,'registration',data)
        self.assertEqual(len(subject),250);self.assertNotIn('\n',subject);self.assertNotIn('\r',subject)
    def test_unverified_confirmation_section_can_be_empty(self):
        data=example_context();data['confirmation_section']=''
        subject,body=render_content(*default_content('confirmed'),'confirmed',data)
        self.assertNotIn('/confirm/',body);self.assertIn('/manage/',body)
    def test_inserted_text_is_never_recursively_formatted(self):
        data=example_context();data['child_name']='{secret_key}'
        subject,body=render_content(*default_content('registration'),'registration',data)
        self.assertIn('{secret_key}',body)
    def test_literal_braces_are_supported(self):
        subject,body=render_content('Text {{Beispiel}}','{{Hinweis}} '+DEFAULT_BODY,'registration',example_context())
        self.assertEqual(subject,'Text {Beispiel}');self.assertTrue(body.startswith('{Hinweis}'))
    def test_testmail_has_no_personal_links_and_needs_no_context(self):
        subject,body=render_content(*default_content('test'),'test',{})
        self.assertNotIn('/manage/',body);self.assertNotIn('/confirm/',body)
    def test_unknown_template_is_rejected(self):
        with self.assertRaises(ValueError):default_content('unknown')

    def test_password_reset_requires_its_own_link_and_no_parent_links(self):
        with self.assertRaises(ValueError):validate_content('Passwort','Ohne Link','password_reset')
        subject,body=render_content(*default_content('password_reset'),'password_reset',example_context())
        self.assertIn('/konto/passwort/',body);self.assertNotIn('/manage/',body);self.assertNotIn('/confirm/',body)
    def test_payment_request_requires_instruction_section_and_manage_link(self):
        for body in ['Nur {manage_url}','Nur {payment_section}']:
            with self.assertRaises(ValueError):validate_content('Zahlung',body,'payment_request')
    def test_existing_custom_registration_template_gets_payment_instructions(self):
        body='Eigene Vorlage {confirmation_section} {manage_url}'
        subject,body=render_content('Betreff',body,'registration',example_context())
        self.assertIn('Bitte noch nicht überweisen',body)
    def test_escaped_placeholder_cannot_suppress_payment_instructions(self):
        body='{{payment_section}} {confirmation_section} {manage_url}'
        subject,body=render_content('Betreff',body,'registration',example_context())
        self.assertIn('Bitte noch nicht überweisen',body)

if __name__=='__main__':unittest.main(verbosity=2)
