import html
import ipaddress
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.db.models import F, Value
from django.db.models.functions import Least, Coalesce
from django.utils import timezone
from user_agents import parse

from .models import Event, IPRecord, Lead, VisitorSession

ALLOWED_EVENTS = {
    "page_load", "human_detected", "funnel_stage", "cta_click", "outbound_click",
    "project_view", "user_engagement", "user_click",
    "user_intent_detected", "exit_intent", "page_exit", "heartbeat",
}
ALLOWED_PROPERTIES = {
    "stage", "cta_name", "destination", "page_section", "platform", "project_name",
    "source", "popup_action", "selected_role", "signal_type", "target", "section",
    "duration_ms", "intent", "confidence", "click_count", "click_target", "click_category",
    "click_step", "time_on_page_ms", "session_duration_ms", "scroll_depth", "interacted",
    "is_human", "interaction_type", "time_to_interaction_ms", "beat_number", "device_type",
    "viewport_width", "viewport_height", "detected_intent",
}
TARGET_LABELS = {}
# Server-written conversion events cannot be claimed by browser telemetry.
ALLOWED_EVENTS |= {"section_view", "form_start", "form_error", "booking_open", "consent_granted"}
ALLOWED_PROPERTIES |= {"goal_key", "form_key", "field_key", "error_code"}
FUNNEL_ORDER = {"landed": 0, "human_verified": 1, "engaged": 2, "form_started": 3, "booking_opened": 3, "converted": 4}



def bounded(value, length):
    return str(value or "").strip()[:length]


def client_ip(request):
    value = request.META.get("REMOTE_ADDR", "")
    if settings.TRUST_X_FORWARDED_FOR:
        value = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",", 1)[0].strip() or value
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return ""


def source_from(referrer, context):
    if context.get("utm_source"):
        return bounded(context["utm_source"], 150)
    try:
        host = (urlparse(referrer).hostname or "").lower().removeprefix("www.")
    except ValueError:
        host = ""
    own = bounded(context.get("host"), 255).split(":", 1)[0].lower().removeprefix("www.")
    return "direct" if not host or host == own else host


def safe_referrer(value):
    try:
        parsed = urlparse(bounded(value, 2000))
        if parsed.scheme in {"http", "https"} and parsed.hostname:
            return f"{parsed.scheme}://{parsed.hostname}"
    except ValueError:
        pass
    return ""


def device_details(user_agent):
    ua = parse(user_agent or "")
    if ua.is_mobile:
        device_class = "mobile"
    elif ua.is_tablet:
        device_class = "tablet"
    elif ua.is_pc:
        device_class = "desktop"
    else:
        device_class = "other"
    family = ua.device.family
    if family in {"Other", "Generic Smartphone"}:
        family = ua.os.family
    return device_class, bounded(family, 100), bounded(ua.os.family, 100), bounded(ua.browser.family, 100)


def sanitize_properties(raw):
    if not isinstance(raw, dict):
        return {}
    result = {}
    for key, value in raw.items():
        if key not in ALLOWED_PROPERTIES or isinstance(value, (dict, list)):
            continue
        result[key] = value if isinstance(value, (bool, int, float)) else bounded(value, 300)
    return result


def target_label(value):
    value = str(value or "").strip()
    return TARGET_LABELS.get(value, value.replace("_", " ").strip().title() or "item")


def describe_event(event, *, include_routine=False):
    name = event.name if hasattr(event, "name") else event.get("name", "")
    props = event.properties if hasattr(event, "properties") else event.get("properties", {}) or {}
    if name == "page_load": return "Opened the landing page"
    if name == "human_detected": return f"Interacted via {props.get('interaction_type', 'the page')}"
    if name == "outbound_click": return f"Clicked {target_label(props.get('platform'))}"
    if name == "project_view": return f"Viewed {target_label(props.get('project_name'))}"
    if name == "cta_click": return f"Clicked {target_label(props.get('cta_name'))}"
    if name == "section_view": return f"Viewed {target_label(props.get('section'))}"
    if name == "form_start": return "Started a request"
    if name == "form_error": return "Request needs corrections"
    if name == "booking_open": return "Opened the scheduling link (booking not yet confirmed)"
    if name == "conversion": return f"Submitted {target_label(props.get('goal_key') or 'request')}"
    if name == "user_engagement" and props.get("signal_type") == "hover_significant":
        return f"Hovered {target_label(props.get('target'))}"
    if name == "user_intent_detected": return f"Likely intent: {target_label(props.get('intent'))}"
    if name == "exit_intent": return "Showed exit intent"
    if name == "page_exit": return "Left the landing page"
    if include_routine:
        if name == "funnel_stage": return f"Reached {target_label(props.get('stage'))}"
        if name == "heartbeat": return "Stayed active"
        if name == "user_click": return f"Clicked {target_label(props.get('click_target'))}"
        if name == "user_engagement": return f"Engaged with {target_label(props.get('target') or props.get('section'))}"
        return name.replace("_", " ").strip().title()
    return None


