import hmac
import time
import uuid
from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from .roles import is_admin
from .sso import configuration, require_config, callback_url, client, validate_token, resolve_identity, can_enter, sync_stages, SSOError
from .sso_models import SSOConfiguration, EntraIdentity, EntraStageMapping, SSOAudit
from .sso_forms import SSOSettingsForm, MappingFormSet, ManualIdentityForm


def failed(request, text, status=400):
    return render(request, 'sso_waiting.html', {'error': text}, status=status)


def begin(request, mode='login'):
    from .request_security import client_address
    from .services import throttle
    # No empty shared username bucket: each SSO account is unknown until Microsoft replies.
    if not throttle('sso-start:' + client_address(request), limit=60, seconds=900):
        return failed(request, 'Zu viele Anmeldeversuche. Bitte später erneut versuchen.', 429)
    try:
        config = require_config()
        flow = client(config).initiate_auth_code_flow(scopes=[], redirect_uri=callback_url(), prompt='select_account', response_mode='query')
        if not flow.get('auth_uri') or not flow.get('state') or not flow.get('nonce'):
            raise SSOError('Microsoft konnte keine Anmeldung starten. Bitte die App-Konfiguration prüfen.')
        request.session['entra_flow'] = {'flow': flow, 'at': time.time(), 'revision': str(config.revision),
                                         'mode': mode, 'user': request.user.pk if request.user.is_authenticated else None}
        return redirect(flow['auth_uri'])
    except SSOError as error: return failed(request, str(error))
    except Exception:
        # Provider exceptions can contain client secrets, tokens or personal claims.
        return failed(request, 'Microsoft ist nicht erreichbar oder die App-Konfiguration ist ungültig. Bitte Tenant-ID, Client-ID, Geheimnis und Netzwerk prüfen. Die lokale Anmeldung bleibt verfügbar.', 502)


@require_POST
def sso_start(request):
    if request.user.is_authenticated: return redirect('dashboard')
    return begin(request)


@require_GET
@sensitive_variables()
def sso_callback(request):
    saved = request.session.pop('entra_flow', None)
    if not saved or time.time() - saved.get('at', 0) > 600:
        return failed(request, 'Die Microsoft-Anmeldung ist abgelaufen oder wurde bereits verwendet. Bitte neu starten.')
    flow = saved['flow']
    if not hmac.compare_digest(str(request.GET.get('state', '')), str(flow.get('state', ''))):
        return failed(request, 'Die Sicherheitsprüfung der Anmeldung ist fehlgeschlagen. Bitte neu starten.')
    if request.GET.get('error'):
        return failed(request, 'Die Microsoft-Anmeldung wurde abgebrochen oder nicht genehmigt. Bitte erneut versuchen oder die Administration kontaktieren.')
    if not request.GET.get('code'): return failed(request, 'Microsoft hat keinen Anmeldecode geliefert. Bitte erneut anmelden.')
    try:
        config = require_config()
        if saved['revision'] != str(config.revision): raise SSOError('Die Einstellungen wurden geändert. Bitte die Anmeldung neu starten.')
        mode = saved.get('mode', 'login')
        if mode == 'login' and request.user.is_authenticated:
            raise SSOError('Du bist inzwischen mit einem MAP-Konto angemeldet. Bitte zuerst abmelden und die Microsoft-Anmeldung neu starten.')
        if mode == 'test' and (not request.user.is_authenticated or request.user.pk != saved.get('user')):
            raise SSOError('Das ursprüngliche MAP-Konto ist nicht mehr angemeldet. Bitte den Vorgang dort erneut starten.')
        if mode not in ['login','test']:raise SSOError('Dieser Anmeldevorgang wird nicht mehr unterstützt. Bitte die Anmeldung neu starten.')
        if mode == 'test' and not is_admin(request.user): raise SSOError('Dieser Test erfordert Adminrechte.')
        result = client(config).acquire_token_by_auth_code_flow(flow, request.GET.dict())
        if not result.get('id_token'):
            if result.get('error') == 'invalid_client':
                raise SSOError('Microsoft hat die App-Zugangsdaten abgelehnt. Client-ID und Wert/Ablaufdatum des Geheimnisses prüfen.')
            if result.get('error') == 'invalid_grant':
                raise SSOError('Der Microsoft-Anmeldecode ist ungültig oder abgelaufen. Bitte den Anmeldevorgang neu starten und die Web-Umleitungsadresse prüfen.')
            raise SSOError('Microsoft hat die Anmeldung abgelehnt. Bitte App-Geheimnis, Web-Umleitungsadresse und Benutzerzustimmung prüfen. Es wurden keine Rechte vergeben.')
        claims = validate_token(result['id_token'], config, flow)
        if mode == 'test':
            from .sso import groups_from
            groups, complete = groups_from(claims)
            request.session['entra_test'] = {'groups': groups, 'complete': complete, 'at': timezone.now().isoformat()}
            messages.success(request, 'Microsoft-Anmeldung und Tokenprüfung erfolgreich. Gruppeninformationen stehen unten. Dein MAP-Konto wurde nicht gewechselt.')
            return redirect('sso_settings')
        identity = resolve_identity(claims, config)
        login(request, identity.user, backend='map.auth_backend.RoleBackend')
        request.session['map_sso'] = {'identity': identity.pk, 'at': time.time(), 'revision': str(config.revision)}
        request.session.set_expiry(900)
        return redirect('dashboard' if can_enter(identity) else 'sso_waiting')
    except SSOError as error: return failed(request, str(error))
    except IntegrityError: return failed(request, 'Das Microsoft-Konto wurde gleichzeitig angelegt oder geändert. Bitte erneut anmelden oder die Administration kontaktieren.')
    except Exception:
        return failed(request, 'Die Microsoft-Anmeldung konnte nicht sicher geprüft werden. Bitte erneut versuchen; bei Wiederholung Tenant-ID, Client-ID, Geheimnis und Umleitungsadresse durch die Administration prüfen lassen. Es wurden keine neuen Rechte vergeben.', 502)


