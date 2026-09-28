import json
from datetime import timedelta, timezone as datetime_timezone

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .models import IPRecord, Lead, NotificationPreference, TelegramAccount, VisitorSession
from .services import ingest
from .services import journey_summary


WINDOWS = {
    "1h": (timedelta(hours=1), "Last hour"),
    "6h": (timedelta(hours=6), "Last 6 hours"),
    "24h": (timedelta(hours=24), "Last 24 hours"),
    "3d": (timedelta(days=3), "Last 3 days"),
    "7d": (timedelta(days=7), "Last 7 days"),
    "30d": (timedelta(days=30), "Last 30 days"),
    "90d": (timedelta(days=90), "Last 90 days"),
    "365d": (timedelta(days=365), "Last year"),
}


def _parse_utc_datetime(value):
    parsed = parse_datetime(value or "")
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, datetime_timezone.utc)
    return parsed


def dashboard_window(query, *, now=None):
    now = now or timezone.now()
    preset = query.get("range", "30d")
    error = ""
    if preset == "custom":
        since = _parse_utc_datetime(query.get("from"))
        until = _parse_utc_datetime(query.get("to"))
        if until:
            until = min(until, now)
        if not since or not until or since >= until:
            error = "Choose a valid custom start and end time. Showing the last 30 days instead."
            preset, since, until = "30d", now - WINDOWS["30d"][0], now
        elif until - since > timedelta(days=366):
            error = "Custom ranges are limited to 366 days. Showing the last 30 days instead."
            preset, since, until = "30d", now - WINDOWS["30d"][0], now
    else:
        if preset not in WINDOWS:
            preset = "30d"
        since, until = now - WINDOWS[preset][0], now
    return {
        "preset": preset, "since": since, "until": until, "error": error,
        "from_value": since.astimezone(datetime_timezone.utc).strftime("%Y-%m-%dT%H:%M"),
        "to_value": until.astimezone(datetime_timezone.utc).strftime("%Y-%m-%dT%H:%M"),
    }


def health(request):
    from django.db import connection
    with connection.cursor() as cursor: cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


@csrf_protect
@require_POST
@transaction.atomic
def collect(request):
    from website.views import site_settings, tracking_allowed, analytics_identity, set_identity
    from website.security import rate_limited
    site = site_settings()
    if not tracking_allowed(request, site):
        return JsonResponse({"accepted":0}, status=202)
    if rate_limited(request, 'events', 90):
        return JsonResponse({"error":"Please slow down"}, status=429)
    if request.content_type != "application/json":
        return JsonResponse({"error":"Content-Type must be application/json"}, status=415)
    if len(request.body) > 32768:
        return JsonResponse({"error":"Batch too large"}, status=413)
    identity = analytics_identity(request)
    try:
        payload = json.loads(request.body)
        items = payload if isinstance(payload, list) else [payload]
        if not 1 <= len(items) <= 20: raise ValueError("Batch must contain 1-20 events")
        # Inner savepoint rolls back a partially valid batch on validation failure.
        with transaction.atomic():
            for item in items:
                if not isinstance(item, dict): raise ValueError("Each event must be an object")
                item.update(identity)
                # Only the actual request host participates in source attribution.
                context = item.get('context') if isinstance(item.get('context'), dict) else {}
                item['context'] = {**context, 'host':request.get_host()}
                ingest(request, item)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as exc:
        return JsonResponse({"error":str(exc)}, status=400)
    response = JsonResponse({"accepted":len(items)}, status=202)
    set_identity(response, identity)
    return response



@staff_member_required
def dashboard(request):
    window = dashboard_window(request.GET)
    sessions = VisitorSession.objects.filter(first_seen_at__gte=window["since"], first_seen_at__lte=window["until"])
    source = request.GET.get("source", "")
    device = request.GET.get("device", "")
    stage = request.GET.get("stage", "")
    human = request.GET.get("human", "")
    if source: sessions = sessions.filter(source=source)
    if device: sessions = sessions.filter(device_class=device)
    if stage: sessions = sessions.filter(funnel_stage=stage)
    if human == "likely": sessions = sessions.filter(human_score__gte=60)
    elif human == "possible": sessions = sessions.filter(human_score__gte=25, human_score__lt=60)
    elif human == "unclear": sessions = sessions.filter(human_score__lt=25)
    leads = Lead.objects.filter(session__in=sessions)
    ip_records = IPRecord.objects.filter(sessions__in=sessions).annotate(session_total=Count("sessions", distinct=True)).distinct()[:100]
    notification_preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)
    session_rows = list(sessions.select_related("lead").prefetch_related("events")[:150])
    for session in session_rows:
        session.human_journey = journey_summary(session)
    context = {
        "sessions": session_rows, "window": window, "lead_count": leads.count(),
        "visitor_count": sessions.values("visitor_id").distinct().count(), "session_count": sessions.count(),
        "human_count": sessions.filter(human_score__gte=60).count(),
        "booking_count": sessions.filter(funnel_stage__in=["booking_opened"]).count(),
        "stage_counts": sessions.values("funnel_stage").annotate(total=Count("id")).order_by("-total"),
        "source_counts": sessions.values("source").annotate(total=Count("id")).order_by("-total")[:10],
        "sources": VisitorSession.objects.exclude(source="").values_list("source", flat=True).distinct().order_by("source"),
        "filters": {"source": source, "device": device, "stage": stage, "human": human},
        "status_choices": Lead.Status.choices,
        "notification_preferences": notification_preferences,
        "telegram_accounts": TelegramAccount.objects.filter(user=request.user).order_by("username", "first_name"),
        "ip_records": ip_records,
    }
    from website.dashboard import metrics
    context.update(metrics(sessions))
    from website.models import SiteSettings
    context['site'] = SiteSettings.objects.first()
    return render(request, "analytics/dashboard.html", context)


@staff_member_required
@require_POST
def update_notifications(request):
    preference, _ = NotificationPreference.objects.get_or_create(user=request.user)
    for field in ("enabled", "traffic_enabled", "engagement_enabled", "funnel_enabled", "lead_enabled"):
        setattr(preference, field, request.POST.get(field) == "on")
    if request.POST.get("resume_now"):
        preference.paused_until = None
    preference.save()
    return redirect("/dashboard/")


@staff_member_required
@require_POST
def update_lead(request, lead_id):
    lead = get_object_or_404(Lead, pk=lead_id)
    status = request.POST.get("status")
    valid = {choice for choice, _ in Lead.Status.choices}
    if status not in valid: return JsonResponse({"error": "Invalid status"}, status=400)
    lead.status = status
    lead.save(update_fields=["status", "updated_at"])
    return redirect("/dashboard/")

@require_POST
def forget_journey(request):
    response = JsonResponse({'ok': True})
    response.delete_cookie('journey', samesite='Lax')
    return response
