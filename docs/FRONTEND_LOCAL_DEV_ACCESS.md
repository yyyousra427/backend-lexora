# Lexora API — running your frontend locally against the hosted backend

Audience: frontend developers who run the app on their own machine (`npm run dev`) and want it to talk to the real backend at `https://lexora.duckdns.org`. Nothing to install, nothing to ask for: any `localhost` port is already allowed.

For the full endpoint contracts see [FRONTEND_API_GUIDE.md](FRONTEND_API_GUIDE.md) and [FRONTEND_FEATURES.md](FRONTEND_FEATURES.md); this page is only about getting connected.

## 1. Point the app at the backend

| Setting | Value |
|---|---|
| API base URL | `https://lexora.duckdns.org` |
| Scheme | **HTTPS only.** `http://` answers a `301` redirect, and browsers refuse redirects on CORS preflights, so every call fails before it starts. |
| Port / `/api` prefix | None. Paths hang directly off the base: `/auth/login/`, `/juridique/directions`, … |

Put it in your tool's env file rather than in code:

```bash
# Vite            -> .env.local
VITE_API_URL=https://lexora.duckdns.org
# Create React App -> .env.local
REACT_APP_API_URL=https://lexora.duckdns.org
# Next.js          -> .env.local
NEXT_PUBLIC_API_URL=https://lexora.duckdns.org
```

```js
// src/api.js — one place for the base URL and the auth header
const API = import.meta.env.VITE_API_URL; // or process.env.REACT_APP_API_URL / NEXT_PUBLIC_API_URL

export async function api(path, { method = 'GET', body, token } = {}) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw Object.assign(new Error(data?.message || res.statusText), { status: res.status, data });
  return data;
}
```

No cookies or sessions are involved, so you do not need `credentials: 'include'` / `withCredentials`. Adding it does no harm.

## 2. Which local origins are allowed

The *origin* is what is in your browser's address bar, not the API URL. The backend accepts:

| Origin in the address bar | Allowed |
|---|---|
| `http://localhost:<any port>` — 3000, 5173, 4200, 8080, … | ✅ |
| `http://127.0.0.1:<any port>` | ✅ |
| `https://lexora-dz.netlify.app` (the deployed app) | ✅ |
| `https://localhost:<port>` (dev server started with HTTPS) | ❌ start it plain `http` |
| `http://192.168.x.x:<port>`, `http://my-pc.local:<port>` | ❌ open the tab on `localhost` instead |
| Vercel/Netlify preview URLs, ngrok, Codespaces, … | ❌ send the exact origin to the backend team to get it added |

So `npm run dev` on whatever port your tool picks just works. If your tool opens the app on a LAN address, open `http://localhost:<port>` yourself.

## 3. Log in

Everything except `/uploads/**` needs a token. Get one with a login call (**trailing slash required** on all `/auth`, `/affectation`, `/clm` routes):

```http
POST https://lexora.duckdns.org/auth/login/
Content-Type: application/json

{ "email": "rd@sonatrach.dz", "password": "Test1234!" }
```

Success `200` (fields you will use):

```json
{
  "status": "success",
  "access": "<JWT>",  "refresh": "<JWT>",
  "user_id": "4",     "role": "responsable_departement",
  "nom_complet": "Yacine Haddad",
  "direction_id": "…", "departement_id": "…"
}
```

Then send `Authorization: Bearer <access>` on every call. Read `role` and the ids from this response; the token itself carries no custom claims.

- Wrong email or password → `401 {"status":"error","message":"Email ou mot de passe incorrect."}`
- Access and refresh tokens both live **1 day**. `POST /auth/token/refresh/` with `{"refresh": "<refresh>"}` returns a new `access` **and** a new `refresh`; store both, the old refresh is dead.
- `POST /auth/logout/` (Bearer header + `{"refresh": "<refresh>"}`) invalidates the refresh token.
- There is no self-signup; accounts are created by an admin.

### Test accounts

Throwaway seeded accounts, all with password `Test1234!`. They will be reset or disabled once real users exist.

