"""Reports use registration snapshots so later form edits do not rewrite history."""
from collections import Counter
import json
from .text_labels import question_label

def question_id(module,field):
    return (module['title'],field['key'],question_label(field['label']),field['type'],tuple(field.get('choices',[])))

def categories(rows):
    questions={}
    for row in rows:
        for module in row.schema_snapshot:
            for field in module.get('fields',[]):
                if field['type'] not in ['select','checkbox']:continue
                identity=question_id(module,field)
                item=questions.setdefault(identity,{'section':module['title'],'label':question_label(field['label']),'choices':['Ja','Nein'] if field['type']=='checkbox' else list(field.get('choices',[])),'counts':Counter(),'missing':0,'total':0})
                item['total']+=1
                value=row.answers.get(field['key'])
                if value is None or value=='':item['missing']+=1
                else:
                    value=('Ja' if value else 'Nein') if isinstance(value,bool) else str(value)
                    item['counts'][value]+=1
    for item in questions.values():
        options=list(dict.fromkeys(item['choices']+list(item['counts'])))
        item['options']=[{'label':value,'count':item['counts'][value],'percent':round(100*item['counts'][value]/item['total']) if item['total'] else 0} for value in options]
        del item['counts']
    return list(questions.values())

def answer_text(value):
    if value is True:return 'Ja'
    if value is False:return 'Nein'
    if isinstance(value,(list,dict)):return json.dumps(value,ensure_ascii=False)
    return '' if value is None else str(value)

def export_grid(rows):
    columns={}
    for row in rows:
        for module in row.schema_snapshot:
            for field in module.get('fields',[]):columns.setdefault(question_id(module,field),field)
        known={field['key'] for module in row.schema_snapshot for field in module.get('fields',[])}
        for key in row.answers:
            if key not in known:columns.setdefault(('Weitere Angaben',key,'Weitere Angabe: '+key,'text',()),{'key':key,'type':'text'})
    headers=['ID','Kind','E-Mail','Gruppe','Status','E-Mail bestätigt','Angemeldet am (Berlin)','Zahlungseingang bestätigt am (Berlin)']
    labels=Counter(identity[2] for identity in columns)
    for index,identity in enumerate(columns):
        label=identity[2]
        if labels[label]>1:label=identity[0]+' · '+label+' (Variante '+str(index+1)+')'
        headers.append(label)
    result=[headers]
    for row in rows:
        mapping={question_id(module,field):field for module in row.schema_snapshot for field in module.get('fields',[])}
        for key in row.answers:
            if not any(identity[1]==key for identity in mapping):mapping[('Weitere Angaben',key,'Weitere Angabe: '+key,'text',())]={'key':key,'type':'text'}
        values=[row.pk,row.child_name,row.email,row.event_group.group.name if row.event_group_id else row.event.group.name,row.get_status_display(),'Ja' if row.email_verified else 'Nein',row.created_at,row.payment_received_at]
        for identity in columns:
            field=mapping.get(identity);value=row.answers.get(field['key']) if field else None
            if field and field['type']=='integer' and isinstance(value,int) and not isinstance(value,bool):values.append(value)
            else:values.append(answer_text(value))
        result.append(values)
    return result
