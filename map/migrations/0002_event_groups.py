from django.db import migrations, models
import django.db.models.deletion

def assign_existing_groups(apps, schema_editor):
    Event = apps.get_model('map', 'Event')
    EventGroup = apps.get_model('map', 'EventGroup')
    Registration = apps.get_model('map', 'Registration')
    alias = schema_editor.connection.alias
    for event in Event.objects.using(alias).all().iterator():
        slot = EventGroup.objects.using(alias).create(event_id=event.pk, group_id=event.group_id, capacity=event.capacity, enabled=True)
        Registration.objects.using(alias).filter(event_id=event.pk).update(event_group_id=slot.pk)

class Migration(migrations.Migration):
    dependencies = [('map', '0001_initial')]
    operations = [
        migrations.AlterField(model_name='event', name='privacy_text', field=models.TextField('Datenschutzhinweis', blank=True, default='')),
        migrations.CreateModel(name='EventGroup', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('capacity', models.PositiveIntegerField('Plätze dieser Gruppe', default=20)),
            ('enabled', models.BooleanField('Aktiv', default=True)),
            ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='group_slots', to='map.event', verbose_name='Veranstaltung')),
            ('group', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='event_slots', to='map.scoutgroup', verbose_name='Gruppe')),
        ], options={'verbose_name':'Veranstaltungsgruppe','verbose_name_plural':'Veranstaltungsgruppen','ordering':['group__name','pk'],'constraints':[models.UniqueConstraint(fields=('event','group'),name='unique_event_group')]}),
        migrations.AddField(model_name='event',name='groups',field=models.ManyToManyField(related_name='participating_events',through='map.EventGroup',to='map.scoutgroup',verbose_name='Gruppen')),
        migrations.AddField(model_name='registration',name='event_group',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='registrations',to='map.eventgroup',verbose_name='Veranstaltungsgruppe')),
        migrations.RunPython(assign_existing_groups,migrations.RunPython.noop),
    ]
