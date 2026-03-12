from django.urls import path, include
from frontend.views import index

urlpatterns = [
    path("",            index),
    path("api/users/",  include("users.urls")),
    path("api/rooms/",  include("rooms.urls")),
    path("sms/",        include("sms.urls")),
]
