from datetime import datetime,timedelta
from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Room,RoomSettings


def local_datetime(day,clock):
    # Reject ambiguous/nonexistent local times rather than silently booking the wrong hour.
    from datetime import timezone as utc
    tz=timezone.get_current_timezone();naive=datetime.combine(day,clock)
    candidates=[]
    for fold in [0,1]:
        value=naive.replace(tzinfo=tz,fold=fold)
        if value.astimezone(utc.utc).astimezone(tz).replace(tzinfo=None)==naive:candidates.append(value)
    if not candidates or len({value.utcoffset() for value in candidates})>1:
        raise ValidationError('Diese Uhrzeit ist wegen der Zeitumstellung nicht eindeutig oder existiert nicht. Bitte eine andere Uhrzeit wählen.')
    return candidates[0]


class BookingForm(forms.Form):
    recurring=forms.BooleanField(label='Wiederkehrend · wöchentlich',required=False,widget=forms.CheckboxInput(attrs={'role':'switch'}))
    weekday=forms.TypedChoiceField(label='Wochentag',choices=[(i,name) for i,name in enumerate(['Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag','Sonntag'])],coerce=int,required=False,empty_value=None)
    start_date=forms.DateField(label='Von – Datum',widget=forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d'))
    end_date=forms.DateField(label='Bis – Datum (einschließlich bei ganztägig)',widget=forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d'))
    all_day=forms.BooleanField(label='Ganztägig – ohne Uhrzeit',required=False)
    start_time=forms.TimeField(label='Von – Uhrzeit',required=False,widget=forms.TimeInput(attrs={'type':'time'},format='%H:%M'))
    end_time=forms.TimeField(label='Bis – Uhrzeit',required=False,widget=forms.TimeInput(attrs={'type':'time'},format='%H:%M'))
    rooms=forms.ModelMultipleChoiceField(label='Räume',queryset=Room.objects.all(),widget=forms.CheckboxSelectMultiple)
    grouping=forms.CharField(label='Gruppierung',max_length=160,help_text='Zum Beispiel Wölflinge oder eine externe Gruppierung.')
    purpose=forms.CharField(label='Veranstaltung / Zweck',max_length=250)
    contact_person=forms.CharField(label='Ansprechperson',max_length=160)
    contact=forms.CharField(label='Kontakt',max_length=500,widget=forms.Textarea(attrs={'rows':2}),help_text='Freitext, z. B. Telefon oder E-Mail einer externen Person. Bitte keine medizinischen Daten eintragen.')
    version=forms.IntegerField(widget=forms.HiddenInput,required=False,min_value=1)
    def __init__(self,*args,booking=None,**kwargs):
        self.booking=booking;super().__init__(*args,**kwargs)
        from django.db.models import Q
        allowed=Q(active=True)
        if booking:allowed|=Q(roombooking_entries=booking)
        self.fields['rooms'].queryset=Room.objects.filter(allowed).distinct()
        if booking:
            start=timezone.localtime(booking.starts_at);end=timezone.localtime(booking.ends_at)
            self.initial.update(recurring=booking.recurring,weekday=start.weekday(),start_date=start.date(),end_date=(end.date()-timedelta(days=1)) if booking.all_day else end.date(),
                start_time=start.time().replace(tzinfo=None),end_time=end.time().replace(tzinfo=None),all_day=booking.all_day,
                rooms=list(booking.rooms.values_list('pk',flat=True)),grouping=booking.grouping,purpose=booking.purpose,
                contact_person=booking.contact_person,contact=booking.contact,version=booking.version)
        else:self.initial.update(start_date=timezone.localdate()+timedelta(days=1),end_date=timezone.localdate()+timedelta(days=1),start_time='09:00',end_time='17:00')
        for field in self.fields.values():
            if isinstance(field,forms.CharField) and not isinstance(field.widget,forms.HiddenInput) and 'medizinischen Daten' not in field.help_text:
                field.help_text=(field.help_text+' ' if field.help_text else '')+'Bitte keine medizinischen Daten eingeben.'
    def clean(self):
        data=super().clean();first=data.get('start_date');last=data.get('end_date')
        if not first or not last:return data
        from datetime import date
        if last==date.max:raise ValidationError('Das Enddatum liegt außerhalb des unterstützten Zeitraums.')
        if data.get('recurring'):
            from .recurrence import MAX_WEEKS
            weekday=data.get('weekday')
            if weekday is None:raise ValidationError('Bitte einen Wochentag auswählen.')
            if data.get('all_day'):raise ValidationError('Wiederkehrende Buchungen benötigen eine Start- und Enduhrzeit.')
            if last<first or (last-first).days>MAX_WEEKS*7:raise ValidationError('Bitte einen gültigen Wiederholungszeitraum von höchstens zehn Jahren auswählen.')
            first+=timedelta(days=(weekday-first.weekday())%7)
            last-=timedelta(days=(last.weekday()-weekday)%7)
            if first>last:raise ValidationError('Im gewählten Zeitraum liegt keiner der ausgewählten Wochentage.')
            if data.get('start_time') is None or data.get('end_time') is None or data['end_time']<=data['start_time']:
                raise ValidationError('Bitte Start- und Enduhrzeit am selben Tag angeben; das Ende muss nach dem Beginn liegen.')
        if data.get('all_day'):
            from datetime import time
            start=local_datetime(first,time.min);end=local_datetime(last+timedelta(days=1),time.min)
        elif data.get('start_time') is None or data.get('end_time') is None:
            raise ValidationError('Bitte beide Uhrzeiten angeben oder „Ganztägig“ auswählen.')
        else:start=local_datetime(first,data['start_time']);end=local_datetime(last,data['end_time'])
        if end<=start:raise ValidationError('Das Ende muss nach dem Beginn liegen.')
        unchanged=self.booking and start==self.booking.starts_at and end==self.booking.ends_at and data.get('all_day',False)==self.booking.all_day and data.get('recurring',False)==self.booking.recurring and {r.pk for r in data.get('rooms',[])}==set(self.booking.rooms.values_list('pk',flat=True))
        past=(first<timezone.localdate()) if data.get('all_day') else (start<timezone.now())
        if past and not unchanged:raise ValidationError('Buchungen in der Vergangenheit sind nicht erlaubt.')
        from types import SimpleNamespace
        from .recurrence import intervals
        list(intervals(SimpleNamespace(starts_at=start,ends_at=end,all_day=data.get('all_day',False),recurring=data.get('recurring',False))))
        data.update(starts_at=start,ends_at=end)
        return data


class ConflictForm(BookingForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for name in ['grouping','purpose','contact_person','contact','version']:self.fields.pop(name,None)


class FilterForm(forms.Form):
    start=forms.DateField(label='Ab',required=False,widget=forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d'))
    end=forms.DateField(label='Bis',required=False,widget=forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d'))
    rooms=forms.ModelMultipleChoiceField(label='Räume',queryset=Room.objects.all(),required=False,widget=forms.CheckboxSelectMultiple)
    grouping=forms.CharField(label='Gruppierung',required=False,max_length=160)
    status=forms.ChoiceField(label='Status',required=False,choices=[('','Alle Status'),('pending','Schwebend'),('approved','Genehmigt'),('rejected','Abgelehnt'),('cancelled','Storniert')])
    def clean(self):
        data=super().clean()
        from datetime import date
        if data.get('end')==date.max:raise ValidationError('Das Filter-Enddatum liegt außerhalb des unterstützten Zeitraums.')
        if data.get('start') and data.get('end') and data['end']<data['start']:raise ValidationError('Das Filter-Ende liegt vor dem Beginn.')
        return data


class DecisionForm(forms.Form):
    version=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    action=forms.ChoiceField(choices=[('approve','Genehmigen'),('reject','Ablehnen')],widget=forms.HiddenInput)
    reason=forms.CharField(label='Begründung (optional)',max_length=2000,required=False,widget=forms.Textarea(attrs={'rows':2}))
    confirm_conflicts=forms.BooleanField(label='Ich genehmige die angezeigten Überschneidungen mit bereits genehmigten Buchungen ausdrücklich.',required=False)
    conflict_token=forms.CharField(required=False,widget=forms.HiddenInput,max_length=64)


class SettingsForm(forms.ModelForm):
    class Meta:
        model=RoomSettings;fields=['notification_emails','public_api_enabled']
        labels={'notification_emails':'E-Mail-Empfänger für Raumbuchungen'}
        widgets={'notification_emails':forms.Textarea(attrs={'rows':4})}
    def clean_notification_emails(self):
        from django.core.validators import validate_email
        addresses=list(dict.fromkeys(line.strip() for line in self.cleaned_data['notification_emails'].splitlines() if line.strip()))
        if len(addresses)>30:raise ValidationError('Bitte höchstens 30 Empfänger eintragen.')
        for address in addresses:validate_email(address)
        return '\n'.join(addresses)


class RoomForm(forms.ModelForm):
    class Meta:
        model=Room;fields=['name','position']
        labels={'position':'Reihenfolge'}
