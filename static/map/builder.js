/* MAP form builder. Structured data only; user-entered labels never become HTML. */
(() => {
  'use strict';
  const copy=value=>JSON.parse(JSON.stringify(value));
  const id=()=> 'f_'+(globalThis.crypto?.randomUUID?.().replaceAll('-','').slice(0,18)||Math.random().toString(36).slice(2,18));
  const field=(label,type='text',required=false,choices=[])=>({key:id(),label,type,required,choices,help:''});
  const standard=()=>[{title:'Kontakt',fields:[field('Telefon für Rückfragen','text',true)]},{title:'Teilnahme',fields:[field('Verpflegung','select',true,['Vegetarisch','Vegan','Keine besondere Kost']),field('Anmerkungen','textarea')]}];
  const blocks=[
    {title:'Kontakt',text:'Telefon und Anschrift',build:()=>({title:'Kontakt',fields:[field('Telefon für Rückfragen','text',true),field('Straße und Hausnummer'),field('Postleitzahl und Ort')]})},
    {title:'Verpflegung',text:'Ernährung und ergänzende Hinweise',build:()=>({title:'Verpflegung',fields:[field('Verpflegung','select',true,['Vegetarisch','Vegan','Keine besondere Kost']),field('Hinweise zur Verpflegung','textarea')]})},
    {title:'Kontakt im Notfall',text:'Name und erreichbare Telefonnummer',build:()=>({title:'Kontakt im Notfall',fields:[field('Name der Kontaktperson','text',true),field('Telefonnummer der Kontaktperson','text',true),field('Verhältnis zur teilnehmenden Person','text',true)]})},
    {title:'Weitere Angaben',text:'Freitext für ergänzende Informationen',build:()=>({title:'Weitere Angaben',fields:[field('Was möchtest du uns noch mitteilen?','textarea')]})},
    {title:'Datenschutz',text:'Fotoverwendung einzeln mit Ja oder Nein entscheiden',build:(photoLabel)=>({title:'Datenschutz',fields:["Zeigen von Fotos im Rahmen eines Fotoabends", "Veröffentlichung in Medien des Verbandes (z. B. Zeitschrift, Newsletter)", "Veröffentlichung in Medien (z. B. Pressefotos, Rundfunkbeiträge)", "Veröffentlichung auf der Homepage", "Veröffentlichung auf Social-Media-Kanälen des Stamms (z. B. Instagram)", (photoLabel || 'Aushang von Bildern in den Veranstaltungsräumen')].map(label=>field(label,'select',true,['Ja','Nein']))})}
  ];
  const types=[['text','Kurzer Text'],['textarea','Langer Text'],['email','E-Mail'],['integer','Zahl'],['date','Datum'],['checkbox','Kontrollkästchen'],['select','Auswahl']];
  const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;};
  const button=(text,action,cls='map-builder-button')=>{const node=el('button',cls,text);node.type='button';node.addEventListener('click',action);return node;};
  const labeled=(label,input)=>{const wrap=el('label','map-builder-label');wrap.append(el('span','',label),input);return wrap;};
  document.querySelectorAll('[data-map-builder]').forEach(root=>{
    if(root.dataset.ready)return;root.dataset.ready='true';
    const source=root.querySelector('input[type="hidden"][name]'),canvas=root.querySelector('[data-builder-canvas]'),preview=root.querySelector('[data-builder-preview]'),library=root.querySelector('[data-builder-library]'),status=root.querySelector('[data-builder-status]');
    let modules,mode='edit';
    const expanded=new WeakMap();
    const normalize=data=>Array.isArray(data)?data.map(module=>({title:String(module.title||'Neuer Abschnitt'),fields:Array.isArray(module.fields)?module.fields.map(item=>({...item,key:item.key||id(),label:String(item.label||''),type:item.type||'text',required:!!item.required,choices:Array.isArray(item.choices)?item.choices:[],help:String(item.help||'')})):[]})):[];
    const templates=(()=>{try{return JSON.parse(root.querySelector('script[type="application/json"]').textContent);}catch{return {};}})();
    const chooser=root.closest('form')?.querySelector('[name="form_template"]');
    try{modules=normalize(source.value?JSON.parse(source.value):(templates[chooser?.value]||standard()));}catch{modules=standard();}
    const sync=()=>{source.value=JSON.stringify(modules);const count=modules.reduce((sum,module)=>sum+module.fields.length,0);status.textContent=`${modules.length} Abschnitte · ${count} zusätzliche Fragen`;};
    const move=(items,index,direction)=>{const target=index+direction;if(target<0||target>=items.length)return;[items[index],items[target]]=[items[target],items[index]];render();};
    const addQuestion=(module,type='text')=>{module.fields.push(field('Neue Frage',type,false,type==='select'?['Erste Möglichkeit','Zweite Möglichkeit']:[]));render();};
    const drawPreview=()=>{
      preview.replaceChildren();
      const info=el('div','map-preview-note','Vorschau: Die Eltern sehen die festen Angaben und anschließend deine Fragen. Diese Vorschau verschickt keine Anmeldung.');preview.append(info);
      ['Name des Kindes','E-Mail-Adresse','Gruppe des Kindes'].forEach(label=>{const input=el('input');input.disabled=true;input.placeholder=label;preview.append(labeled(label,input));});
      modules.forEach(module=>{const section=el('section','map-preview-section');section.append(el('h3','',module.title));module.fields.forEach(item=>{
        let input;if(item.type==='select'&&item.choices.join('|')==='Ja|Nein'){input=el('span','map-preview-binary');['Ja','Nein'].forEach(answer=>{const label=el('label','',answer),radio=el('input');radio.type='radio';radio.disabled=true;label.prepend(radio);input.append(label);});}else if(item.type==='select'){input=el('select');['Bitte wählen',...item.choices].forEach(value=>{const option=el('option','',value);input.append(option);});}else if(item.type==='textarea'){input=el('textarea');input.rows=1;input.dataset.autogrow='';}else{input=el('input');input.type={integer:'number',checkbox:'checkbox',date:'date',email:'email'}[item.type]||'text';}
        input.disabled=true;
        const wrap=item.type==='select'&&item.choices.join('|')==='Ja|Nein'?el('div','map-builder-label'):labeled(item.label+(item.required?' *':''),input);if(item.type==='select'&&item.choices.join('|')==='Ja|Nein')wrap.append(el('span','',item.label+(item.required?' *':'')),input);if(item.type==='checkbox'){wrap.classList.add('map-preview-check');wrap.prepend(input);}
        if(item.help)wrap.append(el('small','',item.help));if(['text','textarea'].includes(item.type))wrap.append(el('small','', 'Bitte keine medizinischen Daten eingeben (z. B. Diagnosen, Allergien oder Medikamente).'));section.append(wrap);
      });preview.append(section);});
    };
    const render=()=>{
      root.querySelectorAll('[data-view]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.view===mode)));
      canvas.replaceChildren();sync();
      if(!modules.length)canvas.append(el('div','map-builder-empty','Noch keine zusätzlichen Fragen. Wähle rechts einen Baustein oder füge einen leeren Abschnitt hinzu.'));
      modules.forEach((module,mi)=>{
        const section=el('details','map-builder-section'),heading=el('div','map-builder-section-head');
        section.open=expanded.get(module)??true;section.addEventListener('toggle',()=>expanded.set(module,section.open));
        const summary=el('summary','map-builder-section-summary',module.title+' · '+module.fields.length+' Fragen');section.append(summary);
        const title=el('input');title.value=module.title;title.setAttribute('aria-label','Überschrift des Abschnitts');title.addEventListener('input',()=>{module.title=title.value;summary.textContent=title.value+' · '+module.fields.length+' Fragen';sync();});
        const tools=el('div','map-builder-tools');const up=button('↑',()=>move(modules,mi,-1));up.setAttribute('aria-label','Abschnitt nach oben verschieben');up.disabled=mi===0;const down=button('↓',()=>move(modules,mi,1));down.setAttribute('aria-label','Abschnitt nach unten verschieben');down.disabled=mi===modules.length-1;
        tools.append(up,down,button('Entfernen',()=>{if(module.fields.length && !confirm('Diesen Abschnitt mit allen Fragen entfernen?'))return;modules.splice(mi,1);render();}));heading.append(title,tools);section.append(heading);
        module.fields.forEach((item,fi)=>{
          const row=el('div','map-builder-question'),top=el('div','map-builder-question-head');
          const name=el('input');name.value=item.label;name.placeholder='Frage für die Eltern';name.setAttribute('aria-label','Beschriftung der Frage');name.addEventListener('input',()=>{item.label=name.value;sync();});
          const tools=el('div','map-builder-tools');const up=button('↑',()=>move(module.fields,fi,-1));up.disabled=fi===0;up.setAttribute('aria-label','Frage nach oben verschieben');const down=button('↓',()=>move(module.fields,fi,1));down.disabled=fi===module.fields.length-1;down.setAttribute('aria-label','Frage nach unten verschieben');tools.append(up,down,button('Entfernen',()=>{module.fields.splice(fi,1);render();}));top.append(name,tools);row.append(top);
          const options=el('div','map-builder-options'),type=el('select');types.forEach(([value,label])=>{const option=el('option','',label);option.value=value;type.append(option);});type.value=item.type;type.addEventListener('change',()=>{item.type=type.value;if(item.type==='select'&&!item.choices.length)item.choices=['Erste Möglichkeit','Zweite Möglichkeit'];render();});
          const required=el('input');required.type='checkbox';required.checked=item.required;required.addEventListener('change',()=>{item.required=required.checked;sync();});const requiredLabel=el('label','map-check-label');requiredLabel.append(required,el('span','','Pflichtfrage'));options.append(labeled('Antworttyp',type),requiredLabel);row.append(options);
          if(item.type==='select'){const choices=el('textarea');choices.rows=3;choices.value=item.choices.join('\n');choices.addEventListener('input',()=>{item.choices=choices.value.split('\n');sync();});row.append(labeled('Auswahlmöglichkeiten – eine pro Zeile',choices));}
          const details=el('details','map-builder-more');details.append(el('summary','','Hilfetext ergänzen'));const help=el('input');help.value=item.help;help.placeholder='Optionaler Hinweis zu dieser Frage';help.addEventListener('input',()=>{item.help=help.value;sync();});details.append(labeled('Hilfetext',help));row.append(details);section.append(row);
        });
        section.append(button('+ Frage hinzufügen',()=>addQuestion(module),'map-add-question'));canvas.append(section);
      });
      canvas.hidden=mode!=='edit';preview.hidden=mode!=='preview';root.querySelector('[data-add-section]').hidden=mode!=='edit';if(mode==='preview')drawPreview();
    };
    blocks.forEach(block=>{const b=button('',()=>{modules.push(block.build(root.dataset.photoLabel));mode='edit';render();},'map-library-item');b.append(el('strong','',block.title),el('small','',block.text));library.append(b);});
    const individual=el('div','map-library-fields');individual.append(el('h4','','Einzelne Frage hinzufügen'));types.forEach(([value,label])=>individual.append(button('+ '+label,()=>{if(!modules.length)modules.push({title:'Weitere Angaben',fields:[]});addQuestion(modules[modules.length-1],value);})));library.append(individual);
    root.querySelector('[data-add-section]').addEventListener('click',()=>{modules.push({title:'Neuer Abschnitt',fields:[]});render();});
    root.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.view;root.querySelectorAll('[data-view]').forEach(other=>other.setAttribute('aria-pressed',String(other===b)));render();}));
    let previousTemplate=chooser?.value||'';chooser?.addEventListener('change',()=>{if(!confirm('Die Fragen durch die ausgewählte Vorlage ersetzen?')){chooser.value=previousTemplate;return;}previousTemplate=chooser.value;modules=normalize(templates[chooser.value]||standard());render();});
    root.closest('form')?.addEventListener('submit',sync);render();
  });
})();
