"""OAuth client-credentials and Graph sending; no tokens are persisted or logged."""
import hashlib
import json
import socket
import ssl
import threading
import time
import uuid
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,quote
from urllib.request import Request,build_opener,HTTPSHandler,HTTPRedirectHandler

MESSAGES={
    'ms_configuration':'Die Microsoft-Einstellungen sind unvollständig. Bitte Mandanten-ID, Anwendungs-ID, Anwendungsgeheimnis und Absenderpostfach prüfen.',
    'ms_invalid_client':'Microsoft hat die App-Anmeldung abgelehnt. Bitte Anwendungs-ID, richtigen Mandanten und den Wert des Anwendungsgeheimnisses prüfen.',
    'ms_secret_expired':'Das Anwendungsgeheimnis ist abgelaufen. Bitte in Microsoft Entra ein neues Geheimnis erstellen und dessen Wert in MAP speichern.',
    'ms_tenant':'Der Microsoft-Mandant wurde nicht gefunden. Bitte die Mandanten-ID aus der richtigen Organisation verwenden.',
    'ms_app':'Die Anwendung wurde im angegebenen Mandanten nicht gefunden oder ist dort nicht freigegeben. Bitte Mandanten-ID und Anwendungs-ID vergleichen.',
    'ms_consent':'Microsoft hat die Anwendung nicht für diesen Zugriff freigegeben. Bitte die App- und Exchange-Berechtigungen durch den Microsoft-365-Admin prüfen lassen.',
    'ms_policy':'Eine Microsoft-Sicherheitsrichtlinie blockiert die App-Anmeldung. Bitte die Anmeldeprotokolle für die Anwendung durch den Microsoft-365-Admin prüfen lassen.',
    'ms_scope':'Microsoft hat den angeforderten Graph-Zugriff abgelehnt. Bitte die App-Registrierung und den gewählten Versandweg prüfen.',
    'ms_token':'Microsoft hat kein gültiges Zugriffstoken geliefert. Bitte App-Konfiguration und Microsoft-Dienststatus prüfen.',
    'ms_auth':'Das Zugriffstoken wurde von Microsoft Graph abgelehnt. Bitte Mandant und App-Freigabe prüfen.',
    'ms_mailbox_permission':'Die Anmeldung bei Microsoft war möglich, der Versand aus diesem Postfach wurde aber verweigert. Bitte die Exchange-Rolle Application Mail.Send, deren Postfachbereich und die Postfachlizenz prüfen.',
    'ms_mailbox_missing':'Das Absenderpostfach wurde in Exchange Online nicht gefunden oder steht für Graph nicht zur Verfügung. Bitte primäre Postfachadresse bzw. Benutzeranmeldenamen und Postfachbereitstellung prüfen.',
    'ms_recipient':'Microsoft hat mindestens eine Empfängeradresse abgelehnt. Bitte die Empfängeradresse prüfen.',
    'ms_request':'Microsoft hat die Versanddaten abgelehnt. Bitte Absenderpostfach und Empfängeradressen prüfen.',
    'ms_throttled':'Microsoft begrenzt gerade die Anfragen. Bitte warten; die Warteschlange versucht den Versand später erneut.',
    'ms_unavailable':'Der Microsoft-Dienst ist vorübergehend nicht verfügbar. Die Warteschlange versucht es später erneut.',
    'ms_network':'Microsoft ist vom Server aus nicht erreichbar oder antwortet nicht rechtzeitig. Bitte ausgehendes HTTPS auf Port 443, DNS und die Netzwerkverbindung prüfen.',
    'ms_tls':'Die sichere Verbindung zu Microsoft konnte nicht hergestellt werden. Bitte Systemzeit und Zertifikatsspeicher des Servers prüfen.',
    'ms_response':'Die Antwort von Microsoft konnte nicht sicher verarbeitet werden. Bitte später erneut versuchen.',
    'ms_redirect':'Microsoft hat unerwartet auf eine andere Adresse umgeleitet. Zugangsdaten wurden dieser Umleitung nicht gefolgt; bitte Konfiguration und Netzwerk prüfen.',
}
class MicrosoftMailError(Exception):
    def __init__(self,code,diagnostic=None,retry_after=None):
        self.code=code if code in MESSAGES else 'ms_response'
        self.diagnostic=diagnostic if isinstance(diagnostic,int) and not isinstance(diagnostic,bool) and 10000<=diagnostic<=99999999 else None
        self.retry_after=min(3600,max(0,retry_after)) if isinstance(retry_after,int) else None
        text=MESSAGES[self.code]
        if self.diagnostic: text+=' Microsoft-Diagnosecode: AADSTS'+str(self.diagnostic)+'.'
        super().__init__(text)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl): return None

