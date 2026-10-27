from django.db import migrations,models
class Migration(migrations.Migration):
    dependencies=[('map','0008_leader_profiles')]
    operations=[
        migrations.AddField(model_name='mailconfiguration',name='provider',field=models.CharField('Versandweg',max_length=20,choices=[('smtp','SMTP mit Benutzername und Passwort'),('microsoft_graph','Microsoft 365 / Exchange Online (OAuth)')],default='smtp')),
        migrations.AddField(model_name='mailconfiguration',name='tenant_id',field=models.UUIDField('Mandanten-ID (Tenant-ID)',null=True,blank=True)),
        migrations.AddField(model_name='mailconfiguration',name='client_id',field=models.UUIDField('Anwendungs-ID (Client-ID)',null=True,blank=True)),
        migrations.AddField(model_name='mailconfiguration',name='client_secret_encrypted',field=models.TextField(blank=True,editable=False)),
        migrations.AddField(model_name='mailconfiguration',name='client_secret_expires_on',field=models.DateField('Ablaufdatum des Anwendungsgeheimnisses',null=True,blank=True)),
    ]
