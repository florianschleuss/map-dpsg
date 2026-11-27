from django.urls import path
from . import views
from .room_admin import catalogue
from .group_sessions import sessions
app_name='rooms'
urlpatterns=[path('gruppenstunden/',sessions,name='group_sessions'),path('gruppenstunden/<int:pk>/',sessions,name='group_session_edit'),path('raumverwaltung/',catalogue,name='catalogue'),path('konflikte/',views.live_conflicts,name='live_conflicts'),path('',views.index,name='index'),path('neu/',views.edit,name='new'),path('kalender/',views.calendar_view,name='calendar'),
 path('genehmigungen/',views.pending,name='pending'),path('einstellungen/',views.settings_view,name='settings'),
 path('mailvorlagen/',views.templates,name='templates'),path('mailvorlagen/<slug:key>/',views.template_edit,name='template_edit'),
 path('export/<str:kind>/',views.export,name='export'),path('<int:pk>/',views.detail,name='detail'),path('<int:pk>/bearbeiten/',views.edit,name='edit')]
