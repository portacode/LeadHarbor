import json
import os
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps
from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from website.models import SiteSettings, Section, FormField, Goal

class Command(BaseCommand):
    help = 'Idempotently seed the business website and unique owner account.'
    @transaction.atomic
    def handle(self, *args, **options):
        site = SiteSettings.objects.filter(pk=1).first()
        created = site is None
        if created: site = SiteSettings(pk=1)
        if created:
            for field in ['name','tagline','headline','description','primary_color','conversion_mode','booking_url','contact_email']:
                key = 'BUSINESS_NAME' if field == 'name' else field.upper()
                if os.environ.get(key): setattr(site,field,os.environ[key])
            for field, key in [('logo','LOGO_FILE'),('hero_image','HERO_IMAGE')]:
                if not os.environ.get(key): continue
                path = Path(os.environ[key])
                imported = settings.BASE_DIR/'.private'/key.lower()
                if imported.exists(): path = imported
                if path.stat().st_size > 10*1024*1024: raise CommandError('Brand images must be under 10 MB.')
                try:
                    with Image.open(path) as image:
                        if image.width*image.height > 25_000_000: raise ValueError('Image too large')
                        image = ImageOps.exif_transpose(image)
                        image.thumbnail((1800,1800))
                        converted = image.convert('RGBA' if field == 'logo' else 'RGB')
                        content = BytesIO(); converted.save(content, format='PNG' if field == 'logo' else 'JPEG')
                    getattr(site,field).save(f'{field}.{"png" if field == "logo" else "jpg"}', ContentFile(content.getvalue()), save=False)
                except Exception as exc: raise CommandError('Upload a valid PNG, JPEG or WebP brand image.') from exc
            site.save()
            for index,(kind,title,body) in enumerate([
                ('benefit','Built around your goals','We start by listening. Your priorities shape the way forward, from the first conversation to the final detail.'),
                ('benefit','Clarity at every step','Understand your options, know what comes next, and make decisions with confidence.'),
                ('benefit','People, not processes','Thoughtful service from people who care about getting the details right.'),
                ('step','Tell us what matters','Share your goals, questions, or the challenge you want to solve.'),
                ('step','Explore the possibilities','We’ll get in touch to understand your needs and discuss the right approach.'),
                ('step','Move forward with confidence','Agree on a clear next step that works for you.'),
                ('faq','What happens after I get in touch?','Your request goes directly to our team. We’ll review the details and contact you to discuss next steps.'),
                ('faq','Do I need to know exactly what I need?','Not at all. A question or an initial idea is a perfectly good place to start.'),
            ]): Section.objects.create(kind=kind,title=title,body=body,position=index)
            for index,(key,label,kind,required) in enumerate([('name','Your name','text',True),('email','Email address','email',True),('message','What do you have in mind?','textarea',False)]):
                FormField.objects.create(key=key,label=label,kind=kind,required=required,position=index)
            Goal.objects.create(key='requests',label='Submitted requests',event_name='conversion',primary=True)
            Goal.objects.create(key='booking_intent',label='Scheduling link opened',event_name='booking_open')
        username = settings.RUNTIME.get('ADMIN_USERNAME','owner')
        password = settings.RUNTIME.get('ADMIN_PASSWORD')
        if not password: raise CommandError('Run scripts/configure.py before bootstrap.')
        user, new = get_user_model().objects.get_or_create(username=username, defaults={'is_staff':True,'is_superuser':True,'email':site.contact_email})
        if new:
            user.set_password(password); user.save()
        credentials = settings.BASE_DIR/'.private/ADMIN-CREDENTIALS.md'
        if new or not credentials.exists():
            credentials.write_text(f'# Private owner handoff\n\nWebsite: {settings.PUBLIC_URL}/\nAdmin: {settings.PUBLIC_URL}/admin/\nDashboard: {settings.PUBLIC_URL}/dashboard/\nUsername: {username}\nPassword: {password}\n\nChange this password in Django admin after first login. This file records the initial password only; it does not track later changes.\n')
            credentials.chmod(0o600)
        self.stdout.write('Website ready. Owner credentials: .private/ADMIN-CREDENTIALS.md (private device file).')
