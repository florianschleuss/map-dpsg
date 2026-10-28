from django.apps import AppConfig


def seed(sender,using='default',**kwargs):
    if sender.label!='rooms':return
    from django.contrib.auth.models import Group,Permission
    from .models import Room,RoomSettings
    settings,_=RoomSettings.objects.using(using).get_or_create(pk=1)
    if not settings.defaults_seeded:
        for index,name in enumerate(['Raum 1','Raum 2','Raum 3','Raum 4','Raum 5','Garten']):
            Room.objects.using(using).get_or_create(name=name,defaults={'position':index})
        settings.defaults_seeded=True;settings.save(using=using,update_fields=['defaults_seeded'])
    group,_=Group.objects.using(using).get_or_create(name='Vorstand')
    group.permissions.add(*Permission.objects.using(using).filter(content_type__app_label='rooms',codename__in=['view_roombooking','add_roombooking','manage_bookings','configure_rooms']))


class RoomsConfig(AppConfig):
    name='rooms'
    verbose_name='Raumbuchung'
    default_auto_field='django.db.models.BigAutoField'
    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(seed,dispatch_uid='rooms.defaults',weak=False)
