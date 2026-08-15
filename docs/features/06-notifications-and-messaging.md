# Feature 6 — Notifications, Messaging & Risk Alerts

| | |
|---|---|
| **Service** | `service-notification/` — Node, Express 5.2, Mongoose 9.6, Socket.IO 4.8 (declared), port 8004 |
| **Database** | MongoDB `notification_base` |
| **Public prefix** | `/notifications` (gateway → `lb://SERVICE-NOTIFICATION`) |
| **Eureka name** | `SERVICE-NOTIFICATION` |

## What it does

Three sub-features in one service:

1. **Direct messaging** — one-to-one conversations between users, with read tracking.
2. **Notifications** — a per-user notification feed (unread counts, mark-as-read).
3. **Risk alerts** — ingestion and management of contract risk alerts pushed by service_clm.

## Data model

| Model | Fields (essence) |
|---|---|
| `Conversation` | participants (user ids from feature 1), `lastMessageAt` |
| `Message` | `conversationId`, `senderId` / `senderRole` / `senderName`, `content`, `readBy[]` (`userId` + `readAt`) |
| `RiskAlert` | `contrat_id`, risk type/severity/description, `statut` (workflow; `resolu` stamps `resolved_at`) |

**There is no `Notification` collection** — the notification feed is *synthesized* by the controller from unread messages and alerts at read time. "Deleting" or "marking read" manipulates the underlying message/alert state.

## Endpoint reference

### Messaging — `/notifications/…` (JWT required)

| Method | Path | Purpose |
|---|---|---|
| POST | `/notifications/conversations/direct` | create/open a direct conversation |
| GET | `/notifications/conversations` | list my conversations |
| GET | `/notifications/conversations/:conversationId` | conversation detail |
| POST | `/notifications/messages` | send a message |
| GET | `/notifications/messages/:conversationId` | messages of a conversation |
| PUT | `/notifications/messages/:messageId` | edit a message |
| DELETE | `/notifications/messages/:messageId` | delete a message |
| PUT | `/notifications/messages/conversation/:conversationId/read` | mark a whole conversation read |

### Notification feed — `/notifications/…` (JWT required)

| Method | Path | Purpose |
|---|---|---|
| GET | `/notifications/` | my notifications (synthesized) |
| GET | `/notifications/all` | all notifications |
| GET | `/notifications/unread/count` | unread badge count |
| PUT | `/notifications/:id/read` | mark one read |
| PUT | `/notifications/read-all` | mark all read |
| DELETE | `/notifications/:id` | remove one |
| GET | `/notifications/users` | user directory for starting conversations |

### Risk alerts — `/notifications/risk-alerts/…` (⚠ **no auth**)

| Method | Path | Purpose |
|---|---|---|
| POST | `/notifications/risk-alerts/` | **ingestion endpoint used by service_clm** |
| GET | `/notifications/risk-alerts/` | list alerts |
| GET | `/notifications/risk-alerts/summary/:contrat_id` | per-contract summary |
| GET | `/notifications/risk-alerts/:id` | alert detail |
| PATCH | `/notifications/risk-alerts/:id` | update workflow status (`resolu` sets `resolved_at`) |

## Real-time status (important)

Socket.IO is a declared dependency and a complete handler exists in `socket/socketHandler.js` — token handshake, per-user rooms (`user_<id>`), per-role rooms (`role_<role>`), a `send_message` flow. **But `server.js` never attaches it to the HTTP server**, so as deployed the feature is **REST/polling only**. Activating it requires:

1. Wiring `socket.io` + the handler into `server.js`.
2. Fixing the handshake's user-verification call — it targets gateway `/api/verify-token/`, a route that does not exist (the working equivalent is `/auth/all_users/<id>/` or a new verify endpoint).
3. Exposing `/socket.io/` at the edge — the nginx block in [../deployment/08-nginx-and-https.md](../deployment/08-nginx-and-https.md) is already prepared; the gateway does not route it.

## Known limitations

- **`/notifications/risk-alerts` is fully unauthenticated** — mounted before the auth middleware. Anyone reaching the gateway can create, read, or resolve alerts. Intended caller is service_clm only; add service-to-service auth before production (deployment gap G-7).
- No pagination guarantees on feed/list endpoints — large histories degrade.
- Notification identity is synthetic (derived ids) — clients should treat the feed as a projection, not a stable collection.
