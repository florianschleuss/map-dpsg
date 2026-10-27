from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion

def preserve_staff_status(apps,schema_editor):
    User=apps.get_model(*settings.AUTH_USER_MODEL.split('.'));Profile=apps.get_model('map','LeaderProfile')
    alias=schema_editor.connection.alias
    for user_id in User.objects.using(alias).filter(is_staff=True).values_list('pk',flat=True).iterator():
        Profile.objects.using(alias).get_or_create(user_id=user_id,defaults={'is_leader':True})

class Migration(migrations.Migration):
    dependencies=[('map','0007_mail_configuration'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name='formtemplate',name='created_by',field=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=django.db.models.deletion.SET_NULL,related_name='created_form_templates',editable=False,verbose_name='Angelegt von')),
        migrations.CreateModel(name='LeaderProfile',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('is_leader',models.BooleanField('Leitendenstatus',default=False)),
            ('user',models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.CASCADE,related_name='leadership',verbose_name='Benutzerkonto')),
            ('stages',models.ManyToManyField('map.scoutgroup',blank=True,related_name='leader_profiles',verbose_name='Zugeordnete Stufen')),
        ],options={'verbose_name':'Leitendenprofil','verbose_name_plural':'Leitendenprofile'}),
        migrations.RunPython(preserve_staff_status,migrations.RunPython.noop),
    ]
