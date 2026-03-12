from django.conf import settings
from django.db import transaction
from django.utils import timezone
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
            client = get_sms_client()
            try:
                twilio_number = client.provision_number()
                room.twilio_number = twilio_number
                room.save(update_fields=["twilio_number"])
            except Exception as e:
                raise e

        return Response(RoomSerializer(room).data, status=status.HTTP_201_CREATED)


class RoomDetailView(APIView):
    def get(self, request, pk):
        try:
            room = Room.objects.get(pk=pk)
        except Room.DoesNotExist:
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

        current_room_count = len(user.memberships.all())
        if current_room_count >= settings.MAX_ROOMS_PER_USER:
            return Response(
                {"error": f"Users may not join more than {settings.MAX_ROOMS_PER_USER} rooms."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership, created = Membership.objects.get_or_create(user=user, room=room)
        if not created:
            return Response({"error": "Already a member."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            send_welcome(user=user, room=room)
        except Exception as e:
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


class RoomFeedView(APIView):
    """
    GET  /api/rooms/:id/feed/?after=<id>
         Returns ProcessedSMSEvents for this room (inbound SMS messages),
         ordered oldest-first. Pass ?after=<id> to poll only new events.

    POST /api/rooms/:id/feed/
         Web UI test harness: send a message as a given user without
         needing a real phone. Runs through broadcast_message() — the
         same path the inbound SMS webhook uses — so the full send
         pipeline is exercised. No extra persistence needed.
    """

    def get(self, request, pk):
        try:
            room = Room.objects.get(pk=pk)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        from sms.models import ProcessedSMSEvent
        events = ProcessedSMSEvent.objects.filter(
            to_number=room.twilio_number
        ).order_by("received_at")

        after = request.query_params.get("after")
        if after:
            events = events.filter(id__gt=after)

        data = [
            {
                "id":          e.id,
                "from_number": e.from_number,
                "body":        e.body,
                "status":      e.status,
                "received_at": e.received_at,
                # Resolve sender name if we know the number
                "sender_name": _resolve_name(e.from_number),
            }
            for e in events
        ]
        return Response(data)

    def post(self, request, pk):
        user_id = request.data.get("user_id")
        body    = request.data.get("body", "").strip()

        if not user_id or not body:
            return Response({"error": "user_id and body required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            room = Room.objects.get(pk=pk)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            sender = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if not room.memberships.filter(user=sender).exists():
            return Response({"error": "User is not a member of this room."}, status=status.HTTP_403_FORBIDDEN)

        # Write a ProcessedSMSEvent so the feed picks it up, just like a real inbound SMS would.
        # Use a synthetic sid so idempotency logic is satisfied.
        import uuid
        from sms.models import ProcessedSMSEvent
        ProcessedSMSEvent.objects.create(
            message_sid  = f"WEB_{uuid.uuid4().hex}",
            from_number  = sender.phone_number,
            to_number    = room.twilio_number or "web",
            body         = body,
            status       = ProcessedSMSEvent.Status.PROCESSED,
        )

        # Broadcast through the same service the webhook calls
        try:
            broadcast_message(sender=sender, room=room, body=body)
        except Exception as e:
            print(f"[WARN] Broadcast failed (SMS may be unconfigured): {e}")

        return Response({"ok": True}, status=status.HTTP_201_CREATED)


def _resolve_name(phone_number: str) -> str:
    """Best-effort: look up user name by phone number for display."""
    try:
        return User.objects.get(phone_number=phone_number).name
    except User.DoesNotExist:
        return phone_number
