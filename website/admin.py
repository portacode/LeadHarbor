from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import SiteSettings, Section, FormField, Goal, Submission

@admin.register(SiteSettings)
class SettingsAdmin(ModelAdmin):
    fieldsets = [('Brand', {'fields':['name','tagline','logo','hero_image','primary_color','contact_email']}),
                 ('Landing page', {'fields':['headline','description','cta_label','thank_you']}),
                 ('Conversion', {'fields':['conversion_mode','booking_url']}),
                 ('Privacy & measurement', {'fields':['analytics_mode','privacy_notice']})]
    def has_add_permission(self, request): return not SiteSettings.objects.exists()
    def has_delete_permission(self, request, obj=None): return False

@admin.register(Section)
class SectionAdmin(ModelAdmin):
    list_display = ['title','kind','position','enabled']
    list_editable = ['position','enabled']
    list_filter = ['kind','enabled']

@admin.register(FormField)
class FieldAdmin(ModelAdmin):
    list_display = ['label','key','kind','required','position','enabled']
    list_editable = ['required','position','enabled']

@admin.register(Goal)
class GoalAdmin(ModelAdmin):
    list_display = ['label','event_name','target','primary','enabled']

@admin.register(Submission)
class SubmissionAdmin(ModelAdmin):
    list_display = ['id','kind','status','created_at']
    list_filter = ['kind','status','created_at']
    search_fields = ['data','notes']
    readonly_fields = ['data','session','kind','consent_at','created_at']
    fields = ['status','notes','data','session','kind','consent_at','created_at']
