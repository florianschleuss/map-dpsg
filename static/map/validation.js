(() => {
  const message=input=>{
    const v=input.validity;
    if(v.valueMissing)return input.type==='checkbox'?'Bitte dieses Kästchen bestätigen.':input.type==='radio'?'Bitte eine Antwort auswählen.':'Bitte dieses Feld ausfüllen.';
    if(v.typeMismatch)return input.type==='email'?'Bitte eine gültige E-Mail-Adresse eingeben.':'Bitte eine gültige Internetadresse eingeben.';
    if(v.badInput)return 'Bitte einen gültigen Wert eingeben.';
    if(v.rangeUnderflow)return 'Bitte einen Wert von mindestens '+input.min+' eingeben.';
    if(v.rangeOverflow)return 'Bitte einen Wert von höchstens '+input.max+' eingeben.';
    if(v.stepMismatch)return 'Bitte einen Wert in den vorgesehenen Schritten eingeben.';
    if(v.tooShort)return 'Bitte mindestens '+input.minLength+' Zeichen eingeben.';
    if(v.tooLong)return 'Bitte höchstens '+input.maxLength+' Zeichen eingeben.';
    if(v.patternMismatch)return 'Bitte die Eingabe im angegebenen Format ergänzen.';
    return 'Bitte die Eingabe prüfen.';
  };
  document.addEventListener('invalid',event=>{const input=event.target;if(!input.setCustomValidity)return;input.setCustomValidity('');if(!input.validity.valid)input.setCustomValidity(message(input));},true);
  const clear=event=>{if(event.target.setCustomValidity)event.target.setCustomValidity('');};
  document.addEventListener('input',clear);document.addEventListener('change',clear);
})();
