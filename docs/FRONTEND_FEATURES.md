# Frontend Features Spec — what to build, per role, with exact API contracts

Audience: the frontend team. This is the **build guide** for the real screens — it maps every role to the screens it needs and gives each screen its exact endpoints with request/response shapes, **extracted from the actual backend code** (not from intentions). Connection basics (base URL, CORS, login/refresh handling, headers) live in [FRONTEND_API_GUIDE.md](FRONTEND_API_GUIDE.md) — read that first.

Base URL everywhere below: `https://lexora.duckdns.org`. Every authenticated call: `Authorization: Bearer <access>`.

> The current deployed frontend menu (Dashboard / Mon Équipe / Tâches / Rapports) matches **nothing** in this backend. The real domain is: **contracts & risks (CLM)**, **org structure**, **role assignments**, **legal document library**, **messaging & risk alerts**, **user administration**. This doc is organized so each role's menu can be rebuilt from its section.

---

## 1. Global rules (read once, they bite)

| Rule | Detail |
|---|---|
| **Trailing slash** | Django services (`/auth`, `/affectation`, `/clm`): **mandatory** on every path. A slash-less POST/PUT/PATCH/DELETE is not redirected — it fails (404/500). Node services (`/juridique`, `/bib`, `/notifications`, `/uploads`): **no** trailing slash. |
| **Role strings** | Exactly 11, case-sensitive, incl. the intentional misspelling **`vice_presedent`**: `admin`, `agent`, `vice_presedent`, `directeur_direction`, `responsable_departement`, `directeur_centrale`, `assistant_directeur_centrale`, `directeur_direction_activite`, `directeur_division_activite`, `responsable_direction_division`, `responsable_departement_division`. **`role` can be `null`** on a user — handle it (route such users to a "no role yet" screen). |
| **Where role/ids come from** | The **login response body**. Do NOT decode the access token — it carries only default claims (`user_id`, `exp`…), not `role` or the org ids. For session refresh/bootstrap use `GET /auth/users/me/` (it returns all 7 org ids). |
| **Ids** | User `id` is an integer (but login returns `user_id` as a *string*). All org ids (`departement_id`, `direction_id`, …) are 24-char MongoDB ObjectId strings. Cross-service references are plain string comparison — no FK integrity. |
| **Tokens** | Access + refresh both live 1 day. Refresh **rotates and is single-use**: every `POST /auth/token/refresh/` returns a new `access` AND a new `refresh` — persist both, the old refresh is blacklisted. |
| **401 vs 403** | Auth service: expired token → `401 {"detail":"…","code":"token_not_valid"}`. `affectation` and `clm` verify tokens by calling the auth service and return **403** (not 401) for missing/invalid tokens (`{"detail":"Token invalide ou expiré."}`); some CLM views return their own `401 {"error":"…"}`. Treat 401 **and** 403-with-`detail` as "re-login". |
| **Response envelopes differ per service** | `auth`/`affectation`: mostly `{"status":"success"|"error", …}` (but not always — see each endpoint). `juridique`/`bib`: `{"success":true|false, "message"?, "data"|…}`. `notifications`: raw objects/arrays, errors as `{"error":…}` or `{"message":…}`. `clm`: `{"success":true,…}` or bare `{"error":…}`. Build one API client per service, not one global unwrapping. |
| **Pagination** | Only where stated. `auth` and `affectation` lists return **everything** (no pagination, no search params). `clm` list: `limit`/`offset`. `bib` list: `page`/`limit`. `notifications` risk-alerts & messages: `page`/`limit`. |
| **French messages** | All human-readable `message`/`error` strings are French (sometimes bilingual FR/AR for CLM risk texts) — displayable as-is. |

### Known-broken endpoints — do NOT call these

