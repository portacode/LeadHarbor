from django.urls import path
from . import views
app_name = 'website'
urlpatterns = [path('', views.home, name='home'), path('submit/', views.submit, name='submit'),
               path('thanks/', views.thanks, name='thanks'), path('privacy/', views.privacy, name='privacy'),
               path('brand/<str:field>/', views.brand_image, name='brand')]
