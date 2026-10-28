from map.form_builder import form_builder
from map.event_wizard import event_wizard
from map.unified_auth import MapLoginView, MapLogoutView, admin_login
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from rooms.public_api import occupancy
urlpatterns = [path('api/v1/rooms/occupancy/',occupancy,name='room_occupancy_api'),path('raeume/', include('rooms.urls')),path('admin/formularbaukasten/neu/',form_builder,name='map_form_builder_new'), path('admin/formularbaukasten/<int:pk>/',form_builder,name='map_form_builder'), path('admin/veranstaltung-anlegen/', event_wizard, name='map_event_wizard'), path('admin/login/', admin_login, name='map_admin_login'), path('admin/', admin.site.urls),
 path('accounts/login/', MapLoginView.as_view(), name='login'),
 path('accounts/logout/', MapLogoutView.as_view(), name='logout'),
 path('', include('map.urls'))]
admin.site.site_header = 'MAP – Modulare Anmeldeplattform – Verwaltung'
admin.site.site_title = 'MAP – Verwaltung'
admin.site.index_title = 'Einrichtung und Konten'

handler400='map.error_views.bad_request'
handler403='map.error_views.permission_denied'
handler404='map.error_views.page_not_found'
handler500='map.error_views.server_error'
