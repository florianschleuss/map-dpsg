from decimal import Decimal
from django import forms
from .payment_rules import COST_FIELDS,normalized_costs

class CostFieldsMixin:
    def add_cost_fields(self,initial=None):
        fields={
            'cost_mode':forms.ChoiceField(label='Kosten der Veranstaltung',choices=[('free','Kostenlos'),('fixed','Fester Betrag pro Person'),('custom','Kostenbeschreibung als Freitext')],required=False,initial='free',help_text='Die Kosten werden vor der Anmeldung angezeigt; Bankdaten bleiben bis zur bestätigten Teilnahme geschützt.'),
            'cost_amount':forms.DecimalField(label='Beitrag pro Person in Euro',max_digits=8,decimal_places=2,min_value=Decimal('0.01'),required=False,localize=True),
            'cost_text':forms.CharField(label='Kostenbeschreibung',required=False,max_length=2000,widget=forms.Textarea(attrs={'rows':3}),help_text='Diese Beschreibung wird vor der Anmeldung angezeigt. Bitte hier keine Bankdaten eintragen.'),
            'payment_method':forms.ChoiceField(label='Bezahlungsvorgang',required=False,choices=[('none','Bitte auswählen'),('cash','Bargeld zur Veranstaltung mitbringen'),('transfer','Überweisung nach bestätigter Anmeldung'),('reminder','Zahlungsaufforderung später per E-Mail')]),
            'bank_account_holder':forms.CharField(label='Kontoinhaber',required=False,max_length=70),
            'bank_iban':forms.CharField(label='IBAN',required=False,max_length=50,help_text='Leerzeichen sind erlaubt und werden beim Speichern entfernt. Die Prüfung bestätigt keine tatsächliche Kontoinhaberschaft.'),
            'bank_bic':forms.CharField(label='BIC',required=False,max_length=11,help_text='Für Konten im Europäischen Wirtschaftsraum meist nicht erforderlich; außerhalb bitte angeben.'),
            'payment_note':forms.CharField(label='Zusätzlicher Zahlungshinweis',required=False,max_length=2000,widget=forms.Textarea(attrs={'rows':3})),
            'payment_due':forms.DateField(label='Zahlbar bis (optional)',required=False,widget=forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d')),
        }
        self.fields.update(fields)
        if initial:self.initial.update(initial)
    def clean_costs(self,data):
        if any(name in self.errors for name in COST_FIELDS):return data
        try:data.update(normalized_costs(data))
        except ValueError as error:raise forms.ValidationError(str(error))
        return data

class CostForm(CostFieldsMixin,forms.Form):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.add_cost_fields()
    def clean(self):return self.clean_costs(super().clean())
