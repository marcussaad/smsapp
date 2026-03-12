from django.urls import path
from .views import RoomListCreateView, RoomDetailView, JoinRoomView, LeaveRoomView

urlpatterns = [
    path("",              RoomListCreateView.as_view()),
    path("<int:pk>/",     RoomDetailView.as_view()),
    path("<int:pk>/join/",  JoinRoomView.as_view()),
    path("<int:pk>/leave/", LeaveRoomView.as_view()),
]
