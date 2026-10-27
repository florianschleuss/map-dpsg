import csv
from .text_labels import question_label
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .models import Event, Registration, AuditLog, new_token
from .forms import RegistrationForm, ResendForm, EventSettingsForm, template_schema
from . import services as svc

def limited(request, scope):
    # REMOTE_ADDR is set by the trusted reverse proxy in deployment.
    from .request_security import client_address
    return not svc.throttle(scope + ':' + client_address(request), limit=60)

def home(request):
    return redirect('dashboard' if request.user.is_authenticated else 'login')

@require_http_methods(['GET', 'POST'])
def event_detail(request, slug):
    event = get_object_or_404(Event.objects.select_related('form_template', 'group'), slug=slug, published=True)
    form = RegistrationForm(request.POST if request.method == 'POST' else None, modules=template_schema(event.form_template), event=event)
    if request.method == 'POST':
        if limited(request, 'register'): return HttpResponse('Zu viele Versuche. Bitte später erneut versuchen.', status=429)
        if form.is_valid():
            if not svc.throttle('registration-recipient:'+form.cleaned_data['email'].strip().casefold(),limit=10):
                return render(request,'message.html',{'title':'Bitte später erneut versuchen','text':'Für diese E-Mail-Adresse wurden bereits mehrere Anmeldungen angefordert. Bitte warte eine Stunde oder wende dich an die Leitenden.'},status=429)
            try:
                row = svc.register(event.pk, form.cleaned_data['child_name'], form.cleaned_data['email'], form.answers(), schema=form.modules, group_id=form.cleaned_data.get('group_id') or None)
                return render(request, 'message.html', {'title': 'Anmeldung eingegangen', 'text': 'Bitte prüfe dein E-Mail-Postfach und auch den Spam-Ordner. Falls keine E-Mail ankommt, wende dich an die Leitenden der Veranstaltung. Status: ' + row.get_status_display(),'manage_url':('/manage/'+svc.token_for(row,'manage')+'/') if row.status=='confirmed' else ''})
            except ValidationError as exc: form.add_error(None, exc)
    group_slots=list(event.group_slots.filter(enabled=True).select_related('group'))
    if not group_slots:
        from types import SimpleNamespace
        group_slots=[SimpleNamespace(group=event.group,capacity=event.capacity,registrations=event.registrations)]
    for slot in group_slots:
        slot.available=max(0,slot.capacity-slot.registrations.filter(status__in=['pending','confirmed']).count())
    occupied = event.registrations.filter(status__in=['pending', 'confirmed']).count()
    from .payment_rules import cost_label
    return render(request, 'event.html', {'event': event,'cost_label':cost_label(event), 'form': form, 'group_slots':group_slots, 'free': max(0, event.capacity - occupied), 'open': event.registration_opens <= timezone.now() <= event.registration_closes})

@require_http_methods(['GET', 'POST'])
def resend(request, slug):
    event = get_object_or_404(Event, slug=slug, published=True)
    form = ResendForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if limited(request, 'resend'): return HttpResponse('Zu viele Versuche.', status=429)
        if form.is_valid():
            key = svc.identity(form.cleaned_data['child_name'], form.cleaned_data['email'])
            with transaction.atomic():
                Event.objects.select_for_update().get(pk=event.pk)
                row = event.registrations.filter(identity=key, status__in=svc.ACTIVE).first()
                if row and svc.throttle('mail:' + str(row.pk), limit=3):
                    svc.queue_message(row, 'Anmeldelinks erneut gesendet')
            return render(request, 'message.html', {'title': 'Anfrage erhalten', 'text': 'Falls eine aktive Anmeldung vorliegt, erhalten Sie eine E-Mail. Die ursprüngliche Bestätigungsfrist bleibt bestehen. Bitte auch im Spam-Ordner nachsehen. Falls keine Mail ankommt, wende dich an die Leitenden der Veranstaltung.'})
    return render(request, 'form.html', {'title': 'Link erneut senden', 'form': form})

def invalid_link(request, exc):
    return render(request, 'message.html', {'title': 'Link nicht verfügbar', 'text': ' '.join(exc.messages)}, status=400)

