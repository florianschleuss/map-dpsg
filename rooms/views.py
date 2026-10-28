import calendar
from datetime import date,datetime,time,timedelta
from urllib.parse import urlencode
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse,JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods,require_GET,require_POST
from .access import require_user,can_edit,board,can_configure,can_request
from .models import RoomBooking,BookingChange,RoomSettings,RoomEmailTemplate
from .forms import BookingForm,ConflictForm,FilterForm,DecisionForm,SettingsForm,local_datetime
from .services import conflicts,conflict_token,save_booking,decide,cancel,withdraw
from .presentation import period,decorate,ical_bytes


def filtered(request):
    require_user(request.user)
    form=FilterForm(request.GET)
    rows=RoomBooking.objects.select_related('creator','decided_by').prefetch_related('rooms','changes__rooms').order_by('starts_at','pk')
    if not form.is_valid():return form,rows.none()
    data=form.cleaned_data
    from django.db.models import Q
    current=Q(pk__isnull=False);proposed=Q(status='approved',changes__status='pending')
    if data.get('start'):
        start=local_datetime(data['start'],time.min);current&=Q(ends_at__gt=start);proposed&=Q(changes__ends_at__gt=start)
    if data.get('end'):
        end=local_datetime(data['end']+timedelta(days=1),time.min);current&=Q(starts_at__lt=end);proposed&=Q(changes__starts_at__lt=end)
    if data.get('rooms'):current&=Q(rooms__in=data['rooms']);proposed&=Q(changes__rooms__in=data['rooms'])
    if data.get('grouping'):current&=Q(grouping__icontains=data['grouping']);proposed&=Q(changes__grouping__icontains=data['grouping'])
    if data.get('status'):
        current&=Q(status=data['status'])
        if data['status']!='pending':proposed&=Q(pk__isnull=True)
    rows=rows.filter(current|proposed).distinct()
    if request.GET.get('mine')=='1':rows=rows.filter(creator=request.user)
    return form,rows


def decorate_row(row,user):
    decorate(row);row.can_edit=can_edit(user,row)
    row.pending_change=next((c for c in row.changes.all() if c.status=='pending'),None)
    row.overlaps=conflicts([r.pk for r in row.rooms.all()],row.starts_at,row.ends_at,row.pk) if row.status in ['pending','approved'] else []
    if row.pending_change:
        seen={(c['booking'].pk,c['proposal']) for c in row.overlaps}
        row.overlaps += [c for c in conflicts([r.pk for r in row.pending_change.rooms.all()],row.pending_change.starts_at,row.pending_change.ends_at,row.pk) if (c['booking'].pk,c['proposal']) not in seen]
    return row


def entry_matches(item,criteria):
    if criteria.get('rooms') and not {r.pk for r in item.rooms.all()}&{r.pk for r in criteria['rooms']}:return False
    if criteria.get('grouping') and criteria['grouping'].casefold() not in item.grouping.casefold():return False
    if criteria.get('status') and item.status!=criteria['status']:return False
    if criteria.get('start') and item.ends_at<=local_datetime(criteria['start'],time.min):return False
    if criteria.get('end') and item.starts_at>=local_datetime(criteria['end']+timedelta(days=1),time.min):return False
    return True


@login_required
@require_GET
def index(request):
    form,rows=filtered(request);page=Paginator(rows,30).get_page(request.GET.get('page'))
    for row in page.object_list:decorate_row(row,request.user)
    query=request.GET.copy();query.pop('page',None)
    return render(request,'rooms/index.html',{'filter_form':form,'page':page,'query':query.urlencode(),'room_board':board(request.user)})


@login_required
@require_GET
def pending(request):
    if not board(request.user):raise PermissionDenied
    from django.db.models import Q
    rows=RoomBooking.objects.filter(Q(status='pending')|Q(status='approved',changes__status='pending')).distinct().prefetch_related('rooms','changes__rooms').order_by('starts_at','pk')
    page=Paginator(rows,30).get_page(request.GET.get('page'))
    for row in page.object_list:decorate_row(row,request.user)
    return render(request,'rooms/index.html',{'page':page,'pending_only':True,'room_board':True})


