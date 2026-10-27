"""Safe, dependency-free formatting for editable system emails."""
from string import Formatter

PLACEHOLDERS={
 'status_guidance':'Klare Erklärung des aktuellen Status und der nächsten Handlung',
 'event_title':'Name der Veranstaltung',
 'child_name':'Name der teilnehmenden Person',
 'status':'Aktueller Anmeldestatus',
 'stage':'Stufe der teilnehmenden Person',
 'notification':'Anlass der Nachricht',
 'confirmation_section':'Bestätigungsanleitung mit persönlichem Link und Frist, sofern noch erforderlich; sonst leer',
 'manage_url':'Persönlicher Bearbeitungs- und Stornierungslink',
 'valid_days':'Gültigkeit persönlicher Links in Tagen',
 'cost_summary':'Öffentliche Kostenbeschreibung',
 'payment_section':'Zahlungshinweise; Bankdaten nur bei bestätigter Teilnahme und gegebenenfalls manueller Freigabe',
 'account_name':'Benutzername (nur Passwort-Reset)',
 'reset_url':'Persönlicher Passwort-Link (nur Passwort-Reset)',
 'reset_hours':'Gültigkeit des Passwort-Links in Stunden',
}
DEFAULT_BODY='Veranstaltung: {event_title}\nKind: {child_name}\nStufe: {stage}\nStatus: {status}\n\n{confirmation_section}{payment_section}\nBearbeiten oder stornieren (vertraulicher Link):\n{manage_url}\n\nLinks sind {valid_days} Tage gültig. Bitte nicht weitergeben.\n'
TEMPLATES={
 'payment_request':('Zahlungsaufforderung','Wird manuell an bestätigte, noch offene Anmeldungen ausgelöst.'),
 'password_reset':('Passwort zurücksetzen','Wird aus der Benutzerverwaltung ausgelöst. Nur technische Admins können diese Sicherheitsvorlage bearbeiten.'),
 'registration':('Anmeldung eingegangen','Wird bei einer neuen Anmeldung erzeugt.'),
 'confirmed':('E-Mail bestätigt','Wird nach der Bestätigung der E-Mail-Adresse erzeugt.'),
 'promotion':('Platz auf der Warteliste frei','Wird beim Nachrücken von der Warteliste erzeugt.'),
 'expired':('Bestätigungsfrist abgelaufen','Wird beim Ablauf einer unbestätigten Anmeldung erzeugt.'),
 'cancelled':('Anmeldung storniert','Wird nach einer Stornierung erzeugt.'),
 'changed':('Anmeldung geändert','Wird nach gespeicherten Änderungen erzeugt.'),
 'resend':('Persönliche Links erneut senden','Wird beim Anfordern neuer Anmeldelinks erzeugt.'),
 'test':('Testmail','Wird beim Testversand in den E-Mail-Einstellungen verwendet.'),
}
NOTIFICATION_KEYS={'Ihre Anmeldung':'registration','E-Mail bestätigt':'confirmed','Ein Platz ist frei geworden':'promotion','Ein Platz in deiner Gruppe ist frei geworden':'promotion','Bestätigungsfrist abgelaufen':'expired','Anmeldung storniert':'cancelled','Anmeldung geändert':'changed','Anmeldelinks erneut gesendet':'resend'}

