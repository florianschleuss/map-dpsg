"""German error responses independent of the database and template context."""
from html import escape
from django.conf import settings
from django.http import HttpResponse

MESSAGES={400:('Anfrage nicht verarbeitet','Die übermittelten Angaben sind ungültig oder zu umfangreich. Bitte öffne das Formular erneut und prüfe deine Eingaben.'),403:('Zugriff nicht möglich','Für diese Aktion fehlt die Berechtigung oder die Formularsitzung ist abgelaufen. Öffne die ursprüngliche Seite erneut und versuche es noch einmal.'),404:('Seite nicht gefunden','Der aufgerufene Link ist ungültig, wurde geändert oder ist nicht mehr verfügbar.'),429:('Bitte kurz warten','Es gab zu viele Anfragen. Bitte warte 15 Minuten und versuche es dann erneut. Bei Problemen wende dich an die Leitenden oder die Administration.'),500:('Gerade ist ein Fehler aufgetreten','Die Anfrage konnte nicht abgeschlossen werden. Bitte versuche es später erneut. Falls das Problem bleibt, informiere die Administration.')}
def error_response(status):
    title,message=MESSAGES[status]
    response=HttpResponse('<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+' · '+escape(settings.MAP_ORGANIZATION)+'</title><style>body{font:17px/1.65 system-ui,sans-serif;background:#f3f6f8;color:#233f4c;margin:0;padding:24px}main{max-width:620px;margin:10vh auto;background:white;padding:32px;border:1px solid #ccd9df;border-radius:16px}a{color:#174d68}h1{line-height:1.2}</style></head><body><main><p>'+escape(settings.MAP_ORGANIZATION)+' · Anmeldungsverwaltung</p><h1>'+escape(title)+'</h1><p>'+escape(message)+'</p><p><a href="/">Zur Startseite</a></p></main></body></html>',status=status)
    response['Cache-Control']='no-store';response['Content-Language']='de';response['Referrer-Policy']='strict-origin'
    if status==429:response['Retry-After']='900'
    return response
def bad_request(request,exception):return error_response(400)
def permission_denied(request,exception):return error_response(403)
def page_not_found(request,exception):return error_response(404)
def server_error(request):return error_response(500)
def csrf_failure(request,reason=''):return error_response(403)
