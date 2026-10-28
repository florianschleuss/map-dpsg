"""Room templates and notifications reuse MAP's protected mail queue and transport."""
from string import Formatter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse
from .models import RoomSettings,RoomEmailTemplate

EVENTS={
 'request':('Neue Buchungsanfrage','Eine neue Raumbuchung wartet auf die Entscheidung des Vorstands.'),
 'change_request':('Neuer Änderungsantrag','Für eine genehmigte Raumbuchung wurde eine Änderung beantragt. Die bisher genehmigte Belegung bleibt bis zu einer neuen Genehmigung gültig.'),
 'approved':('Raumbuchung genehmigt','Der Vorstand hat deine Raumbuchung genehmigt. Die unten genannten Räume und Zeiten sind freigegeben.'),
 'rejected':('Raumbuchung abgelehnt','Der Vorstand hat deine Buchungsanfrage abgelehnt. Sie gilt nicht als freigegebene Belegung.'),
 'change_approved':('Änderung genehmigt','Der Vorstand hat die Änderung genehmigt. Die neue Belegung ersetzt ab jetzt die bisherige Genehmigung.'),
 'change_rejected':('Änderung abgelehnt','Der Änderungsantrag wurde abgelehnt. Die ursprünglich genehmigte Belegung bleibt unverändert gültig.'),
 'cancelled':('Raumbuchung storniert','Die Raumbuchung wurde storniert. Sie und eventuell offene Änderungen gelten nicht mehr als Belegung.'),
 'change_withdrawn':('Änderungsantrag zurückgezogen','Der Änderungsantrag wurde zurückgezogen. Die bisher genehmigte Belegung bleibt gültig.'),
 'contact_updated':('Kontaktdaten aktualisiert','Ansprechperson oder Kontakt einer Raumbuchung wurden aktualisiert. Die Belegungsdaten und ihr bisheriger Status bleiben unverändert.'),
}
PLACEHOLDERS={'purpose':'Veranstaltung / Zweck','grouping':'Gruppierung','rooms':'Räume','period':'Zeitraum','status':'Aktueller Buchungsstatus',
 'contact_person':'Ansprechperson','contact':'Kontakt','reason':'Begründung der Entscheidung','booking_url':'Link zu den Buchungsdetails','creator':'Buchende Person',
 'change_status':'Status des Änderungsantrags','current_period':'Zeitraum der aktuell gültigen Buchungsfassung','current_rooms':'Räume der aktuell gültigen Buchungsfassung','current_purpose':'Zweck der aktuell gültigen Buchungsfassung'}


def defaults(key):
    title,intro=EVENTS[key]
    details='Veranstaltung: {purpose}\nGruppierung: {grouping}\nRäume: {rooms}\nZeitraum: {period}\nStatus der Buchung: {status}\n'
    if key.startswith('change_'):
        details='Änderungsantrag:\nVeranstaltung: {purpose}\nGruppierung: {grouping}\nVorgeschlagene Räume: {rooms}\nVorgeschlagener Zeitraum: {period}\nStatus des Änderungsantrags: {change_status}\n\nAktuelle Buchungsfassung:\nVeranstaltung: {current_purpose}\nRäume: {current_rooms}\nZeitraum: {current_period}\nStatus der Buchung: {status}\n'
    return title+' – {purpose}', 'Hallo,\n\n'+intro+'\n\n'+details+'\nAnsprechperson: {contact_person}\nKontakt: {contact}\nBuchende Person: {creator}\n\nHinweis / Begründung: {reason}\n\nBuchung und gegebenenfalls Änderungsantrag ansehen:\n{booking_url}\n\nBei Rückfragen wende dich bitte an den Vorstand.\n'


def validate_template(subject,body):
    if '\n' in subject or '\r' in subject:raise ValueError('Der Betreff darf keinen Zeilenumbruch enthalten.')
    try:
        for text in [subject,body]:
            for literal,name,spec,conversion in Formatter().parse(text):
                if name is not None and (name not in PLACEHOLDERS or spec or conversion):raise ValueError('Nur die aufgeführten Platzhalter ohne Formatierung verwenden.')
    except (ValueError,KeyError):raise ValueError('Ungültige Platzhalter. Bitte nur die unten aufgeführten Namen in einfachen geschweiften Klammern verwenden.') from None
    if '{booking_url}' not in body:raise ValueError('Der Platzhalter {booking_url} muss im Nachrichtentext bleiben.')


def content(key,context):
    saved=RoomEmailTemplate.objects.filter(key=key).first();subject,body=(saved.subject,saved.body) if saved else defaults(key)
    try:validate_template(subject,body)
    except ValueError:subject,body=defaults(key)
    if '{status}' not in body:body+='\nStatus der Buchung: {status}\n'
    if key.startswith('change_'):
        if '{change_status}' not in body:body+='\nStatus des Änderungsantrags: {change_status}\n'
        if '{current_period}' not in body or '{current_rooms}' not in body:
            body+='\nAktuelle Buchungsfassung: {current_period}\nRäume: {current_rooms}\nStatus der Buchung: {status}\n'
    subject=subject.format_map(context)
    subject=' '.join(subject.splitlines())[:200]
    return subject,body.format_map(context)


def context_for(booking,change=None):
    from .presentation import period
    target=change or booking
    return {'purpose':target.purpose,'grouping':target.grouping,'rooms':', '.join(target.rooms.values_list('name',flat=True)),
      'period':period(target),'status':booking.get_status_display(),'contact_person':booking.contact_person,'contact':booking.contact,
      'reason':target.decision_reason or 'Keine zusätzliche Begründung angegeben.',
      'change_status':change.get_status_display() if change else 'Kein Änderungsantrag',
      'current_period':period(booking),'current_rooms':', '.join(booking.rooms.values_list('name',flat=True)),'current_purpose':booking.purpose,
      'booking_url':settings.PUBLIC_URL.rstrip('/')+reverse('rooms:detail',args=[booking.pk]),
      'creator':(booking.creator.get_full_name() or booking.creator.get_username()) if booking.creator else 'Gelöschtes Konto'}


def notify(booking,key,change=None):
    from map.models import EmailJob
    from map.mail_policy import enabled
    if not enabled('rooms',key):return
    config=RoomSettings.objects.filter(pk=1).first()
    addresses=set(config.notification_emails.splitlines()) if config else set()
    # Applicants are informed of every transition and cancellations; configured board recipients too.
    if booking.creator and booking.creator.is_active:
        if booking.creator.email:addresses.add(booking.creator.email)
    subject,body=content(key,context_for(booking,change))
    for address in sorted(a.strip() for a in addresses if a.strip()):
        EmailJob.objects.create(template_scope='rooms',template_key=key,room_booking=booking,room_change=change,room_expected_status=booking.status,
          room_expected_change_status=change.status if change else '',room_expected_version=booking.version,recipient=address,subject=subject,body=body,next_attempt=timezone.now())


def job_current(job):
    if not job.room_booking_id:return True
    if job.room_booking.status!=job.room_expected_status or (job.room_expected_version is not None and job.room_booking.version!=job.room_expected_version):return False
    return not job.room_change_id or job.room_change.status==job.room_expected_change_status
