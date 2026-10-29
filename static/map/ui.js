/* MAP controls: German calendar, time presets, exclusive access choices and group quotas. */
(() => {
  'use strict';
  const el = (tag, cls, text) => {const item=document.createElement(tag);if(cls)item.className=cls;if(text!==undefined)item.textContent=text;return item;};
  const pad = n => String(n).padStart(2,'0');
  const berlinNow = () => {
    const parts = Object.fromEntries(new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date()).filter(p=>p.type!=='literal').map(p=>[p.type,p.value]));
    return {date:`${parts.year}-${parts.month}-${parts.day}`,time:`${parts.hour}:${parts.minute}`};
  };
  const initDatePickers=()=>{
  document.querySelectorAll('input[type="date"]').forEach(input=>{
    if(input.closest('[data-map-datetime]')||input.disabled)return;
    const root=el('div','map-datetime');root.dataset.mapDatetime='';root.dataset.dateOnly='true';
    root.innerHTML='<div class="map-date-controls" hidden><div class="map-date-column"><button type="button" class="map-date-open" aria-haspopup="dialog" aria-expanded="false">Datum auswählen</button><button type="button" data-time="now">Heute</button></div><div class="map-time-column"><input type="time" class="map-time-input" aria-label="Uhrzeit"></div></div><div class="map-calendar" role="dialog" aria-label="Datum auswählen" hidden></div>';
    input.replaceWith(root);root.prepend(input);
  });
  document.querySelectorAll('[data-map-datetime]').forEach(root=>{
    if(root.dataset.dateReady)return;

    const source=root.querySelector('input:not(.map-time-input)');
    if(!source || source.disabled)return;root.dataset.dateReady='true';
    const controls=root.querySelector('.map-date-controls'),open=root.querySelector('.map-date-open'),time=root.querySelector('.map-time-input'),calendar=root.querySelector('.map-calendar');
    const dateOnly=root.dataset.dateOnly==='true';
    if(dateOnly){root.querySelector('.map-time-column').hidden=true;root.querySelector('[data-time=now]').textContent='Heute';}
    let selected=(source.value||'').replace(' ','T').slice(0,10);
    if(!/^\d{4}-\d{2}-\d{2}$/.test(selected))selected='';
    time.value=(source.value||'').replace(' ','T').slice(11,16)||'09:00';
    let [year,month]=(selected||berlinNow().date).split('-').map(Number);month--;
    source.type='hidden';controls.hidden=false;
    const sync=()=>{
      source.value=dateOnly?selected:(selected&&time.value?`${selected}T${time.value}`:'');
      open.textContent=selected?new Intl.DateTimeFormat('de-DE',{day:'2-digit',month:'long',year:'numeric'}).format(new Date(selected+'T12:00:00')):'Datum auswählen';
      const clear=root.querySelector('.map-date-clear');if(clear)clear.hidden=!selected;
      source.dispatchEvent(new Event('change',{bubbles:true}));
    };
    const close=()=>{calendar.hidden=true;open.setAttribute('aria-expanded','false');};
    const button=(text,label,action)=>{const b=el('button','',text);b.type='button';b.setAttribute('aria-label',label);b.addEventListener('click',action);return b;};
    const draw=()=>{
      calendar.replaceChildren();
      const heading=el('div','map-calendar-heading');
      heading.append(button('←','Vorheriger Monat',()=>{month--;if(month<0){month=11;year--;}draw();}));
      heading.append(el('strong','',new Intl.DateTimeFormat('de-DE',{month:'long',year:'numeric'}).format(new Date(year,month,1))));
      heading.append(button('→','Nächster Monat',()=>{month++;if(month>11){month=0;year++;}draw();}));
      const grid=el('div','map-calendar-grid');
      ['Mo','Di','Mi','Do','Fr','Sa','So'].forEach(day=>grid.append(el('span','map-calendar-weekday',day)));
      const offset=(new Date(year,month,1).getDay()+6)%7;
      for(let i=0;i<offset;i++)grid.append(el('span'));
      const days=new Date(year,month+1,0).getDate(),today=berlinNow().date;
      for(let day=1;day<=days;day++){
        const value=`${year}-${pad(month+1)}-${pad(day)}`;
        const b=button(String(day),new Intl.DateTimeFormat('de-DE',{dateStyle:'full'}).format(new Date(year,month,day)),()=>{selected=value;sync();close();open.focus();});
        if(value===selected){b.classList.add('is-selected');b.setAttribute('aria-pressed','true');}
        if(value===today)b.classList.add('is-today');
        grid.append(b);
      }
      calendar.append(heading,grid);

    };
    open.addEventListener('click',()=>{const show=calendar.hidden;calendar.hidden=!show;open.setAttribute('aria-expanded',String(show));if(show){draw();calendar.querySelector('.is-selected')?.focus();}});
    root.addEventListener('keydown',e=>{if(e.key==='Escape'){close();open.focus();}});
    root.mapCloseDate=close;
    time.addEventListener('input',sync);
    root.querySelectorAll('[data-time]').forEach(b=>b.addEventListener('click',()=>{if(b.dataset.time==='now'){const now=berlinNow();selected=now.date;time.value=now.time;}else{selected=selected||berlinNow().date;time.value=b.dataset.time;}[year,month]=selected.split('-').map(Number);month--;sync();}));
    if(!source.required){const clear=button('×','Datum löschen',()=>{selected='';sync();close();open.focus();});clear.className='map-date-clear';clear.title='Datum löschen';controls.append(clear);}
    sync();
  });
  };initDatePickers();
  document.addEventListener('click',event=>document.querySelectorAll('[data-map-datetime]').forEach(root=>{if(!event.composedPath().includes(root))root.mapCloseDate?.();}));
  new MutationObserver(records=>{if(records.some(record=>record.addedNodes.length))initDatePickers();}).observe(document.body,{childList:true,subtree:true});
  const rights=[...document.querySelectorAll('input[type="checkbox"][name="viewers"],input[type="checkbox"][name="editors"]')];
  const syncRights=()=>rights.forEach(box=>{
    const opposite=rights.some(other=>other.name!==box.name && other.value===box.value && other.checked);
    box.disabled=opposite&&!box.checked;
    box.closest('label')?.classList.toggle('map-choice-disabled',box.disabled);
    box.title=box.disabled?'Diese Person ist bereits im anderen Berechtigungsbereich ausgewählt.':'';
  });
  rights.forEach(box=>box.addEventListener('change',syncRights));syncRights();
  document.querySelectorAll('[data-group-limits]').forEach(root=>{
    const source=root.querySelector('input[type="hidden"]');
    const sync=()=>{const limits={};root.querySelectorAll('[data-group-id]').forEach(box=>{const input=root.querySelector(`[data-limit-for="${box.dataset.groupId}"]`);input.disabled=!box.checked;if(box.checked)limits[box.dataset.groupId]=input.value===''?null:Number(input.value);});source.value=JSON.stringify(limits);};
    root.addEventListener('change',sync);root.addEventListener('input',sync);sync();
  });
})();

