"""Bounded weekly schedules in local wall-clock time, including DST validation."""
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.utils import timezone

MAX_WEEKS=520
WEEKDAYS=['Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag','Sonntag']

def intervals(item,start=None,end=None):
    if not getattr(item,'recurring',False):
        if (end is None or item.starts_at<end) and (start is None or item.ends_at>start):
            yield item.starts_at,item.ends_at
        return
    from .forms import local_datetime
    first=timezone.localtime(item.starts_at);last=timezone.localtime(item.ends_at)
    if item.all_day or last.date()<first.date() or last.time()<=first.time() or (last.date()-first.date()).days>MAX_WEEKS*7:
        raise ValidationError('UngÃ¼ltige Wiederholung. Bitte einen Wochentag mit Ende nach Beginn und hÃ¶chstens zehn Jahren auswÃ¤hlen.')
    day=first.date()
    if start is not None:
        delta=(timezone.localtime(start).date()-day).days
        if delta>0:day+=timedelta(weeks=delta//7)
    while day<=last.date():
        a=local_datetime(day,first.time().replace(tzinfo=None));b=local_datetime(day,last.time().replace(tzinfo=None))
        if end is not None and a>=end:break
        if start is None or b>start:yield a,b
        if (last.date()-day).days<7:break
        day+=timedelta(days=7)

def overlaps(left,right):
    a=iter(intervals(left));b=iter(intervals(right))
    x=next(a,None);y=next(b,None)
    while x and y:
        if x[0]<y[1] and y[0]<x[1]:return True
        if x[1]<=y[1]:x=next(a,None)
        else:y=next(b,None)
    return False
