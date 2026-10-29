from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies=[('rooms','0003_public_api_description')]
    operations=[migrations.AddField(model_name=name,name='recurring',field=models.BooleanField(default=False,verbose_name='Wöchentlich wiederholen')) for name in ['roombooking','bookingchange']]
