# Feature 1 — Authentication & User Management

| | |
|---|---|
| **Service** | `authentification/` — Django 5.1 + DRF, port 8010 |
| **Database** | MySQL `loisonatrach` |
| **Public prefix** | `/auth` (gateway → `http://localhost:8010`) |
| **Eureka name** | `AUTHENTICATION-SOUNATRACH` |

## What it does

The identity core of the system: it stores every employee account, authenticates users, issues the JWTs that **all other services** trust, manages passwords (including emailed credentials for new agents), and exposes user-lookup endpoints consumed by the Node services' auth middleware.

## Data model

Custom user model **`api.User`** (`AUTH_USER_MODEL`), replacing Django's default:

| Group | Fields |
|---|---|
| Identity | `email` (unique, login identifier), `nom`, `prenom`, `matricule` (unique employee number) |
| Role | `role` — one of 11 choices (below) |
| Profile | `photo_profil` (CloudinaryField), `adresse`, `date_naissance`, `sexe` (M/F), `telephone` |
| Org linkage | department/direction references set by the affectation service |
| State | active flag (toggle endpoint), standard Django permissions mixin |

### Roles

These strings are **cross-service API surface** — Node middleware and the affectation service match them verbatim:

`admin` · `agent` · `vice_presedent` · `directeur_direction` · `responsable_departement` · `directeur_centrale` · `assistant_directeur_centrale` · `directeur_direction_activite` · `directeur_division_activite` · `responsable_direction_division` · `responsable_departement_division`

(Note the misspelling `vice_presedent` — it is live data; do not "fix" it.)

## Token issuing (simplejwt)

| Setting | Value |
|---|---|
| Algorithm | HS256, signing key = Django `SECRET_KEY` (the shared cross-service secret) |
| Access token lifetime | 1 day *(code comment says "1 heure" — the code wins)* |
| Refresh token lifetime | 1 day |
| Rotation | `ROTATE_REFRESH_TOKENS=True` + blacklist after rotation (`token_blacklist` app) |

## Endpoint reference

All paths under `/auth/`.

### Tokens & session

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/token/` | none | simplejwt token pair (standard `TokenObtainPairView`) |
| POST | `/auth/token/refresh/` | refresh token | refresh the access token |
| POST | `/auth/login/` | none | application login (custom view) |
| POST | `/auth/logout/` | JWT | logout / blacklist |
| GET | `/auth/me/` | JWT | current authenticated identity |

### Passwords

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/password/change/` | JWT | change own password |
| POST | `/auth/reset-password/` | none | start reset (sends email) |
| POST | `/auth/reset-password-confirm/` | none | confirm reset with token |

### User administration

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/users/create/` | admin | create a user; generated password emailed via Gmail SMTP |
| GET | `/auth/users/` | JWT/admin | list users |
| GET | `/auth/users/<id>/` | JWT | user detail |
| PUT | `/auth/users/<id>/update/` | admin | update user |
| PUT | `/auth/users/<id>/update-role/` | admin | change role (used by affectation flows) |
| PUT | `/auth/users/<id>/update-departement/` | admin | set org linkage (used by affectation flows) |
| POST | `/auth/users/<id>/desactive-user/` | admin | toggle active state |
| DELETE | `/auth/users/<id>/delete/` | admin | delete user |
| GET | `/auth/users/me/` · PUT `/auth/users/me/update/` | JWT | own profile read/update |

### Lookup endpoints (consumed by other services)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/auth/all_users/` | JWT | full user list |
| GET | `/auth/all_users/<id>/` | JWT (Bearer forwarded) | **the endpoint Node auth middleware calls** to resolve id → role/profile |
| GET | `/auth/all_users/public/` | ⚠ none | public user listing — review before production |

## Flows

**New agent onboarding**: admin `POST /auth/users/create/` → service generates a password → emails it via Gmail SMTP (`EMAIL_HOST_USER` account) → agent logs in and changes password. Bulk import supported through Excel (`openpyxl`; sample workbook `Classeur1.xlsx` sits in the service root).

**Cross-service identity resolution**: a Node service receives a request → verifies JWT locally → `GET /auth/all_users/<id>/` through the gateway with the same Bearer token → caches the profile 10 min → applies `checkRole(...)`.

## Known limitations

- `/auth/all_users/public/` exposes user data without authentication.
- Access tokens live 24 h (long for an internal admin system).
- Password emails depend on a hardcoded Gmail app password (rotation required — see deployment guide G-1).
- Duplicate URL registration for `users/<id>/` appears twice in `api/urls.py` (harmless; first match wins).
