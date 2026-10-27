from io import BytesIO
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from .models import Event
from .services import require_permission

def registration_url(event):
    return settings.PUBLIC_URL.rstrip('/')+reverse('event',args=[event.slug])

@login_required
def event_qr(request,pk):
    event=get_object_or_404(Event,pk=pk)
    require_permission(request.user,event)
    if not event.published: raise Http404
    import qrcode
    from qrcode.image.pure import PyPNGImage
    code=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=10,border=4)
    code.add_data(registration_url(event));code.make(fit=True)
    buffer=BytesIO();code.make_image(image_factory=PyPNGImage).save(buffer)
    response=HttpResponse(buffer.getvalue(),content_type='image/png')
    response['Content-Disposition']='inline; filename="anmeldung-qr.png"'
    return response
