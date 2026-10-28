from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetConfirmView,PasswordResetCompleteView
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404,redirect
from django.urls import reverse,reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_POST
from .access import can_users
from .models import EmailJob
from .services import throttle
from .mailer import encrypt_password,decrypt_password


def technical_admin(user):return bool(user.is_authenticated and user.is_active and user.is_superuser)
def can_edit_person(actor,user):return can_users(actor) and (not user.is_superuser or technical_admin(actor))

@login_required
@require_POST
def send_password_reset(request,pk):
    user=get_object_or_404(get_user_model(),pk=pk)
    if not can_edit_person(request.user,user):raise PermissionDenied
    if request.POST.get('confirm_reset')!='yes':
        messages.error(request,'Bitte bestätigen, dass der Passwort-Link an die gespeicherte E-Mail-Adresse gesendet werden soll.');return redirect('person_edit',pk=pk)
    with transaction.atomic():
        user=get_user_model().objects.select_for_update().get(pk=pk)
        if not can_edit_person(request.user,user):raise PermissionDenied
        if not user.is_active or not user.email or not user.has_usable_password():
            messages.error(request,'Für den Passwort-Reset braucht das Konto einen aktiven Zugang, eine gespeicherte E-Mail-Adresse und ein lokales Passwort.');return redirect('person_edit',pk=pk)
        if not throttle('account-reset:'+str(pk),limit=3,seconds=3600):
            messages.error(request,'Für dieses Konto wurden bereits mehrere Passwort-Links angefordert. Bitte eine Stunde warten.');return redirect('person_edit',pk=pk)
        token=default_token_generator.make_token(user);uid=urlsafe_base64_encode(force_bytes(user.pk))
        url=settings.PUBLIC_URL.rstrip('/')+reverse('password_reset_confirm',kwargs={'uidb64':uid,'token':token})
        from .mail_templates import system_content
        subject,body=system_content('password_reset',{'account_name':user.get_username(),'reset_url':url,'reset_hours':max(1,settings.PASSWORD_RESET_TIMEOUT//3600)})
        # Replace any still queued reset for this account, including failed requests.
        EmailJob.objects.filter(reset_user=user,sent_at__isnull=True).delete()
        EmailJob.objects.create(template_scope='map',template_key='password_reset',reset_user=user,recipient=user.email,subject=subject,
            body='Vertrauliche Sicherheitsnachricht. Der Inhalt wird nur für den Versand entschlüsselt und hier nicht angezeigt.',
            body_encrypted=encrypt_password(body),reset_token_encrypted=encrypt_password(token),next_attempt=timezone.now())
    messages.success(request,'Der Passwort-Link wurde für '+user.email+' in die E-Mail-Warteschlange gestellt. Die Zustellung hängt vom eingerichteten Versanddienst ab.')
    return redirect('person_edit',pk=pk)

class MapPasswordResetConfirmView(PasswordResetConfirmView):
    template_name='registration/password_reset_confirm.html'
    success_url=reverse_lazy('password_reset_complete')
    post_reset_login=False
    def get_user(self,uidb64):
        user=super().get_user(uidb64)
        return user if user and user.is_active and user.has_usable_password() else None

class MapPasswordResetCompleteView(PasswordResetCompleteView):
    template_name='registration/password_reset_complete.html'

def reset_job_is_valid(job):
    if not job.reset_user_id:return True
    try:token=decrypt_password(job.reset_token_encrypted)
    except Exception:return False
    user=job.reset_user
    return user.is_active and user.has_usable_password() and default_token_generator.check_token(user,token)
