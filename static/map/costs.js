(() => {
  document.querySelectorAll('form').forEach(form => {
    const mode = form.querySelector('[name="cost_mode"]');
    if (!mode) return;
    const method = form.querySelector('[name="payment_method"]');
    const names = ['cost_mode','cost_amount','cost_text','payment_method','bank_account_holder','bank_iban','bank_bic','payment_note','payment_due','confirm_existing_costs'];
    const locked = new Set(names.filter(name => form.querySelector(`[name="${name}"]`)?.disabled));
    const show = (name, visible) => {
      const field = form.querySelector(`[name="${name}"]`);
      if (!field) return;
      field.closest('.map-field')?.toggleAttribute('hidden', !visible);
      field.disabled = locked.has(name) || !visible;
    };
    const sync = () => {
      const paid = mode.value !== 'free';
      const bank = paid && ['transfer','reminder'].includes(method?.value);
      show('cost_amount', mode.value === 'fixed');
      show('cost_text', mode.value === 'custom');
      show('payment_method', paid);
      ['bank_account_holder','bank_iban','bank_bic'].forEach(name => show(name, bank));
      show('payment_note', paid);show('payment_due', bank);
      const confirmation = form.querySelector('[name="confirm_existing_costs"]');
      show('confirm_existing_costs', paid && confirmation?.dataset.existingCosts === 'yes');
    };
    mode.addEventListener('change',sync);method?.addEventListener('change',sync);sync();
  });
})();
