**Idempotency layer** (`sms/models.py` + `sms/views.py`) — the key design decisions:
- `ProcessedSMSEvent` table uses Twilio's `MessageSid` as a unique key
- Inbound webhook does an atomic `INSERT` — if it fails with `IntegrityError`, it's a duplicate and we return `200` immediately (so Twilio stops retrying)
- Failed broadcasts are marked `status=FAILED` rather than returning a non-2xx, which would cause Twilio to flood with retries. A separate Celery beat job can query `status='failed'` and reprocess them safely
- Multiple Django workers are safe — the DB unique constraint is the single source of truth, no Redis lock needed

**Tests** cover: first event processed, duplicate ignored, unknown sender skipped, broadcast failure marking, and sender exclusion from broadcast.