(() => {
  const grow=area=>{area.style.height='auto';area.style.height=Math.max(42,area.scrollHeight+2)+'px';};
  document.querySelectorAll('textarea[data-autogrow]').forEach(area=>{grow(area);area.addEventListener('input',()=>grow(area));});
  document.querySelectorAll('[data-event-share]').forEach(root=>{
    const status=root.querySelector('[data-share-status]'),input=root.querySelector('[data-share-url]');
    root.querySelector('[data-copy-link]').addEventListener('click',async()=>{
      try{if(!navigator.clipboard?.writeText)throw Error();await navigator.clipboard.writeText(input.value);status.textContent='Anmeldelink kopiert.';}
      catch{input.focus();input.select();try{if(!document.execCommand('copy'))throw Error();status.textContent='Anmeldelink kopiert.';}catch{status.textContent='Bitte den markierten Link manuell kopieren.';}}
    });
    root.querySelector('[data-copy-qr]').addEventListener('click',async event=>{
      const button=event.currentTarget;
      if(!navigator.clipboard?.write || !globalThis.ClipboardItem){status.textContent='Dieser Browser unterstützt das Kopieren von Bildern nicht. Bitte den PNG-Download verwenden.';return;}
      try{
        const png=fetch(button.dataset.qrUrl,{credentials:'same-origin'}).then(response=>{if(!response.ok)throw Error();return response.blob();});
        await navigator.clipboard.write([new ClipboardItem({'image/png':png})]);status.textContent='QR-Code als Bild kopiert.';
      }catch{status.textContent='Bild konnte nicht kopiert werden. Bitte den PNG-Download verwenden.';}
    });
  });
})();

(() => {
  const menus=[...document.querySelectorAll('.map-menu')];
  document.addEventListener('click',event=>menus.forEach(menu=>{if(!menu.contains(event.target))menu.open=false;}));
  document.addEventListener('keydown',event=>{if(event.key==='Escape')menus.forEach(menu=>{if(menu.open){menu.open=false;menu.querySelector('summary').focus();}});});
  document.querySelectorAll('.selector-filter input').forEach(input=>{if(!input.hasAttribute('aria-label'))input.setAttribute('aria-label','Berechtigungen filtern');});
})();

