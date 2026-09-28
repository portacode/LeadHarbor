import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class IPRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        OK = "ok", "Resolved"
        PRIVATE = "private", "Private/reserved"
        FAILED = "failed", "Failed"

    ip_address = models.GenericIPAddressField(unique=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    country = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    timezone_name = models.CharField(max_length=100, blank=True)
    isp = models.CharField(max_length=200, blank=True)
    lookup_attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=300, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]

    def __str__(self):
        return f"{self.ip_address} ({self.status})"


class VisitorSession(models.Model):
    visitor_id = models.UUIDField(db_index=True)
    session_id = models.UUIDField(unique=True)
    landing_path = models.CharField(max_length=500, default="/")
    initial_referrer = models.URLField(max_length=2000, blank=True)
    source = models.CharField(max_length=150, default="direct", db_index=True)
    medium = models.CharField(max_length=120, blank=True)
    campaign = models.CharField(max_length=200, blank=True)
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    ip_record = models.ForeignKey(IPRecord, null=True, blank=True, related_name="sessions", on_delete=models.SET_NULL)
    device_class = models.CharField(max_length=20, blank=True)
    device_name = models.CharField(max_length=100, blank=True)
    os_name = models.CharField(max_length=100, blank=True)
    browser_name = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=30, blank=True)
    timezone_name = models.CharField(max_length=100, blank=True)
    human_score = models.PositiveSmallIntegerField(default=0, db_index=True)
    funnel_stage = models.CharField(max_length=80, default="landed", db_index=True)
    event_count = models.PositiveIntegerField(default=0)
    first_seen_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen_at = models.DateTimeField(default=timezone.now, db_index=True)
    digest_due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    telegram_message_id = models.CharField(max_length=100, blank=True)
    geo_enriched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]
        indexes = [models.Index(fields=["-first_seen_at", "source"])]


class TelegramAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="analytics_telegram_accounts", on_delete=models.SET_NULL)
    chat_id = models.CharField(max_length=100, unique=True)
    telegram_user_id = models.CharField(max_length=100, blank=True)
    username = models.CharField(max_length=100, blank=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    enabled = models.BooleanField(default=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    @property
    def display_name(self):
        return self.username and f"@{self.username}" or " ".join(filter(None, [self.first_name, self.last_name])) or self.chat_id

    def __str__(self):
        return f"{self.display_name} → {self.user or 'unlinked'}"


class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="analytics_notification_preferences", on_delete=models.CASCADE)
    enabled = models.BooleanField(default=True)
    traffic_enabled = models.BooleanField(default=True)
    engagement_enabled = models.BooleanField(default=True)
    funnel_enabled = models.BooleanField(default=True)
    lead_enabled = models.BooleanField(default=True)
    paused_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def category_enabled(self, category):
        return self.enabled and getattr(self, f"{category}_enabled", False) and (not self.paused_until or self.paused_until <= timezone.now())


class TelegramBotState(models.Model):
    key = models.CharField(max_length=30, primary_key=True, default="analytics")
    last_update_id = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class TelegramDelivery(models.Model):
    session = models.ForeignKey(VisitorSession, related_name="telegram_deliveries", on_delete=models.CASCADE)
    account = models.ForeignKey(TelegramAccount, related_name="deliveries", on_delete=models.CASCADE)
    category = models.CharField(max_length=20, db_index=True)
    telegram_message_id = models.CharField(max_length=100, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)



class Event(models.Model):
    session = models.ForeignKey(VisitorSession, related_name="events", on_delete=models.CASCADE)
    name = models.CharField(max_length=80, db_index=True)
    path = models.CharField(max_length=500, default="/")
    properties = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [models.Index(fields=["session", "occurred_at"]), models.Index(fields=["name", "-occurred_at"])]


class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        QUALIFIED = "qualified", "Qualified"
        CONTACTED = "contacted", "Contacted"
        MEETING = "meeting", "Meeting booked"
        WON = "won", "Won"
        LOST = "lost", "Lost"
        SPAM = "spam", "Spam"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(VisitorSession, related_name="lead", on_delete=models.CASCADE)
    role = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    company = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    booking_opened_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
