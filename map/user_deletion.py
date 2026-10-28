"""Explicit account deletion; retain operational records and last-admin access."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.http import require_http_methods
from .account_security import can_edit_person
from .access import can_users

SALT='map-account-deletion'

def deletion_reason(actor,target):
    if not can_edit_person(actor,target):return 'Dieses Konto darfst du nicht löschen.'
    if actor.pk==target.pk:return 'Dein eigenes Konto kannst du nicht löschen. Verwende dafür ein anderes berechtigtes Admin-Konto.'
    User=get_user_model()
    if target.is_active and target.is_superuser and not User.objects.filter(is_active=True,is_superuser=True).exclude(pk=target.pk).exists():
        return 'Das letzte aktive technische Admin-Konto darf nicht gelöscht werden.'
    admins=User.objects.filter(is_active=True).filter(Q(is_superuser=True)|Q(groups__name='Admin'))
    if not admins.exclude(pk=target.pk).exists():return 'Mindestens ein anderes aktives Admin-Konto muss erhalten bleiben.'
    return ''

def deletion_context(actor,target):
    reason=deletion_reason(actor,target)
    return {'can_delete_account':not reason,'delete_account_reason':reason,
        'delete_account_token':signing.dumps({'actor':actor.pk,'target':target.pk,'username':target.username},salt=SALT) if not reason else '',
        'delete_has_sso':hasattr(target,'entra_identity')}

@transaction.atomic
def delete_account(actor_id,target_id,token):
    User=get_user_model()
    # Match the administrator-first lock order of the existing account editor.
    list(User.objects.select_for_update(of=('self',)).filter(Q(is_superuser=True)|Q(groups__name='Admin')).order_by('pk').values_list('pk',flat=True))
    locked={u.pk:u for u in User.objects.select_for_update().filter(pk__in=[actor_id,target_id]).order_by('pk')}
    actor=locked.get(actor_id);target=locked.get(target_id)
    if actor is None or target is None:raise PermissionDenied
    if not can_edit_person(actor,target):raise PermissionDenied
    reason=deletion_reason(actor,target)
    if reason:raise ValidationError(reason)
    try:data=signing.loads(token,salt=SALT,max_age=900)
    except (signing.BadSignature,TypeError):raise ValidationError('Die Löschbestätigung ist abgelaufen oder ungültig. Bitte erneut öffnen.') from None
    if data!={'actor':actor.pk,'target':target.pk,'username':target.username}:
        raise ValidationError('Das Konto oder die Bestätigung wurde zwischenzeitlich geändert. Bitte erneut öffnen.')
    from .models import FormTemplate
    # A null creator denotes a shared standard; deletion must not broaden template visibility.
    FormTemplate.objects.filter(created_by=target).update(created_by=actor)
    target.delete()

@login_required
@require_http_methods(['GET','POST'])
def person_delete(request,pk):
    if not can_users(request.user):raise PermissionDenied
    target=get_object_or_404(get_user_model(),pk=pk)
    if not can_edit_person(request.user,target):raise PermissionDenied
    if request.method=='POST':
        if request.POST.get('confirm_delete')!='yes':
            messages.error(request,'Bitte das endgültige Löschen ausdrücklich bestätigen.');return redirect('person_edit',pk=pk)
        try:delete_account(request.user.pk,pk,request.POST.get('delete_token',''))
        except ValidationError as error:
            messages.error(request,' '.join(error.messages));return redirect('person_edit',pk=pk)
        messages.success(request,'Das Benutzerkonto und seine Zugriffszuordnungen wurden gelöscht. Veranstaltungen, Anmeldungen und Raumbuchungen bleiben erhalten.')
        return redirect('people')
    return render(request,'person_delete.html',{'person':target,**deletion_context(request.user,target)})
