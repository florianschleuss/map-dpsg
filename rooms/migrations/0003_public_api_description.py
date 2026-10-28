from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies=[('rooms','0002_room_management')]
    operations=[migrations.AlterField(model_name='roomsettings',name='public_api_enabled',field=models.BooleanField(default=False,verbose_name='Öffentliche Belegungs-API aktivieren',help_text='Veröffentlicht Tage, aggregierte Belegungsstatus und die Namen betroffener Räume; keine Veranstaltungs- oder Kontaktdaten.'))]
