from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404,redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Event,AuditLog
from .services import require_permission
from .forms import template_schema

@login_required
@require_POST
def publish_event(request,pk):
    with transaction.atomic():
        event=get_object_or_404(Event.objects.select_for_update(),pk=pk)
        require_permission(request.user,event,True)
        if not event.published:
            try:
                event.full_clean();template_schema(event.form_template)
            except ValidationError:
                messages.error(request,'Die Veranstaltung konnte nicht veröffentlicht werden. Bitte zuerst Angaben, Termine, Plätze und Formularvorlage im Bearbeiten-Modus prüfen.')
                return redirect('event_settings',pk=event.pk)
            event.published=True;event.save(update_fields=['published'])
            AuditLog.objects.create(actor=request.user,event=event,action='Veranstaltung veröffentlicht')
            messages.success(request,'Die Veranstaltung ist veröffentlicht. Der Anmeldelink kann jetzt geteilt werden.')
            if not event.registration_opens<=timezone.now()<=event.registration_closes:
                messages.warning(request,'Der Anmeldezeitraum ist gerade nicht geöffnet. Bitte die Termine prüfen.')
    return redirect('dashboard') if request.POST.get('return_to')=='dashboard' else redirect('event_admin',pk=pk)
