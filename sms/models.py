from django.db import models


class ProcessedSMSEvent(models.Model):
    """
    Idempotency log for inbound Twilio webhook events.

    Twilio guarantees at-least-once delivery — the same webhook POST can
    arrive more than once (network retries, Twilio-side retries on non-2xx,
    infra restarts mid-flight). We store the Twilio MessageSid here so we
    can detect and skip duplicates.

    Retention: rows older than SMS_IDEMPOTENCY_TTL seconds can be pruned
    by a periodic cleanup task (e.g. a cron or Celery beat job).
    """

    message_sid  = models.CharField(max_length=64, unique=True, db_index=True)
    from_number  = models.CharField(max_length=20)
    to_number    = models.CharField(max_length=20)
    body         = models.TextField()
    received_at  = models.DateTimeField(auto_now_add=True)

    # Outcome tracking — useful for reprocessing failed events
    class Status(models.TextChoices):
        PROCESSED = "processed", "Processed"
        FAILED    = "failed",    "Failed"
        SKIPPED   = "skipped",   "Skipped"   # e.g. sender not a member

    status       = models.CharField(max_length=16, choices=Status.choices, default=Status.PROCESSED)
    failure_reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.message_sid} [{self.status}]"
