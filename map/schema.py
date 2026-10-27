import re
from django.core.exceptions import ValidationError
FIELD_TYPES = {'text', 'textarea', 'email', 'integer', 'date', 'checkbox', 'select'}
def validate_schema(value):
    if not isinstance(value, list) or len(value) > 30:
        raise ValidationError('Eine Liste mit höchstens 30 Modulen ist erforderlich.')
    keys = set()
    count = 0
    for module in value:
        if not isinstance(module, dict) or not isinstance(module.get('title'), str) or not isinstance(module.get('fields'), list):
            raise ValidationError('Jedes Modul benötigt title und fields.')
        for field in module['fields']:
            count += 1
            if not isinstance(field, dict): raise ValidationError('Ein Feld muss ein Objekt sein.')
            key = field.get('key', '')
            if not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,49}', key) or key in keys:
                raise ValidationError('Feldschlüssel müssen eindeutig sein: a-z, 0-9, _.')
            keys.add(key)
            if field.get('type') not in FIELD_TYPES or not isinstance(field.get('label'), str):
                raise ValidationError('Unbekannter Feldtyp oder fehlende Beschriftung.')
            if not isinstance(field.get('required', False), bool): raise ValidationError('required muss true oder false sein.')
            if field['type'] == 'select':
                choices = field.get('choices')
                if not isinstance(choices, list) or not choices or len(choices) > 100 or any(not isinstance(x, str) for x in choices) or len(set(choices)) != len(choices):
                    raise ValidationError('select benötigt eindeutige Textwerte in choices.')
    if count > 100: raise ValidationError('Höchstens 100 Felder sind erlaubt.')
