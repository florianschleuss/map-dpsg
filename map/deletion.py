from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404,render,redirect
from django.views.decorators.http import require_http_methods
from .models import Event, Registration, EmailJob, FormTemplate, FormModule, FormField, EventGroup, EventPermission, AuditLog
from .roles import can_delete_event
from django.core.exceptions import PermissionDenied

@transaction.atomic
def delete_event(event_id,actor):
    event=Event.objects.select_for_update().filter(pk=event_id).first()
    if event is None: return
    if not can_delete_event(actor,event): raise PermissionDenied
    template_id=event.form_template_id
    from django.contrib.admin.models import LogEntry
    from django.contrib.contenttypes.models import ContentType
    def erase_admin_logs(model,ids):
        LogEntry.objects.filter(content_type=ContentType.objects.get_for_model(model),object_id__in=[str(pk) for pk in ids]).delete()
    erase_admin_logs(Event,[event.pk])
    for model in [Registration,EmailJob,EventGroup,EventPermission,AuditLog]:
        erase_admin_logs(model,model.objects.filter(event=event).values_list('pk',flat=True))
    EmailJob.objects.filter(event=event).delete()
    Registration.objects.filter(event=event).delete()
    event.delete()
    template=FormTemplate.objects.select_for_update().filter(pk=template_id).first()
    if template and not template.event_set.exists():
        erase_admin_logs(FormTemplate,[template.pk])
        erase_admin_logs(FormModule,template.modules.values_list('pk',flat=True))
        erase_admin_logs(FormField,FormField.objects.filter(module__template=template).values_list('pk',flat=True))
        template.delete()

@login_required
@require_http_methods(['GET','POST'])
def event_delete(request,pk):
    event=get_object_or_404(Event,pk=pk)
    if not can_delete_event(request.user,event): raise PermissionDenied
    if request.method=='POST':
        if request.POST.get('confirm_delete')!='delete': return HttpResponseBadRequest('Bitte die Löschung ausdrücklich bestätigen.')
        delete_event(event.pk,request.user)
        messages.success(request,'Die Veranstaltung und ihre zugehörigen Daten wurden gelöscht.')
        return redirect('dashboard')
    return render(request,'event_delete.html',{'event':event})
