from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from analytics.models import IPRecord, VisitorSession
from website.models import RateBucket

class Command(BaseCommand):
    help = 'Expire analytics and orphan IP records. Business submissions are retained separately.'
    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=settings.ANALYTICS_RETENTION_DAYS)
        count, _ = VisitorSession.objects.filter(last_seen_at__lt=cutoff).delete()
        IPRecord.objects.filter(sessions__isnull=True, last_seen_at__lt=cutoff).delete()
        RateBucket.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(f'Deleted {count} expired analytics rows; business requests retained.')
