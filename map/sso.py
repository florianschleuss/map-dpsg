"""OIDC via MSAL plus explicit RS256 signature, issuer and audience validation."""
import hashlib
import hmac
import time
import uuid
from datetime import timedelta
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from .sso_models import SSOConfiguration, EntraIdentity, EntraStageMapping

SESSION_SECONDS = 900


class SSOError(Exception):
    pass


def configuration():
    return SSOConfiguration.objects.filter(pk=1).first()


def require_config():
    config = configuration()
    if not config or not config.enabled or not config.tenant_id or not config.client_id or not config.client_secret_encrypted:
        raise SSOError('Die Microsoft-Anmeldung ist noch nicht eingerichtet oder wurde deaktiviert. Bitte lokal anmelden oder die Administration kontaktieren.')
    if config.secret_expires_on and config.secret_expires_on < timezone.localdate():
        raise SSOError('Das Microsoft-Anwendungsgeheimnis ist abgelaufen. Die Administration muss es erneuern. Die lokale Anmeldung bleibt verfügbar.')
    return config


def callback_url():
    from django.urls import reverse
    origin = settings.PUBLIC_URL.rstrip('/')
    parsed = urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
        raise SSOError('Für Microsoft-Anmeldung muss PUBLIC_URL eine HTTPS-Adresse ohne Pfad sein.')
    return origin + reverse('sso_callback')


def client(config):
    import msal
    import requests
    from .mailer import decrypt_client_secret

    class BoundedHTTP(requests.Session):
        def request(self, method, url, **kwargs):
            kwargs.setdefault('timeout', 12)
            return super().request(method, url, **kwargs)

    return msal.ConfidentialClientApplication(
        str(config.client_id), client_credential=decrypt_client_secret(config.client_secret_encrypted),
        authority='https://login.microsoftonline.com/' + str(config.tenant_id),
        http_client=BoundedHTTP(), instance_discovery=False, exclude_scopes=['offline_access'])


def validate_token(raw, config, flow):
    import jwt
    # Never fetch a key URL from a token header or a group-overage claim.
    jwks = jwt.PyJWKClient('https://login.microsoftonline.com/' + str(config.tenant_id) + '/discovery/v2.0/keys', timeout=12)
    key = jwks.get_signing_key_from_jwt(raw).key
    claims = jwt.decode(raw, key, algorithms=['RS256'], audience=str(config.client_id),
                        issuer='https://login.microsoftonline.com/' + str(config.tenant_id) + '/v2.0',
                        options={'require': ['exp', 'iat', 'nbf', 'iss', 'aud', 'sub', 'tid', 'oid', 'nonce']}, leeway=30)
    if str(uuid.UUID(claims['tid'])) != str(config.tenant_id):
        raise SSOError('Dieses Microsoft-Konto gehört nicht zum freigegebenen Mandanten.')
    uuid.UUID(claims['oid'])
    if claims.get('idtyp') == 'app':
        raise SSOError('Die Anmeldung erfordert ein persönliches Microsoft-Konto.')
    nonce = hashlib.sha256(flow['nonce'].encode('ascii')).hexdigest()
    if not hmac.compare_digest(str(claims['nonce']), nonce):
        raise SSOError('Die Anmeldeantwort gehört nicht zu dieser Sitzung. Bitte erneut anmelden.')
    return claims


def groups_from(claims):
    # An absent claim is treated as unknown, not as a trusted group list.
    if claims.get('hasgroups') or 'groups' in claims.get('_claim_names', {}) or not isinstance(claims.get('groups'), list):
        return [], False
    try:
        groups = sorted({str(uuid.UUID(value)) for value in claims['groups']})
    except (ValueError, TypeError, AttributeError):
        return [], False
    return (groups, True) if len(groups) <= 200 else ([], False)


