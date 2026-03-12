from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from users.models import User
from .models import Room, Membership
from .serializers import RoomSerializer, MembershipSerializer
from sms.client import get_sms_client
from sms.service import send_welcome, broadcast_message


class RoomListCreateView(APIView):
    def get(self, request):
        q = request.query_params.get("q", "").strip()
        rooms = Room.objects.all().order_by("-created_at")
        if q:
            rooms = rooms.filter(name__icontains=q)
        return Response(RoomSerializer(rooms, many=True).data)

    def post(self, request):
        serializer = RoomSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            room = serializer.save()
            # Provision a Twilio number for this room
            client = get_sms_client()
            try:
                twilio_number = client.provision_number()
                room.twilio_number = twilio_number
                room.save(update_fields=["twilio_number"])
            except Exception as e:
                # Roll back room creation if provisioning fails
                raise e

        return Response(RoomSerializer(room).data, status=status.HTTP_201_CREATED)


class RoomDetailView(APIView):
    def get_room(self, pk):
        try:
            return Room.objects.get(pk=pk)
        except Room.DoesNotExist:
            return None

    def get(self, request, pk):
        room = self.get_room(pk)
        if not room:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)
        members = room.memberships.select_related("user").all()
        return Response({
            "room": RoomSerializer(room).data,
            "members": MembershipSerializer(members, many=True).data,
        })


class JoinRoomView(APIView):
    def post(self, request, pk):
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"error": "user_id required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.filter(pk=user_id).prefetch_related("memberships").first()
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            room = Room.objects.get(pk=pk)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        # Enforce max rooms per user
        current_room_count = len(user.memberships.all())
        if current_room_count >= settings.MAX_ROOMS_PER_USER:
            return Response(
                {"error": f"Users may not join more than {settings.MAX_ROOMS_PER_USER} rooms."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership, created = Membership.objects.get_or_create(user=user, room=room)
        if not created:
            return Response({"error": "Already a member."}, status=status.HTTP_400_BAD_REQUEST)

        # Send welcome SMS (non-blocking failure: log but don't 500)
        try:
            send_welcome(user=user, room=room)
        except Exception as e:
            # In production: emit to error tracker (Sentry, etc.)
            print(f"[WARN] Failed to send welcome SMS to {user.phone_number}: {e}")

        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class LeaveRoomView(APIView):
    def delete(self, request, pk):
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"error": "user_id required."}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = Membership.objects.filter(user_id=user_id, room_id=pk).delete()
        if not deleted:
            return Response({"error": "Membership not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_204_NO_CONTENT)
