# Frontend Guide — Connecting to the Production Backend

> Once connected, build the screens against [FRONTEND_FEATURES.md](FRONTEND_FEATURES.md) — the per-role screen map with exact endpoint contracts for every feature.

Audience: the frontend team. You were pointed at a locally-running backend; the backend now runs on a VPS behind nginx + HTTPS. **The only change you need is the base URL — every path, body, and header stays the same.**

## 1. Base URL

| | Before (local) | Now (production) |
|---|---|---|
| API base URL | `http://localhost:8083` | **`https://lexora.duckdns.org`** |

All service prefixes hang directly off that base (no `/api` segment, no port):

| Prefix | Service |
|---|---|
| `/auth/**` | Authentication (Django) |
| `/affectation/**` | Assignments (Django) |
| `/clm/**` | Contracts / CLM (Django) |
| `/juridique/**` | Org structure (Node) |
| `/bib/**` | Legal document library (Node) |
| `/notifications/**` | Notifications, conversations, risk alerts (Node) |
| `/uploads/**` | Uploaded PDF files (public, no token needed) |

Put the base URL in an env var instead of hardcoding it:

```bash
# Vite
VITE_API_URL=https://lexora.duckdns.org
# CRA
REACT_APP_API_URL=https://lexora.duckdns.org
```

```js
const API = import.meta.env.VITE_API_URL; // or process.env.REACT_APP_API_URL
fetch(`${API}/auth/login/`, { ... })
```

Note: the site is HTTPS. If your frontend is also served over HTTPS (it should be), there are no mixed-content issues. Never call `http://` against this domain — you'll get redirected and POST bodies can be dropped on redirect.

## 2. ⚠ CORS — we need your origin

The backend only accepts browser requests from allow-listed origins (`allowCredentials` is on, so no wildcards). Currently only `localhost:3000` dev origins are listed.

**Send the backend team the exact production origin your app will be served from** (scheme + host, no trailing slash — e.g. `https://app.example.com`). Until it is added on the backend (5 config spots + service restarts), your deployed app's requests will fail with CORS errors even though the same calls work from curl/Postman. `localhost:3000` keeps working for your local dev against the production API in the meantime.

## 3. Authentication (unchanged, documented here for reference)

No cookies/sessions — pure JWT in a header.

**Login** — `POST /auth/login/` (trailing slash required; Django is strict about this on all `/auth`, `/affectation`, `/clm` routes):

```json
{ "email": "user@example.com", "password": "secret" }
```

Success `200`:

```json
{
  "status": "success",
  "message": "Logged in as Prenom Nom",
  "access": "<JWT>", "refresh": "<JWT>",
  "user_id": "3",
  "role": "agent",
  "nom_complet": "Prenom Nom",
  "photo_profil": null,
  "activite_id": null, "direction_id": null, "departement_id": null,
  "direction_centrale_id": null, "structure_id": null,
  "direction_activite_id": null, "division_activite_id": null,
  "activite_detail": null, "direction_detail": null, "departement_detail": null,
  "direction_centrale_detail": null, "direction_activite_detail": null,
  "division_activite_detail": null, "structure_detail": null
}
```

- `user_id` is a **string**. `*_detail` objects are resolved live from the org service and are `null` when the user has no assignment.
- Failure is `401` with `{"status":"error","message":"Email ou mot de passe incorrect."}` (same message for wrong email or wrong password); a deactivated account gets `"Compte désactivé. Contactez l'administrateur."`.
- **Take `role` and the ids from the login response, not from decoding the access token** — the access token only carries default claims (`user_id`, `exp`, …).

**Every authenticated call:**

```
Authorization: Bearer <access>
```

**Token lifetimes:** access **1 day**, refresh **1 day**. Refresh tokens rotate and are single-use (the old one is blacklisted when used).

**Refresh** — `POST /auth/token/refresh/` with `{"refresh": "<refresh>"}` → returns a new `access` **and** a new `refresh` (store both, the old refresh is now dead).

**Logout** — `POST /auth/logout/` (Bearer header + body `{"refresh": "<refresh>"}`) blacklists the refresh token.

**No self-signup.** Accounts are created by an admin via `POST /auth/users/create/` (admin token; requires `email`, `nom`, `prenom`; password is auto-generated, emailed to the user, and returned once in the response under `credentials.generated_password`).

**Roles** (exact strings, used in `role` everywhere): `admin`, `agent`, `vice_presedent` *(spelling is intentional)*, `directeur_direction`, `responsable_departement`, `directeur_centrale`, `assistant_directeur_centrale`, `directeur_direction_activite`, `directeur_division_activite`, `responsable_direction_division`, `responsable_departement_division`.

## 4. Uploads & files

- Library PDFs upload via `POST /bib/documents` (multipart, file field name **`pdf`**, PDF only, **max 20 MB**).
- Documents store a **relative** `pdfUrl` like `/uploads/1723980000000-123456789.pdf` — prepend the base URL: `https://lexora.duckdns.org/uploads/<filename>`. These file URLs are public (no token).
- Global request cap at the edge: 50 MB. Long operations (contract OCR on `/clm/contrats/upload/`) may take up to 300 s — set your HTTP client timeout accordingly for those calls.

## 5. Gotchas & current limitations

- **Socket.IO is NOT active** in production. `service-notification` is REST-only for now — poll `/notifications/**` endpoints; don't open a websocket.
- The general notification endpoints (`GET /notifications/`, `/notifications/all`, mark-read) currently return **stub data**. Real persistence exists for **conversations/messages** (`/notifications/conversations`, `/notifications/messages/...`, `/notifications/unread/count`) and **risk alerts** (`/notifications/risk-alerts/...`).
- `GET /notifications/users` is broken server-side — don't use it; list users via `GET /auth/all_users/public/` instead.
- One org-structure path contains a **deliberate typo that is live**: `/juridique/departemet_activite` (no "n"). Keep using it as-is.
- `GET https://lexora.duckdns.org/` returns 404 — normal, nothing is mounted at the root.
- Django endpoints need the **trailing slash** (`/auth/login/`, not `/auth/login`); Node endpoints (`/juridique`, `/bib`, `/notifications`) don't use one.

## 6. Quick smoke test (from your machine)

```bash
# login (ask the backend team for test credentials — see docs/SEED_TEST_DATA.md)
curl -s -X POST https://lexora.duckdns.org/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"<test-email>","password":"<test-password>"}'

# authenticated call with the "access" value from above
curl -s https://lexora.duckdns.org/juridique/directions \
  -H "Authorization: Bearer <access>"
```

If both answer with JSON, the backend is reachable and your remaining integration work is purely the base-URL + CORS items above.
