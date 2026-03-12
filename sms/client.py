from __future__ import annotations
from django.conf import settings


class TwilioSMSClient:
    """
    Thin wrapper around the Twilio REST client.
    Inject a mock of this class in tests — never call Twilio directly from business logic.
    """

    def __init__(self):
        from twilio.rest import Client
        self._client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    def provision_number(self) -> str:
        """
        Purchase an available local US number and configure its inbound webhook.
        Returns the provisioned E.164 phone number string.
        """
        available = (
            self._client.available_phone_numbers("US")
            .local.list(sms_enabled=True, limit=1)
        )
        if not available:
            raise RuntimeError("No available Twilio numbers to provision.")

        purchased = self._client.incoming_phone_numbers.create(
            phone_number=available[0].phone_number,
            sms_url=settings.TWILIO_WEBHOOK_URL,
            sms_method="POST",
        )
        return purchased.phone_number

    def release_number(self, twilio_number: str) -> None:
        """Release a number back to Twilio (call when a room is deleted)."""
        numbers = self._client.incoming_phone_numbers.list(phone_number=twilio_number)
        for n in numbers:
            n.delete()

    def send(self, *, from_number: str, to: str, body: str) -> str:
        """
        Send an SMS. Returns the Twilio message SID.
        Keyword-only args prevent accidental argument transposition.
        """
        msg = self._client.messages.create(
            to=to,
            from_=from_number,
            body=body,
        )
        return msg.sid


class StubSMSClient:
    """
    Drop-in stub for local development and tests.
    Prints to stdout instead of hitting Twilio.
    """

    _counter = 0

    def provision_number(self) -> str:
        StubSMSClient._counter += 1
        number = f"+1555000{StubSMSClient._counter:04d}"
        print(f"[STUB] Provisioned number: {number}")
        return number

    def release_number(self, twilio_number: str) -> None:
        print(f"[STUB] Released number: {twilio_number}")

    def send(self, *, from_number: str, to: str, body: str) -> str:
        sid = f"STUB_{id(body):x}"
        print(f"[STUB] SMS from={from_number} to={to}: {body!r}  (sid={sid})")
        return sid


def get_sms_client() -> TwilioSMSClient | StubSMSClient:
    """
    Factory: returns the real Twilio client in production,
    the stub when DEBUG=True or TWILIO_ACCOUNT_SID is not set.
    """
    from django.conf import settings
    if settings.DEBUG or not settings.TWILIO_ACCOUNT_SID.startswith("AC"):
        return StubSMSClient()
    return TwilioSMSClient()