@require_http_methods(['GET', 'POST'])
def confirm_link(request, token):
    try:
        row = svc.resolve_token(token, 'confirm')
        if request.method == 'POST':
            row = svc.confirm(row.pk)
            return render(request, 'message.html', {'title': 'E-Mail bestätigt', 'text': 'Status: ' + row.get_status_display(),'manage_url':'/manage/'+svc.token_for(row,'manage')+'/'})
    except ValidationError as exc: return invalid_link(request, exc)
    return render(request, 'confirm.html', {'row': row})

@require_http_methods(['GET', 'POST'])
def manage_link(request, token):
    try: row = svc.resolve_token(token, 'manage')
    except ValidationError as exc: return invalid_link(request, exc)
    return registration_editor(request, row)

def registration_editor(request, row, actor=None):
    form = RegistrationForm(request.POST if request.method == 'POST' else None, modules=row.schema_snapshot,
          answers=row.answers, editing=True, initial={'child_name': row.child_name, 'email': row.email})
    if request.method == 'POST':
        try:
            if request.POST.get('action') == 'cancel':
                if request.POST.get('cancel_confirm') != 'yes':
                    form.add_error(None, 'Bitte die Stornierung ausdrücklich bestätigen.')
                else:
                    svc.cancel(row.pk, actor=actor)
                    return render(request, 'message.html', {'title': 'Storniert', 'text': 'Die Anmeldung wurde storniert.'})
            elif request.POST.get('action') == 'resend':
                if svc.throttle('mail:' + str(row.pk), limit=3): svc.queue_message(row, 'Anmeldelinks erneut gesendet')
                messages.success(request, 'Versand angefordert.')
                return redirect(request.path)
            elif form.is_valid():
                svc.edit_registration(row.pk, form.answers(), actor=actor)
                messages.success(request, 'Änderungen gespeichert.')
                return redirect(request.path)
        except ValidationError as exc: form.add_error(None, exc)
    from .payments import payment_details
    return render(request, 'manage.html', {'row': row, 'form': form, 'active': row.status in svc.ACTIVE,'payment':payment_details(row)})

@login_required
def dashboard(request):
    from .roles import visible_events
    events=visible_events(request.user)
    from .sharing import registration_url
    events=list(events.order_by('starts_at'))
    from django.db.models import Count
    for event in events:
        event.registration_url=registration_url(event)
        event.can_edit=svc.permitted(request.user,event,True)
        event.occupied=event.registrations.filter(status__in=['pending','confirmed']).count()
        event.waiting=event.registrations.filter(status='waitlisted').count()
        event.days_until=(timezone.localdate(event.starts_at)-timezone.localdate()).days
        counts={row['event_group_id']:row['n'] for row in event.registrations.filter(status__in=['pending','confirmed']).values('event_group_id').annotate(n=Count('pk'))}
        event.stage_metrics=[{'name':slot.group.name,'occupied':counts.get(slot.pk,0),'capacity':slot.capacity} for slot in event.group_slots.filter(enabled=True).select_related('group')]

    return render(request, 'dashboard.html', {'events': events})

@login_required
def event_admin(request, pk):
    event = get_object_or_404(Event, pk=pk)
    svc.require_permission(request.user, event)
    from django.core.paginator import Paginator
    page=Paginator(event.registrations.select_related('event_group__group').order_by('created_at','pk'),50).get_page(request.GET.get('page'))
    rows = list(page.object_list)
    for row in rows:
        labels = {field['key']: field['label'] for module in row.schema_snapshot for field in module.get('fields', [])}
        row.display_answers = [{'label': question_label(labels.get(key, 'Weitere Angabe')), 'value': 'Ja' if value is True else 'Nein' if value is False else value} for key, value in row.answers.items()]
    from .sharing import registration_url
    event.registration_url=registration_url(event)
    from .roles import can_delete_event
    from .payment_rules import cost_label
    return render(request, 'event_admin.html', {'event': event, 'rows': rows,'page_obj':page,'registration_count':page.paginator.count, 'can_edit': svc.permitted(request.user, event, True),'can_delete':can_delete_event(request.user,event),'cost_label':cost_label(event)})

