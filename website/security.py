import hashlib
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import RateBucket
from analytics.services import client_ip

def rate_limited(request, scope, limit, seconds=60):
    now = timezone.now()
    window = int(now.timestamp()) // seconds
    key = hashlib.sha256(f'{settings.SECRET_KEY}:{scope}:{client_ip(request)}:{window}'.encode()).hexdigest()
    with transaction.atomic():
        bucket, _ = RateBucket.objects.get_or_create(key=key, defaults={'expires_at':now + timedelta(seconds=seconds * 2)})
        bucket = RateBucket.objects.select_for_update().get(pk=bucket.pk)
        if bucket.count >= limit: return True
        bucket.count += 1
        bucket.save(update_fields=['count'])
    return False