def journey_descriptions(session, *, limit=None):
    items = []
    for event in session.events.all():
        description = describe_event(event)
        if description and (not items or items[-1]["description"] != description):
            items.append({"description": description, "occurred_at": event.occurred_at})
    if limit and len(items) > limit:
        half = limit // 2
        omitted = len(items) - (half * 2)
        items = items[:half] + [{"description": f"… {omitted} more meaningful actions …", "occurred_at": None}] + items[-half:]
    return items


def journey_summary(session):
    clicked, explored, steps, intents = [], [], [], []
    for event in session.events.all():
        props = event.properties or {}
        target = str(props.get('target') or props.get('cta_name') or props.get('platform') or '')
        if event.name in {'cta_click', 'outbound_click', 'user_click'} and target:
            if target not in clicked: clicked.append(target)
        elif event.name == 'user_engagement' and props.get('signal_type') == 'hover_significant' and target:
            if target not in explored: explored.append(target)
        elif event.name == 'user_intent_detected':
            intent = target_label(props.get('intent'))
            if intent not in intents: intents.append(intent)
        elif event.name in {'section_view','form_start','form_error','booking_open','conversion'}:
            text = describe_event(event)
            if text not in steps: steps.append(text)
    groups = []
    number = 0
    for kind, icon, label, entries in [
        ('click','🖱️','Clicks',[target_label(t) for t in clicked]),
        ('explore','👀','Explored without clicking',[target_label(t) for t in explored if t not in clicked]),
        ('conversion','📋','Conversion journey',steps),
        ('signal','🎯','Likely intent (inferred)',intents),
    ]:
        if not entries: continue
        rendered = []
        for text in entries[:5]:
            number += 1
            rendered.append({'number':number, 'description':text[:100]})
        groups.append({'kind':kind, 'icon':icon, 'label':label, 'entries':rendered})
    return {'groups':groups, 'total':number}


def ingest(request, raw):
    if not isinstance(raw, dict): raise ValueError("Each event must be an object")
    name = bounded(raw.get("event"), 80)
    if name not in ALLOWED_EVENTS:
        raise ValueError(f"Unsupported event: {name}")
    context = raw.get("context") if isinstance(raw.get("context"), dict) else {}
    try:
        import uuid
        visitor_id = uuid.UUID(str(raw.get("visitor_id")))
        session_id = uuid.UUID(str(raw.get("session_id")))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("visitor_id and session_id must be UUIDs")
    path = bounded(raw.get("path") or "/", 500).split("?", 1)[0]
    path = path.split("#", 1)[0]
    referrer = safe_referrer(raw.get("referrer"))
    now = timezone.now()
    ip_value = client_ip(request)
    ip_record = None
    if ip_value:
        ip_record, _ = IPRecord.objects.get_or_create(ip_address=ip_value)
        IPRecord.objects.filter(pk=ip_record.pk).update(last_seen_at=now)
    device_class, device_name, os_name, browser_name = device_details(request.META.get("HTTP_USER_AGENT", ""))
    cached_geo = ip_record if ip_record and ip_record.status == IPRecord.Status.OK else None
    session, _ = VisitorSession.objects.get_or_create(session_id=session_id, defaults={
        "visitor_id": visitor_id, "landing_path": path, "initial_referrer": referrer,
        "source": source_from(referrer, context), "medium": bounded(context.get("utm_medium"), 120),
        "campaign": bounded(context.get("utm_campaign"), 200), "ip_address": ip_value or None, "ip_record": ip_record,
        "country_code": cached_geo.country_code if cached_geo else "",
        "country": cached_geo.country if cached_geo else "", "city": cached_geo.city if cached_geo else "",
        "device_class": device_class, "device_name": device_name, "os_name": os_name,
        "browser_name": browser_name, "language": bounded(context.get("language"), 30),
        "timezone_name": bounded(context.get("timezone"), 100),
    })
    props = sanitize_properties(raw.get("properties"))
    Event.objects.create(session=session, name=name, path=path, properties=props)

    stage = session.funnel_stage
    if name == "funnel_stage":
        candidate = bounded(props.get("stage"), 80)
        if candidate != "converted" and FUNNEL_ORDER.get(candidate, -1) > FUNNEL_ORDER.get(stage, -1):
            stage = candidate
    elif name in {'form_start', 'booking_open'}:
        candidate = 'form_started' if name == 'form_start' else 'booking_opened'
        if FUNNEL_ORDER[candidate] > FUNNEL_ORDER.get(stage, 0): stage = candidate
    elif name in {"cta_click", "outbound_click", "project_view", "user_click"} and FUNNEL_ORDER.get(stage, 0) < 2:
        stage = "engaged"

    human_delta = 0
    if name == "human_detected": human_delta = 50
    elif name in {"cta_click", "outbound_click", "booking_open", "user_click"}: human_delta = 15
    elif name == "user_engagement": human_delta = 5
    updates = {"last_seen_at": now, "event_count": F("event_count") + 1, "funnel_stage": stage,
               "human_score": Least(Value(100), F("human_score") + human_delta),
               "digest_due_at": Coalesce(F("digest_due_at"), Value(now + timezone.timedelta(seconds=settings.ANALYTICS_DIGEST_DELAY_SECONDS)))}
    VisitorSession.objects.filter(pk=session.pk).update(**updates)

    return session


