from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies=[('map','0006_capacity_mail')]
    operations=[migrations.CreateModel(name='MailConfiguration',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('enabled',models.BooleanField('Eigene SMTP-Einstellungen verwenden',default=False)),
        ('host',models.CharField('SMTP-Server',max_length=250,blank=True)),
        ('port',models.PositiveIntegerField('Port',default=587)),
        ('username',models.CharField('Benutzername',max_length=250,blank=True)),
        ('password_encrypted',models.TextField(blank=True,editable=False)),
        ('security',models.CharField('Verschlüsselung',max_length=12,choices=[('starttls','STARTTLS (meist Port 587)'),('ssl','SSL/TLS (meist Port 465)'),('plain','Unverschlüsselt (nur lokaler Testbetrieb)')],default='starttls')),
        ('from_email',models.EmailField('Absenderadresse',blank=True,max_length=254)),
        ('updated_at',models.DateTimeField(auto_now=True)),
    ],options={'verbose_name':'SMTP-Einstellung','verbose_name_plural':'SMTP-Einstellungen'})]