@login_required
@require_http_methods(['GET','POST'])
def edit(request,pk=None):
    require_user(request.user);booking=get_object_or_404(RoomBooking,pk=pk) if pk else None
    if not can_request(request.user):raise PermissionDenied
    if booking and not can_edit(request.user,booking):raise PermissionDenied
    form=BookingForm(request.POST if request.method=='POST' else None,booking=booking)
    preview=None
    if request.method=='POST' and form.is_valid():
        preview=conflicts([r.pk for r in form.cleaned_data['rooms']],form.cleaned_data['starts_at'],form.cleaned_data['ends_at'],booking.pk if booking else None)
        if request.POST.get('action')!='preview':
            try:row=save_booking(request.user,form.cleaned_data,booking.pk if booking else None)
            except ValidationError as error:form.add_error(None,error)
            else:
                messages.success(request,'Anfrage gespeichert. Bei Änderungen an einer genehmigten Belegung bleibt die bisherige Fassung bis zur Freigabe gültig.')
                return redirect('rooms:detail',pk=row.pk)
    return render(request,'rooms/edit.html',{'form':form,'booking':booking,'conflicts':preview,'previewed':preview is not None,
        'existing_change':booking.changes.filter(status='pending').exists() if booking else False})


def history_rows(booking):
    labels={'starts_at':'Beginn','ends_at':'Ende (exklusiv)','all_day':'Ganztägig','rooms':'Räume','grouping':'Gruppierung','purpose':'Veranstaltung / Zweck','status':'Status','contact_person':'Ansprechperson','contact':'Kontakt','version':'Fassung','decision_reason':'Begründung'}
    from django.utils.dateparse import parse_datetime
    from .models import STATUSES
    def display(key,value):
        if value is None:return '—'
        if key in ['starts_at','ends_at']:
            parsed=parse_datetime(value)
            return timezone.localtime(parsed).strftime('%d.%m.%Y, %H:%M') if parsed else value
        if key=='status':return dict(STATUSES).get(value,value)
        if isinstance(value,list):return ', '.join(value)
        if isinstance(value,bool):return 'Ja' if value else 'Nein'
        return value
    result=[]
    for row in booking.history.select_related('actor')[:100]:
        row.differences=[{'label':label,'before':display(key,row.before.get(key)),'after':display(key,row.after.get(key))} for key,label in labels.items() if row.before.get(key)!=row.after.get(key)]
        result.append(row)
    return result


@login_required
@require_http_methods(['GET','POST'])
def detail(request,pk):
    require_user(request.user)
    booking=get_object_or_404(RoomBooking.objects.select_related('creator','decided_by').prefetch_related('rooms','changes__rooms'),pk=pk)
    proposal=booking.changes.filter(status='pending').prefetch_related('rooms').first()
    target=proposal or booking
    current_conflicts=conflicts(booking.rooms.values_list('pk',flat=True),booking.starts_at,booking.ends_at,booking.pk) if proposal else []
    overlaps=conflicts(target.rooms.values_list('pk',flat=True),target.starts_at,target.ends_at,booking.pk) if booking.status in ['pending','approved'] else []
    decision_form=DecisionForm(initial={'version':booking.version,'conflict_token':conflict_token(overlaps)})
    error=None
    if request.method=='POST':
        action=request.POST.get('action')
        try:
            if action in ['approve','reject']:
                if not board(request.user):raise PermissionDenied
                decision_form=DecisionForm(request.POST)
                if decision_form.is_valid():
                    data=decision_form.cleaned_data
                    decide(request.user,pk,action,data['version'],data['reason'],data['confirm_conflicts'],data['conflict_token'],proposal.pk if proposal else None)
                    messages.success(request,'Entscheidung gespeichert.');return redirect('rooms:detail',pk=pk)
            elif action in ['cancel','withdraw']:
                version=forms.IntegerField(min_value=1).clean(request.POST.get('version'))
                if request.POST.get('confirm')!='yes':raise ValidationError('Bitte die Aktion ausdrücklich bestätigen.')
                (cancel if action=='cancel' else withdraw)(request.user,pk,version)
                messages.success(request,'Stornierung gespeichert.' if action=='cancel' else 'Änderungsantrag zurückgezogen.');return redirect('rooms:detail',pk=pk)
            else:raise ValidationError('Unbekannte Aktion.')
        except ValidationError as exception:error=' '.join(exception.messages)
        if error and action in ['approve','reject']:
            messages.error(request,error);return redirect('rooms:detail',pk=pk)
    decorate(booking)
    if proposal:proposal.period_label=period(proposal)
    return render(request,'rooms/detail.html',{'booking':booking,'proposal':proposal,'conflicts':overlaps,
        'current_conflicts':current_conflicts,'has_approved_conflicts':any(c['status']=='approved' for c in overlaps),'can_edit':can_edit(request.user,booking),
        'room_board':board(request.user),'decision_form':decision_form,'error':error,'history_rows':history_rows(booking)})


