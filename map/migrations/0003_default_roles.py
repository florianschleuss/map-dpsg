from django.db import migrations

def seed_roles(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for name in ['Admin', 'Manager', 'Read-Only']:
        Group.objects.using(schema_editor.connection.alias).get_or_create(name=name)

class Migration(migrations.Migration):
    dependencies = [('map', '0002_event_groups'), ('auth', '0012_alter_user_first_name_max_length')]
    operations = [migrations.RunPython(seed_roles, migrations.RunPython.noop)]
