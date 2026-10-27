from django.db import migrations, models
import django.db.models.deletion
import re

def link_email_jobs(apps,schema_editor):
    from django.core import signing
    Job=apps.get_model('map','EmailJob'); Registration=apps.get_model('map','Registration')
    alias=schema_editor.connection.alias
    for job in Job.objects.using(alias).filter(event__isnull=True).iterator():
        match=re.search(r'/manage/([^/\s]+)/',job.body)
        if not match: continue
        try:
            data=signing.loads(match.group(1),salt='map-link')
        except signing.BadSignature: continue
        if not isinstance(data,dict) or data.get('action')!='manage': continue
        event_id=Registration.objects.using(alias).filter(pk=data.get('id'),token_nonce=data.get('nonce')).values_list('event_id',flat=True).first()
        if event_id: Job.objects.using(alias).filter(pk=job.pk).update(event_id=event_id)

class Migration(migrations.Migration):
    dependencies=[('map','0005_role_permissions')]
    operations=[
        migrations.AddField(model_name='event',name='capacity_mode',field=models.CharField('Platzverteilung',max_length=12,choices=[('per_group','Eigene Plätze je Stufe'),('shared','Gemeinsamer Gesamtpool')],default='per_group')),
        migrations.AddField(model_name='event',name='waitlist_mode',field=models.CharField('Wartelistenverteilung',max_length=12,choices=[('per_group','Warteliste je Stufe'),('shared','Gemeinsame Warteliste')],default='per_group')),
        migrations.AddField(model_name='event',name='show_availability',field=models.BooleanField('Verfügbare Plätze in der Anmeldung anzeigen',default=True)),
        migrations.AddField(model_name='emailjob',name='event',field=models.ForeignKey('map.event',null=True,blank=True,on_delete=django.db.models.deletion.CASCADE,related_name='email_jobs',verbose_name='Veranstaltung')),
        migrations.RunPython(link_email_jobs,migrations.RunPython.noop),
    ]
