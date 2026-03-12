from unittest.mock import MagicMock, patch

from django.test import TestCase, RequestFactory

from rooms.models import Room, Membership
from rooms.views import RoomFeedView
from sms.models import ProcessedSMSEvent
from users.models import User


def _feed_url(pk):
    return f"/api/rooms/{pk}/feed/"


class RoomFeedGetTest(TestCase):
    """GET /api/rooms/:id/feed/ — polls ProcessedSMSEvent for the room."""

    def setUp(self):
        self.factory = RequestFactory()
        self.alice   = User.objects.create(name="Alice", phone_number="+15550001111")
        self.bob     = User.objects.create(name="Bob",   phone_number="+15550002222")
        self.room    = Room.objects.create(name="Feed Room", twilio_number="+15559990000")
        Membership.objects.create(user=self.alice, room=self.room)
        Membership.objects.create(user=self.bob,   room=self.room)

    def _get(self, params=""):
        req = self.factory.get(_feed_url(self.room.pk) + params)
        return RoomFeedView.as_view()(req, pk=self.room.pk)

    def _make_event(self, sid, from_number, body):
        return ProcessedSMSEvent.objects.create(
            message_sid=sid,
            from_number=from_number,
            to_number=self.room.twilio_number,
            body=body,
        )

    def test_returns_events_for_room(self):
        self._make_event("SM001", self.alice.phone_number, "Hello!")
        self._make_event("SM002", self.bob.phone_number,   "Hey!")
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    def test_does_not_return_events_for_other_rooms(self):
        other_room = Room.objects.create(name="Other", twilio_number="+15559990099")
        ProcessedSMSEvent.objects.create(
            message_sid="SM_OTHER", from_number="+15550009999",
            to_number=other_room.twilio_number, body="not for this room"
        )
        self._make_event("SM001", self.alice.phone_number, "Hello!")
        resp = self._get()
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["body"], "Hello!")

    def test_after_param_returns_only_newer_events(self):
        e1 = self._make_event("SM001", self.alice.phone_number, "First")
        e2 = self._make_event("SM002", self.bob.phone_number,   "Second")
        resp = self._get(f"?after={e1.id}")
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["body"], "Second")

    def test_sender_name_resolved(self):
        self._make_event("SM001", self.alice.phone_number, "Hi")
        resp = self._get()
        self.assertEqual(resp.data[0]["sender_name"], "Alice")

    def test_unknown_number_falls_back_to_phone(self):
        self._make_event("SM001", "+19999999999", "Hi")
        resp = self._get()
        self.assertEqual(resp.data[0]["sender_name"], "+19999999999")

    def test_room_not_found_returns_404(self):
        req  = self.factory.get("/api/rooms/9999/feed/")
        resp = RoomFeedView.as_view()(req, pk=9999)
        self.assertEqual(resp.status_code, 404)


class RoomFeedPostTest(TestCase):
    """POST /api/rooms/:id/feed/ — web UI send, exercises the broadcast path."""

    def setUp(self):
        self.factory = RequestFactory()
        self.alice   = User.objects.create(name="Alice", phone_number="+15550001111")
        self.bob     = User.objects.create(name="Bob",   phone_number="+15550002222")
        self.room    = Room.objects.create(name="Send Room", twilio_number="+15559990000")
        Membership.objects.create(user=self.alice, room=self.room)
        Membership.objects.create(user=self.bob,   room=self.room)

    def _post(self, data):
        req = self.factory.post(_feed_url(self.room.pk), data, content_type="application/json")
        return RoomFeedView.as_view()(req, pk=self.room.pk)

    @patch("rooms.views.broadcast_message")
    def test_creates_processed_sms_event(self, mock_broadcast):
        resp = self._post({"user_id": self.alice.id, "body": "Hello from web"})
        self.assertEqual(resp.status_code, 201)
        event = ProcessedSMSEvent.objects.get(from_number=self.alice.phone_number)
        self.assertEqual(event.body, "Hello from web")
        self.assertTrue(event.message_sid.startswith("WEB_"))

    @patch("rooms.views.broadcast_message")
    def test_calls_broadcast_message(self, mock_broadcast):
        """Confirms the web send goes through the same service as the SMS webhook."""
        self._post({"user_id": self.alice.id, "body": "Test broadcast"})
        mock_broadcast.assert_called_once_with(
            sender=self.alice, room=self.room, body="Test broadcast"
        )

    @patch("rooms.views.broadcast_message")
    def test_event_appears_in_feed(self, mock_broadcast):
        """Round-trip: send via POST, confirm it shows up in GET."""
        self._post({"user_id": self.alice.id, "body": "Round trip"})
        req  = self.factory.get(_feed_url(self.room.pk))
        resp = RoomFeedView.as_view()(req, pk=self.room.pk)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["body"], "Round trip")

    @patch("rooms.views.broadcast_message")
    def test_non_member_cannot_send(self, mock_broadcast):
        outsider = User.objects.create(name="Eve", phone_number="+15550003333")
        resp = self._post({"user_id": outsider.id, "body": "Sneaky"})
        self.assertEqual(resp.status_code, 403)
        mock_broadcast.assert_not_called()

    @patch("rooms.views.broadcast_message")
    def test_missing_body_returns_400(self, mock_broadcast):
        resp = self._post({"user_id": self.alice.id, "body": ""})
        self.assertEqual(resp.status_code, 400)

    @patch("rooms.views.broadcast_message")
    def test_broadcast_failure_does_not_500(self, mock_broadcast):
        """Broadcast errors are swallowed — SMS being unconfigured shouldn't break the UI."""
        mock_broadcast.side_effect = RuntimeError("Twilio down")
        resp = self._post({"user_id": self.alice.id, "body": "Still works"})
        self.assertEqual(resp.status_code, 201)
