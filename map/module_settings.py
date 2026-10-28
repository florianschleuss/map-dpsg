from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .roles import is_admin
from .access import can_mail_templates,can_mail_settings,can_users,can_roles,can_stages,can_queue


@login_required
@require_GET
def module_settings(request):
    from rooms.access import can_configure
    if not any([is_admin(request.user),can_configure(request.user),can_mail_templates(request.user),can_mail_settings(request.user),can_users(request.user),can_roles(request.user),can_stages(request.user),can_queue(request.user)]):raise PermissionDenied
    return render(request,'module_settings.html')


@login_required
@require_GET
def event_module_settings(request):
    if not can_mail_templates(request.user):raise PermissionDenied
    return render(request,'event_module_settings.html',{'settings_area':'events'})
