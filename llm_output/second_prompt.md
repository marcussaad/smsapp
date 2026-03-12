Here's the full cost breakdown per room:

### Fixed Cost (per room/month)
A standard local US number runs **$1.15/month** per room. That's your baseline — one number provisioned at room creation, billed monthly regardless of activity.

### Variable Costs (per message)
SMS in the US is **$0.0083 per message** sent or received. So every broadcast multiplies that cost — if a room has 10 members and someone sends a message, that's 9 outbound SMS at $0.0083 each = ~$0.075 per message sent.

### What this looks like at scale

| Rooms | Fixed/month | + message volume |
|---|---|---|
| 10 rooms | ~$11.50 | + per-message costs |
| 100 rooms | ~$115 | + per-message costs |
| 1,000 rooms | ~$1,150 | + per-message costs |

### Hidden costs worth flagging in the debrief
Twilio also passes carrier surcharges directly to you, which vary by carrier and aren't always visible upfront. There's also the A2P 10DLC registration requirement for business SMS in the US, which adds a one-time brand registration fee on top.

### Bottom line for the debrief
The per-room number cost is negligible at small scale, but the **broadcast multiplication effect on SMS costs** is the real scaling concern — a busy room with 50 members gets expensive fast. That's a natural talking point for why you might revisit the architecture (e.g. switching to app-based delivery for active users, only falling back to SMS for offline ones).