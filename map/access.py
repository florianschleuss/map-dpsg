"""Supported permissions shared by forms, menus and server-side guards."""
from django.contrib.auth.models import Permission
from django.db.models import Q

GLOBAL_RIGHTS={
 'map.view_event':('Alle Veranstaltungen lesen','Zeigt alle Veranstaltungen und deren Anmeldungen; erlaubt CSV-Export.'),
 'map.add_event':('Veranstaltungen für beliebige Stufen anlegen','Erlaubt neue Veranstaltungen für alle Stufen. Für selbst angelegte Veranstaltungen erhält die Person Bearbeitungsrechte.'),
 'map.change_event':('Alle Veranstaltungen bearbeiten','Erlaubt Einstellungen, Veröffentlichung und Anmeldungsänderungen bei allen Veranstaltungen. Enthält Leserechte, aber kein Löschrecht.'),
 'map.delete_event':('Alle Veranstaltungen löschen','Erlaubt das endgültige Löschen aller Veranstaltungen samt zugehörigen Daten. Enthält Leserechte.'),
 'map.change_formtemplate':('Alle Formularvorlagen bearbeiten','Erlaubt den Baukasten auch für fremde und gemeinsam genutzte Vorlagen. Änderungen gelten für alle verknüpften Veranstaltungen.'),
 'auth.change_user':('Benutzer verwalten','Erlaubt Konten anzulegen, zu bearbeiten, zu sperren, Passwörter zu setzen und Rollen zu vergeben. Damit kann auch Admin-Zugriff vergeben werden; nur vertrauten Personen gewähren. Technische Admin-Konten können nur technische Admins bearbeiten.'),
 'auth.change_group':('Rollen und Berechtigungen verwalten','Erlaubt eigene Rollen anzulegen und Rechte zu ändern. Damit können weitreichende Rechte vergeben werden; nur vertrauten Personen gewähren.'),
 'map.change_scoutgroup':('Stufen verwalten','Erlaubt Stufen anzulegen, zu bearbeiten und unbenutzte Stufen zu löschen. Jede neue Stufe bekommt automatisch eine Stufenrolle.'),
 'map.change_mailconfiguration':('E-Mail-Zugangsdaten verwalten','Erlaubt Versanddienst, Absender und Geheimnisse einzutragen sowie Zugangsdaten und Testversand zu prüfen.'),
 'map.view_emailjob':('E-Mail-Warteschlange lesen','Zeigt Empfänger, Betreff und Nachrichteninhalt einschließlich persönlicher Anmeldelinks.'),
 'map.change_emailjob':('E-Mail-Aufträge erneut versuchen','Erlaubt ausstehende oder fehlgeschlagene Aufträge erneut freizugeben. Bereits gesendete Nachrichten werden nicht erneut versendet.'),
 'map.delete_emailjob':('E-Mail-Aufträge löschen','Erlaubt ausgewählte oder nach Status gefilterte Aufträge endgültig zu entfernen. Bereits zugestellte Nachrichten werden dadurch nicht zurückgerufen.'),
 'map.change_emailtemplate':('E-Mail-Vorlagen bearbeiten','Erlaubt Betreff und Text der verwendeten Systemmails zu ändern, mit Beispieldaten vorzuschauen und zurückzusetzen.'),
}
STAGE_ACTIONS={'view':('Lesen','Veranstaltungen dieser Stufe einschließlich aller Anmeldedaten lesen und exportieren.'),'add':('Anlegen','Neue Veranstaltungen für diese Stufe anlegen. Bei mehreren Stufen wird das Anlegerecht für jede davon benötigt. Für selbst angelegte Veranstaltungen entstehen persönliche Bearbeitungsrechte.'),'change':('Bearbeiten','Einstellungen, Veröffentlichung und Anmeldungen bearbeiten. Bei mehreren Stufen wird das Bearbeitungsrecht für jede davon benötigt.'),'delete':('Löschen','Veranstaltung und zugehörige Daten endgültig löschen. Bei mehreren Stufen wird das Löschrecht für jede davon benötigt.')}
BUILTIN_ROLES={'Admin':'Fachlicher Vollzugriff auf Veranstaltungen, normale Konten, Rollen, Stufen und E-Mail-Verwaltung. Technische Admin-Konten und deren Status bleiben technischen Admins vorbehalten.','Manager':'Alle Veranstaltungen anlegen, bearbeiten und löschen sowie Formularvorlagen bearbeiten. Keine Konten-, Rollen- oder E-Mail-Verwaltung.','Read-Only':'Alle Veranstaltungen lesen und exportieren. Veranstaltungsänderungen bleiben auch bei zusätzlicher Stufenzuordnung gesperrt; Admin und Manager haben Vorrang.'}

def active(user): return bool(user.is_authenticated and user.is_active)
def codes_for(user):
    if not active(user): return set()
    return set(Permission.objects.filter(Q(group__user=user)|Q(user=user)).values_list('content_type__app_label','codename').distinct())
def granted(user,code):
    if not active(user): return False
    from .roles import is_admin
    return is_admin(user) or tuple(code.split('.',1)) in codes_for(user)
def stage_code(stage_id,action): return action+'_stage_'+str(stage_id)
def supported_permissions():
    from .models import ScoutGroup
    ids=list(ScoutGroup.objects.values_list('pk',flat=True))
    wanted=Q(pk__in=[])
    for code in GLOBAL_RIGHTS:
        app,name=code.split('.',1);wanted|=Q(content_type__app_label=app,codename=name)
    wanted|=Q(content_type__app_label='map',content_type__model='scoutgroup',codename__in=[stage_code(pk,action) for pk in ids for action in STAGE_ACTIONS])
    return Permission.objects.filter(wanted).select_related('content_type').order_by('content_type__app_label','codename')

def stage_ids(user,action='view'):
    if not active(user): return set()
    from .roles import is_read_only
    from .models import LeaderProfile,ScoutGroup
    if action!='view' and is_read_only(user): return set()
    automatic=set(LeaderProfile.objects.filter(user=user,is_leader=True).exclude(stages__isnull=True).values_list('stages__pk',flat=True))
    actions=list(STAGE_ACTIONS) if action=='view' else [action]
    codes={name for app,name in codes_for(user) if app=='map'}
    explicit={pk for pk in ScoutGroup.objects.values_list('pk',flat=True) if any(stage_code(pk,verb) in codes for verb in actions)}
    return automatic|explicit

def can_users(user):return granted(user,'auth.change_user')
def can_roles(user):return granted(user,'auth.change_group')
def can_stages(user):return granted(user,'map.change_scoutgroup')
def can_mail_settings(user):return granted(user,'map.change_mailconfiguration')
def can_mail_templates(user):return granted(user,'map.change_emailtemplate')
def can_queue(user,action='view'):
    if action=='view': return any(granted(user,'map.'+verb+'_emailjob') for verb in ['view','change','delete'])
    return granted(user,'map.'+action+'_emailjob')
def can_templates(user):
    from .roles import can_manage,is_read_only
    return can_manage(user) or (not is_read_only(user) and granted(user,'map.change_formtemplate'))
