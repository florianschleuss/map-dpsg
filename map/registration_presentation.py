"""Display answers in their original form snapshot order, never JSON key order."""
from .text_labels import question_label

def answer_sections(row):
    sections=[];seen=set()
    def answer(key,label):
        value=row.answers.get(key)
        if value is True:value='Ja'
        elif value is False:value='Nein'
        elif value is None or value=='':value='Nicht angegeben'
        return {'label':question_label(label),'value':value}
    for module in row.schema_snapshot:
        fields=[]
        for field in module.get('fields',[]):
            key=field['key']
            if key in seen:continue
            seen.add(key);fields.append(answer(key,field['label']))
        if fields:sections.append({'title':module['title'],'answers':fields})
    remaining=[answer(key,key) for key in sorted(set(row.answers)-seen)]
    if remaining:sections.append({'title':'Weitere gespeicherte Angaben','answers':remaining})
    return sections
