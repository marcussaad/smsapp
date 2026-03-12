import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from twilio.request_validator import RequestValidator

from rooms.models import Room, Membership
from users.models import User
from sms.models import ProcessedSMSEvent
from sms.service import broadcast_message

logger = logging.getLogger(__name__)


def _validate_twilio_signature(request) -> bool:
    """
    Verify the request genuinely came from Twilio.
    Uses HMAC-SHA1 over the full callback URL + sorted POST params.
    See: https://www.twilio.com/docs/usage/webhooks/webhooks-security
    """
    validator  = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    url        = settings.TWILIO_WEBHOOK_URL
    post_vars  = request.POST.dict()
    signature  = request.META.get("HTTP_X_TWILIO_SIGNATURE", "")
    return validator.validate(url, post_vars, signature)


@csrf_exempt
@require_POST
def inbound_sms(request):
    """
    Twilio posts here when a user texts a room's number.

    Idempotency strategy:
    - Use Twilio's MessageSid as a natural idempotency key.
    - Attempt INSERT into ProcessedSMSEvent inside a transaction.
    - If INSERT fails (duplicate key), the event was already handled → return 200.
    - On any processing error, mark the event as FAILED so it can be reprocessed
      by an operator or an async retry job without re-querying Twilio.

    Redundancy / reprocessing notes:
    - Twilio retries delivery if we return non-2xx. Always return 200 after
      recording the event, even on business-logic errors, to prevent Twilio
      flooding us with retries for unrecoverable cases (e.g. unknown sender).
    - For recoverable failures (downstream SMS send errors), mark status=FAILED.
      A periodic Celery beat task can query ProcessedSMSEvent.objects.filter(
      status='failed') and replay them.
    - If running multiple Django workers/pods, the unique DB constraint on
      message_sid is the single source of truth — no Redis lock needed.
    """
    # ── 1. Authenticate ────────────────────────────────────────────────────────
    if not settings.DEBUG and not _validate_twilio_signature(request):
        logger.warning("Rejected webhook: invalid Twilio signature.")
        return HttpResponse(status=403)

    # ── 2. Extract fields ──────────────────────────────────────────────────────
    message_sid  = request.POST.get("MessageSid", "")
    from_number  = request.POST.get("From", "")
    to_number    = request.POST.get("To", "")
    body         = request.POST.get("Body", "").strip()

    if not all([message_sid, from_number, to_number]):
        logger.error("Inbound SMS missing required fields.")
        return HttpResponse(status=400)

    # ── 3. Idempotency check (atomic INSERT) ───────────────────────────────────
    try:
        with transaction.atomic():
            event = ProcessedSMSEvent.objects.create(
                message_sid=message_sid,
                from_number=from_number,
                to_number=to_number,
                body=body,
                status=ProcessedSMSEvent.Status.PROCESSED,
            )
    except IntegrityError:
        # Duplicate MessageSid — already processed, return 200 so Twilio stops retrying
        logger.info(f"Duplicate inbound SMS ignored: {message_sid}")
        return HttpResponse(status=200)

    # ── 4. Route to room ───────────────────────────────────────────────────────
    try:
        room = Room.objects.get(twilio_number=to_number)
    except Room.DoesNotExist:
        _mark_failed(event, f"No room found for number {to_number}")
        return HttpResponse(status=200)

    try:
        sender = User.objects.get(phone_number=from_number)
    except User.DoesNotExist:
        _mark_skipped(event, f"Unknown sender {from_number}")
        return HttpResponse(status=200)

    # ── 5. Verify membership ───────────────────────────────────────────────────
    if not Membership.objects.filter(user=sender, room=room).exists():
        _mark_skipped(event, f"{sender.phone_number} is not a member of room {room.id}")
        return HttpResponse(status=200)

    # ── 6. Broadcast ───────────────────────────────────────────────────────────
    try:
        sids = broadcast_message(sender=sender, room=room, body=body)
        logger.info(f"Broadcast {len(sids)} messages for event {message_sid}")
    except Exception as exc:
        # Mark FAILED so a retry job can reprocess without re-validating Twilio sig
        _mark_failed(event, str(exc))
        logger.exception(f"Broadcast failed for event {message_sid}: {exc}")
        # Still return 200 — Twilio retrying won't help with a downstream send error

    return HttpResponse(status=200)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mark_failed(event: ProcessedSMSEvent, reason: str) -> None:
    event.status         = ProcessedSMSEvent.Status.FAILED
    event.failure_reason = reason
    event.save(update_fields=["status", "failure_reason"])
    logger.warning(f"SMS event {event.message_sid} marked FAILED: {reason}")


def _mark_skipped(event: ProcessedSMSEvent, reason: str) -> None:
    event.status         = ProcessedSMSEvent.Status.SKIPPED
    event.failure_reason = reason
    event.save(update_fields=["status", "failure_reason"])
    logger.info(f"SMS event {event.message_sid} marked SKIPPED: {reason}")
