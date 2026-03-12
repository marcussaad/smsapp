## Technical Architecture — Group SMS Chat (Django)

---

### Stack
- **Django + Django REST Framework** — API layer
- **SQLite** (dev) / **PostgreSQL** (prod) — relational DB fits the data model perfectly
- **Twilio Python SDK** — stubbed/mocked (no real account needed)
- **ngrok** — expose local webhook for Twilio inbound SMS (dev only)

---

### Data Model

```
User
├── id
├── name
├── phone_number (unique)
└── created_at

Room
├── id
├── name
└── created_at

Membership          ← join table
├── user_id (FK)
├── room_id (FK)
└── joined_at
```

**Key constraint:** enforce a max memberships per user (e.g. 10 rooms) at the model/serializer level.

---

### App Structure

```
groupsms/
├── manage.py
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── users/
│   ├── models.py        # User model
│   ├── serializers.py
│   └── views.py         # create user
├── rooms/
│   ├── models.py        # Room + Membership models
│   ├── serializers.py
│   └── views.py         # CRUD + join/leave
└── sms/
    ├── client.py        # Twilio SDK wrapper (easy to mock)
    ├── views.py         # /sms/inbound webhook (POST from Twilio)
    └── tests.py
```

Keeping `sms/` isolated means the Twilio integration is swappable and independently testable.

---

### API Endpoints

| Method | Route | Action |
|---|---|---|
| POST | `/api/users/` | Create user (name + phone) |
| GET | `/api/rooms/?q=` | Search rooms by name |
| POST | `/api/rooms/` | Create a room |
| POST | `/api/rooms/:id/join/` | Join a room → triggers welcome SMS |
| DELETE | `/api/rooms/:id/leave/` | Leave a room |
| POST | `/sms/inbound/` | Twilio webhook — receives texts |

---

### SMS Flows

**On join** → `sms/client.py` sends:
> *"Welcome to [Room]! Reply to this number to message the group."*

**Inbound text** (Twilio POSTs to `/sms/inbound/`):
1. Look up user by `From` phone number
2. Identify their active room (see routing note below)
3. Broadcast to all other room members:
> *"[Name]: message text"*

**Security:** validate Twilio's `X-Twilio-Signature` header on every inbound POST.

---

### ⚠️ Multi-Room Routing

When a user is in multiple rooms, which room does their inbound SMS go to?

**Recommended MVP approach:** last-joined room. Simple, defensible in the debrief, easy to implement with `Membership.joined_at`.

A production solution would assign a unique Twilio number per room — worth mentioning in the debrief even if you don't build it.

---

### Twilio Client Wrapper (stub pattern)

```python
# sms/client.py
from django.conf import settings

class TwilioClient:
    def __init__(self):
        from twilio.rest import Client
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.from_number = settings.TWILIO_PHONE_NUMBER

    def send(self, to: str, body: str):
        self.client.messages.create(to=to, from_=self.from_number, body=body)
```

In tests, swap this with a mock — nothing ever actually calls Twilio.

---

### Key Debrief Talking Points
- Why SQLite → Postgres is a trivial swap with Django's ORM
- Multi-room routing trade-offs (last-joined vs. per-room numbers)
- How you'd add message persistence (a `Message` model) as a next step
- Twilio signature validation as the security boundary

---

Want me to go deeper on anything — the Twilio webhook view, the serializers, or how to structure the tests?