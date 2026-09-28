import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from analytics.models import IPRecord, VisitorSession
from analytics.services import enrich_ip_record
from analytics.telegram import deliver_session, sync_telegram_updates

class Command(BaseCommand):
    help = "Enrich session locations and deliver editable Telegram journey summaries."

    def handle(self, *args, **options):
        self.stdout.write("Analytics worker started")
        while True:
            now = timezone.now()
            try:
                sync_telegram_updates()
            except Exception as exc:
                self.stderr.write(f"Telegram sync: {type(exc).__name__}")
            legacy_sessions = VisitorSession.objects.filter(ip_record__isnull=True, ip_address__isnull=False)[:100]
            for session in legacy_sessions:
                record, _ = IPRecord.objects.get_or_create(ip_address=session.ip_address)
                VisitorSession.objects.filter(pk=session.pk).update(ip_record=record)
            resolved_records = IPRecord.objects.filter(status=IPRecord.Status.OK, sessions__country="").distinct()[:20]
            for record in resolved_records:
                record.sessions.filter(country="").update(
                    country=record.country, country_code=record.country_code,
                    city=record.city, geo_enriched_at=record.resolved_at,
                )
            records = list(IPRecord.objects.filter(status__in=[IPRecord.Status.PENDING, IPRecord.Status.FAILED], lookup_attempts__lt=5).order_by("last_seen_at")[:20])
            for record in records:
                try:
                    enrich_ip_record(record)
                except Exception as exc:
                    self.stderr.write(f"IP record {record.pk}: {type(exc).__name__}")
            sessions = list(VisitorSession.objects.filter(digest_due_at__lte=now).order_by("digest_due_at")[:20])
            for session in sessions:
                try:
                    deliver_session(session)
                    VisitorSession.objects.filter(pk=session.pk, digest_due_at=session.digest_due_at).update(digest_due_at=None)
                except Exception as exc:
                    self.stderr.write(f"Session {session.pk}: {type(exc).__name__}")
            time.sleep(5)
