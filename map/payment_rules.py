"""Dependency-free cost validation and EPC transfer-data formatting."""
import re
from decimal import Decimal,InvalidOperation

COST_FIELDS=['cost_mode','cost_amount','cost_text','payment_method','bank_account_holder','bank_iban','bank_bic','payment_note','payment_due']
FROZEN_FIELDS=['cost_mode','cost_amount','cost_text','payment_method']

def normalize_iban(value):
    value=re.sub(r'\s+','',str(value or '')).upper()
    if not re.fullmatch(r'[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}',value):raise ValueError('Bitte eine gültige IBAN eingeben.')
    country_lengths={'DE':22,'AT':20,'CH':21,'FR':27,'NL':18,'BE':16,'LU':20,'ES':24,'IT':27,'IE':22,'PT':25,'GB':22}
    if value[:2] in country_lengths and len(value)!=country_lengths[value[:2]]:raise ValueError('Die IBAN hat für dieses Land eine falsche Länge.')
    numeric=''.join(str(ord(char)-55) if char.isalpha() else char for char in value[4:]+value[:4])
    if int(numeric)%97!=1:raise ValueError('Die IBAN-Prüfziffer ist ungültig. Bitte die Bankverbindung prüfen.')
    return value

def one_line(value):return ' '.join(str(value or '').split())
def normalized_costs(data):
    data={name:data.get(name) for name in COST_FIELDS}
    data['cost_mode']=data['cost_mode'] or 'free'
    if data['cost_mode'] not in ['free','fixed','custom']:raise ValueError('Bitte eine gültige Kostenart auswählen.')
    if data['cost_mode']=='free':
        data.update(cost_amount=None,cost_text='',payment_method='none',bank_account_holder='',bank_iban='',bank_bic='',payment_note='',payment_due=None);return data
    if data['cost_mode']=='fixed':
        try:amount=Decimal(str(data['cost_amount']))
        except (InvalidOperation,ValueError,TypeError):raise ValueError('Bitte einen Betrag pro Person in Euro angeben.') from None
        if not amount.is_finite() or not Decimal('0.01')<=amount<=Decimal('999999.99') or amount!=amount.quantize(Decimal('.01')):raise ValueError('Der Beitrag muss zwischen 0,01 und 999.999,99 Euro liegen und darf höchstens zwei Nachkommastellen haben.')
        data['cost_amount']=amount;data['cost_text']=''
    else:
        data['cost_amount']=None;data['cost_text']=str(data['cost_text'] or '').strip()
        if not data['cost_text']:raise ValueError('Bitte die Kosten im Freitext erklären.')
        if len(data['cost_text'])>2000:raise ValueError('Der Kostentext darf höchstens 2.000 Zeichen enthalten.')
    if data['payment_method'] not in ['cash','transfer','reminder']:raise ValueError('Bitte einen Bezahlungsvorgang auswählen.')
    if data['payment_method'] in ['transfer','reminder']:
        data['bank_account_holder']=one_line(data['bank_account_holder'])
        if not data['bank_account_holder'] or len(data['bank_account_holder'])>70:raise ValueError('Bitte einen Kontoinhaber mit höchstens 70 Zeichen angeben.')
        data['bank_iban']=normalize_iban(data['bank_iban'])
        data['bank_bic']=one_line(data['bank_bic']).upper()
        if data['bank_bic'] and not re.fullmatch(r'[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?',data['bank_bic']):raise ValueError('Bitte einen gültigen BIC mit 8 oder 11 Zeichen eingeben.')
        # A BIC is mandatory for non-EEA SEPA countries; require it outside the EEA list.
        eea={'AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IS','IE','IT','LV','LI','LT','LU','MT','NL','NO','PL','PT','RO','SK','SI','ES','SE'}
        if data['bank_iban'][:2] not in eea and not data['bank_bic']:raise ValueError('Für diese Bankverbindung außerhalb des EWR bitte zusätzlich den BIC angeben.')
    else:data.update(bank_account_holder='',bank_iban='',bank_bic='',payment_due=None)
    data['payment_note']=str(data['payment_note'] or '').strip()
    if len(data['payment_note'])>2000:raise ValueError('Der Zahlungshinweis darf höchstens 2.000 Zeichen enthalten.')
    return data

def cost_label(event):
    if event.cost_mode=='fixed':return format(event.cost_amount,'.2f').replace('.',',')+' € pro Person'
    if event.cost_mode=='custom':return event.cost_text
    return 'Kostenlos'

def payment_visible(event,row):
    if event.cost_mode=='free' or row.status!='confirmed':return False
    return event.payment_method=='transfer' or event.payment_method=='reminder' and bool(event.payment_released_at)

def epc_payload(holder,iban,bic,amount,reference):
    holder=one_line(holder)[:70];iban=normalize_iban(iban);bic=one_line(bic).upper()
    if not holder:raise ValueError('Kontoinhaber fehlt.')
    if bic and not re.fullmatch(r'[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?',bic):raise ValueError('Ungültiger BIC.')
    value=''
    if amount is not None:
        try:amount=Decimal(str(amount))
        except (InvalidOperation,ValueError,TypeError):raise ValueError('Ungültiger Überweisungsbetrag.') from None
        if not amount.is_finite() or not Decimal('.01')<=amount<=Decimal('999999999.99') or amount!=amount.quantize(Decimal('.01')):raise ValueError('Ungültiger Überweisungsbetrag.')
        value='EUR'+format(amount,'.2f')
    lines=['BCD','002','1','SCT',bic,holder,iban,value,'','',one_line(reference)[:140]]
    while len('\n'.join(lines).encode('utf-8'))>331 and lines[-1]:lines[-1]=lines[-1][:-1]
    if len('\n'.join(lines).encode('utf-8'))>331:raise ValueError('Die Bankdaten sind zu lang für den Überweisungs-QR-Code.')
    return '\n'.join(lines).rstrip('\n')


def transfer_data(event_title,child_name,holder,iban,bic,amount):
    prefix=epc_payload(holder,iban,bic,amount,'X')[:-1]
    budget=min(280,331-len(prefix.encode('utf-8')))
    if budget<9:raise ValueError('Für den Verwendungszweck ist im QR-Code zu wenig Platz.')
    def fit(value,limit):
        value=one_line(value)[:65]
        while len(value.encode('utf-8'))>limit:value=value[:-1]
        return value
    part=(budget-3)//2
    reference=fit(event_title,part)+' - '+fit(child_name,budget-3-part)
    return reference,epc_payload(holder,iban,bic,amount,reference)
