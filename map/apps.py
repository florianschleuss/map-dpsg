from django.apps import AppConfig

class MapConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'map'
    verbose_name = 'MAP – Organisation'

    def ready(self):
        from django.db.models.signals import post_migrate
        from .default_roles import sync_default_roles
        post_migrate.connect(sync_default_roles,dispatch_uid='map.default_role_permissions',weak=False)

        from django.db.models.signals import post_save,pre_delete,post_delete
        from .models import ScoutGroup
        from .stage_roles import stage_saved,stage_deleting,stage_deleted
        post_save.connect(stage_saved,sender=ScoutGroup,dispatch_uid='map.stage_role.save',weak=False)
        pre_delete.connect(stage_deleting,sender=ScoutGroup,dispatch_uid='map.stage_role.before_delete',weak=False)
        post_delete.connect(stage_deleted,sender=ScoutGroup,dispatch_uid='map.stage_role.delete',weak=False)
