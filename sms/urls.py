from django.urls import path
from .views import inbound_sms

urlpatterns = [
    path("inbound/", inbound_sms),
]
