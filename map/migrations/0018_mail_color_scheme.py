from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies=[('map','0017_feedback_email')]
    operations=[migrations.AddField(model_name='mailconfiguration',name='mail_color_scheme',field=models.CharField('Farbschema der E-Mails',max_length=16,choices=[('blue','Blau'),('mono','Grau / Schwarzweiß'),('rainbow','Regenbogen')],default='blue',help_text='Gilt für alle HTML-E-Mails, unabhängig vom Versandweg. Die Textversion bleibt unverändert.'))]