REGISTRATION_TAIL='\nVeranstaltung: {event_title}\nKind: {child_name}\nStufe: {stage}\nAktueller Status: {status}\n\n{status_guidance}\n\n{confirmation_section}{payment_section}\nAnmeldung ansehen, Angaben ändern oder stornieren:\n{manage_url}\n\nDieser persönliche Link ist {valid_days} Tage gültig. Bitte vertraulich behandeln. Bei Fragen wende dich an die Leitenden der Veranstaltung.\n'
MESSAGES={
 'registration':('Anmeldung eingegangen – {event_title}','Hallo,\n\nwir haben die Anmeldung für {child_name} erhalten. Ob bereits ein Teilnahmeplatz bestätigt ist oder noch etwas zu tun ist, steht unten. Bitte lies den aktuellen Status und die nächsten Schritte.'),
 'confirmed':('E-Mail-Adresse bestätigt – {event_title}','Hallo,\n\ndie E-Mail-Adresse zur Anmeldung von {child_name} ist jetzt bestätigt. Eine bestätigte E-Mail-Adresse bedeutet bei einer Wartelistenanmeldung noch keine Platzzusage. Maßgeblich ist der aktuelle Anmeldestatus unten.'),
 'promotion':('Nachgerückt: Ein Platz ist frei – {event_title}','Hallo,\n\nfür {child_name} ist ein Platz frei geworden. Die Anmeldung ist von der Warteliste nachgerückt. Bitte beachte unten, ob noch eine Bestätigung erforderlich ist.'),
 'expired':('Anmeldung abgelaufen: Frist verpasst – {event_title}','Hallo,\n\ndie erforderliche E-Mail-Bestätigung für {child_name} ist nicht rechtzeitig eingegangen. Diese Anmeldung ist abgelaufen; ein reservierter Platz wird nicht weiter freigehalten. Wenn das Kind weiterhin teilnehmen möchte, wende dich bitte an die Leitenden oder melde es erneut an, sofern die Anmeldung noch offen ist.'),
 'cancelled':('Stornierung bestätigt – {event_title}','Hallo,\n\ndie Anmeldung von {child_name} wurde storniert. Das Kind nimmt über diese Anmeldung nicht mehr teil. Falls bereits Geld überwiesen wurde, kläre eine mögliche Erstattung bitte direkt mit den Leitenden. MAP veranlasst keine Rückzahlung.'),
 'changed':('Anmeldedaten aktualisiert – {event_title}','Hallo,\n\ndie gespeicherten Angaben zur Anmeldung von {child_name} wurden geändert. Über den persönlichen Link kannst du die aktuellen Angaben prüfen. Diese Nachricht ist keine zusätzliche Platzzusage.'),
 'resend':('Dein persönlicher Anmeldelink – {event_title}','Hallo,\n\ndu hast die Links zur Anmeldung von {child_name} erneut angefordert. Unten findest du den persönlichen Verwaltungslink und, falls noch nötig, den Bestätigungslink. Das erneute Senden ändert den Anmeldestatus nicht.'),
}
def default_content(key):
    if key not in TEMPLATES:raise ValueError('Unbekannte E-Mail-Vorlage.')
    if key=='password_reset':return ('Neues Passwort für dein Konto – Anmeldungsverwaltung','Hallo {account_name},\n\nfür dein Konto wurde ein neues Passwort angefordert. Öffne diesen persönlichen Link innerhalb von {reset_hours} Stunde(n):\n{reset_url}\n\nWähle dort ein neues Passwort. Der Link kann nach erfolgreicher Änderung nicht erneut verwendet werden. Wenn du dies nicht erwartet hast, ignoriere diese Nachricht und kontaktiere die Administration. Dein Passwort bleibt bis zur Änderung unverändert.\n')
    if key=='payment_request':return ('Bitte Teilnahmebeitrag überweisen – {event_title}','Hallo,\n\nfür die bestätigte Teilnahme von {child_name} an {event_title} ist der Beitrag noch als offen markiert. Bitte beachte Betrag, Verwendungszweck und gegebenenfalls Zahlungsfrist in den folgenden Angaben:\n\n{payment_section}\nFalls du bereits bezahlt hast, überweise bitte nicht erneut, sondern wende dich an die Leitenden. Der Zahlungseingang wird manuell erfasst.\n\nAnmeldung und Banking-QR aufrufen:\n{manage_url}\n')
    if key=='test':return ('Test erfolgreich: E-Mail-Versand – Anmeldungsverwaltung','Hallo,\n\ndiese Testnachricht wurde über die aktuell gespeicherten E-Mail-Einstellungen versendet. Wenn du sie lesen kannst, ist sie in diesem Postfach angekommen. Bitte prüfe auch Absender und Spam-Einstufung. Ein erfolgreicher Zugangstest allein garantiert keine Zustellung bei anderen Empfängern.\n')
    subject,intro=MESSAGES[key]
    return subject,intro+'\n'+REGISTRATION_TAIL

LEGACY_SPECIAL={'password_reset': ('Passwort zurücksetzen – Anmeldungsverwaltung', 'Hallo {account_name},\n\nfür dein Konto wurde ein Passwort-Reset angefordert. Du kannst innerhalb von {reset_hours} Stunden ein neues Passwort setzen:\n{reset_url}\n\nWenn du dies nicht erwartet hast, ignoriere diese Nachricht und kontaktiere die Administration. Dein Passwort bleibt unverändert, bis du selbst ein neues setzt.\n'), 'payment_request': ('Zahlungsaufforderung: {event_title}', 'Hallo,\n\n{payment_section}\nDeine Anmeldung verwalten:\n{manage_url}\n'), 'test': ('E-Mail-Test – Anmeldungsverwaltung', 'Die Testmail wurde über die aktuell gespeicherten E-Mail-Einstellungen versendet.')}

def effective_content(key,saved=None):
    if saved is None:return default_content(key)
    # Upgrade exact shipped legacy boilerplate only. Never overwrite edited text.
    if key in MESSAGES and saved.subject=='{notification}: {event_title}' and saved.body in [DEFAULT_BODY,DEFAULT_BODY.replace('{payment_section}','')]:
        return default_content(key)
    if (saved.subject,saved.body)==LEGACY_SPECIAL.get(key):return default_content(key)
    return saved.subject,saved.body