@login_required
@require_GET
def sso_waiting(request):
    return render(request, 'sso_waiting.html', {'identity': EntraIdentity.objects.filter(user=request.user).first()})


@login_required
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters('client_secret')
def sso_settings(request):
    if not is_admin(request.user): raise PermissionDenied
    config, _ = SSOConfiguration.objects.get_or_create(pk=1)
    action = request.POST.get('action') if request.method == 'POST' else ''
    form = SSOSettingsForm(request.POST if action == 'settings' else None, instance=config)
    mappings = MappingFormSet(request.POST if action == 'settings' else None, queryset=EntraStageMapping.objects.select_related('stage').order_by('stage__name'), prefix='mapping')
    identity_form = None; edited_identity = None
    if action == 'test': return begin(request, 'test')
    if action == 'settings':
        if form.is_valid() and mappings.is_valid():
            try: callback_url()
            except SSOError as error: form.add_error(None, str(error))
            else:
                with transaction.atomic():
                    SSOConfiguration.objects.select_for_update().get(pk=1)
                    form.save(); mappings.save()
                    for identity in EntraIdentity.objects.all(): sync_stages(identity)
                    SSOAudit.objects.create(actor=request.user, action='Microsoft-Einstellungen und Stufenzuordnungen gespeichert')
                request.session.pop('entra_test', None)
                messages.success(request, 'Microsoft-Einstellungen gespeichert. Bestehende Microsoft-Sitzungen müssen sich erneut anmelden. Der Anmeldetest prüft die tatsächlichen Zugangsdaten.')
                return redirect('sso_settings')
    elif action == 'identity':
        from .account_security import can_edit_person
        from .security_rules import numeric_pk
        edited_identity = get_object_or_404(EntraIdentity, pk=numeric_pk(request.POST.get('identity_id')))
        if not can_edit_person(request.user, edited_identity.user): raise PermissionDenied
        identity_form = ManualIdentityForm(request.POST)
        if identity_form.is_valid():
            from .models import LeaderProfile
            with transaction.atomic():
                edited_identity = EntraIdentity.objects.select_for_update().get(pk=edited_identity.pk)
                edited_identity.approved = identity_form.cleaned_data['approved']; edited_identity.blocked = identity_form.cleaned_data['blocked']
                edited_identity.save(update_fields=['approved', 'blocked'])
                profile, _ = LeaderProfile.objects.get_or_create(user=edited_identity.user)
                profile.is_leader = bool(identity_form.cleaned_data['stages']); profile.save(update_fields=['is_leader'])
                profile.stages.set(identity_form.cleaned_data['stages']); sync_stages(edited_identity)
                SSOAudit.objects.create(actor=request.user, action='Microsoft-Freigabe für Konto ' + str(edited_identity.user_id) + ' geändert')
            messages.success(request, 'Freigabe und manuelle Stufen gespeichert. Rollen und Adminrechte wurden nicht verändert.')
            return redirect('sso_settings')
    identities = list(EntraIdentity.objects.select_related('user').prefetch_related('automatic_stages', 'user__leadership__stages').order_by('-created_at')[:200])
    from .account_security import can_edit_person
    for identity in identities:
        profile = getattr(identity.user, 'leadership', None)
        identity.manual_form = identity_form if edited_identity and edited_identity.pk == identity.pk else ManualIdentityForm(auto_id='identity_' + str(identity.pk) + '_%s', initial={
            'approved': identity.approved, 'blocked': identity.blocked, 'stages': list(profile.stages.values_list('pk', flat=True)) if profile else []})
        identity.can_edit = can_edit_person(request.user, identity.user)
        identity.waiting = not can_enter(identity)
    try: callback = callback_url()
    except SSOError: callback = 'PUBLIC_URL muss zuerst auf die HTTPS-Adresse dieser Dev-Installation gesetzt werden.'
    return render(request, 'sso_settings.html', {'form': form, 'mapping_formset': mappings, 'config': config,
        'callback_url': callback, 'identities': identities, 'test_result': request.session.get('entra_test'),
        'audit_rows': SSOAudit.objects.select_related('actor').order_by('-created_at')[:15]})
