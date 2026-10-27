from django.core.exceptions import ValidationError
from django.db import transaction
from .models import FormTemplate, FormModule, FormField
from .schema import validate_schema

STANDARD_SCHEMA=[{'title':'Kontakt','fields':[{'key':'phone','label':'Telefon für Rückfragen','type':'text','required':True}]},{'title':'Teilnahme','fields':[{'key':'food','label':'Verpflegung','type':'select','required':True,'choices':['Vegetarisch','Vegan','Keine besondere Kost']},{'key':'notes','label':'Anmerkungen','type':'textarea','required':False}]}]

def validate_builder_schema(schema):
    validate_schema(schema)
    for module in schema:
        if not module['title'].strip() or len(module['title'])>160: raise ValidationError('Jeder Abschnitt benötigt eine Überschrift mit höchstens 160 Zeichen.')
        for field in module['fields']:
            if not field['label'].strip() or len(field['label'])>200: raise ValidationError('Jede Frage benötigt eine Beschriftung mit höchstens 200 Zeichen.')
            help_text=field.get('help','')
            if not isinstance(help_text,str) or len(help_text)>300: raise ValidationError('Ein Hilfetext darf höchstens 300 Zeichen lang sein.')
            if field['type']=='select' and any(not item.strip() or len(item)>160 for item in field['choices']):
                raise ValidationError('Auswahlwerte müssen nicht leer und höchstens 160 Zeichen lang sein.')
    return schema

@transaction.atomic
def persist_schema(schema,name,template=None):
    validate_builder_schema(schema)
    if template is None: template=FormTemplate.objects.create(name=name)
    else:
        template=FormTemplate.objects.select_for_update().get(pk=template.pk)
        template.name=name
        template.save(update_fields=['name'])
        template.modules.all().delete()
    for position,module in enumerate(schema):
        section=FormModule.objects.create(template=template,title=module['title'],position=position)
        for index,field in enumerate(module['fields']):
            row=FormField(module=section,key=field['key'],label=field['label'],kind=field['type'],required=field.get('required',False),help_text=field.get('help',''),choices='\n'.join(field.get('choices',[])),position=index)
            row.full_clean()
            row.save()
    return FormTemplate.objects.get(pk=template.pk)
