from unittest.mock import MagicMock, patch

from django.test import TestCase, RequestFactory

from rooms.models import Room, Membership
from sms.models import ProcessedSMSEvent
from sms.views import inbound_sms
from users.models import User


def _post_data(override=None):
    data = {
        "MessageSid":  "SM_test_001",
        "From":        "+15550001111",
        "To":          "+15559990000",
        "Body":        "Hello group!",
    }
    if override:
        data.update(override)
    return data


class InboundSMSIdempotencyTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user    = User.objects.create(name="Alice", phone_number="+15550001111")
        self.room    = Room.objects.create(name="Test Room", twilio_number="+15559990000")
        Membership.objects.create(user=self.user, room=self.room)

    def _post(self, data=None):
        req = self.factory.post("/sms/inbound/", data or _post_data())
        return inbound_sms(req)

    @patch("sms.views._validate_twilio_signature", return_value=True)
    @patch("sms.service.get_sms_client")
    def test_first_event_processed(self, mock_client_factory, _sig):
        mock_client_factory.return_value = MagicMock()
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ProcessedSMSEvent.objects.filter(message_sid="SM_test_001").count(), 1)

    @patch("sms.views._validate_twilio_signature", return_value=True)
    @patch("sms.service.get_sms_client")
    def test_duplicate_event_ignored(self, mock_client_factory, _sig):
        """Second POST with the same MessageSid must not broadcast again."""
        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client

        self._post()
        self._post()  # duplicate

        # broadcast called exactly once despite two webhook hits
        self.assertEqual(mock_client.send.call_count, 0)  # Alice is only member, no recipients
        self.assertEqual(ProcessedSMSEvent.objects.count(), 1)

    @patch("sms.views._validate_twilio_signature", return_value=True)
    @patch("sms.service.get_sms_client")
    def test_unknown_sender_skipped(self, mock_client_factory, _sig):
        mock_client_factory.return_value = MagicMock()
        resp = self._post(_post_data({"From": "+19999999999"}))
        self.assertEqual(resp.status_code, 200)
        event = ProcessedSMSEvent.objects.get(message_sid="SM_test_001")
        self.assertEqual(event.status, ProcessedSMSEvent.Status.SKIPPED)

    @patch("sms.views._validate_twilio_signature", return_value=True)
    @patch("sms.service.get_sms_client")
    def test_broadcast_failure_marks_event_failed(self, mock_client_factory, _sig):
        bob = User.objects.create(name="Bob", phone_number="+15550002222")
        Membership.objects.create(user=bob, room=self.room)

        mock_client         = MagicMock()
        mock_client.send.side_effect = RuntimeError("Twilio 500")
        mock_client_factory.return_value = mock_client

        resp  = self._post()
        event = ProcessedSMSEvent.objects.get(message_sid="SM_test_001")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(event.status, ProcessedSMSEvent.Status.FAILED)
        self.assertIn("Twilio 500", event.failure_reason)


class BroadcastTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.alice   = User.objects.create(name="Alice", phone_number="+15550001111")
        self.bob     = User.objects.create(name="Bob",   phone_number="+15550002222")
        self.carol   = User.objects.create(name="Carol", phone_number="+15550003333")
        self.room    = Room.objects.create(name="Broadcast Room", twilio_number="+15559990001")
        for u in [self.alice, self.bob, self.carol]:
            Membership.objects.create(user=u, room=self.room)

    @patch("sms.views._validate_twilio_signature", return_value=True)
    @patch("sms.service.get_sms_client")
    def test_sender_excluded_from_broadcast(self, mock_client_factory, _sig):
        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client

        data = _post_data({"To": "+15559990001"})
        req  = self.factory.post("/sms/inbound/", data)
        inbound_sms(req)

        calls = mock_client.send.call_args_list
        sent_to = [c.kwargs["to"] for c in calls]

        self.assertIn(self.bob.phone_number,   sent_to)
        self.assertIn(self.carol.phone_number, sent_to)
        self.assertNotIn(self.alice.phone_number, sent_to)
        self.assertEqual(len(sent_to), 2)
