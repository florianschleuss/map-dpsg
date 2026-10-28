from datetime import timedelta,timezone as utc
from django.utils import timezone


def period(item):
    start=timezone.localtime(item.starts_at);end=timezone.localtime(item.ends_at)
    if item.all_day:
        last=(end-timedelta(days=1)).date()
        return start.strftime('%d.%m.%Y')+(' – '+last.strftime('%d.%m.%Y') if last!=start.date() else '')+' · Ganztägig'
    if start.date()==end.date():return start.strftime('%d.%m.%Y · %H:%M')+'–'+end.strftime('%H:%M')+' Uhr'
    return start.strftime('%d.%m.%Y, %H:%M')+' – '+end.strftime('%d.%m.%Y, %H:%M')+' Uhr'


def decorate(booking):
    booking.period_label=period(booking);return booking


def ical_escape(value):return str(value).replace('\\','\\\\').replace('\r\n','\n').replace('\r','\n').replace('\n','\\n').replace(';','\\;').replace(',','\\,')


def ical_bytes(bookings):
    # Stable UIDs, exclusive all-day end dates, UTC timed values, UTF-8 folding at 75 octets.
    from django.conf import settings
    from hashlib import sha256
    installation=sha256(settings.PUBLIC_URL.rstrip('/').encode()).hexdigest()[:20]
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//MAP//Raumbuchung//DE','CALSCALE:GREGORIAN','METHOD:PUBLISH']
    for row in bookings:
        lines+=['BEGIN:VEVENT','UID:map-room-'+installation+'-'+str(row.pk)+'@map.invalid','SEQUENCE:'+str(row.version),
          'DTSTAMP:'+row.updated_at.astimezone(utc.utc).strftime('%Y%m%dT%H%M%SZ'),
          'SUMMARY:'+ical_escape(row.purpose),'LOCATION:'+ical_escape(', '.join(r.name for r in row.rooms.all())),
          'DESCRIPTION:'+ical_escape('Gruppierung: '+row.grouping+'\nAnsprechperson: '+row.contact_person+'\nKontakt: '+row.contact+'\nStatus: '+row.get_status_display()),
          'STATUS:'+({'approved':'CONFIRMED','pending':'TENTATIVE'}.get(row.status,'CANCELLED'))]
        if row.all_day:lines+=['DTSTART;VALUE=DATE:'+timezone.localtime(row.starts_at).strftime('%Y%m%d'),'DTEND;VALUE=DATE:'+timezone.localtime(row.ends_at).strftime('%Y%m%d')]
        else:lines+=['DTSTART:'+row.starts_at.astimezone(utc.utc).strftime('%Y%m%dT%H%M%SZ'),'DTEND:'+row.ends_at.astimezone(utc.utc).strftime('%Y%m%dT%H%M%SZ')]
        lines.append('END:VEVENT')
    lines.append('END:VCALENDAR');folded=[]
    for line in lines:
        current=''
        for char in line:
            if len((current+char).encode('utf-8'))>75:folded.append(current);current=' '+char
            else:current+=char
        folded.append(current)
    return ('\r\n'.join(folded)+'\r\n').encode('utf-8')
