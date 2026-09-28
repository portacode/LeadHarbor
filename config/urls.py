from django.contrib import admin
from django.urls import include, path
from website import views
admin.site.site_header = 'LeadHarbor'
admin.site.site_title = 'LeadHarbor'
admin.site.index_title = 'Business overview'
urlpatterns = [path('admin/', admin.site.urls), path('', include('website.urls')),
               path('', include('analytics.urls'))]
