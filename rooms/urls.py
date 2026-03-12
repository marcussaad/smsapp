from django.urls import path
from .views import RoomListCreateView, RoomDetailView, JoinRoomView, LeaveRoomView, RoomFeedView

urlpatterns = [
    path("",                    RoomListCreateView.as_view()),
    path("<int:pk>/",           RoomDetailView.as_view()),
    path("<int:pk>/join/",      JoinRoomView.as_view()),
    path("<int:pk>/leave/",     LeaveRoomView.as_view()),
    path("<int:pk>/feed/",      RoomFeedView.as_view()),
]
