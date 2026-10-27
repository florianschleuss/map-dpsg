import base64
import hashlib
from django.conf import settings
from django.core.mail import get_connection, send_mail as django_send_mail
from django.core.exceptions import ValidationError
from .models import MailConfiguration
from .mail_presentation import sender_address,with_footer,html_message

def secret_cipher():
    from cryptography.fernet import Fernet
    key=base64.urlsafe_b64encode(hashlib.sha256(('map-smtp:'+settings.SECRET_KEY).encode()).digest())
    return Fernet(key)

def encrypt_password(password):
    return secret_cipher().encrypt(password.encode()).decode() if password else ''

def decrypt_password(encrypted):
    if not encrypted: return ''
    from cryptography.fernet import InvalidToken
    try: return secret_cipher().decrypt(encrypted.encode()).decode()
    except (InvalidToken,ValueError,UnicodeError):
        raise ValidationError('Das gespeicherte SMTP-Passwort kann nicht entschlüsselt werden. Bitte neu eingeben.')

def decrypt_client_secret(encrypted):
    try: return decrypt_password(encrypted)
    except ValidationError:
        raise ValidationError('Das gespeicherte Microsoft-Anwendungsgeheimnis kann nicht entschlüsselt werden. Bitte seinen Wert erneut eintragen; nach einem Anwendungsschlüsselwechsel ist dies erforderlich.') from None

def send_mail(subject,message,from_email,recipient_list,fail_silently=False):
    message=with_footer(message)
    config=MailConfiguration.objects.filter(pk=1,enabled=True).first()
    if config is None:
        return django_send_mail(subject,message,sender_address(from_email),recipient_list,fail_silently=fail_silently,html_message=html_message(message))
    if config.provider=='microsoft_graph':
        from .microsoft_mail import send_graph
        return send_graph(config,decrypt_client_secret(config.client_secret_encrypted),subject,message,recipient_list)
    connection=get_connection('django.core.mail.backends.smtp.EmailBackend',host=config.host,port=config.port,username=config.username,password=decrypt_password(config.password_encrypted),use_tls=config.security=='starttls',use_ssl=config.security=='ssl',timeout=15,fail_silently=fail_silently)
    with connection:
        return django_send_mail(subject,message,sender_address(config.from_email),recipient_list,connection=connection,fail_silently=fail_silently,html_message=html_message(message))


def test_credentials(config):
    if not config.enabled: return 'Die Servervorgaben sind aktiv. Es wurden keine eigenen Zugangsdaten geprüft; verwende eine Testmail zur Prüfung dieses Versandwegs.'
    if config.provider=='microsoft_graph':
        from .microsoft_mail import access_token
        access_token(config,decrypt_client_secret(config.client_secret_encrypted),fresh=True)
        return 'Die Anmeldung bei Microsoft war erfolgreich. Mandanten-ID, Anwendungs-ID und Anwendungsgeheimnis wurden akzeptiert. Die Sendeberechtigung für das Absenderpostfach ist damit noch nicht bestätigt; bitte anschließend eine Testmail senden.'
    connection=get_connection('django.core.mail.backends.smtp.EmailBackend',host=config.host,port=config.port,username=config.username,password=decrypt_password(config.password_encrypted),use_tls=config.security=='starttls',use_ssl=config.security=='ssl',timeout=15,fail_silently=False)
    with connection: pass
    return 'Die Verbindung zum SMTP-Server und die konfigurierte Anmeldung waren erfolgreich. Absender- und Empfängerberechtigungen bitte mit einer Testmail prüfen.'
