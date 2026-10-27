"""Operator readiness checks, separate from ordinary Django checks."""
from django.core.management.base import BaseCommand, CommandError
from map.site_config import validate_operator

class Command(BaseCommand):
    help = 'Prüft Betreiberangaben, HTTPS und Versand vor der Veröffentlichung.'
    def handle(self, *args, **options):
        errors = validate_operator()
        if errors: raise CommandError('Produktivfreigabe nicht bestanden:\n' + '\n'.join('- ' + error for error in errors))
        self.stdout.write(self.style.SUCCESS('Konfiguration vollständig. Mailzustellung und rechtliche Angaben zusätzlich fachlich prüfen.'))
