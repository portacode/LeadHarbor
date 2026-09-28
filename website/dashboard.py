from datetime import timedelta
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from analytics.models import VisitorSession, Event
from .models import Goal, Submission

def metrics(sessions):
    total = sessions.count()
    conversions = sessions.filter(submissions__isnull=False).distinct().count()
    goals = []
    for goal in Goal.objects.filter(enabled=True):
        events = Event.objects.filter(session__in=sessions, name=goal.event_name)
        if goal.target:
            events = events.filter(Q(properties__goal_key=goal.target) | Q(properties__target=goal.target) | Q(properties__cta_name=goal.target))
        count = events.values('session_id').distinct().count()
        goals.append({'label':goal.label, 'count':count, 'rate':round(100*count/total,1) if total else 0, 'primary':goal.primary})
    funnel = []
    for label, names in [('Visited', ['page_load']), ('Engaged',['cta_click','user_click','user_engagement']), ('Started',['form_start','booking_open']), ('Converted',['conversion'])]:
        count = Event.objects.filter(session__in=sessions, name__in=names).values('session_id').distinct().count()
        funnel.append({'label':label, 'count':count, 'percent':round(100*count/total,1) if total else 0})
    daily = list(sessions.annotate(day=TruncDate('first_seen_at')).values('day').annotate(visits=Count('id', distinct=True), conversions=Count('id', filter=Q(submissions__isnull=False), distinct=True)).order_by('day'))
    return {'conversion_count':conversions, 'conversion_rate':round(conversions*100/total,1) if total else 0,
            'goals':goals, 'funnel':funnel, 'daily':daily,
            'submission_count':Submission.objects.filter(session__in=sessions).count(),
            'unattributed_count':Submission.objects.filter(session__isnull=True, created_at__gte=timezone.now()-timedelta(days=30)).count()}

def admin_dashboard(request, context):
    sessions = VisitorSession.objects.filter(first_seen_at__gte=timezone.now()-timedelta(days=30))
    context.update(metrics(sessions))
    context['session_count'] = sessions.count()
    context['new_requests'] = Submission.objects.filter(status='new').count()
    return context
