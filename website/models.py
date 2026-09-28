import re
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

class SiteSettings(models.Model):
    name = models.CharField(max_length=120, default='Your business')
    tagline = models.CharField(max_length=160, default='A thoughtful approach. A better outcome.')
    headline = models.CharField(max_length=200, default='Your next chapter starts with a conversation.')
    description = models.TextField(default='Tell us what you have in mind. We’ll help you find a clear, practical path forward, with personal attention at every step.')
    logo = models.ImageField(upload_to='branding/', blank=True)
    hero_image = models.ImageField(upload_to='branding/', blank=True)
    primary_color = models.CharField(max_length=7, default='#31594f', validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$')])
    cta_label = models.CharField(max_length=70, default='Let’s talk')
    conversion_mode = models.CharField(max_length=20, choices=[('form', 'Contact / quote form'), ('booking', 'Booking request'), ('external', 'External scheduling link')], default='form')
    booking_url = models.URLField(blank=True)
    contact_email = models.EmailField(blank=True)
    thank_you = models.CharField(max_length=300, default='Thank you. Your request is safely with us, and we’ll be in touch soon.')
    privacy_notice = models.TextField(default='We use your submitted details to respond to your request. With your permission, first-party analytics records visits, interactions, campaign attribution, device information and IP-based approximate location. Authorized team members may receive journey summaries through Telegram. Analytics is retained for 180 days. Contact us to request access or deletion.')
    analytics_mode = models.CharField(max_length=12, choices=[('consent', 'Ask permission'), ('off', 'Disabled'), ('essential', 'Always on (check your legal basis)')], default='consent')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Site settings'

    def clean(self):
        if self.conversion_mode == 'external' and not self.booking_url.startswith('https://'):
            raise ValidationError({'booking_url': 'An HTTPS scheduling URL is required for external mode.'})
    def save(self, *args, **kwargs):
        self.pk = 1
        self.full_clean()
        super().save(*args, **kwargs)
    def __str__(self): return self.name

class Section(models.Model):
    kind = models.CharField(max_length=20, choices=[('benefit','Benefit'),('step','How it works'),('faq','FAQ'),('testimonial','Testimonial')], default='benefit')
    title = models.CharField(max_length=150)
    body = models.TextField()
    attribution = models.CharField(max_length=150, blank=True, help_text='For genuine, approved customer quotes only.')
    position = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)
    class Meta: ordering = ['position', 'id']
    def __str__(self): return self.title

class FormField(models.Model):
    key = models.SlugField(unique=True, help_text='Stable ID; never collect passwords or payment card details.')
    label = models.CharField(max_length=120)
    kind = models.CharField(max_length=12, choices=[('text','Short text'),('email','Email'),('textarea','Long text'),('select','Dropdown'),('date','Preferred date'),('checkbox','Checkbox')], default='text')
    choices = models.TextField(blank=True, help_text='One dropdown choice per line.')
    required = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)
    class Meta: ordering = ['position', 'id']
    def clean(self):
        if not re.fullmatch('[a-z][a-z0-9_]*', self.key) or self.key in {'website','consent','csrfmiddlewaretoken','session_id'}:
            raise ValidationError({'key': 'Use a unique lowercase ID with underscores; reserved IDs are not allowed.'})
        if self.kind == 'select' and not self.choices.strip():
            raise ValidationError({'choices': 'Add at least one choice.'})
    def __str__(self): return self.label

class Goal(models.Model):
    key = models.SlugField(unique=True)
    label = models.CharField(max_length=100)
    event_name = models.CharField(max_length=80, default='conversion', help_text='Must exist in analytics/services.py ALLOWED_EVENTS, or be a server-side event.')
    target = models.CharField(max_length=100, blank=True, help_text='Optional goal_key, target or CTA ID to match.')
    primary = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    def __str__(self): return self.label

class Submission(models.Model):
    session = models.ForeignKey('analytics.VisitorSession', null=True, blank=True, on_delete=models.SET_NULL, related_name='submissions')
    kind = models.CharField(max_length=20, default='form')
    status = models.CharField(max_length=20, choices=[('new','New'),('contacted','Contacted'),('confirmed','Confirmed'),('won','Won'),('lost','Lost'),('spam','Spam')], default='new')
    data = models.JSONField(default=dict)
    consent_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    class Meta: ordering = ['-created_at']
    def __str__(self): return f'{self.get_kind_display() if hasattr(self,"get_kind_display") else self.kind} request #{self.pk}'

class RateBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
