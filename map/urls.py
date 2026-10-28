from django.urls import path
from .health import health
from . import views
from .sharing import event_qr
from .deletion import event_delete
from .mail_admin import mail_settings,mail_queue
from .form_builder import template_options
from .privacy import privacy, imprint
from .publication import publish_event
from .payments import payment_qr,request_payments,record_payment
from .account_security import send_password_reset,MapPasswordResetConfirmView,MapPasswordResetCompleteView
from .people import people,person_edit,role_list,role_edit
from .mail_templates import email_templates,email_template_edit
from .sso_views import sso_start,sso_callback,sso_settings,sso_waiting
from .module_settings import module_settings,event_module_settings
from .demo_events import dummy_event
from .mail_policy import set_template_state
from .user_deletion import person_delete
urlpatterns = [path('verwaltung/benutzer/<int:pk>/loeschen/',person_delete,name='person_delete'),path('verwaltung/mailvorlagen/<slug:scope>/<slug:key>/status/',set_template_state,name='set_mail_template_state'),path('verwaltung/einstellungen/veranstaltungen/',event_module_settings,name='event_module_settings'),path('entwicklung/dummy-veranstaltung/',dummy_event,name='dummy_event'),path('verwaltung/einstellungen/',module_settings,name='module_settings'),path('accounts/microsoft/start/',sso_start,name='sso_start'),path('accounts/microsoft/callback/',sso_callback,name='sso_callback'),path('accounts/microsoft/warten/',sso_waiting,name='sso_waiting'),path('verwaltung/microsoft/',sso_settings,name='sso_settings'),path('healthz/',health,name='health'),path('impressum/',imprint,name='imprint'),path('dashboard/events/<int:pk>/statistik/',views.event_statistics,name='event_statistics'),path('dashboard/events/<int:pk>/anmeldungen.xlsx',views.export_excel,name='export_excel'),path('manage/<str:token>/payment-qr.png',payment_qr,name='payment_qr'),path('dashboard/events/<int:pk>/payment-request/',request_payments,name='request_payments'),path('dashboard/registrations/<int:pk>/payment/',record_payment,name='record_payment'),path('verwaltung/benutzer/<int:pk>/passwort-link/',send_password_reset,name='send_password_reset'),path('konto/passwort/fertig/',MapPasswordResetCompleteView.as_view(),name='password_reset_complete'),path('konto/passwort/<uidb64>/<token>/',MapPasswordResetConfirmView.as_view(),name='password_reset_confirm'),path('verwaltung/email-vorlagen/',email_templates,name='email_templates'),path('verwaltung/email-vorlagen/<slug:key>/',email_template_edit,name='email_template_edit'),path('verwaltung/benutzer/',people,name='people'),path('verwaltung/benutzer/neu/',person_edit,name='person_new'),path('verwaltung/benutzer/<int:pk>/',person_edit,name='person_edit'),path('verwaltung/rollen/',role_list,name='roles'),path('verwaltung/rollen/neu/',role_edit,name='role_new'),path('verwaltung/rollen/<int:pk>/',role_edit,name='role_edit'),path('dashboard/events/<int:pk>/publish/',publish_event,name='publish_event'),path('datenschutz/',privacy,name='privacy'),path('verwaltung/email/',mail_queue,name='mail_queue'),path('verwaltung/smtp/',mail_settings,name='mail_settings'),path('dashboard/events/<int:pk>/delete/',event_delete,name='event_delete'),path('dashboard/events/<int:pk>/templates/',template_options,name='template_options'),path('dashboard/events/<int:pk>/qr.png', event_qr, name='event_qr'),
 path('', views.home, name='home'), path('events/<slug:slug>/', views.event_detail, name='event'),
 path('events/<slug:slug>/resend/', views.resend, name='resend'),
 path('confirm/<str:token>/', views.confirm_link, name='confirm'), path('manage/<str:token>/', views.manage_link, name='manage'),
 path('dashboard/', views.dashboard, name='dashboard'), path('dashboard/events/<int:pk>/', views.event_admin, name='event_admin'),
 path('dashboard/events/<int:pk>/settings/', views.event_settings, name='event_settings'),
 path('dashboard/events/<int:pk>/export/', views.export_csv, name='export_csv'),
 path('dashboard/registrations/<int:pk>/', views.staff_registration, name='staff_registration')]
