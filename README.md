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

Live at https://web-production-10a0.up.railway.app/

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


## How this project was built

- Claude Code was leveraged using Sonnet 4.6 Extended thinking (free tier)
- List of prompts that generated the initial skeleton:
    - **Prompt**: You are a software architect that is tasked with building a prototype. The instructions are as follows, take your time to evaluate requirements, plan and prioritize. The ideal outcome is a list of priorities, with explanations about models, architectural decisions and trade offs. <pasted requirements from github>
    - **Output**: [Initial Architecture & Requirements Analysis](./first_prompt.md)

    - **Prompt**: Thanks for bringing up the twillio cost per room. Can you dive deeper into what that cost would look like in order to help me understand what would be the cost to operate rooms with different amount of people?
    - **Output**: [Twillio Cost](./second_prompt.md)

    - **Prompt**: We'll likely need to think about redundancies in the ingestion layer and how to idempotently consume / reprocess events, so let's think about that in the webhook ingestion layer. 
    - **Output**: [Twillio Cost](./third_prompt.md)

    - **Prompt**: I want to host this application with a minimal frontend to interact with these APIs in a way that does not require an active twillio account, but if one were to be configured, it should work too. Can you output the code for this app, including the frontend in a way that it all can be hosted in Railway?
        - This one was less straightforward and had multiple interactions. Had to fix a few deployment files, LLM confused heroku with railway config files, had to update a few URL paths and env variables, but overall a lot less painful than it was in the past.


- After the whole app was running, I took the time to manually comment in places that I see problems with the LLM output, which would've been addressed pre-merge in a real life scenario. I did not feed its output back to another model for code review. For this exercise, I tried building the app as a mix of seasoned engineer but with limited tools (Using windows 11, no terminal, just claude web and VSCode freshly installed as my editor).



## Technical Observations to chat

 - Decoupling Webhook ingestion from whole app (django is heavy, we don't need to spin the whole app up only to have the webhook ingestion pipeline.)
    - Horizontally spread ingestion behind a load balancer so that we can autoscale based on req/s
    - Twillio guarantees at least once deliver, we should guarantee at most once with our idempotency approach
        - Order of messages received is important
 - Inserting thousands of row quickly in the DB would be a challenge due to index contention + read/write traffic at scale.
    - Reader / Writer instance
    - Idempotency check with redis instead of DB storage, 24h TTL
    - Partition table by time (last 24 hours or <retry_window>), smaller B-Tree index to query through.
    - Leverage celery tasks to process work async. Twilio POST → Django view → push to queue → return 200 immediately → Celery worker → idempotency check → broadcast (eventual consistency)
 - Cost to operate rooms can be pretty high, so limiting number of members would be ideal too.
 - Not only cost, but API limit would quickly be a problem in a room with 100+ people and lots of volume of messages. We'll need to handle send events to a queue (to guarantee order), try to batch messages in order to avoid API limits, implement retries and exponential backoff. Perhaps defining a reasonable delay of time to try and batch messages on a given room would also be helpful.
 - Phone number provisioning is sync and slow, a background job could be tasked with keeping a buffer of <N> numbers available at all times.
 - Currently there's no rate limiting in the amount of messages a room can send within a given period of time, we should also address this.
 - Polling approach isn't scalable. Either use websocket or pub/sub (appsync in aws).


 If this were going to production, the order I'd address these:
- Make number provisioning async — user-facing latency improvement
- Add room member cap — cost and safety guardrail
- Move broadcast fan-out to Celery — unblocks the webhook under load
- Add read replica — separates read/write contention
- Replace polling with options described — the right long-term architecture
- CI/CD, test coverage
