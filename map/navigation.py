from django.urls import reverse

def breadcrumbs(request):
    if not request.user.is_authenticated:
        return []
    match=request.resolver_match
    crumbs=[{'label':'MAP','url':reverse('home')},{'label':'Dashboard','url':reverse('dashboard')}]
    if not match or match.url_name in ['home','dashboard','index']:
        crumbs[-1]['url']=''
        return crumbs
    from .models import Event
    from .services import permitted
    name=match.url_name
    event=None
    if name in ['event_statistics','export_excel','event_admin','event_settings','event_qr','event_delete','publish_event','request_payments']:
        event=Event.objects.filter(pk=match.kwargs.get('pk')).first()
    elif name in ['map_form_builder','map_form_builder_new']:
        event=Event.objects.filter(pk=request.GET.get('event') or 0).first() if str(request.GET.get('event','')).isdigit() else None
    if event and permitted(request.user,event):
        crumbs.append({'label':event.title,'url':reverse('event_admin',args=[event.pk])})
        if name=='event_admin': crumbs[-1]['url']=''
    labels={'event_statistics':'Statistik','export_excel':'Excel-Export','request_payments':'Zahlungsaufforderung','password_reset_confirm':'Passwort zurücksetzen','password_reset_complete':'Passwort geändert','people':'Benutzer','person_new':'Benutzer anlegen','person_edit':'Benutzer bearbeiten','roles':'Rollen und Rechte','role_new':'Rolle anlegen','role_edit':'Rolle bearbeiten','email_templates':'E-Mail-Vorlagen','email_template_edit':'E-Mail-Vorlage bearbeiten','mail_queue':'E-Mail-Warteschlange','mail_settings':'E-Mail-Einstellungen','privacy':'Datenschutz','event_delete':'Veranstaltung löschen','event_settings':'Einstellungen','map_form_builder':'Formularvorlage','map_form_builder_new':'Neue Formularvorlage','map_event_wizard':'Veranstaltung anlegen','auth_user_changelist':'Benutzer','auth_user_add':'Benutzer anlegen','auth_user_change':'Benutzer bearbeiten','auth_group_changelist':'Benutzergruppen','auth_group_add':'Benutzergruppe anlegen','auth_group_change':'Benutzergruppe bearbeiten','map_scoutgroup_changelist':'Stufen','map_scoutgroup_add':'Stufe anlegen','map_scoutgroup_change':'Stufe bearbeiten','map_formtemplate_changelist':'Formularvorlagen'}
    if name in labels: crumbs.append({'label':labels[name],'url':''})
    elif not event: crumbs.append({'label':'Verwaltung' if match.app_name=='admin' else 'Anmeldung','url':''})
    return crumbs