@login_required
@require_GET
def calendar_view(request):
    form,rows=filtered(request)
    try:anchor=date.fromisoformat(request.GET.get('date',''))
    except ValueError:anchor=timezone.localdate()
    if not 1901<=anchor.year<=2199:anchor=timezone.localdate()
    mode='week' if request.GET.get('view')=='week' else 'month'
    if mode=='week':
        first=anchor-timedelta(days=anchor.weekday());last=first+timedelta(days=6)
        weeks=[[first+timedelta(days=i) for i in range(7)]];previous=anchor-timedelta(days=7);following=anchor+timedelta(days=7)
    else:
        weeks=calendar.Calendar(firstweekday=0).monthdatescalendar(anchor.year,anchor.month);first=weeks[0][0];last=weeks[-1][-1]
        previous=anchor.replace(day=1)-timedelta(days=1);following=(anchor.replace(day=28)+timedelta(days=4)).replace(day=1)
    start=local_datetime(first,time.min);end=local_datetime(last+timedelta(days=1),time.min)
    # Include a requested move into this window even while its old booking lies outside it.
    from django.db.models import Q
    candidates=rows.filter(Q(starts_at__lt=end,ends_at__gt=start)|Q(status='approved',changes__status='pending',changes__starts_at__lt=end,changes__ends_at__gt=start)).distinct()
    entries=[]
    criteria=form.cleaned_data if form.is_valid() else {}
    def matches(item):return entry_matches(item,criteria)
    for row in candidates:
        if matches(row) and (row.status in ['pending','approved'] or request.GET.get('status') in ['rejected','cancelled']):
            entries.append({'booking':row,'entry':row,'proposal':False})
        if row.status=='approved':
            for change in row.changes.all():
                if change.status=='pending' and matches(change):entries.append({'booking':row,'entry':change,'proposal':True})
    cells=[]
    for week in weeks:
        days=[]
        for day in week:
            day_start=local_datetime(day,time.min);day_end=local_datetime(day+timedelta(days=1),time.min)
            items=[]
            for item in entries:
                if item['entry'].starts_at<day_end and item['entry'].ends_at>day_start:
                    copy=dict(item);copy['period']=period(item['entry']);items.append(copy)
            days.append({'date':day,'items':items,'today':day==timezone.localdate(),'outside':day.month!=anchor.month})
        cells.append(days)
    def link(day,view=mode):
        query=request.GET.copy();query['date']=day.isoformat();query['view']=view;return '?'+query.urlencode()
    return render(request,'rooms/calendar.html',{'filter_form':form,'weeks':cells,'anchor':anchor,'mode':mode,
        'previous_url':link(previous),'next_url':link(following),'month_url':link(anchor,'month'),'week_url':link(anchor,'week'),'today_url':link(timezone.localdate())})


