"""Board-managed weekly hints, never bookings or public occupancy."""
from datetime import date,datetime,timedelta
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404,redirect,render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .access import board
from .models import GroupSession,Room
from .recurrence import WEEKDAYS,intervals


class GroupSessionForm(forms.ModelForm):
    version=forms.IntegerField(min_value=1,required=False,widget=forms.HiddenInput)
    class Meta:
        model=GroupSession
        fields=['weekday','start_time','end_time','rooms','group_name']
        widgets={'start_time':forms.TimeInput(format='%H:%M',attrs={'type':'time'}),'end_time':forms.TimeInput(format='%H:%M',attrs={'type':'time'}),'rooms':forms.CheckboxSelectMultiple}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from django.db.models import Q
        allowed=Q(active=True)
        if self.instance.pk:allowed|=Q(group_sessions=self.instance)
        self.fields['rooms'].queryset=Room.objects.filter(allowed).distinct()
        self.fields['group_name'].help_text='Freie Bezeichnung, zum Beispiel Wölflinge Gruppe 2. Bitte keine medizinischen Daten eingeben.'
        self.initial['version']=self.instance.version
    def clean(self):
        data=super().clean()
        if data.get('start_time') and data.get('end_time') and data['end_time']<=data['start_time']:
            self.add_error('end_time','Das Ende muss am selben Tag nach dem Beginn liegen.')
        return data


def period(session):
    return f'Jeden {WEEKDAYS[session.weekday]} · {session.start_time:%H:%M}–{session.end_time:%H:%M} Uhr'


def advisory_conflicts(room_ids,target):
    """Compare actual booking occurrences in local wall-clock time, with exclusive ends."""
    rows=list(GroupSession.objects.filter(rooms__pk__in=room_ids).distinct().prefetch_related('rooms'))
    if not rows:return []
    found={}
    for a,b in intervals(target):
        start=timezone.localtime(a).replace(tzinfo=None)
        end=timezone.localtime(b).replace(tzinfo=None)
        for row in rows:
            if row.pk in found:continue
            offset=(row.weekday-start.weekday())%7
            if offset>(date.max-start.date()).days:continue
            day=start.date()+timedelta(days=offset)
            # If this week's session has already ended, only the next can overlap.
            if datetime.combine(day,row.end_time)<=start:
                if (end.date()-day).days<7:continue
                day+=timedelta(days=7)
            if datetime.combine(day,row.start_time)<end and datetime.combine(day,row.end_time)>start:
                found[row.pk]={'group_session':row,'entry':row,'booking':None,'proposal':False,'status':'group_session','period':period(row),'rooms':[room.name for room in row.rooms.all() if room.pk in room_ids]}
    return list(found.values())


@login_required
@require_http_methods(['GET','POST'])
def sessions(request,pk=None):
    if not board(request.user):raise PermissionDenied
    instance=get_object_or_404(GroupSession,pk=pk) if pk else None
    form=GroupSessionForm(request.POST if request.method=='POST' and request.POST.get('action')=='save' else None,instance=instance)
    if request.method=='POST':
        action=request.POST.get('action')
        if action=='save' and form.is_valid():
            try:
                with transaction.atomic():
                    from .services import lock_schedule
                    lock_schedule()
                    if instance:
                        current=get_object_or_404(GroupSession.objects.select_for_update(),pk=instance.pk)
                        if form.cleaned_data.get('version')!=current.version:raise ValidationError('Die Gruppenstunde wurde zwischenzeitlich geändert. Bitte neu laden.')
                    room_ids={room.pk for room in form.cleaned_data['rooms']}
                    retained=set(current.rooms.values_list('pk',flat=True)) if instance else set()
                    if Room.objects.filter(pk__in=room_ids).count()!=len(room_ids) or Room.objects.filter(pk__in=room_ids-retained,active=False).exists():
                        raise ValidationError('Die Raumauswahl wurde zwischenzeitlich geändert. Bitte neu laden und aktive Räume auswählen.')
                    row=form.save(commit=False);row.updated_by=request.user;row.version=(current.version+1) if instance else 1
                    row.save();form.save_m2m()
            except ValidationError as error:form.add_error(None,error)
            else:
                messages.success(request,'Gruppenstunde gespeichert. Sie wird nur als Konflikthinweis berücksichtigt.')
                return redirect('rooms:group_sessions')
        elif action=='delete' and instance:
            with transaction.atomic():
                from .services import lock_schedule
                lock_schedule();current=get_object_or_404(GroupSession.objects.select_for_update(),pk=pk)
                if request.POST.get('confirm')!='yes':messages.error(request,'Bitte das Löschen ausdrücklich bestätigen.')
                elif request.POST.get('version')!=str(current.version):messages.error(request,'Die Gruppenstunde wurde zwischenzeitlich geändert. Bitte neu laden.')
                else:current.delete();messages.success(request,'Gruppenstunde gelöscht.')
            return redirect('rooms:group_sessions')
        elif action!='save':
            messages.error(request,'Unbekannte Aktion. Bitte die Seite neu öffnen.')
    rows=GroupSession.objects.prefetch_related('rooms','updated_by')
    return render(request,'rooms/group_sessions.html',{'form':form,'sessions':rows,'editing':instance})
