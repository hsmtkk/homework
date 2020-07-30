from django.urls import path
from . import views

app_name = 'aifx'

urlpatterns = [
    path('', views.candle, name='candle'),
]