| Endpoint | Problem | Use instead |
|---|---|---|
| `POST /clm/contrats/create/` | Always 500 (server bug: renamed model field) | `POST /clm/contrats/formulaire/` |
| `POST /clm/contrats/create-from-pdf/` | Always 500 (same bug) | `POST /clm/contrats/upload/` |
| `PUT /clm/contrats/<id>/update/` with `partie_b_nom` | Field silently ignored — supplier name cannot be changed via update | create correctly the first time |
| `PUT /bib/documents/:id` **with a new file** | Stores a broken, non-servable `pdfUrl` | update metadata only; to replace the PDF, delete + re-create |
| `GET /notifications/users` | Proxies a route that doesn't exist | `GET /auth/all_users/public/` |
| `GET /notifications` and `/notifications/all` | Return **hardcoded fake data** (stubs) | risk alerts + `GET /notifications/unread/count` |
| `PUT/PATCH /affectation/reassign-direction-activite/` | Calls a juridique path that doesn't exist → 404s | remove + assign again |
| `GET /affectation/structures/<id>/directeurs-division-activite/` | Filters the wrong field → always `count: 0` | — |
| `POST /auth/reset-password/` | Emails a link hardcoded to `localhost:3000` | works only for local dev until backend fixes the URL |

---

## 2. Role → screens map (the menu each role should see)

| Role | Menu / screens |
|---|---|
| `admin` | **Utilisateurs** (list/create/detail/edit/deactivate/delete) · **Affectation des rôles** (assign role + activité, direction, direction centrale panels) · **Structure organisationnelle** (full CRUD on all 8 entity types) · **Contrats** (sees ALL, read + PDF) · **Bibliothèque juridique** · **Messagerie** |
| `vice_presedent` | **Affectations activité** (directions d'activité + divisions d'activité panels) · **Contrats** (scoped) · **Bibliothèque** · **Messagerie** |
| `directeur_direction` | **Mes départements** (assign/reassign/remove responsables, scoped to own direction) · **Contrats de ma direction** (read + risks) · **Bibliothèque** · **Messagerie** |
| `responsable_departement` | ⭐ the main CLM user — **Mes contrats** (list/detail) · **Nouveau contrat** (form) · **Importer un PDF** (OCR) · **Risques & alertes** · **Bibliothèque** · **Messagerie** |
| `directeur_centrale` | **Contrats de ma direction centrale** (read) · **Bibliothèque** · **Messagerie** |
| `directeur_division_activite` | **Affectations structures** (direction + département panels) · **Bibliothèque** · **Messagerie** |
| all other roles (`agent`, assistants, responsables division…) | **Contrats de mon département** (read, if `departement_id` set) · **Bibliothèque** · **Messagerie** · org lookups |
| every role | **Profil** (view/edit own) · **Changer le mot de passe** · logout |

Test accounts for each: [SEED_TEST_DATA.md](SEED_TEST_DATA.md) (`admin@sonatrach.dz`, `vp@sonatrach.dz`, `dd@sonatrach.dz`, `rd@sonatrach.dz`, all `Test1234!`).

---

## 3. Session, profile & password (all roles)

Login/refresh/logout request-response shapes: see [FRONTEND_API_GUIDE.md §3](FRONTEND_API_GUIDE.md). Beyond those:

### Session bootstrap — `GET /auth/users/me/`
The one endpoint with **all 7 org ids** for the current user. Use it on app load / token restore.

```json
{ "status": "success",
  "data": { "id": 4, "nom": "Haddad", "prenom": "Yacine", "nom_complet": "Yacine Haddad",
    "email": "rd@sonatrach.dz", "role": "responsable_departement",
    "adresse": null, "telephone": null, "matricule": null, "sexe": null, "date_naissance": null,
    "activite_id": null, "direction_id": "68a…", "departement_id": "68a…",
    "direction_centrale_id": null, "division_activite_id": null,
    "direction_activite_id": null, "structure_id": null,
    "is_active": true, "photo_profil": null, "date_joined": null, "last_login": "2026-08-19T…" },
  "metadata": { "timestamp": "…" } }
```

(`GET /auth/me/` also exists but returns only 3 of the 7 ids — prefer `/auth/users/me/`.)

