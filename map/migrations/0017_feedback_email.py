from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies=[('map','0016_unlimited_events')]
    operations=[migrations.AddField(model_name='mailconfiguration',name='feedback_email',field=models.EmailField('Feedback-Adresse für die Website',blank=True,max_length=254,help_text='Wird öffentlich im Footer als Mailto-Link angezeigt. Leer lassen, um den Feedback-Link auszublenden. Unabhängig vom Versandpostfach.'))]
