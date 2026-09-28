import json
from datetime import timedelta
from django.test import TestCase, Client
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.utils import timezone
from analytics.models import Event, VisitorSession, IPRecord
from .models import SiteSettings, FormField, Submission
from .dashboard import metrics

class WebsiteTests(TestCase):
    def setUp(self):
        self.site=SiteSettings.objects.create()
        FormField.objects.create(key='name',label='Name',required=True)
        FormField.objects.create(key='email',label='Email',kind='email',required=True)
    def submit(self, **extra):
        return self.client.post('/submit/',{'name':'Visitor','email':'visitor@example.com','consent':'on',**extra})
    def test_home_and_privacy_render(self):
        self.assertContains(self.client.get('/'),'Your next chapter')
        self.assertContains(self.client.get('/privacy/'),'Privacy')
    def test_submission_works_without_analytics(self):
        self.assertEqual(self.submit().status_code,302)
        self.assertIsNone(Submission.objects.get().session)
        self.assertFalse(Event.objects.exists())
        self.assertContains(self.client.get('/thanks/'),'You’re all set.')
        self.assertEqual(self.client.get('/thanks/').status_code,302)
    def test_invalid_email_and_honeypot(self):
        self.assertEqual(self.submit(email='bad').status_code,400)
        self.assertEqual(self.submit(website='spam').status_code,400)
        self.assertFalse(Submission.objects.exists())
    def test_server_records_conversion_and_excludes_pii_from_events(self):
        self.client.cookies['analytics_consent']='yes'
        self.client.post('/api/v1/events/',json.dumps({'event':'page_load'}),content_type='application/json')
        self.assertEqual(self.submit().status_code,302)
        self.assertEqual(Event.objects.filter(name='conversion').count(),1)
        self.assertEqual(VisitorSession.objects.get().funnel_stage,'converted')
        self.assertNotIn('visitor@example.com',str(list(Event.objects.values('properties'))))
        self.assertEqual(metrics(VisitorSession.objects.all())['conversion_rate'],100)
    def test_booking_request_requires_future_date(self):
        self.site.conversion_mode='booking';self.site.save()
        self.assertEqual(self.submit(preferred_date='2000-01-01').status_code,400)
        self.assertEqual(self.submit(preferred_date=(timezone.localdate()+timedelta(days=7)).isoformat()).status_code,302)
        self.assertEqual(Submission.objects.get().kind,'booking')
    def test_external_booking_validates_url(self):
        self.site.conversion_mode='external'
        with self.assertRaises(ValidationError): self.site.save()
        self.site.booking_url='https://cal.com/example';self.site.save()
        self.assertContains(self.client.get('/'),'https://cal.com/example')
        self.submit()
        self.assertFalse(Submission.objects.exists())
    def test_form_csrf_protection(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post('/submit/',{}).status_code,403)
    def test_retention_keeps_business_request(self):
        self.client.cookies['analytics_consent']='yes';self.submit()
        session=VisitorSession.objects.get()
        VisitorSession.objects.filter(pk=session.pk).update(last_seen_at=timezone.now()-timedelta(days=190))
        IPRecord.objects.update(last_seen_at=timezone.now()-timedelta(days=190))
        call_command('cleanup_analytics')
        self.assertFalse(VisitorSession.objects.exists())
        self.assertFalse(IPRecord.objects.exists())
        self.assertIsNone(Submission.objects.get().session)
    def test_rate_limit(self):
        for _ in range(5): self.submit()
        self.assertEqual(self.submit().status_code,429)
    def test_field_reserved_names(self):
        with self.assertRaises(ValidationError): FormField(key='consent',label='Bad').full_clean()
