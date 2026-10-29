from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies=[('map','0015_mail_template_delivery')]
    operations=[migrations.AlterField(model_name='event',name='capacity_mode',field=models.CharField('Platzverteilung',max_length=12,choices=[('per_group','Eigene Plätze je Stufe'),('shared','Gemeinsamer Gesamtpool'),('unlimited','Ohne Limit')],default='per_group'))]