def enrich_ip_record(record):
    if record.status in {IPRecord.Status.OK, IPRecord.Status.PRIVATE}:
        return
    ip = ipaddress.ip_address(record.ip_address)
    if not ip.is_global:
        record.status = IPRecord.Status.PRIVATE
        record.resolved_at = timezone.now()
        record.lookup_attempts += 1
        record.save(update_fields=["status", "resolved_at", "lookup_attempts", "last_seen_at"])
        return
    if not settings.GEOIP_ENABLED:
        return
    try:
        response = requests.get(f"https://ipwho.is/{ip}", timeout=5)
        data = response.json()
        if response.ok and data.get("success") is True:
            record.status = IPRecord.Status.OK
            record.country = bounded(data.get("country"), 100)
            record.country_code = bounded(data.get("country_code"), 2)
            record.region = bounded(data.get("region"), 100)
            record.city = bounded(data.get("city"), 100)
            record.timezone_name = bounded((data.get("timezone") or {}).get("id"), 100)
            record.isp = bounded((data.get("connection") or {}).get("isp"), 200)
            record.last_error = ""
        else:
            record.status = IPRecord.Status.FAILED
            record.last_error = bounded(data.get("message") or "Lookup rejected", 300)
    except (requests.RequestException, ValueError):
        record.status = IPRecord.Status.FAILED
        record.last_error = "Lookup request failed"
        record.lookup_attempts += 1
        record.save(update_fields=["status", "last_error", "lookup_attempts", "last_seen_at"])
        return
    record.lookup_attempts += 1
    record.resolved_at = timezone.now()
    record.save(update_fields=["status", "country", "country_code", "region", "city", "timezone_name", "isp", "last_error", "lookup_attempts", "resolved_at", "last_seen_at"])
    if record.status == IPRecord.Status.OK:
        record.sessions.update(country=record.country, country_code=record.country_code, city=record.city, geo_enriched_at=record.resolved_at)


def journey_text(session):
    summary = journey_summary(session)
    duration = max(0, int((session.last_seen_at - session.first_seen_at).total_seconds()))
    mins, secs = divmod(duration, 60)
    location = ", ".join(filter(None, [session.city, session.country])) or session.country_code or "Unknown location"
    device = " · ".join(filter(None, [session.device_name, session.os_name, session.browser_name])) or session.device_class
    confidence = "Likely human" if session.human_score >= 60 else "Possibly human" if session.human_score >= 25 else "Unclear"
    source = session.source + (f" / {session.medium}" if session.medium else "")
    from website.models import SiteSettings
    site = SiteSettings.objects.first()
    lines = [f"<b>{html.escape(site.name if site else 'Visitor')} journey</b>", html.escape(f"📍 {location}"), html.escape(f"💻 {device}"),
             html.escape(f"↗️ {source}"), html.escape(f"🧠 {confidence} · {min(session.human_score, 100)}% · {mins}m {secs}s")]
    if summary["groups"]:
        for group in summary["groups"]:
            lines.extend(["", f"<b>{group['icon']} {html.escape(group['label'])}</b>"])
            lines.extend(f"{entry['number']}. {html.escape(entry['description'])}" for entry in group["entries"])
    else:
        lines.extend(["", "No meaningful action yet."])
    if session.campaign: lines.append(html.escape(f"Campaign: {session.campaign}"))
    return "\n".join(lines)
