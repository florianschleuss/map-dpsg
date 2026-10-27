from django.db import migrations

def assign_roles(Group, Permission, alias='default'):
    permissions=Permission.objects.using(alias)
    event_models=['event','eventgroup','eventpermission','registration','formtemplate','formmodule','formfield','scoutgroup']
    for name in ['Admin','Manager','Read-Only']:
        group,_=Group.objects.using(alias).get_or_create(name=name)
        if name=='Admin': selected=permissions.all()
        elif name=='Read-Only': selected=permissions.filter(content_type__app_label='map',content_type__model__in=event_models,codename__startswith='view_')
        else:
            from django.db.models import Q
            selected=permissions.filter(content_type__app_label='map',content_type__model__in=event_models).filter(~Q(content_type__model='scoutgroup') | Q(codename='view_scoutgroup'))
        group.permissions.set(selected)

def seed_permissions(apps,schema_editor):
    assign_roles(apps.get_model('auth','Group'),apps.get_model('auth','Permission'),schema_editor.connection.alias)

class Migration(migrations.Migration):
    dependencies=[('map','0004_stage_labels')]
    operations=[migrations.RunPython(seed_permissions,migrations.RunPython.noop)]
