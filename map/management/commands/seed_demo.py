from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from map.models import ScoutGroup, FormTemplate, FormModule, FormField, Event

class Command(BaseCommand):
    help = 'Create an unpublished sample event and reusable form. No user accounts or passwords are created.'
    @transaction.atomic
    def handle(self, *args, **options):
        group, _ = ScoutGroup.objects.get_or_create(name='Beispielstamm')
        template, created = FormTemplate.objects.get_or_create(name='Standard-Anmeldung')
        if created:
            contact = FormModule.objects.create(template=template, title='Kontakt', position=0)
            FormField.objects.create(module=contact, key='phone', label='Telefon für Rückfragen', kind='text', required=True)
            trip = FormModule.objects.create(template=template, title='Teilnahme', position=1)
            FormField.objects.create(module=trip, key='food', label='Verpflegung', kind='select', choices='Vegetarisch\nVegan\nKeine besondere Kost', required=True)
            FormField.objects.create(module=trip, key='notes', label='Anmerkungen', kind='textarea', position=1)
        now = timezone.now()
        Event.objects.get_or_create(slug='beispiellager', defaults={'group': group, 'title': 'Beispiellager', 'starts_at': now + timedelta(days=60), 'registration_opens': now - timedelta(days=1), 'registration_closes': now + timedelta(days=30), 'capacity': 20, 'form_template': template, 'published': False})
        self.stdout.write('Unveröffentlichtes Beispiel ist in der Verwaltung verfügbar.')
