# Feature 2 — Role & Organizational Assignments

| | |
|---|---|
| **Service** | `affectation-service/` — Django 5.1 + DRF, port 8011 |
| **Database** | MySQL `affectation-sonatrach` (Django system tables only — **no domain models**) |
| **Public prefix** | `/affectation` (gateway → `http://localhost:8011`) |
| **Eureka name** | `AFFECTATION-SOUNATRACH` |

## What it does

Connects **people to the organizational chart**: it assigns users (by role) to the org entities owned by service-juridique — activités, directions, départements, directions centrales, divisions, structures. It is a pure **orchestration service**: it stores nothing of its own; every operation composes the user store (authentification) with the org structure (service-juridique), resolved at runtime via Eureka discovery (`get_juridique_base_url()` / `get_gateway_url()`).

## The assignment pattern

The API is one pattern repeated per organizational level. For each level `X`:

| Operation | Endpoint shape |
|---|---|
| Assign | `POST /affectation/assign-X/` |
| Reassign | `POST /affectation/reassign-X/` |
| Remove | `DELETE\|POST /affectation/users/<user_id>/remove-X/` |
| List unassigned holders of the matching role | `GET /affectation/users/<role-plural>/non-affectes/` (or base list) |
| List assigned | `GET /affectation/users/<role-plural>/affectes/` |
| List all | `GET /affectation/users/<role-plural>/all/` |

### Levels and the roles they manage

| Level (`X`) | Role concerned | Org entity (service-juridique) |
|---|---|---|
| `role` (`assign-role/`) | any | sets the user's role itself |
| `activite` | `vice_presedent` context | Activité |
| `direction` | `directeur_direction` | Direction |
| `departement` | `responsable_departement` | Département |
| `direction-centrale` | `directeur_centrale` (+ `assistant_directeur_centrale`) | Direction Centrale |
| `direction-activite` | `directeur_direction_activite` | Direction Activité |
| `division-activite` | `directeur_division_activite` | Division |
| `structure-direction` | `responsable_direction_division` | Structure |
| `structure-departement` | `responsable_departement_division` | Structure |

## Query endpoints (reverse lookups)

Given an org entity, list the people holding a role in it — all `GET`, JWT-authenticated:

| Path | Returns |
|---|---|
| `/affectation/directions/<direction_id>/responsables-departement/` | department heads within a direction |
| `/affectation/departements/<departement_id>/responsables-departement/` | head(s) of a department |
| `/affectation/activites/<activite_id>/directeurs-direction/` | direction directors in an activité |
| `/affectation/activites/<activite_id>/vice-presidents/` | VPs of an activité |
| `/affectation/activites/<activite_id>/directeurs-direction-activite/` | activity-direction directors |
| `/affectation/directions-centrales/<id>/directeurs-centrale/` | central-direction directors |
| `/affectation/directions-centrales/<id>/assistants/` | their assistants |
| `/affectation/structures/<structure_id>/directeurs-division-activite/` | division directors in a structure |
| `/affectation/structures/<structure_id>/responsables-direction-division/` | direction-division managers |
| `/affectation/structures/<structure_id>/responsables-departement-division/` | department-division managers |

`<*_id>` parameters are **MongoDB ObjectId strings** (24 chars) from service-juridique — passed through as strings.

## How an assignment actually works

1. Caller (admin UI) posts a `user_id` + target entity id.
2. The service validates the entity against **service-juridique** (Eureka-resolved base URL, 60 s discovery cache, gateway fallback when `USE_EUREKA=false`).
3. It updates the user record via the **authentification** endpoints (`update-role`, `update-departement`).
4. Result: the user carries the role + org linkage; no row is written in this service's own schema.

## Known limitations

- No local persistence means no assignment history/audit trail — current state lives only on the user record.
- Consistency is best-effort: if step 3 fails after step 2 validated, there is no rollback mechanism.
- Depends on both authentification and service-juridique being up; degrades with 5xx otherwise.
