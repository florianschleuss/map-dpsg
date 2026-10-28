"""Public opt-in day aggregates: room names and day aggregates only; no event details or contact information."""
from datetime import date,datetime,time,timedelta
from django import forms
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from .models import Room,RoomBooking,BookingChange,RoomSettings
from .forms import local_datetime

class RangeForm(forms.Form):
    start=forms.DateField(input_formats=['%Y-%m-%d'],required=False)
    end=forms.DateField(input_formats=['%Y-%m-%d'],required=False)
    def clean(self):
        data=super().clean();start=data.get('start') or timezone.localdate()
        if not 2000<=start.year<=2100:raise forms.ValidationError('Das Startdatum muss zwischen 2000 und 2100 liegen.')
        end=data.get('end') or start+timedelta(days=89)
        if start.year<2000 or end.year>2100 or end<start or (end-start).days>365:
            raise forms.ValidationError('Bitte einen Zeitraum von höchstens 366 Tagen zwischen 2000 und 2100 wählen.')
        data.update(start=start,end=end);return data

def response(payload,status=200):
    result=JsonResponse(payload,status=status,json_dumps_params={'ensure_ascii':False})
    result['Access-Control-Allow-Origin']='*'
    result['X-Content-Type-Options']='nosniff'
    result['Cache-Control']='no-store'
    return result

@require_GET
def occupancy(request):
    if not RoomSettings.objects.filter(pk=1,public_api_enabled=True).exists():
        return response({'error':'Die öffentliche Belegungs-API ist nicht aktiviert.'},404)
    form=RangeForm(request.GET)
    if not form.is_valid():return response({'error':'Ungültiger Zeitraum.','details':[str(e) for errors in form.errors.values() for e in errors]},400)
    first,last=form.cleaned_data['start'],form.cleaned_data['end']
    begin=local_datetime(first,time.min);finish=local_datetime(last+timedelta(days=1),time.min)
    from datetime import timezone as utc
    rooms=dict(Room.objects.filter(active=True).values_list('pk','name'));days={}
    def bounds(day):
        return (local_datetime(day,time.min).astimezone(utc.utc),local_datetime(day+timedelta(days=1),time.min).astimezone(utc.utc))
    def include(query,status):
        for start,end,room in query.values_list('starts_at','ends_at','rooms__pk').iterator(chunk_size=1000):
            if room not in rooms:continue
            day=max(first,timezone.localtime(start).date());stop=min(last,timezone.localtime(end-timedelta(microseconds=1)).date())
            start=start.astimezone(utc.utc);end=end.astimezone(utc.utc)
            while day<=stop:
                low,high=bounds(day)
                intervals=days.setdefault(day,{'approved':{},'pending':{}})[status].setdefault(room,[])
                intervals.append((max(start,low),min(end,high)));day+=timedelta(days=1)
    include(RoomBooking.objects.filter(status='approved',starts_at__lt=finish,ends_at__gt=begin),'approved')
    include(RoomBooking.objects.filter(status='pending',starts_at__lt=finish,ends_at__gt=begin),'pending')
    include(BookingChange.objects.filter(status='pending',booking__status='approved',starts_at__lt=finish,ends_at__gt=begin),'pending')
    def level(day,mapping):
        if not mapping:return 'none'
        if set(mapping)!=set(rooms):return 'partial'
        low,high=bounds(day)
        for intervals in mapping.values():
            cursor=low
            for start,end in sorted(intervals):
                if start>cursor:return 'partial'
                cursor=max(cursor,end)
            if cursor<high:return 'partial'
        return 'full'
    rows=[]
    for day,values in sorted(days.items()):
        combined={}
        for mapping in values.values():
            for room,intervals in mapping.items():combined.setdefault(room,[]).extend(intervals)
        rows.append({'date':day.isoformat(),'occupancy':level(day,combined),
            'statuses':[status for status in ['approved','pending'] if values[status]],
            'approved':level(day,values['approved']),'pending':level(day,values['pending']),
            'rooms':[name for pk,name in rooms.items() if pk in combined],
            'approved_rooms':[name for pk,name in rooms.items() if pk in values['approved']],
            'pending_rooms':[name for pk,name in rooms.items() if pk in values['pending']]})
    return response({'version':1,'timezone':str(timezone.get_current_timezone()),'start':first.isoformat(),'end':last.isoformat(),
        'aggregation':'continuous_full_day','semantics':'full means every active room is continuously occupied for the complete local calendar day across all matching bookings',
        'days':rows})
