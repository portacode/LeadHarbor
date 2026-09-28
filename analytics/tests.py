import json
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import Event, IPRecord, NotificationPreference, TelegramAccount, TelegramDelivery, VisitorSession
from .services import journey_text, enrich_ip_record
from .telegram import deliver_session, _handle_callback, sync_telegram_updates
from .views import dashboard_window
from website.models import SiteSettings, Submission

class AnalyticsTests(TestCase):
    def setUp(self):
        SiteSettings.objects.create(analytics_mode='consent')
        self.client.cookies['analytics_consent'] = 'yes'
    def send(self, event='page_load', **kwargs):
        return self.client.post('/api/v1/events/',json.dumps({'event':event,'path':'/?secret=x#private','referrer':'https://search.example/query?private=yes','context':{'utm_source':'newsletter'},**kwargs}),content_type='application/json')
    def test_collect_minimizes_data_and_sets_signed_identity(self):
        self.assertEqual(self.send().status_code,202)
        session = VisitorSession.objects.get()
        self.assertEqual(session.initial_referrer,'https://search.example')
        self.assertEqual(session.landing_path,'/')
        self.assertEqual(session.source,'newsletter')
        self.assertTrue(self.client.cookies['journey']['httponly'])
    def test_consent_and_gpc(self):
        self.client.cookies.clear()
        self.assertEqual(self.send().status_code,202)
        self.assertFalse(Event.objects.exists())
        self.client.cookies['analytics_consent']='yes'
        response=self.client.post('/api/v1/events/',json.dumps({'event':'page_load'}),content_type='application/json',HTTP_SEC_GPC='1')
        self.assertEqual(response.status_code,202)
        self.assertFalse(Event.objects.exists())
    def test_browser_cannot_claim_conversion(self):
        self.assertEqual(self.send('conversion').status_code,400)
        self.assertFalse(Event.objects.exists())
    def test_bad_batch_is_atomic(self):
        result=self.client.post('/api/v1/events/',json.dumps([{'event':'page_load'},None]),content_type='application/json')
        self.assertEqual(result.status_code,400)
        self.assertFalse(Event.objects.exists())
    def test_arbitrary_properties_are_dropped(self):
        self.send(properties={'password':'private','scroll_depth':50,'nested':{'email':'x'}})
        self.assertEqual(Event.objects.get().properties,{'scroll_depth':50})
    def test_client_cannot_choose_another_session(self):
        self.send(); first=VisitorSession.objects.get()
        self.send(session_id=str(uuid.uuid4()),visitor_id=str(uuid.uuid4()))
        self.assertEqual(VisitorSession.objects.count(),1)
        self.assertEqual(VisitorSession.objects.get().pk,first.pk)
    def test_csrf_required(self):
        client=Client(enforce_csrf_checks=True)
        client.cookies['analytics_consent']='yes'
        self.assertEqual(client.post('/api/v1/events/','{}',content_type='application/json').status_code,403)
    def test_dashboard_requires_active_staff(self):
        self.assertEqual(self.client.get('/dashboard/').status_code,302)
        user=get_user_model().objects.create_user('normal')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/dashboard/').status_code,302)
        user.is_staff=True;user.save()
        self.assertEqual(self.client.get('/dashboard/').status_code,200)
        self.assertEqual(self.client.get('/admin/').status_code,200)
    def test_time_windows(self):
        now=timezone.now()
        self.assertEqual(dashboard_window({'range':'1h'},now=now)['since'],now-timedelta(hours=1))
        self.assertTrue(dashboard_window({'range':'custom','from':'bad'})['error'])
    @override_settings(TELEGRAM_BOT_TOKEN='test')
    @patch('analytics.telegram.telegram_call',return_value={'message_id':44})
    def test_one_editable_message_and_preferences(self,call):
        staff=get_user_model().objects.create_user('staff',is_staff=True)
        TelegramAccount.objects.create(user=staff,chat_id='123')
        TelegramAccount.objects.create(chat_id='unlinked')
        self.send();session=VisitorSession.objects.get()
        self.assertEqual(deliver_session(session),1)
        Submission.objects.create(session=session)
        self.assertEqual(deliver_session(session),1)
        self.assertEqual(call.call_args.args[0],'editMessageText')
        self.assertEqual(TelegramDelivery.objects.count(),1)
        self.assertEqual(TelegramDelivery.objects.get().category,'lead')
        preference=NotificationPreference.objects.get(user=staff)
        preference.lead_enabled=False;preference.save()
        self.assertEqual(deliver_session(session),0)
    @patch('analytics.telegram.telegram_call')
    def test_mute_callback(self,call):
        staff=get_user_model().objects.create_user('staff',is_staff=True)
        TelegramAccount.objects.create(user=staff,chat_id='123')
        _handle_callback({'id':'cb','data':'mute:traffic','message':{'chat':{'id':123}}})
        self.assertFalse(NotificationPreference.objects.get(user=staff).traffic_enabled)
    @override_settings(TELEGRAM_BOT_TOKEN='test')
    @patch('analytics.telegram.telegram_call')
    def test_discovery_does_not_authorize(self,call):
        call.side_effect=[[{'update_id':1,'message':{'chat':{'id':123,'type':'private'},'from':{'id':123}}}],{}]
        sync_telegram_updates()
        self.assertIsNone(TelegramAccount.objects.get().user)
    def test_generic_journey_with_escaped_labels(self):
        self.send('cta_click',properties={'cta_name':'<test>'})
        session=VisitorSession.objects.get()
        self.assertIn('&lt;Test&gt;',journey_text(session))
        self.assertNotIn('menas.pro',journey_text(session))
    @patch('analytics.services.requests.get')
    def test_private_ips_are_not_sent_to_geo_provider(self,call):
        record=IPRecord.objects.create(ip_address='127.0.0.1')
        enrich_ip_record(record)
        self.assertFalse(call.called)

    def test_heartbeat_does_not_postpone_pending_digest(self):
        self.send()
        due = VisitorSession.objects.get().digest_due_at
        self.send('heartbeat')
        self.assertEqual(VisitorSession.objects.get().digest_due_at, due)
    def test_browser_cannot_claim_converted_funnel_stage(self):
        self.send('funnel_stage', properties={'stage':'converted'})
        self.assertNotEqual(VisitorSession.objects.get().funnel_stage,'converted')