def validate_content(subject,body,key):
    if key not in TEMPLATES:raise ValueError('Unbekannte E-Mail-Vorlage.')
    if not subject.strip() or not body.strip():raise ValueError('Bitte Betreff und Nachrichtentext ausfüllen.')
    if '\n' in subject or '\r' in subject:raise ValueError('Der Betreff darf keine Zeilenumbrüche enthalten.')
    if len(subject)>200 or len(body)>20000:raise ValueError('Betreff oder Nachrichtentext ist zu lang.')
    found=set()
    try:
        for text in [subject,body]:
            for literal,field,spec,conversion in Formatter().parse(text):
                if field is None:continue
                if field not in PLACEHOLDERS or spec or conversion:raise ValueError('Bitte nur die angezeigten Platzhalter ohne Zusätze verwenden: {'+str(field)+'}.')
                if text is subject and field in ['manage_url','confirmation_section','payment_section','reset_url']:raise ValueError('Bitte nur den Nachrichtentext für persönliche Links und Bestätigungsabschnitte verwenden.')
                if text is body:found.add(field)
    except ValueError as error:
        if str(error).startswith('Bitte nur'):raise
        raise ValueError('Die geschweiften Klammern sind nicht korrekt. Platzhalter bitte als {name} schreiben; normale Klammern doppelt schreiben: {{ und }}.') from None
    if key!='test':
        required=({'reset_url'} if key=='password_reset' else {'manage_url','payment_section'} if key=='payment_request' else {'manage_url','confirmation_section'})
        if not required.issubset(found):raise ValueError('Diese erforderlichen Platzhalter müssen im Nachrichtentext erhalten bleiben: '+', '.join('{'+name+'}' for name in sorted(required))+'.')

def render_content(subject,body,key,context):
    # Validate the editable input before trusted automatic sections are appended.
    validate_content(subject,body,key)
    if key in set(NOTIFICATION_KEYS.values()):
        try:has_payment=any(field=='payment_section' for literal,field,spec,conversion in Formatter().parse(body))
        except ValueError:has_payment=False
        if not has_payment:body+='\n\n{payment_section}'
    if key in MESSAGES and not any(field=='status_guidance' for literal,field,spec,conversion in Formatter().parse(body)):
        body+='\n\n{status_guidance}'
    values={name:str(context.get(name,'')) for name in PLACEHOLDERS}
    from .mail_presentation import with_footer
    return subject.format_map(values).replace('\r',' ').replace('\n',' ')[:250],with_footer(body.format_map(values))

def status_explanation(status,email_verified=True):
    guidance={
      'confirmed':'Die Teilnahme ist bestätigt. Es ist keine weitere E-Mail-Bestätigung erforderlich.',
      'pending':'Dein Platz ist vorläufig reserviert. Bitte bestätige deine E-Mail-Adresse bis zur angegebenen Frist. Erst danach ist die Teilnahme bestätigt.',
      'waitlisted':'Das Kind steht auf der Warteliste. Es gibt noch keine Platzzusage. Wir informieren dich per E-Mail, sobald ein Platz frei wird.',
      'cancelled':'Die Anmeldung ist storniert. Bitte überweise für diese Anmeldung keinen Beitrag mehr.',
      'expired':'Die Anmeldung ist abgelaufen. Es besteht keine Platzzusage.',
    }.get(status,'Bitte prüfe den aktuellen Status über deinen persönlichen Anmeldelink.')
    if status=='waitlisted' and not email_verified:guidance+=' Bitte bestätige auch für die Warteliste deine E-Mail-Adresse innerhalb der angegebenen Frist.'
    return guidance

def example_context(key=None,status=None):
    status=status or {'expired':'expired','cancelled':'cancelled','confirmed':'confirmed','promotion':'confirmed','payment_request':'confirmed'}.get(key,'pending')
    names={'pending':'Bestätigung ausstehend','confirmed':'Bestätigt','waitlisted':'Warteliste','cancelled':'Storniert','expired':'Abgelaufen'}
    return {'status_guidance':status_explanation(status,status!='pending'),'event_title':'Beispiel-Sommerlager','child_name':'Alex Beispiel','status':names.get(status,'Bestätigung ausstehend'),'stage':'Wölflinge','notification':'Ihre Anmeldung','confirmation_section':('E-Mail bestätigen (Frist: 30.10.2026, 17:00 Uhr):\nhttps://beispiel.invalid/confirm/BEISPIEL/\n\n' if status=='pending' else ''),'manage_url':'https://beispiel.invalid/manage/BEISPIEL/','valid_days':'30','cost_summary':'25,00 € pro Person','payment_section':('Bitte überweise den Beitrag entsprechend der Bankdaten in deiner persönlichen Anmeldungsverwaltung.\n' if status=='confirmed' else 'Kosten: 25,00 € pro Person. Bitte noch nicht überweisen.\n'),'account_name':'beispiel-konto','reset_url':'https://beispiel.invalid/konto/passwort/BEISPIEL/','reset_hours':'1'}