@login_required
@require_GET
def export(request,kind):
    form,rows=filtered(request)
    if not form.is_valid():return HttpResponse('Ungültige Filter. Bitte die Buchungsübersicht öffnen und korrigieren.',status=400)
    if rows.count()>10000:return HttpResponse('Bitte den Export durch Zeitraum oder Räume auf höchstens 10.000 Buchungen begrenzen.',status=400)
    if kind=='excel':
        from map.excel_export import workbook_bytes
        grid=[['Buchungsnummer','Fassung','Zeitraum','Räume','Gruppierung','Veranstaltung / Zweck','Ansprechperson','Kontakt','Status','Buchende Person']]
        for row in rows:
            for item in [row]+[c for c in row.changes.all() if c.status=='pending']:
                if not entry_matches(item,form.cleaned_data):continue
                grid.append([row.pk,'Änderungsantrag' if isinstance(item,BookingChange) else 'Aktuelle Buchung',period(item),', '.join(r.name for r in item.rooms.all()),item.grouping,item.purpose,row.contact_person,row.contact,item.get_status_display(),row.creator.get_username() if row.creator else 'Gelöschtes Konto'])
        response=HttpResponse(workbook_bytes(grid,sheet_name='Raumbuchungen'),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');filename='raumbuchungen.xlsx'
    elif kind=='ical':
        response=HttpResponse(ical_bytes(row for row in rows if entry_matches(row,form.cleaned_data)),content_type='text/calendar; charset=utf-8');filename='raumbuchungen.ics'
    else:
        from django.http import Http404
        raise Http404
    response['Content-Disposition']='attachment; filename="'+filename+'"';return response


@login_required
@require_http_methods(['GET','POST'])
def settings_view(request):
    if not can_configure(request.user):raise PermissionDenied
    settings,_=RoomSettings.objects.get_or_create(pk=1)
    form=SettingsForm(request.POST if request.method=='POST' else None,instance=settings)
    if request.method=='POST' and form.is_valid():
        form.save();messages.success(request,'Raumbuchungs-Einstellungen gespeichert.');return redirect('rooms:settings')
    return render(request,'rooms/settings.html',{'form':form})


class TemplateForm(forms.Form):
    subject=forms.CharField(label='Betreff',max_length=200)
    body=forms.CharField(label='Nachrichtentext',max_length=20000,widget=forms.Textarea(attrs={'rows':14}))
    def clean(self):
        from .notifications import validate_template
        data=super().clean()
        if 'subject' in data and 'body' in data:
            try:validate_template(data['subject'],data['body'])
            except ValueError as error:raise ValidationError(str(error))
        return data


@login_required
@require_GET
def templates(request):
    if not can_configure(request.user):raise PermissionDenied
    from .notifications import EVENTS
    custom=set(RoomEmailTemplate.objects.values_list('key',flat=True))
    from map.mail_policy import state
    return render(request,'rooms/templates.html',{'rows':[{'key':key,'title':value[0],'description':value[1],'custom':key in custom,'delivery':state('rooms',key)} for key,value in EVENTS.items()]})


@login_required
@require_http_methods(['GET','POST'])
def template_edit(request,key):
    if not can_configure(request.user):raise PermissionDenied
    from .notifications import EVENTS,defaults,PLACEHOLDERS
    from django.http import Http404
    if key not in EVENTS:raise Http404
    saved=RoomEmailTemplate.objects.filter(key=key).first();subject,body=(saved.subject,saved.body) if saved else defaults(key)
    form=TemplateForm(request.POST if request.method=='POST' else None,initial={'subject':subject,'body':body});preview=None
    if request.method=='POST':
        if request.POST.get('action')=='reset':
            if request.POST.get('confirm')!='yes':form.add_error(None,'Bitte das Zurücksetzen ausdrücklich bestätigen.')
            else:RoomEmailTemplate.objects.filter(key=key).delete();return redirect('rooms:template_edit',key=key)
        elif form.is_valid():
            context={'purpose':'Beispiel-Gruppenabend','grouping':'Beispielgruppe','rooms':'Raum 1, Garten','period':'15.11.2026, 17:00 – 19:00 Uhr',
                'status':{'approved':'Genehmigt','rejected':'Abgelehnt','cancelled':'Storniert','contact_updated':'Genehmigt'}.get(key,'Genehmigt' if key.startswith('change_') else 'Schwebend'),
                'change_status':{'change_request':'Schwebend','change_approved':'Genehmigt','change_rejected':'Abgelehnt','change_withdrawn':'Storniert'}.get(key,'Kein Änderungsantrag'),
                'current_period':'15.11.2026, 17:00 – 18:00 Uhr','current_rooms':'Raum 1','current_purpose':'Beispiel-Gruppenabend',
                'contact_person':'Alex Beispiel','contact':'kontakt@example.org','reason':'Beispiel einer Begründung','booking_url':'https://beispiel.invalid/raeume/1/','creator':'Beispiel-Leitung'}
            preview=(form.cleaned_data['subject'].format_map(context),form.cleaned_data['body'].format_map(context))
            if request.POST.get('action')=='save':
                RoomEmailTemplate.objects.update_or_create(key=key,defaults=form.cleaned_data);messages.success(request,'Raumbuchungs-Vorlage gespeichert.');return redirect('rooms:template_edit',key=key)
    return render(request,'rooms/template_edit.html',{'form':form,'title':EVENTS[key][0],'placeholders':PLACEHOLDERS.items(),'preview':preview,'custom':bool(saved)})


@login_required
@require_POST
def live_conflicts(request):
    require_user(request.user)
    if not can_request(request.user):raise PermissionDenied
    from map.security_rules import numeric_pk
    booking=None
    if request.POST.get('booking_id'):
        booking=get_object_or_404(RoomBooking,pk=numeric_pk(request.POST['booking_id']))
        if not can_edit(request.user,booking):raise PermissionDenied
    form=ConflictForm(request.POST,booking=booking)
    if not form.is_valid():
        return JsonResponse({'valid':False,'errors':[str(message) for errors in form.errors.values() for message in errors]},status=400)
    data=form.cleaned_data
    rows=conflicts([r.pk for r in data['rooms']],data['starts_at'],data['ends_at'],booking.pk if booking else None)
    from django.template.loader import render_to_string
    return JsonResponse({'valid':True,'count':len(rows),'html':render_to_string('rooms/live_conflicts.html',{'conflicts':rows},request=request)})
