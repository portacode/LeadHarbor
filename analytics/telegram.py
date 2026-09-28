import json
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from .models import NotificationPreference, TelegramAccount, TelegramBotState, TelegramDelivery
from .services import journey_text


class TelegramError(Exception):
    pass


def telegram_call(method, data=None):
    if not settings.TELEGRAM_BOT_TOKEN:
        return None
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}",
            data=data or {}, timeout=15,
        )
        body = response.json()
    except (requests.RequestException, ValueError):
        raise TelegramError("Telegram request failed") from None
    if not response.ok or not body.get("ok"):
        description = str(body.get("description") or "Telegram API rejected the request")
        if "message is not modified" not in description.lower():
            raise TelegramError("Telegram API rejected the request")
    return body.get("result")


def notification_category(session):
    if hasattr(session, "lead") or session.submissions.exists():
        return "lead"
    if session.funnel_stage in {"booking_opened", "form_started"}:
        return "funnel"
    if session.funnel_stage in {"engaged", "human_verified"}:
        return "engagement"
    return "traffic"


def _keyboard(category):
    labels = {"traffic": "traffic", "engagement": "engagement", "funnel": "funnel", "lead": "lead"}
    return json.dumps({"inline_keyboard": [
        [{"text": f"Mute {labels[category]}", "callback_data": f"mute:{category}"},
         {"text": "Pause 24h", "callback_data": "pause:24h"}],
        [{"text": "Stop all notifications", "callback_data": "stop:all"}],
    ]})


def _handle_callback(callback):
    callback_id = str(callback.get("id") or "")
    chat_id = str(((callback.get("message") or {}).get("chat") or {}).get("id") or "")
    account = TelegramAccount.objects.select_related("user").filter(chat_id=chat_id, enabled=True, user__is_staff=True, user__is_active=True).first()
    if not account:
        if callback_id:
            telegram_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "Link this chat to a staff user in Django admin first.", "show_alert": True})
        return
    preference, _ = NotificationPreference.objects.get_or_create(user=account.user)
    action, _, value = str(callback.get("data") or "").partition(":")
    response = "No setting changed."
    if action == "mute" and value in {"traffic", "engagement", "funnel", "lead"}:
        setattr(preference, f"{value}_enabled", False)
        preference.save(update_fields=[f"{value}_enabled", "updated_at"])
        response = f"{value.title()} notifications muted."
    elif action == "pause" and value == "24h":
        preference.paused_until = timezone.now() + timedelta(hours=24)
        preference.save(update_fields=["paused_until", "updated_at"])
        response = "Notifications paused for 24 hours."
    elif action == "stop" and value == "all":
        preference.enabled = False
        preference.save(update_fields=["enabled", "updated_at"])
        response = "All notifications stopped. Re-enable them from the dashboard."
    if callback_id:
        telegram_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": response})


def sync_telegram_updates():
    if not settings.TELEGRAM_BOT_TOKEN:
        return 0
    state, _ = TelegramBotState.objects.get_or_create(key="analytics")
    updates = telegram_call("getUpdates", {"offset": state.last_update_id + 1, "limit": 100, "timeout": 0}) or []
    discovered = 0
    for update in updates:
        update_id = int(update.get("update_id") or 0)
        if update.get("callback_query"):
            _handle_callback(update["callback_query"])
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        if chat.get("type") == "private" and chat.get("id") is not None:
            account, created = TelegramAccount.objects.update_or_create(
                chat_id=str(chat["id"]),
                defaults={
                    "telegram_user_id": str(sender.get("id") or ""),
                    "username": str(sender.get("username") or "")[:100],
                    "first_name": str(sender.get("first_name") or "")[:150],
                    "last_name": str(sender.get("last_name") or "")[:150],
                },
            )
            discovered += int(created)
            if created:
                telegram_call("sendMessage", {"chat_id": account.chat_id, "text": "Chat discovered. Link it to a Django staff user under Analytics → Telegram accounts to authorize notifications."})
        state.last_update_id = max(state.last_update_id, update_id)
    if updates:
        state.save(update_fields=["last_update_id", "updated_at"])
    return discovered


def deliver_session(session):
    if not settings.TELEGRAM_BOT_TOKEN:
        return 0
    category = notification_category(session)
    accounts = TelegramAccount.objects.select_related("user").filter(enabled=True, user__is_staff=True, user__is_active=True)
    sent = 0
    for account in accounts:
        preference, _ = NotificationPreference.objects.get_or_create(user=account.user)
        if not preference.category_enabled(category):
            continue
        delivery = TelegramDelivery.objects.filter(session=session, account=account).order_by("-sent_at", "-id").first()
        if not delivery:
            delivery = TelegramDelivery.objects.create(session=session, account=account, category=category)
        method = "editMessageText" if delivery.telegram_message_id else "sendMessage"
        data = {"chat_id": account.chat_id, "text": f"<b>{category.title()}</b>\n{journey_text(session)}", "parse_mode": "HTML",
                "disable_web_page_preview": True, "reply_markup": _keyboard(category)}
        if delivery.telegram_message_id:
            data["message_id"] = delivery.telegram_message_id
        result = telegram_call(method, data) or {}
        if not delivery.telegram_message_id:
            delivery.telegram_message_id = str(result.get("message_id") or "")
        delivery.sent_at = timezone.now()
        delivery.category = category
        delivery.save(update_fields=["telegram_message_id", "category", "sent_at"])
        sent += 1
    return sent