### Edit own profile — `PUT|PATCH /auth/users/me/update/`
JSON or multipart (for `photo_profil` file). Editable by anyone: `nom`, `prenom`, `adresse`, `telephone`, `sexe` (`M`/`F`), `date_naissance` (`YYYY-MM-DD`), `photo_profil`. Fields like `role`, `email`, `matricule`, org ids are **silently ignored** for non-admins (the response's `summary.modifications` lists them as `"ignoré (non autorisé)"`). Response: `{"status":"success","code":"PROFILE_UPDATED","summary":{…},"before":{…},"after":{…}}` — render `after`.

### Change password — `POST /auth/password/change/`
Body `{"old_password":"…","new_password":"…"}` → `200 {"status":"success","message":"Password changed successfully"}` / `400 {"status":"error","message":"Old password incorrect"}`. ⚠ The backend does **no** strength/length validation — validate on the frontend (min length, not empty).

---

## 4. Admin — user management (`/auth`)

| Action | Endpoint | Notes |
|---|---|---|
| List users (non-admins) | `GET /auth/users/` | `{"status","count","total_users","users":[…]}` — full profile fields incl. all org ids. **No pagination/search** — filter client-side. |
| List ALL users (incl. admins) | `GET /auth/all_users/` | admin-only; slightly smaller per-user shape |
| User detail | `GET /auth/users/<id>/` | rich: adds `role_display`, `age`, `account_stats`, `groups`… wrapped in `{"status","code":"USER_FOUND","user":{…}}` |
| Create user | `POST /auth/users/create/` | JSON or multipart. Required: `email`, `nom`, `prenom`. Optional: `role`, `telephone`, `adresse`, `date_naissance`, `sexe`, `matricule`, `photo_profil` (file). Password is **auto-generated, emailed to the user, and returned once** in `credentials.generated_password` — show it to the admin once, never store it. 201 / `400 "Email déjà utilisé"`. |
| Edit user | `PUT|PATCH /auth/users/<id>/update/` | partial: only sent keys applied; `role` validated against the 11 strings (`400 INVALID_ROLE` + `valid_roles` array); `""`/`"null"` clear a field. Response has `before`/`after` blocks. |
| Change role | `PATCH /auth/users/<id>/update-role/` | body `{"role": "…", …org ids…}`. ⚠ **Resets ALL 7 org-link fields first** — any id not re-sent in the body is wiped. Prefer the `/affectation` endpoints (§5), which handle this correctly. |
| Activate/deactivate | `PATCH /auth/users/<id>/desactive-user/` | body `{"is_active": true|false}` → `{"status","code":"USER_STATUS_UPDATED","data":{old_status,new_status,…}}`. Self-deactivation → `400 CANNOT_DISABLE_SELF`. |
| Delete | `DELETE /auth/users/<id>/delete/` | hard delete, no confirmation server-side — confirm in the UI. |
| User picker (any role) | `GET /auth/all_users/public/` | same shape as `/auth/all_users/`; usable by any JWT — the endpoint for "select a user" dropdowns and messaging contacts. |

---

## 5. Role & org assignments (`/affectation`)

This service has **no data of its own** — every screen is: pick a user (from a candidates list) + pick an org unit (from `/juridique`) → assign. Each family has the same 6 endpoints: assign (PATCH), reassign (PUT), remove (DELETE), and three GET lists (`…/` = unassigned candidates, `…/affectes/` = assigned, `…/all/` = both + `statistics`).

**Success responses** carry a `data` object with the **full enriched user** (all profile fields + resolved org objects `activite`, `direction`, `departement`, … each `{_id, code, nom, description, actif}` or `null`) — enough to update the row in place without refetching.

⚠ **Two list envelope families** (build two parsers):
- Families A–C (admin + directeur_direction screens): `{"status","code","message"?,"data":{"count":N,"directeurs"|"responsables":[…]}}`
- Families D–F (vice_presedent + division screens) and all §5.6 lookups: flat `{"status","count","data":[…]}` (with `statistics` at top level on `/all/`).

### 5.1 Assign a role (admin) — `POST /affectation/assign-role/`
Body: `{"user_id": <int>, "role": "<one of the 10 assignable roles>"}` (+ conditionally required id: `direction_centrale_id` for `assistant_directeur_centrale`, `direction_id` for `responsable_departement`, `activite_id` for `directeur_direction_activite`/`directeur_division_activite`, `division_activite_id` for `responsable_direction_division`/`responsable_departement_division`). `admin` is **not** assignable. Errors carry `code`: `MISSING_ROLE`, `INVALID_ROLE` (+`valid_roles`), `MISSING_<FIELD>`, `USER_NOT_FOUND`, `CANNOT_MODIFY_ADMIN`.

### 5.2 The six assignment families

| | Caller | Target role | Body ids | Endpoints base |
|---|---|---|---|---|
| A. Activité | `admin` | `vice_presedent` | `user_id`, `activite_id` | `PATCH /affectation/assign-activite/` · `PUT /affectation/reassign-activite/` · `DELETE /affectation/users/<id>/remove-activite/` · lists: `GET /affectation/users/directeurs-activite/{,affectes/,all/}` |
| B. Direction | `admin` | `directeur_direction` | `user_id`, `direction_id` | `…/assign-direction/` · `…/reassign-direction/` · `…/users/<id>/remove-direction/` · lists: `…/users/directeurs-direction/{,affectes/,all/}` |
| C. Département | **`directeur_direction`** | `responsable_departement` | `user_id`, `departement_id` (direction is implicit = caller's; département must belong to it, else `403 DEPARTEMENT_NOT_IN_DIRECTION`) | `…/assign-departement/` · `…/reassign-departement/` · `…/users/<id>/remove-departement/` (also clears direction and forces the target to re-login: response `requires_relogin: true` — show that) · lists: `…/users/responsables-departement/{,affectes/,all/}` (key `responsables`) |
| D. Direction centrale | `admin` | `directeur_centrale` | `user_id`, `direction_centrale_id` | `…/assign-direction-centrale/` · `…/reassign-direction-centrale/` · `…/users/<id>/remove-direction-centrale/` · lists: `…/users/directeurs-centrale/{,affectes/,all/}` |
| E. Direction d'activité | **`vice_presedent`** | `directeur_direction_activite` | `user_id`, `direction_activite_id` (`activite_id` derived server-side) | `…/assign-direction-activite/` · ⚠ reassign is broken (see §1) — use remove+assign · `…/users/<id>/remove-direction-activite/` · lists: `…/users/directeurs-direction-activite/{,affectes/,all/}` (flat envelope) |
| F. Division d'activité | **`vice_presedent`** | `directeur_division_activite` | `user_id`, `division_activite_id` | `…/assign-division-activite/` · `…/reassign-division-activite/` · `…/users/<id>/remove-division-activite/` · lists: `…/users/directeurs-division-activite/{,affectes/,all/}` (flat) |
| G/H. Structures | **`directeur_division_activite`** | `responsable_direction_division` / `responsable_departement_division` | `user_id`, `structure_id` (structure `type` must be `direction` / `departement` resp., else `400 INVALID_STRUCTURE_TYPE`) | `…/assign-structure-direction/` + `…/assign-structure-departement/` (+ reassign/remove/lists, flat envelope, list keys `responsables-direction-division` / `responsables-departement-division`) |

Common error codes across families: `ALREADY_ASSIGNED` (assign only — offer "reassign instead"; response often includes the existing assignment), `<X>_NOT_FOUND`, `INVALID_ROLE` (target has the wrong role), `JURIDIQUE_SERVICE_ERROR`/`AUTH_SERVICE_ERROR` (503 — show "service indisponible, réessayez"), `UPDATE_NOT_PERSISTED` (rare; treat as retryable failure). `show_inactive=true` query param exists **only** on the `/all/` lists of families A and D.

### 5.3 Org-unit member lookups (any authenticated role) — for org-chart/detail screens

All return flat `{"status","filter":{…},"count":N,"data":[…full users…]}`; empty = `200, count 0` (never 404).

```
GET /affectation/directions/<direction_id>/responsables-departement/
GET /affectation/departements/<departement_id>/responsables-departement/
GET /affectation/activites/<activite_id>/directeurs-direction/
GET /affectation/activites/<activite_id>/vice-presidents/
GET /affectation/activites/<activite_id>/directeurs-direction-activite/
GET /affectation/directions-centrales/<id>/directeurs-centrale/
GET /affectation/directions-centrales/<id>/assistants/
GET /affectation/structures/<structure_id>/responsables-direction-division/
GET /affectation/structures/<structure_id>/responsables-departement-division/
```

---

## 6. Organizational structure (`/juridique`)

Reads: any JWT. Writes (POST/PUT/DELETE): **admin only**. Envelope: `{"success":true, "count"?, "data":…}`; errors `{"success":false,"message":"…"}`. Objects: `{_id, code, nom, description?, actif, createdAt, updatedAt}` + parent ref.

⚠ Mount-path quirks are **live API surface** — copy them exactly: `/juridique/structure` and `/juridique/division` are **singular**; `/juridique/direction_activite` uses an **underscore**; and the départements d'activité path has a **typo**: `/juridique/departemet_activite` (missing "n").

| Entity | Base path | Parent field (required on create) | List filter | Delete |
|---|---|---|---|---|
| Directions centrales | `/juridique/directions-centrales` | — | — | hard |
| Directions | `/juridique/directions` | `directionCentrale` | `?directionCentrale=<id>` | hard |
| Départements | `/juridique/departements` | `direction` | `?direction=<id>`; also `GET …/departements/direction/<directionId>` | **soft** (`actif:false`) |
| Activités | `/juridique/activites` | — | — | hard |
| Directions d'activité | `/juridique/direction_activite` | `activite` | `?activite=<id>` | hard |
| Départements d'activité | `/juridique/departemet_activite` | `directionActivite` | `?directionActivite=<id>` | hard |
| Divisions | `/juridique/division` | `activite` | `?activite=<id>` | hard |
| Structures | `/juridique/structure` | `division` + `type` (`"direction"`\|`"departement"`) | `?division=<id>&type=…` | hard |

Create body: `{"code":"DJ","nom":"Direction Juridique","description"?, <parent field>: "<id>"}` — `code` is auto-uppercased and unique (duplicate → 409, except départements/activités → 400 `"Ce code existe déjà"`). Detail GETs populate children (e.g. a direction's `departements`); `GET /juridique/directions-centrales/<id>/organigramme` returns the full tree for an org-chart screen. Note: the directions **list** includes inactive rows; the départements list only active ones.

---

## 7. Contracts — CLM (`/clm`) ⭐ the core product

**Who can do what:** list & detail & PDF: any authenticated role (scoped, below). **Everything else — create, upload, update, submit, risks, analyse, alerts — requires role `responsable_departement` exactly** (others get 403). Build write screens only for that role.

### 7.1 List — `GET /clm/contrats/`

Automatic scoping by caller role: `admin` → all · `directeur_centrale` → own `direction_centrale_id` · `directeur_direction` → own `direction_id` · **everyone else** → own `departement_id` (so a user without `departement_id` sees an empty list — handle gracefully).

Query params: `statut` (`brouillon|actif|expire|resilie`) · `type_contrat` (`service|fourniture|travaux|partenariat|vente|transfert`) · `type_partie` (`nationale|etrangere`) · `is_international` (`true|false`) · `search` (substring over numéro/titre/fournisseur/objet) · `ordering` (`date_creation|montant|date_fin`, prefix `-` for desc; default `-date_creation`) · `limit` (default 20, max 100) · `offset`.

```json
{ "success": true, "total": 2, "limit": 20, "offset": 0,
  "results": [ {
    "id": 1, "numero_contrat": "CTR-2026-001", "titre": "Fourniture equipements de forage",
    "type_contrat": "Fournitures / توريد", "type_contrat_code": "fourniture",
    "statut": "actif",
    "partie_a_nom": "SONATRACH", "partie_b_nom": "Sarl EquipDZ",
    "pays_partie_b": "Algerie", "type_partie": "nationale", "is_international": false,
    "montant": 12500000.0, "devise": "DZD",
    "date_signature": "2026-01-10", "date_debut": "2026-02-01", "date_fin": "2027-02-01",
    "delai_livraison_mois": 6, "date_limite_livraison": "2026-08-01", "est_en_retard": true,
    "departement_id": "68a…", "direction_id": "68a…", "direction_centrale_id": null,
    "date_creation": "2026-08-19T…", "date_modification": "2026-08-19T…",
    "risques_total": 2, "risques_critiques": 0, "risques_non_resolus": 2 } ] }
```

⚠ `type_contrat` is the **display label** (bilingual) — use `type_contrat_code` for logic/filters. `statut` here is the **code**. In create/update/submit responses `statut` is the **label** ("Brouillon") — never branch on `statut` from those responses.

### 7.2 Detail — `GET /clm/contrats/<id>/`

Access: admin (all) / directeur_centrale / directeur_direction (matching org id) / same-département — else **403**. Response adds to the list fields: `objet`, `conditions_paiement`, all representative & contact & signature fields (`rep_a_nom`…, `notification_adresse_ligne1`…, `nom_client`…), `ocr_effectue`, `fichier_format`, `moteur_ocr`, `pdf_url`, plus:

- `"metadonnees"`: flat string map, e.g. `{"penalite_retard_pct": "0.5", "tribunal_competent": "Laghouat"}`
- `"risques"`: `{ "total", "non_resolus", "critiques", "retard":[…], "imprecision":[…], "different":[…], "resolus":[…] }` — each risk: `{id, code, type, description, severite, article_ref, suggestion, occurrence_count, niveau_alerte, resolu, date_detection, date_resolution}`
- `"escalade": {}`, `"notifications_en_attente": []`, `"decisions": []` — **always empty** (unimplemented server-side; don't build UI on them)

### 7.3 Create from form — `POST /clm/contrats/formulaire/` (the working manual path)

JSON or multipart (optional file field `fichier`: pdf/docx/png/jpg/jpeg/tiff — stored, not OCR'd). Required: `titre`, `type_contrat` (one of the 6 codes), `societe_b_nom`, `objet`. Optional (defaults): `numero_contrat` (auto `SH-<year>-<HEX>`), `societe_a_nom` (`SONATRACH`), `pays_partie_b` (`Algérie` — drives `is_international`/`type_partie` automatically), `date_signature`/`date_debut`/`date_fin` (`YYYY-MM-DD` also accepts `DD/MM/YYYY`), `delai_livraison_mois` (int → server computes `date_limite_livraison`), `montant`, `devise` (free text, default `DZD`), `conditions_paiement`, `statut`, all representative/contact/signature fields, and metadata keys (`penalite_retard_pct`, `duree_garantie_mois`, `caution_bonne_fin_pct`, `tribunal_competent`, `mode_reglement`…).

201 → `{"success":true,"methode":"formulaire","contrat":{…full contract…},"saisie":{"champs_trouves","champs_manquants","metadonnees"},"risques":{"total","par_type":{retard,imprecision,different},"critique_count","detail":[…]}}` — **risk analysis runs at creation**: show the returned risks immediately. Errors: `409 "Numéro déjà existant"` · `400` champs obligatoires / type_contrat invalide / dates.

### 7.4 Create from PDF (OCR) — `POST /clm/contrats/upload/` (the working import path)

Multipart, file field **`fichier`** (pdf/docx/png/jpg/jpeg/tiff). Any form field from §7.3 can be sent alongside to override what the parser extracts (form value wins). **Long call — OCR can take minutes: set the HTTP timeout to 300 s and show a progress state.**

201 response: `contrat` (as above) + `"extraction": {"method","pages","chars_extraits","champs_trouves":[…],"champs_manquants":[…],"metadonnees":{…}}` + `"risques": {…, "notification":{"success","sent_count","errors"}}`. Recommended UX: upload → show extraction results with `champs_manquants` highlighted as editable fields → let the user fix → (today there is no re-parse endpoint; corrections go through update or by deleting/recreating). Errors: `422 "OCR échoué"` (bad scan — ask for a better file) · `409` duplicate numéro · `400` no/unsupported file.

### 7.5 Update / submit / risks / PDF

| Action | Endpoint | Contract |
|---|---|---|
| Edit (only while `brouillon`) | `PUT /clm/contrats/<id>/update/` (**PUT only** — PATCH → 405) | JSON, partial: `titre`, `type_contrat`, `pays_partie_b`, `objet`, dates, `montant`, `devise`, `conditions_paiement`. Own département only. `400 "Impossible de modifier un contrat en statut Actif"`. ⚠ supplier name not editable (see §1). |
| Submit brouillon → actif | `POST /clm/contrats/<id>/submit/` | no body. 200 or `404 "Contrat non trouvé ou déjà soumis"`. One-way — confirm in UI. |
| Risks of a contract | `GET /clm/contrats/<id>/risques/` | `{contrat_id, numero_contrat, total, retard:[…], imprecision:[…], different:[…]}` |
| Re-notify delay risks | `POST /clm/contrats/<id>/analyser/` | Does **not** re-analyse the text — it re-sends existing unresolved *retard* risks to the notification service. Returns `{contrat_id, risques_retard:[{…, escalade:{niveau,label,escalader,notifier}}], notification:{success,sent_count,errors}}`. Label it "Renvoyer les alertes", not "Analyser". |
| Alerts (from notif service) | `GET /clm/contrats/<id>/alertes/` | `{contrat_id, alerts:[…], count}` — proxy of §9.1 filtered to this contract. |
| Generated PDF | `GET /clm/contrats/<id>/pdf/` | Returns **binary PDF** (`Content-Type: application/pdf`, attachment). Fetch with the Bearer header and save as blob — it is NOT an open URL. |

### 7.6 CLM enums (exact codes)

- `type_contrat`: `service`, `fourniture`, `travaux`, `partenariat`, `vente`, `transfert`
- `statut`: `brouillon` → `actif` → `expire` / `resilie` (creation always starts `brouillon`; only transition endpoint is submit)
- risk `type`: `retard`, `imprecision`, `different` · `severite`: `faible`, `moyen`, `eleve`, `critique` · `niveau_alerte`: `warning`, `alert`, `escalade`
- risk codes you'll see: delays `R-01`, `R-07`, `R-08`; imprecisions `I-01`, `I-5`, `I-06`, `I-07`, `I-08`, `I-10`, `I-11`, `I-12`, `I-13`; disputes `D-01`…`D-07`. Descriptions/suggestions are bilingual `"FR / AR"` — split on `" / "` if you need one language.
- Useful computed fields: `date_limite_livraison` (server-computed, read-only), `jours_restants_livraison` (negative = overdue), `est_en_retard` (bool) — build the "contrats en retard" indicators from these.

---

## 8. Legal document library (`/bib`, `/uploads`)

Any JWT can upload/read/update; **delete is admin-only**. Envelope `{"success":true, …}`.

| Action | Endpoint | Contract |
|---|---|---|
| Upload | `POST /bib/documents` | multipart, file field **`pdf`** (PDF only, ≤ 20 MB), fields: `titre` (req), `categorie` (req, enum below), `reference`, `organismeEmetteur`, `datePublication` (ISO), `motsCles` (comma-separated string ok), `resume`, `statut`. 201 `{"success":true,"data":{…}}`. ⚠ validation errors come back as **500** with the message — treat 500 here as "check your form". |
| List | `GET /bib/documents?page=1&limit=10&categorie=LOIS` | `{"success":true,"page":1,"total":37,"data":[…]}` (compute page count as `ceil(total/limit)`) |
| Search | `GET /bib/search?q=marché` | case-insensitive over titre/référence/résumé; `{"success","total","data"}` (no pagination) |
| Detail | `GET /bib/documents/:id` | `{"success":true,"data":{…}}` |
| Update metadata | `PUT /bib/documents/:id` | multipart/form fields; **do not send a new file** (see §1); `motsCles` not updatable here |
| Delete | `DELETE /bib/documents/:id` | admin; the PDF file itself stays on disk |
| View/download PDF | `GET <base>/uploads/<filename>` | `pdfUrl` from the document is relative (`/uploads/169…pdf`) — prepend the base URL. **Public, no token** — safe for `<iframe>`/`<embed>` viewers. |

`categorie` enum: `CONSTITUTION`, `TRAITES_ET_ACCORDS`, `LOIS`, `ORDONNANCES`, `DECRETS`, `DECISIONS_ET_ARRETES`, `TEXTES_REGLEMENTAIRES`, `CONTRATS_ET_MODELES`, `DOCUMENTATION_INTERNE`, `JURISPRUDENCE`. Document `statut`: `EN_VIGUEUR` (default), `ABROGE`, `MODIFIE`.

---

## 9. Notifications, risk alerts & messaging (`/notifications`)

**Socket.IO is not active — poll.** All endpoints need a JWT. Two real subsystems (risk alerts; conversations/messages) + stub general notifications (see §1). Error key is `{"error": …}` (alerts/conversations) or `{"message": …}` (message edit/delete) — never `success:false`.

### 9.1 Risk alerts (the "Alertes" screen — fed automatically by CLM)

| Action | Endpoint | Contract |
|---|---|---|
| List | `GET /notifications/risk-alerts?contrat_id=&type=&severite=&statut=&page=1&limit=50` | `{"alerts":[…], "total", "page", "limit", "pages"}` |
| Per-contract summary | `GET /notifications/risk-alerts/summary/<contrat_id>` | `{"contrat_id","niveau_global":"ok|attention|eleve|critique|escalade","stats":{total,critique,eleve,moyen,faible,escalades},"alerts":[…]}` — ideal for a dashboard tile |
| One alert | `GET /notifications/risk-alerts/<id>` | the alert object, flat |
| Triage | `PATCH /notifications/risk-alerts/<id>` | body `{"statut":"nouveau|en_cours|resolu|ignore","resolution_note"?}`; `resolu` auto-stamps `resolved_at`. Build the workflow UI on this. |

Alert object: `{_id, contrat_id (int), code, type (retard|imprecision|different), description, severite, article_ref, suggestion, statut, resolution_note, resolved_at, created_by_id, created_by_name, createdAt, occurrence_count, escalade:{niveau (warning|alert|escalade), label, escalader (bool), notifier}}`. `escalade.niveau` drives the badge: warning → 1st occurrence, alert → 2nd, escalade → 3rd+.

### 9.2 Messaging (real, persistent)

| Action | Endpoint | Contract |
|---|---|---|
| Open/create a direct conversation | `POST /notifications/conversations/direct` body `{"targetUserId":"12","targetUserRole"?,"targetUserName"?}` | 201 (new) or 200 (existing) → the conversation object. Pick targets from `GET /auth/all_users/public/`. |
| My conversations | `GET /notifications/conversations` | raw array, sorted by `lastMessageAt` desc: `{_id, participants:[{userId,role,nom_complet}], type, subject, lastMessage, lastMessageAt, createdBy}` |
| Messages | `GET /notifications/messages/<conversationId>?page=1&limit=50` | `{"messages":[…asc…],"page","limit","total"}`; **side effect: marks them read** |
| Send | `POST /notifications/messages` body `{"conversationId","content"}` | 201 → the message `{_id, conversationId, senderId, senderRole, senderName, content, readBy:[…], createdAt}` |
| Edit own (≤ 5 min) | `PUT /notifications/messages/<messageId>` body `{"content"}` | 403 after 5 minutes — hide the edit button then |
| Delete own (or admin) | `DELETE /notifications/messages/<messageId>` | `{"message":"Message supprimé","messageId"}` |
| Mark read | `PUT /notifications/messages/conversation/<id>/read` | `{"…","totalUnread": <global count>}` |
| Unread badge | `GET /notifications/unread/count` | `{"unreadCount": 3}` — poll this (e.g. every 30 s) for the topbar badge |

---

## 10. Suggested build order

1. **Session core**: login → store `access`/`refresh`/role/ids from the response → bootstrap via `/auth/users/me/` → role-based router guard (incl. `role: null`).
2. **RD contract screens** (the seeded, testable path): list → detail (risks tab) → create form (`/formulaire/`) → submit → PDF download. Test with `rd@sonatrach.dz`.
3. **PDF import** with the 300 s upload flow + extraction review.
4. **Risk alerts screen** + unread/summary badges (data already flows from CLM).
5. **Admin**: users CRUD → org structure CRUD → assignment screens (families A, B, D) — then the vice_presedent / directeur_direction / division screens (C, E–H).
6. **Library** + **messaging** (shared by every role).
