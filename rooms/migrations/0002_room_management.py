from django.db import migrations,models


def retain_existing_defaults(apps,schema_editor):
    Room=apps.get_model('rooms','Room');Settings=apps.get_model('rooms','RoomSettings')
    if Room.objects.using(schema_editor.connection.alias).exists():
        Settings.objects.using(schema_editor.connection.alias).update_or_create(pk=1,defaults={'defaults_seeded':True})

class Migration(migrations.Migration):
    dependencies=[('rooms','0001_initial')]
    operations=[migrations.AddField(model_name='room',name='active',field=models.BooleanField(default=True,verbose_name='Aktiv')),
        migrations.AddField(model_name='roomsettings',name='defaults_seeded',field=models.BooleanField(default=False,editable=False)),
        migrations.AddField(model_name='roomsettings',name='public_api_enabled',field=models.BooleanField(default=False,verbose_name='Öffentliche Belegungs-API aktivieren',help_text='Veröffentlicht ausschließlich Tage und aggregierte Belegungsstatus, keine Buchungsdetails.')),
        migrations.RunPython(retain_existing_defaults,migrations.RunPython.noop)]