| Email | Role | Good for |
|---|---|---|
| `admin@sonatrach.dz` | `admin` | User management, org structure CRUD, sees all contracts |
| `vp@sonatrach.dz` | `vice_presedent` (spelling is intentional) | VP-gated assignment screens |
| `dd@sonatrach.dz` | `directeur_direction` | Département assignment screens, contracts of its direction |
| `rd@sonatrach.dz` | `responsable_departement` | Contract creation, listing, detail, submission |
| `agent@lexora.test` | `agent` | Read-only view of rd's département contracts |
| `dc@lexora.test` | `directeur_centrale` | "Contrats de ma direction centrale" (empty until a contract carries its id) |
| `adc@lexora.test` | `assistant_directeur_centrale` | Same direction centrale as `dc` |
| `dda@lexora.test` | `directeur_direction_activite` | Direction d'activité screens |
| `ddiv@lexora.test` | `directeur_division_activite` | "Affectations structures" screens |
| `rdd@lexora.test` | `responsable_direction_division` | Structure-scoped lookups |
| `rdepd@lexora.test` | `responsable_departement_division` | Structure-scoped lookups |

Every role in the system has one account. The `@lexora.test` addresses are deliberately non-deliverable (reserved domain); the org ids they carry are fake, so `*_detail` fields in the login response are `null` for all of them.

## 4. Where things live

| Prefix | What | Trailing slash |
|---|---|---|
| `/auth/**` | Login, tokens, users, profiles | required |
| `/affectation/**` | Assignments | required |
| `/clm/**` | Contracts, OCR upload, risks | required |
| `/juridique/**` | Directions, départements, activités, divisions… | none |
| `/bib/**` | Legal document library (PDF upload, field name `pdf`, max 20 MB) | none |
| `/notifications/**` | Conversations, messages, risk alerts (REST only, no Socket.IO) | none |
| `/uploads/<file>` | Uploaded PDFs, public, no token | — |

`GET https://lexora.duckdns.org/` returns `404`; nothing is mounted at the root, that is normal.

## 5. Sixty-second check from your terminal

Run these three before touching the frontend. Replace `5173` with your real dev port.

```bash
# 1) CORS preflight, exactly what your browser sends first
curl -si -X OPTIONS https://lexora.duckdns.org/auth/login/ \
  -H 'Origin: http://localhost:5173' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type,authorization'
# expect: HTTP/1.1 200  +  Access-Control-Allow-Origin: http://localhost:5173

# 2) login
curl -s -X POST https://lexora.duckdns.org/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"rd@sonatrach.dz","password":"Test1234!"}'
# expect: {"status":"success", ..., "access":"...", "refresh":"...", "role":"responsable_departement", ...}

# 3) an authenticated call, with the "access" value from step 2
curl -s https://lexora.duckdns.org/juridique/directions \
  -H 'Authorization: Bearer <access>'
# expect: a JSON array (possibly empty)
```

If all three answer as expected, the backend is fine and any remaining problem is in the frontend code.

## 6. If it fails

| What DevTools shows | Cause | Fix |
|---|---|---|
| `blocked by CORS policy: No 'Access-Control-Allow-Origin' header` and the `OPTIONS` request is `403` | Origin is not `http://localhost:<port>` / `http://127.0.0.1:<port>` (HTTPS dev server, LAN IP, machine name) | Open the tab on `http://localhost:<port>` |
| `Redirect is not allowed for a preflight request` | API base URL uses `http://` | Use `https://lexora.duckdns.org` |
| `Mixed Content` | Your page is `https://` and the API `http://` | Same fix: HTTPS base URL, plain-HTTP dev server |
| `404` on `/auth/…`, `/affectation/…`, `/clm/…` | Missing trailing slash | `/auth/login/`, not `/auth/login` |
| `401` on login | Wrong email or password | Use a test account above |
| `401` on every other call | `Authorization: Bearer <access>` missing, or the token expired (1 day) | Send the header; refresh or log in again |
| `413` on an upload | File over 20 MB (library) / 50 MB (global cap) | Smaller file |
| An upload or `/clm/contrats/upload/` call times out | OCR can take up to 300 s | Raise your HTTP client timeout for those calls |
| Preflight is `200` in curl but the browser still fails | Browser cached an old preflight (they are cached for 1 hour) | Hard reload, or open a private window |

Still stuck? Send the backend team the failing request as a curl (from the DevTools *Copy as cURL* menu) together with the exact origin shown in your address bar.
