import uuid
from datetime import date
from django.core import signing
from django.db import transaction
from django.db.models import F
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from analytics.models import Event, VisitorSession
from django.utils import timezone
from .forms import ConversionForm
from .models import SiteSettings, Section, Submission
from .security import rate_limited


def site_settings():
    return SiteSettings.objects.get_or_create(pk=1)[0]

def tracking_allowed(request, site):
    return request.COOKIES.get('analytics_consent') != 'no' and site.analytics_mode != 'off' and (site.analytics_mode == 'essential' or request.COOKIES.get('analytics_consent') == 'yes') and request.headers.get('Sec-GPC') != '1' and request.headers.get('DNT') != '1'

def analytics_identity(request):
    try:
        identity = signing.loads(request.COOKIES.get('journey', ''), salt='journey', max_age=1800)
        uuid.UUID(identity['session_id']); uuid.UUID(identity['visitor_id'])
        return identity
    except (signing.BadSignature, ValueError, KeyError, TypeError):
        return {'visitor_id': str(uuid.uuid4()), 'session_id': str(uuid.uuid4())}

def set_identity(response, identity):
    from django.conf import settings
    response.set_cookie('journey', signing.dumps(identity, salt='journey'), max_age=1800, httponly=True, secure=settings.SESSION_COOKIE_SECURE, samesite='Lax')

@ensure_csrf_cookie
def home(request):
    site = site_settings()
    form = ConversionForm(booking=site.conversion_mode == 'booking')
    return render(request, 'website/home.html', {'site':site, 'sections':Section.objects.filter(enabled=True), 'form':form})

@require_POST
@transaction.atomic
def submit(request):
    site = site_settings()
    if site.conversion_mode == 'external': return redirect('/')
    if rate_limited(request, 'submit', 5, 600):
        return render(request, 'website/message.html', {'site':site, 'title':'Please try again shortly', 'message':'We have received several requests. Wait a few minutes before trying again.'}, status=429)
    form = ConversionForm(request.POST, booking=site.conversion_mode == 'booking')
    if not form.is_valid():
        return render(request, 'website/home.html', {'site':site, 'sections':Section.objects.filter(enabled=True), 'form':form}, status=400)
    data = {key: value.isoformat() if isinstance(value,date) else value for key,value in form.cleaned_data.items() if key not in {'website','consent'}}
    session = None
    if tracking_allowed(request, site):
        from analytics.services import ingest
        identity = analytics_identity(request)
        session = ingest(request, {**identity, 'event':'page_load', 'path':'/', 'context':{}})
        Event.objects.create(session=session, name='conversion', properties={'goal_key':site.conversion_mode})
        VisitorSession.objects.filter(pk=session.pk).update(funnel_stage='converted', digest_due_at=timezone.now(), event_count=F('event_count') + 1)
    Submission.objects.create(session=session, kind=site.conversion_mode, data=data)
    request.session['submitted'] = True
    return redirect('website:thanks')

def thanks(request):
    if not request.session.pop('submitted', False): return redirect('/')
    return render(request, 'website/message.html', {'site':site_settings(), 'title':'You’re all set.', 'message':site_settings().thank_you})

def privacy(request):
    return render(request, 'website/privacy.html', {'site':site_settings()})

def brand_image(request, field):
    if field not in {'logo','hero_image'}: raise Http404
    image = getattr(site_settings(), field)
    if not image: raise Http404
    try: return FileResponse(image.open('rb'), content_type='image/png' if image.name.endswith('.png') else 'image/jpeg')
    except FileNotFoundError: raise Http404