def classify_http_error(status,payload,phase,headers=None):
    payload=payload if isinstance(payload,dict) else {}
    errors=payload.get('error_codes',[])
    diagnostic=next((n for n in errors if isinstance(n,int) and not isinstance(n,bool)),None) if isinstance(errors,list) else None
    retry=None
    if headers:
        value=headers.get('Retry-After','')
        if str(value).isdigit(): retry=min(3600,int(value))
    if 300<=status<400: code='ms_redirect'
    elif status==429: code='ms_throttled'
    elif status>=500: code='ms_unavailable'
    elif phase=='token':
        error=payload.get('error')
        if not isinstance(error,str): error=''
        code={'invalid_client':'ms_invalid_client','unauthorized_client':'ms_consent','access_denied':'ms_policy','invalid_scope':'ms_scope','invalid_request':'ms_configuration','invalid_grant':'ms_invalid_client'}.get(error,'ms_token')
        # Numeric codes enrich diagnostics only; control flow follows the standard OAuth error.
        if error=='invalid_client' and diagnostic==7000222: code='ms_secret_expired'
        elif diagnostic==90002: code='ms_tenant'
        elif diagnostic==700016: code='ms_app'
        elif diagnostic in [65001,7000112]: code='ms_consent'
        elif diagnostic==53003: code='ms_policy'
    elif status==401: code='ms_auth'
    elif status==403: code='ms_mailbox_permission'
    elif status==404: code='ms_mailbox_missing'
    else:
        error=payload.get('error',{})
        code='ms_recipient' if isinstance(error,dict) and error.get('code') in ['ErrorInvalidRecipients','ErrorInvalidRecipient'] else 'ms_request'
    return MicrosoftMailError(code,diagnostic,retry)

def request_json(url,*,phase,form=None,body=None,token=None):
    headers={'Accept':'application/json'}
    if form is not None:
        data=urlencode(form).encode();headers['Content-Type']='application/x-www-form-urlencoded'
    else:
        data=json.dumps(body).encode();headers['Content-Type']='application/json'
    if token: headers['Authorization']='Bearer '+token
    request=Request(url,data=data,headers=headers,method='POST')
    opener=build_opener(HTTPSHandler(context=ssl.create_default_context()),NoRedirect())
    try:
        with opener.open(request,timeout=10) as response:
            raw=response.read(131073)
            if len(raw)>131072: raise MicrosoftMailError('ms_response')
            if phase=='send':
                if response.status==202: return {}
                raise MicrosoftMailError('ms_response')
            if response.status!=200: raise MicrosoftMailError('ms_response')
            result=json.loads(raw.decode())
            if not isinstance(result,dict): raise MicrosoftMailError('ms_response')
            return result
    except HTTPError as error:
        try: payload=json.loads(error.read(131072).decode())
        except (ValueError,UnicodeError,OSError): payload={}
        raise classify_http_error(error.code,payload,phase,error.headers) from None
    except URLError as error:
        raise MicrosoftMailError('ms_tls' if isinstance(error.reason,ssl.SSLError) else 'ms_network') from None
    except ssl.SSLError: raise MicrosoftMailError('ms_tls') from None
    except (socket.timeout,OSError): raise MicrosoftMailError('ms_network') from None
    except (ValueError,UnicodeError): raise MicrosoftMailError('ms_response') from None

_TOKEN_CACHE={}
_TOKEN_LOCK=threading.Lock()

def access_token(config,secret,fresh=False):
    try: tenant=str(uuid.UUID(str(config.tenant_id)));client=str(uuid.UUID(str(config.client_id)))
    except (ValueError,TypeError,AttributeError): raise MicrosoftMailError('ms_configuration') from None
    if not secret: raise MicrosoftMailError('ms_configuration')
    cache_key=hashlib.sha256((tenant+'|'+client+'|'+secret).encode()).hexdigest()
    with _TOKEN_LOCK:
        cached=_TOKEN_CACHE.get(cache_key)
        if not fresh and cached and cached[1]>time.monotonic(): return cached[0]
        data=request_json('https://login.microsoftonline.com/'+tenant+'/oauth2/v2.0/token',phase='token',form={'client_id':client,'client_secret':secret,'grant_type':'client_credentials','scope':'https://graph.microsoft.com/.default'})
        token=data.get('access_token')
        if not isinstance(token,str) or not token: raise MicrosoftMailError('ms_token')
        expiry=data.get('expires_in',0)
        try: expiry=int(expiry)
        except (TypeError,ValueError,OverflowError): expiry=0
        if len(_TOKEN_CACHE)>=8: _TOKEN_CACHE.clear()
        _TOKEN_CACHE[cache_key]=(token,time.monotonic()+max(0,min(expiry,7200)-120))
        return token

def send_graph(config,secret,subject,message,recipients):
    from .mail_presentation import html_message,sender_name
    if not config.from_email or not recipients: raise MicrosoftMailError('ms_configuration')
    url='https://graph.microsoft.com/v1.0/users/'+quote(config.from_email,safe='')+'/sendMail'
    body={'message':{'subject':subject,'from':{'emailAddress':{'address':config.from_email,'name':sender_name()}},'body':{'contentType':'HTML','content':html_message(message,getattr(config,'mail_color_scheme','blue'))},'toRecipients':[{'emailAddress':{'address':address}} for address in recipients]},'saveToSentItems':True}
    token=access_token(config,secret)
    try: request_json(url,phase='send',body=body,token=token)
    except MicrosoftMailError as error:
        if error.code!='ms_auth': raise
        token=access_token(config,secret,fresh=True)
        request_json(url,phase='send',body=body,token=token)
    return 1
