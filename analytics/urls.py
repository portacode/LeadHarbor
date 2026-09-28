from django.urls import path
from . import views

app_name = "analytics"
urlpatterns = [
    path("api/v1/forget-journey/", views.forget_journey),
    path("health/", views.health, name="health"),
    path("api/v1/events/", views.collect, name="collect"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/leads/<uuid:lead_id>/status/", views.update_lead, name="update_lead"),
    path("dashboard/notifications/", views.update_notifications, name="update_notifications"),
]
