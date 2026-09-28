import json
from django.contrib import admin
from unfold.admin import ModelAdmin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from .models import Event, IPRecord, Lead, NotificationPreference, TelegramAccount, TelegramDelivery, VisitorSession
from .services import describe_event

@admin.register(VisitorSession)
class SessionAdmin(ModelAdmin):
    list_display = ("session_id", "source", "country", "city", "device_name", "human_score", "funnel_stage", "last_seen_at")
    list_filter = ("source", "country_code", "device_class", "funnel_stage")
    search_fields = ("session_id", "visitor_id", "city", "country", "device_name")

@admin.register(Lead)
class LeadAdmin(ModelAdmin):
    list_display = ("id", "role", "status", "email", "created_at")
    list_filter = ("status", "role")
    search_fields = ("email", "name", "company", "notes")

@admin.register(Event)
class EventAdmin(ModelAdmin):
    list_display = ("human_description", "name", "session", "path", "occurred_at")
    list_filter = ("name",)
    search_fields = ("session__session_id", "name")
    readonly_fields = ("human_description", "formatted_properties", "occurred_at")

    @admin.display(description="What happened")
    def human_description(self, obj):
        return describe_event(obj, include_routine=True)

    @admin.display(description="Readable properties")
    def formatted_properties(self, obj):
        return format_html("<pre style='white-space:pre-wrap'>{}</pre>", json.dumps(obj.properties, indent=2, sort_keys=True))

@admin.register(IPRecord)
class IPRecordAdmin(ModelAdmin):
    list_display = ("ip_address", "status", "country", "region", "city", "isp", "lookup_attempts", "last_seen_at")
    list_filter = ("status", "country_code")
    search_fields = ("ip_address", "country", "region", "city", "isp")
    readonly_fields = ("first_seen_at", "last_seen_at", "resolved_at")

@admin.register(TelegramAccount)
class TelegramAccountAdmin(ModelAdmin):
    list_display = ("display_name", "chat_id", "user", "enabled", "last_seen_at")
    list_filter = ("enabled",)
    search_fields = ("chat_id", "username", "first_name", "last_name", "user__username", "user__email")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["queryset"] = get_user_model().objects.filter(is_staff=True, is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(ModelAdmin):
    list_display = ("user", "enabled", "traffic_enabled", "engagement_enabled", "funnel_enabled", "lead_enabled", "paused_until")

@admin.register(TelegramDelivery)
class TelegramDeliveryAdmin(ModelAdmin):
    list_display = ("session", "account", "category", "telegram_message_id", "sent_at")
    list_filter = ("category",)
