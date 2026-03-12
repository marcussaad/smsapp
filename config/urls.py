from django.urls import path, include

urlpatterns = [
    path("api/users/",  include("users.urls")),
    path("api/rooms/",  include("rooms.urls")),
    path("sms/",        include("sms.urls")),
]
