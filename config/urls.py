from django.urls import path, include
from frontend.views import index
from frontend.health import health

urlpatterns = [
    path("",            index),
    path("health/",     health),
    path("api/users/",  include("users.urls")),
    path("api/rooms/",  include("rooms.urls")),
    path("sms/",        include("sms.urls")),]
