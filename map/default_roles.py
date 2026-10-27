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

def sync_default_roles(sender, using='default', **kwargs):
    if sender.label != 'map': return
    from django.contrib.auth.models import Group, Permission
    from .models import ScoutGroup
    from .stage_roles import sync_stage
    for stage in ScoutGroup.objects.using(using).all(): sync_stage(stage,using)
    assign_roles(Group, Permission, using)
