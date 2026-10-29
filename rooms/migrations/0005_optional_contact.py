from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies=[('rooms','0004_weekly_bookings')]
    operations=[migrations.AlterField(model_name='roombooking',name='contact',field=models.CharField('Kontakt/zusätzliche Angaben',max_length=500,blank=True))]
