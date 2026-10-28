"""Admin-only room catalogue. Preserve names referenced by historical reservations."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_http_methods
from map.roles import is_admin
from .models import Room,RoomBooking,BookingChange
from .forms import RoomForm
from .services import lock_schedule

@login_required
@require_http_methods(['GET','POST'])
def catalogue(request):
    if not is_admin(request.user):raise PermissionDenied
    instance=None
    if request.GET.get('edit'):
        from map.security_rules import numeric_pk
        instance=get_object_or_404(Room,pk=numeric_pk(request.GET['edit']),active=True)
    form=RoomForm(request.POST if request.method=='POST' and request.POST.get('action')=='save' else None,instance=instance)
    if request.method=='POST':
        action=request.POST.get('action')
        if action=='save' and form.is_valid():
            with transaction.atomic():lock_schedule();form.save()
            messages.success(request,'Raum gespeichert.');return redirect('rooms:catalogue')
        if action=='delete':
            from map.security_rules import numeric_pk
            with transaction.atomic():
                lock_schedule();room=get_object_or_404(Room.objects.select_for_update(),pk=numeric_pk(request.POST.get('room_id')))
                if action=='delete' and request.POST.get('confirm')!='yes':
                    messages.error(request,'Bitte das Löschen ausdrücklich bestätigen.')
                elif action=='delete':
                    if room.roombooking_entries.exists() or room.bookingchange_entries.exists():
                        room.active=False;room.save(update_fields=['active']);messages.success(request,'Raum archiviert. Seine Buchungshistorie bleibt erhalten.')
                    else:room.delete();messages.success(request,'Raum gelöscht.')
            return redirect('rooms:catalogue')
    from django.db.models import Exists,OuterRef
    rows=Room.objects.filter(active=True).annotate(has_bookings=Exists(RoomBooking.objects.filter(rooms=OuterRef('pk'))),has_changes=Exists(BookingChange.objects.filter(rooms=OuterRef('pk'))))
    for room in rows:room.will_archive=room.has_bookings or room.has_changes
    archived=Room.objects.filter(active=False)
    return render(request,'rooms/catalogue.html',{'form':form,'rooms':rows,'editing':instance,'settings_area':'rooms','archived_rooms':archived})
