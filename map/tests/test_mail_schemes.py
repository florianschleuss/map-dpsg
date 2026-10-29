import re
from unittest.mock import patch,MagicMock
from django.test import TestCase,override_settings
from django.urls import reverse
from .test_pools_delete_smtp import EventFixture
from map.models import MailConfiguration,EmailJob
from map.mail_admin import MailConfigurationForm
from map.mail_presentation import html_message,MAIL_SCHEMES,FOOTER
from map.mailer import send_mail

@override_settings(ALLOWED_HOSTS=['testserver'])
class MailSchemeTests(EventFixture,TestCase):
    def test_three_schemes_and_unknown_fallback_preserve_text_and_links(self):
        message='color:#213d4b <script>alert(1)</script> https://example.org/manage/token/?color:#174d68'
        for key in MAIL_SCHEMES:
            html=html_message(message,key)
            self.assertIn('data-mail-scheme="'+key+'"',html)
            self.assertIn('color:#213d4b &lt;script&gt;',html)
            self.assertIn('href="https://example.org/manage/token/?color:#174d68"',html)
            self.assertNotIn('<script>',html);self.assertEqual(html.count(FOOTER),1)
        self.assertIn('data-mail-scheme="blue"',html_message('Hallo','unknown'))

    def test_mono_uses_only_grey_colors_and_rainbow_uses_six_solid_bands(self):
        colors=re.findall(r'#[0-9a-f]{6}',html_message('Beispiel','mono'))
        self.assertTrue(colors);self.assertTrue(all(c[1:3]==c[3:5]==c[5:7] for c in colors))
        html=html_message('Beispiel','rainbow')
        for color in ['#c94a42','#e78d2b','#e6be47','#477c5b','#256d94','#8a5884']:self.assertIn('bgcolor="'+color+'"',html)

    def test_text_link_and_footer_contrast_on_white(self):
        def luminance(value):
            rgb=[int(value[i:i+2],16)/255 for i in [1,3,5]]
            rgb=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
            return sum(v*w for v,w in zip(rgb,[.2126,.7152,.0722]))
        for palette in MAIL_SCHEMES.values():
            for key in ['text','link','muted','footer']:self.assertGreaterEqual(1.05/(luminance(palette[key])+.05),4.5)

    def test_scheme_setting_is_independent_of_smtp_and_preserved_by_older_posts(self):
        config=MailConfiguration.objects.create(pk=1,mail_color_scheme='mono',enabled=False,password_encrypted='kept')
        form=MailConfigurationForm({'mail_color_scheme':'rainbow'},instance=config)
        self.assertTrue(form.is_valid(),form.errors);form.save();config.refresh_from_db()
        self.assertFalse(config.enabled);self.assertEqual(config.mail_color_scheme,'rainbow');self.assertEqual(config.password_encrypted,'kept')
        form=MailConfigurationForm({},instance=config);self.assertTrue(form.is_valid(),form.errors);form.save();config.refresh_from_db()
        self.assertEqual(config.mail_color_scheme,'rainbow')
        self.assertFalse(MailConfigurationForm({'mail_color_scheme':'<script>'},instance=config).is_valid())

    def test_server_default_transport_still_uses_selected_scheme(self):
        MailConfiguration.objects.create(pk=1,mail_color_scheme='mono',enabled=False)
        with patch('map.mailer.django_send_mail',return_value=1) as send:
            send_mail('Betreff','Text','sender@example.org',['to@example.org'])
        self.assertIn('data-mail-scheme="mono"',send.call_args.kwargs['html_message'])
        self.assertIn(FOOTER,send.call_args.args[1])

    def test_smtp_transport_uses_selected_scheme(self):
        MailConfiguration.objects.create(pk=1,mail_color_scheme='rainbow',enabled=True,host='mailpit',from_email='sender@example.org')
        with patch('map.mailer.get_connection',return_value=MagicMock()),patch('map.mailer.django_send_mail',return_value=1) as send:
            send_mail('Betreff','Text','sender@example.org',['to@example.org'])
        self.assertIn('data-mail-scheme="rainbow"',send.call_args.kwargs['html_message'])

    def test_graph_transport_uses_selected_scheme(self):
        from map.microsoft_mail import send_graph
        config=MailConfiguration(mail_color_scheme='mono',from_email='sender@example.org')
        with patch('map.microsoft_mail.access_token',return_value='test-token'),patch('map.microsoft_mail.request_json') as request:
            send_graph(config,'secret','Betreff','Text',['to@example.org'])
        self.assertIn('data-mail-scheme="mono"',request.call_args.kwargs['body']['message']['body']['content'])

    def test_settings_have_sandboxed_previews_without_sending_mail(self):
        self.client.force_login(self.admin)
        response=self.client.get(reverse('mail_settings'))
        for key in MAIL_SCHEMES:self.assertContains(response,'data-mail-scheme-preview="'+key+'"')
        self.assertContains(response,'sandbox=""',count=3)
        self.assertEqual(EmailJob.objects.count(),0)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(reverse('mail_settings'),{'mail_color_scheme':'mono'}).status_code,403)

    def test_event_and_room_template_previews_use_selected_renderer(self):
        MailConfiguration.objects.create(pk=1,mail_color_scheme='rainbow');self.client.force_login(self.admin)
        response=self.client.get(reverse('email_template_edit',args=['registration']))
        self.assertEqual(response.status_code,200);self.assertIn('data-mail-scheme="rainbow"',response.context['preview_html'])
        from rooms.notifications import defaults
        subject,body=defaults('request')
        response=self.client.post(reverse('rooms:template_edit',args=['request']),{'subject':subject,'body':body,'action':'preview'})
        self.assertEqual(response.status_code,200);self.assertIn('data-mail-scheme="rainbow"',response.context['preview_html'])
