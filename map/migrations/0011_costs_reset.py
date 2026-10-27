from django.conf import settings
from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies=[('map','0010_permissions_mail_templates'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name='event',name='cost_mode',field=models.CharField('Kostenart', max_length=10, choices=[('free', 'Kostenlos'), ('fixed', 'Fester Betrag pro Person'), ('custom', 'Kosten als Freitext')], default='free')),
        migrations.AddField(model_name='event',name='cost_amount',field=models.DecimalField('Beitrag pro Person in Euro', max_digits=8, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name='event',name='cost_text',field=models.TextField('Kostenbeschreibung', blank=True, max_length=2000)),
        migrations.AddField(model_name='event',name='costs_configured',field=models.BooleanField(default=False, editable=False)),
        migrations.AddField(model_name='event',name='payment_method',field=models.CharField('Bezahlungsvorgang', max_length=10, choices=[('none', 'Keine Zahlung'), ('cash', 'Bargeld zur Veranstaltung mitbringen'), ('transfer', 'Überweisung nach bestätigter Anmeldung'), ('reminder', 'Zahlungsaufforderung später per E-Mail')], default='none')),
        migrations.AddField(model_name='event',name='bank_account_holder',field=models.CharField('Kontoinhaber', max_length=70, blank=True)),
        migrations.AddField(model_name='event',name='bank_iban',field=models.CharField('IBAN', max_length=34, blank=True)),
        migrations.AddField(model_name='event',name='bank_bic',field=models.CharField('BIC', max_length=11, blank=True)),
        migrations.AddField(model_name='event',name='payment_note',field=models.TextField('Zusätzlicher Zahlungshinweis', max_length=2000, blank=True)),
        migrations.AddField(model_name='event',name='payment_due',field=models.DateField('Zahlbar bis', null=True, blank=True)),
        migrations.AddField(model_name='event',name='payment_released_at',field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='registration',name='payment_received_at',field=models.DateTimeField('Zahlungseingang manuell bestätigt', null=True, blank=True)),
        migrations.AddField(model_name='registration',name='payment_received_by',field=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='recorded_payments')),
        migrations.AddField(model_name='emailjob',name='registration',field=models.ForeignKey('map.registration', null=True, blank=True, on_delete=models.CASCADE, related_name='email_jobs', editable=False)),
        migrations.AddField(model_name='emailjob',name='payment_request',field=models.BooleanField(default=False, editable=False)),
        migrations.AddField(model_name='emailjob',name='payment_fingerprint',field=models.CharField(max_length=64, blank=True, editable=False)),
        migrations.AddField(model_name='emailjob',name='reset_user',field=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name='password_reset_jobs', editable=False)),
        migrations.AddField(model_name='emailjob',name='body_encrypted',field=models.TextField(blank=True, editable=False)),
        migrations.AddField(model_name='emailjob',name='reset_token_encrypted',field=models.TextField(blank=True, editable=False)),
        migrations.CreateModel(name='PaymentBatch',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('event',models.ForeignKey('map.event',on_delete=models.CASCADE,related_name='payment_batches')),('nonce',models.UUIDField(unique=True)),('created_by',models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)),('created_at',models.DateTimeField(auto_now_add=True)),('recipient_count',models.PositiveIntegerField(default=0))],options={'verbose_name':'Zahlungsaufforderung','verbose_name_plural':'Zahlungsaufforderungen'}),
    ]
