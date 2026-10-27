(() => {
  document.querySelectorAll('[data-mail-settings]').forEach(form=>{
    const provider=form.querySelector('[name="provider"]');
    const toggle=(name,visible)=>{const field=form.querySelector(`[name="${name}"]`);if(field)field.closest('.map-field')?.toggleAttribute('hidden',!visible);};
    const sync=()=>{
      const graph=provider.value==='microsoft_graph';
      ['tenant_id','client_id','client_secret','clear_client_secret','client_secret_expires_on'].forEach(name=>toggle(name,graph));
      ['host','port','security','username','password','clear_password'].forEach(name=>toggle(name,!graph));
    };
    provider.addEventListener('change',sync);sync();
    form.addEventListener('submit',event=>{
      if(form.dataset.busy){event.preventDefault();return;}
      form.dataset.busy='true';form.classList.add('map-form-pending');
      const action=event.submitter?.value||'save';
      form.querySelector('[data-mail-progress]').textContent=action==='check'?'Einstellungen werden gespeichert und Zugangsdaten geprüft …':action==='test'?'Einstellungen werden gespeichert und die Testmail wird versendet …':'Einstellungen werden gespeichert …';
    });
  });
})();
