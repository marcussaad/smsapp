# GroupSMS

GroupMe-style group SMS chat. Users join rooms via a web UI; messages are sent and received entirely over SMS via Twilio.

## Stack

- **Django 4.2** + Django REST Framework
- **PostgreSQL** (prod) / SQLite (local)
- **Twilio** — one phone number provisioned per room
- **Railway** — hosting + managed Postgres
- **Gunicorn** + WhiteNoise — production serving

## Local Development

```bash
# 1. Clone and install
git clone <your-repo-url>
cd groupsms
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — at minimum set DJANGO_SECRET_KEY

# 3. Run migrations and start
python manage.py migrate
python manage.py runserver
```

Open `frontend.html` directly in your browser — it points to `http://localhost:8000` by default.

For inbound SMS locally, expose your server with [ngrok](https://ngrok.com):
```bash
ngrok http 8000
# Set TWILIO_WEBHOOK_URL=https://<your-ngrok-id>.ngrok.io/sms/inbound/ in .env
```

## Deploy to Railway

### 1. Create the project

```bash
# Install Railway CLI
npm install -g @railway/cli

railway login
railway init        # creates a new project
railway up          # first deploy
```

### 2. Add Postgres

In the Railway dashboard → your project → **+ New** → **Database** → **PostgreSQL**.  
Railway automatically injects `DATABASE_URL` into your app — no extra config needed.

### 3. Set environment variables

In Railway dashboard → your service → **Variables**, add:

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | a long random string |
| `DEBUG` | `false` |
| `ALLOWED_HOSTS` | `yourapp.railway.app` |
| `TWILIO_ACCOUNT_SID` | from Twilio console |
| `TWILIO_AUTH_TOKEN` | from Twilio console |
| `TWILIO_WEBHOOK_URL` | `https://yourapp.railway.app/sms/inbound/` |

### 4. Update Twilio webhook

In the [Twilio console](https://console.twilio.com) → Phone Numbers → set the webhook URL on each provisioned number to match `TWILIO_WEBHOOK_URL` above.

### 5. Migrations

The `Procfile` runs `python manage.py migrate` automatically on every deploy via the `release` phase.

## Project Structure

```
groupsms/
├── config/         # Django settings, URLs, WSGI
├── users/          # User model + API
├── rooms/          # Room + Membership models + API
├── sms/            # Twilio client, inbound webhook, idempotency
├── frontend.html   # Single-file UI
├── Procfile        # Railway/Heroku process config
├── runtime.txt     # Python version pin
└── requirements.txt
```

## Key Design Decisions

- **One Twilio number per room** — eliminates multi-room routing ambiguity entirely
- **Idempotent webhook** — `ProcessedSMSEvent` table uses Twilio's `MessageSid` as a unique key; duplicate webhook deliveries are safely ignored via atomic INSERT + IntegrityError catch
- **Stub SMS client** — `StubSMSClient` used when `DEBUG=true`; no real Twilio calls during local dev or tests
- **Failed events are replayable** — broadcast failures mark the event `status=failed` rather than returning non-2xx (which would cause Twilio retry floods); a Celery beat job can reprocess them
