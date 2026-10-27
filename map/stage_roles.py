"""Create an isolated access role for each stage, including stages added later."""
from django.contrib.auth.models import Group,Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from .models import ScoutGroup,StageRole
from .access import STAGE_ACTIONS,stage_code

@transaction.atomic
def sync_stage(stage,using='default'):
    content=ContentType.objects.db_manager(using).get_for_model(ScoutGroup)
    permissions=[]
    for action,(label,description) in STAGE_ACTIONS.items():
        permission,_=Permission.objects.using(using).update_or_create(content_type=content,codename=stage_code(stage.pk,action),defaults={'name':(stage.name+': '+label)[:255]})
        permissions.append(permission)
    binding=StageRole.objects.using(using).select_related('group').filter(stage_id=stage.pk).first()
    desired=('Stufe: '+stage.name)[:120]+' ['+str(stage.pk)+']'
    if binding:
        group=binding.group
        if group.name!=desired and not Group.objects.using(using).filter(name=desired).exclude(pk=group.pk).exists(): group.name=desired;group.save(using=using,update_fields=['name'])
    else:
        # Never adopt an unrelated existing group and grant it new rights.
        name=desired
        while Group.objects.using(using).filter(name=name).exists():
            import uuid
            name=desired[:130]+' '+uuid.uuid4().hex[:12]
        group=Group.objects.using(using).create(name=name)
        binding=StageRole.objects.using(using).create(stage_id=stage.pk,group=group)
    group.permissions.set(permissions)

def stage_saved(sender,instance,using='default',raw=False,**kwargs):
    if not raw:sync_stage(instance,using)
def stage_deleting(sender,instance,using='default',**kwargs):
    instance._access_group_id=StageRole.objects.using(using).filter(stage_id=instance.pk).values_list('group_id',flat=True).first()
def stage_deleted(sender,instance,using='default',**kwargs):
    group_id=getattr(instance,'_access_group_id',None)
    if group_id:Group.objects.using(using).filter(pk=group_id).delete()
    Permission.objects.using(using).filter(content_type__app_label='map',content_type__model='scoutgroup',codename__in=[stage_code(instance.pk,action) for action in STAGE_ACTIONS]).delete()
