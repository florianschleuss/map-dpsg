import time
from datetime import timedelta
from django.conf import settings
from map.mailer import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction, close_old_connections
from django.utils import timezone
from map.models import EmailJob, Event, Throttle
from django.contrib.sessions.models import Session
from map.services import rebalance

class Command(BaseCommand):
    help = 'Send queued email with bounded retries and expire unconfirmed registrations.'
    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')
    def handle(self, *args, **options):
        while True:
            for event_id in Event.objects.values_list('pk', flat=True):
                try: rebalance(event_id)
                except Event.DoesNotExist: pass
            Session.objects.filter(expire_date__lt=timezone.now()).delete()
            Throttle.objects.filter(window_start__lt=timezone.now() - timedelta(days=2)).delete()
            for _ in range(100):
                candidate=EmailJob.objects.filter(sent_at__isnull=True,attempts__lt=8,next_attempt__lte=timezone.now()).order_by('pk').values('pk','event_id').first()
                if candidate is None:break
                with transaction.atomic():
                    # Same lock order as registration, cancellation and event deletion.
                    if candidate['event_id']:Event.objects.select_for_update().filter(pk=candidate['event_id']).first()
                    job=EmailJob.objects.select_for_update(skip_locked=True).filter(pk=candidate['pk'],sent_at__isnull=True,attempts__lt=8,next_attempt__lte=timezone.now()).first()
                    if job is None:continue
                    if job.room_booking_id:
                        from rooms.notifications import job_current
                        if not job_current(job):
                            job.attempts=8;job.last_error='RoomNotificationObsolete';job.body='Diese Raumbuchungsnachricht ist überholt und wurde nicht versendet.';job.save(update_fields=['attempts','last_error','body']);continue
                    if job.payment_request or job.payment_fingerprint:
                        from map.payments import payment_job_is_current
                        if not payment_job_is_current(job):
                            job.attempts=8;job.last_error='PaymentRequestObsolete';job.body='Diese Zahlungsnachricht ist nicht mehr aktuell und wurde nicht versendet.'
                            job.save(update_fields=['attempts','last_error','body']);continue
                    if job.reset_user_id:
                        from map.account_security import reset_job_is_valid
                        if not reset_job_is_valid(job):
                            job.attempts=8;job.last_error='PasswordResetExpired';job.body_encrypted='';job.reset_token_encrypted=''
                            job.save(update_fields=['attempts','last_error','body_encrypted','reset_token_encrypted']);continue
                    job.attempts += 1
                    try:
                        from map.mailer import decrypt_password
                        body=decrypt_password(job.body_encrypted) if job.body_encrypted else job.body
                        send_mail(job.subject, body, settings.DEFAULT_FROM_EMAIL, [job.recipient], fail_silently=False)
                        job.sent_at = timezone.now()
                        job.last_error = ''
                        if job.reset_user_id:job.body_encrypted='';job.reset_token_encrypted=''
                    except Exception as exc:
                        # Do not store provider responses, credentials, or recipient data in errors.
                        from map.microsoft_mail import MESSAGES
                        code=getattr(exc,'code',None)
                        job.last_error = code if isinstance(code,str) and code in MESSAGES else type(exc).__name__
                        job.next_attempt = timezone.now() + timedelta(seconds=max(min(3600,30*2**job.attempts),getattr(exc,'retry_after',None) or 0))
                    job.save(update_fields=['attempts','sent_at','last_error','next_attempt','body_encrypted','reset_token_encrypted'])
            if not options['loop']: break
            close_old_connections()
            time.sleep(15)
