# Feature 3 — Organizational Structure

| | |
|---|---|
| **Service** | `service-juridique/` — Node, Express 4.18, Mongoose 7.6, port 8084 |
| **Database** | MongoDB `juridique_dbb` |
| **Public prefix** | `/juridique` (gateway → `lb://service-juridique`) |
| **Eureka name** | `service-juridique` |

## What it does

The referential for the legal department's **organizational chart**: central directions, directions, départements, activités, divisions and structures, plus the junction entities linking directions/départements to activités. Every other feature keys into these entities — assignments (feature 2) attach people to them, contracts (feature 5) record `departement_id`/`direction_id` from here.

## Data model (8 Mongoose collections)

| Model | Represents | Notable relations |
|---|---|---|
| `DirectionCentrale` | central direction (top level) | has an organigramme endpoint |
| `Direction` | direction | parent of départements |
| `Departement` | département | `getByDirection` lookup |
| `Activite` | business activity | linked via junctions |
| `DirectionActivite` | junction: direction ↔ activité | |
| `DepartementActivite` | junction: département ↔ activité | |
| `Division` | division | |
| `Structure` | structure (division grouping) | queried by assignments |

Entities carry `code`, `nom`, `description` (French vocabulary; see the commented-out `seed.js` for representative data: DC "Direction Contrats", DRD "Direction Règlement des Différends", etc.).

## Endpoint reference

Uniform CRUD per entity — **reads for any authenticated user, writes admin-only** (`checkRole('admin')`):

| Method | Path pattern | Auth |
|---|---|---|
| GET | `/juridique/<entity>/` | JWT |
| GET | `/juridique/<entity>/:id` | JWT |
| POST | `/juridique/<entity>/` | admin |
| PUT | `/juridique/<entity>/:id` | admin |
| DELETE | `/juridique/<entity>/:id` | admin |

Entity path segments: `directions`, `departements`, `activites`, `directions-centrales`, `structure`, `division`, `direction_activite`, `departemet_activite` *(sic — the typo is the live route)*.

Extras beyond plain CRUD:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/juridique/departements/direction/:directionId` | JWT | départements of one direction |
| GET | `/juridique/directions-centrales/:id/organigramme` | JWT | org chart for a central direction |
| GET | `/juridique/dashboard/counters` | JWT | KPI counts of all 8 entities (`Direction`/`Departement` count only `actif: true`) |
| GET | `/juridique/dashboard/directions-par-direction-centrale` | JWT | active directions grouped per direction centrale, sorted by count desc |
| GET | `/juridique/dashboard/activites-breakdown` | JWT | counts of the four activité sub-entities |
| GET | `/health`, `/info` | none | liveness (root-mounted, not routed by gateway) |

Dashboard aggregates (Sept 2026, `controllers/dashboardController.js`) — read-only, any authenticated role, envelope `{"success":true,"data":…}`:

```json
GET /juridique/dashboard/counters
{"success":true,"data":{"directionsCentrales":3,"directions":9,"departements":21,"activites":4,
  "directionsActivite":6,"departementsActivite":12,"divisions":5,"structures":8}}

GET /juridique/dashboard/directions-par-direction-centrale
{"success":true,"data":[{"directionCentraleId":"<id>","nom":"Direction Contrats","code":"DC","count":4}, …]}

GET /juridique/dashboard/activites-breakdown
{"success":true,"data":{"directionsActivite":6,"departementsActivite":12,"divisions":5,"structures":8}}
```

## Authorization model

`middleware/auth.js`: local HS256 JWT verification (`JWT_SECRET` = Django `SECRET_KEY`) → user/role resolution via gateway `GET /auth/all_users/<id>/` → 10-minute in-memory cache → `checkRole('admin')` gates all writes.

## Known quirks (verified in code)

- **The startup banner lies**: `server.js` advertises `GET /juridique/directions/organigramme`, but that route is commented out in `directionRoutes.js`. The working organigramme lives at `/juridique/directions-centrales/:id/organigramme`.
- ~~Bug — activité update~~ **Fixed (Aug 2026)**: `PUT /juridique/activites/:id` was wired to `ctrl.create`; it now calls `ctrl.update`.
- Route naming is inconsistent: plural (`directions`) vs singular (`structure`, `division`) vs snake_case junctions (`direction_activite`) — clients must match exactly.
- `seed.js` (initial org data) is entirely commented out; reference data enters through the admin CRUD endpoints.
