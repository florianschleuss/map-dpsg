from django.db import migrations,models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('map','0009_microsoft_oauth')]
    operations=[
        migrations.CreateModel(name='StageRole',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('stage',models.OneToOneField('map.scoutgroup',on_delete=django.db.models.deletion.CASCADE,related_name='access_role')),
            ('group',models.OneToOneField('auth.group',on_delete=django.db.models.deletion.CASCADE,related_name='stage_role')),
        ],options={'verbose_name':'Automatische Stufenrolle','verbose_name_plural':'Automatische Stufenrollen'}),
        migrations.CreateModel(name='EmailTemplate',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('key',models.SlugField(unique=True,max_length=32)),
            ('subject',models.CharField('Betreffvorlage',max_length=200)),
            ('body',models.TextField('Nachrichtenvorlage')),
            ('updated_at',models.DateTimeField(auto_now=True)),
        ],options={'verbose_name':'E-Mail-Vorlage','verbose_name_plural':'E-Mail-Vorlagen'}),
    ]