def automatic_stage_ids(user):
    config = configuration()
    if not config or not config.enabled:
        return set()
    return set(EntraIdentity.objects.filter(user=user, tenant_id=config.tenant_id, blocked=False,
               last_login_at__gte=timezone.now() - timedelta(seconds=SESSION_SECONDS)).values_list('automatic_stages__pk', flat=True)) - {None}


def sync_stages(identity):
    ids = EntraStageMapping.objects.filter(group_id__in=identity.group_ids).values_list('stage_id', flat=True) if identity.groups_complete and not identity.blocked else []
    identity.automatic_stages.set(ids)


def can_enter(identity):
    return not identity.blocked and (identity.approved or identity.automatic_stages.exists())


@transaction.atomic
def resolve_identity(claims, config):
    current=SSOConfiguration.objects.select_for_update().get(pk=config.pk)
    if not current.enabled or current.revision!=config.revision:
        raise SSOError('Die Einstellungen wurden geändert. Bitte die Anmeldung neu starten.')
    tenant = uuid.UUID(claims['tid']); oid = uuid.UUID(claims['oid'])
    if tenant != config.tenant_id:
        raise SSOError('Der Mandant ist nicht zugelassen.')
    identity = EntraIdentity.objects.select_for_update().filter(tenant_id=tenant, object_id=oid).first()
    created = identity is None
    if created:
        from .sso_names import available_username
        # Email supplies the readable name, never an existing account lookup key.
        user = get_user_model()(email=str(claims.get('email') or claims.get('preferred_username') or '')[:254],
                first_name=str(claims.get('given_name', ''))[:150], last_name=str(claims.get('family_name', ''))[:150])
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try: validate_email(user.email)
        except ValidationError: user.email = ''
        user.username=available_username(get_user_model(),user.email)
        user.set_unusable_password(); user.save()
        identity = EntraIdentity.objects.create(user=user, tenant_id=tenant, object_id=oid)
    if not identity.user.is_active or identity.blocked:
        raise SSOError('Dieses Konto ist gesperrt. Bitte wende dich an die Administration.')
    identity.group_ids, identity.groups_complete = groups_from(claims)
    identity.last_login_at = timezone.now()
    identity.save(update_fields=['group_ids', 'groups_complete', 'last_login_at'])
    sync_stages(identity)
    if not can_enter(identity) and identity.notification_sent_at is None and config.notification_email:
        from .models import EmailJob
        EmailJob.objects.create(recipient=config.notification_email, subject='Microsoft-Zugang wartet auf Zuordnung',
            body='Ein neues Microsoft-Konto wartet in MAP auf Freigabe.\nKonto: ' + identity.user.get_username() +
            '\nKontakt: ' + identity.user.email + '\nBitte in der Microsoft-Anmeldung die Stufen und Freigabe prüfen.\n' +
            settings.PUBLIC_URL.rstrip('/') + '/verwaltung/microsoft/', next_attempt=timezone.now())
        identity.notification_sent_at = timezone.now(); identity.save(update_fields=['notification_sent_at'])
    return identity


class SSOSessionMiddleware:
    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        from django.urls import reverse
        if request.path in [reverse('logout'),reverse('room_occupancy_api')]:return self.get_response(request)
        stamp = request.session.get('map_sso')
        if stamp and request.user.is_authenticated:
            from django.contrib.auth import logout
            from django.shortcuts import redirect
            config = configuration()
            identity = EntraIdentity.objects.filter(pk=stamp.get('identity'), user=request.user).first()
            valid = config and config.enabled and identity and not identity.blocked and str(identity.tenant_id) == str(config.tenant_id)
            valid = valid and stamp.get('revision') == str(config.revision) and time.time() - stamp.get('at', 0) < SESSION_SECONDS
            if not valid:
                logout(request)
                return redirect('login')
            from django.urls import reverse
            allowed = [reverse(name) for name in ['sso_waiting', 'logout', 'privacy', 'imprint']]
            request.sso_waiting=not can_enter(identity)
            if not can_enter(identity) and request.path not in allowed:
                return redirect('sso_waiting')
        return self.get_response(request)