/* Dialogs keep sharing and deletion out of the dashboard grid flow. */
(() => {
  const updateLock=()=>document.body.classList.toggle('map-modal-open',!!document.querySelector('dialog[open]'));
  const close=dialog=>{if(typeof dialog.close==='function')dialog.close();else dialog.removeAttribute('open');updateLock();};
  document.querySelectorAll('[data-open-dialog]').forEach(trigger=>trigger.addEventListener('click',event=>{
    const dialog=document.getElementById(trigger.dataset.openDialog);if(!dialog)return;
    event.preventDefault();if(dialog.open)return;if(typeof dialog.showModal==='function')dialog.showModal();else dialog.setAttribute('open','');updateLock();
  }));
  document.querySelectorAll('[data-close-dialog]').forEach(button=>button.addEventListener('click',()=>close(button.closest('dialog'))));
  document.querySelectorAll('dialog').forEach(dialog=>{
    dialog.addEventListener('close',updateLock);
    dialog.addEventListener('click',event=>{if(event.target!==dialog)return;const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)close(dialog);});
  });
  document.querySelectorAll('[data-template-picker]').forEach(root=>{
    const select=root.querySelector('select'),edit=root.querySelector('[data-template-edit]');
    const sync=()=>{
      const valid=/^\d+$/.test(select.value);edit.setAttribute('aria-disabled',String(!valid));edit.tabIndex=valid?0:-1;
      if(valid){const url=new URL('/admin/formularbaukasten/'+select.value+'/',location.origin);url.searchParams.set('event',root.dataset.eventId);url.searchParams.set('zurueck',location.pathname);edit.href=url.href;}else edit.href='#';
    };
    edit.addEventListener('click',event=>{if(edit.getAttribute('aria-disabled')==='true')event.preventDefault();});
    select.addEventListener('change',sync);sync();
    window.addEventListener('focus',async()=>{
      if(!root.dataset.optionsUrl)return;
      try{const response=await fetch(root.dataset.optionsUrl,{credentials:'same-origin'});if(!response.ok)return;const data=await response.json(),old=select.value;select.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent='Bitte Vorlage auswählen';select.append(empty);data.templates.forEach(item=>{const option=document.createElement('option');option.value=String(item.id);option.textContent=item.name;select.append(option);});const exists=[...select.options].some(o=>o.value===old);select.value=exists?old:'';if(old&&!exists){empty.textContent='Bisherige Vorlage nicht mehr verfügbar – bitte auswählen';}sync();}catch{}
    });
  });
  document.querySelectorAll('select[name="capacity_mode"]').forEach(mode=>{
    const form=mode.closest('form'),shared=form.querySelector('[name="shared_capacity"]'),waiting=form.querySelector('[name="waitlist_mode"]');
    const sync=()=>{
      const pooled=mode.value==='shared',unlimited=mode.value==='unlimited';
      if(shared){shared.disabled=unlimited;shared.closest('.map-field,.form-row')?.toggleAttribute('hidden',!pooled);shared.required=pooled;}
      form.querySelectorAll('input[name="capacity"],input[name^="capacity_"]').forEach(input=>input.closest('.map-field,.form-row')?.toggleAttribute('hidden',pooled||unlimited));
      form.querySelectorAll('[data-limit-for]').forEach(input=>input.parentElement.hidden=pooled||unlimited);
      if(pooled&&waiting)waiting.value='shared';
      if(waiting)waiting.closest('.map-field,.form-row')?.toggleAttribute('hidden',unlimited);
      const waitlist=form.querySelector('[name=waitlist_enabled]');if(waitlist){waitlist.closest('.map-field,.form-row')?.toggleAttribute('hidden',unlimited);if(unlimited)waitlist.checked=false;}
      form.querySelectorAll('input[name=capacity],input[name^=capacity_]').forEach(input=>input.disabled=unlimited);
    };
    mode.addEventListener('change',sync);sync();
  });
})();

/* Keep long editing sessions from losing unsaved work accidentally. */
(() => {
  document.querySelector('[data-error-summary]')?.focus();
  document.querySelectorAll('form[data-unsaved-guard]').forEach(form=>{
    let dirty=false;
    const mark=event=>{if(event.isTrusted)dirty=true;};
    form.addEventListener('input',mark);form.addEventListener('change',mark);
    form.addEventListener('click',event=>{if(event.isTrusted&&event.target.closest('[data-map-builder] button:not([data-view])'))dirty=true;});
    form.addEventListener('submit',()=>{dirty=false;});
    window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  });
})();