@login_required
@require_http_methods(['GET', 'POST'])
def event_settings(request, pk):
    with transaction.atomic():
        event = get_object_or_404(Event.objects.select_for_update(), pk=pk)
        svc.require_permission(request.user, event, True)
        form = EventSettingsForm(request.POST if request.method == 'POST' else None, instance=event, actor=request.user)
        if request.method == 'POST' and form.is_valid():
            form.save()
            AuditLog.objects.create(actor=request.user, event=event, action='edit event settings')
            svc.rebalance(event.pk)
            return redirect('event_admin', pk=pk)
    return render(request, 'form.html', {'title': 'Veranstaltung bearbeiten', 'form': form, 'event':event})

@login_required
@require_http_methods(['GET', 'POST'])
def staff_registration(request, pk):
    row = get_object_or_404(Registration.objects.select_related('event'), pk=pk)
    svc.require_permission(request.user, row.event, True)
    return registration_editor(request, row, actor=request.user)

def csv_safe(value):
    value = str(value)
    return "'" + value if value.startswith(('\t', '\r', '\n')) or value.lstrip().startswith(('=', '+', '-', '@')) else value

@login_required
def export_csv(request, pk):
    event = get_object_or_404(Event, pk=pk)
    svc.require_permission(request.user, event)
    from django.core.paginator import Paginator
    page=Paginator(event.registrations.select_related('event_group__group').order_by('created_at','pk'),50).get_page(request.GET.get('page'))
    rows = list(page.object_list)
    keys = sorted({key for row in rows for key in row.answers})
    column_labels = {field['key']:field['label'] for row in rows for module in row.schema_snapshot for field in module.get('fields',[])}
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="event-{event.pk}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow([csv_safe(value) for value in ['ID', 'Kind', 'E-Mail', 'Gruppe', 'Status', 'E-Mail bestätigt', 'Angemeldet am','Zahlungseingang manuell bestätigt'] + [column_labels.get(key,'Weitere Angabe') for key in keys]])
    for row in rows:
        writer.writerow([csv_safe(v) for v in [row.pk, row.child_name, row.email, row.event_group.group.name if row.event_group_id else event.group.name, row.get_status_display(), row.email_verified, row.created_at.isoformat(),row.payment_received_at.isoformat() if row.payment_received_at else ''] + [row.answers.get(key, '') for key in keys]])
    AuditLog.objects.create(actor=request.user, event=event, action='export csv')
    return response


@login_required
@require_http_methods(['GET'])
def event_statistics(request,pk):
    from collections import Counter
    from .registration_reports import categories
    event=get_object_or_404(Event,pk=pk)
    svc.require_permission(request.user,event)
    scope=request.GET.get('umfang','confirmed')
    if scope not in ['confirmed','active','all']:scope='confirmed'
    rows=list(event.registrations.select_related('event_group__group').order_by('pk'))
    statuses=Counter(row.get_status_display() for row in rows)
    selected=[row for row in rows if scope=='all' or row.status=='confirmed' or (scope=='active' and row.status in ['pending','confirmed','waitlisted'])]
    stages=Counter(row.event_group.group.name if row.event_group_id else event.group.name for row in selected)
    return render(request,'event_statistics.html',{'event':event,'scope':scope,'total':len(selected),'statuses':dict(statuses),'stages':dict(stages),'questions':categories(selected)})

@login_required
@require_http_methods(['GET'])
def export_excel(request,pk):
    from .registration_reports import export_grid
    from .excel_export import workbook_bytes
    event=get_object_or_404(Event,pk=pk)
    svc.require_permission(request.user,event)
    rows=list(event.registrations.select_related('event_group__group','event__group').order_by('created_at','pk'))
    response=HttpResponse(workbook_bytes(export_grid(rows)),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition']='attachment; filename="anmeldungen-'+str(event.pk)+'.xlsx"'
    AuditLog.objects.create(actor=request.user,event=event,action='export excel')
    return response
