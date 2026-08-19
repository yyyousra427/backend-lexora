# Seed Test Data — accounts + sample records for end-to-end testing

Run everything on the **VPS as the `lexora` user**. Each block is copy-paste-ready. Order matters: users → (optional) org structure → contracts → verify.

> These are throwaway test credentials. If any of these accounts survive into real use, change the passwords (all set to `Test1234!` here). No welcome emails are sent by these scripts.

## Test accounts created below

| Email | Password | Role | What it can exercise |
|---|---|---|---|
| `admin@sonatrach.dz` | `Test1234!` | `admin` | Everything: user management (`/auth/users/**`), all `/affectation/**` admin screens, all org CRUD (`/juridique/**`), sees **all** contracts in `/clm/**`, Django admin (`/admin/`) |
| `vp@sonatrach.dz` | `Test1234!` | `vice_presedent` | Appears in `/affectation/users/directeurs-activite/non-affectes/`; the VP-gated affectation blocks |
| `dd@sonatrach.dz` | `Test1234!` | `directeur_direction` | Département-assignment screens (`IsDirecteurDirection` block); sees contracts of its `direction_id` |
| `rd@sonatrach.dz` | `Test1234!` | `responsable_departement` | **The main CLM test account**: create/list/detail/submit contracts on its département |

## Step 1 — Create the users (authentification, MySQL)

```bash
cd /opt/lexora/authentification
.venv/bin/python manage.py shell <<'EOF'
from api.models import User

# Fake-but-valid 24-char Mongo ObjectIds. CLM filtering is plain string
# comparison, so these work; org NAMES will show as unresolved until you
# use real ids from service-juridique (see Step 2).
DEP = "64a000000000000000000001"
DIR = "64a000000000000000000002"
ACT = "64a000000000000000000003"

def mk(email, nom, prenom, role, **extra):
    u = User.objects.filter(email=email).first()
    if u:
        print("= exists:", email, "id =", u.id); return u
    u = User(email=email, nom=nom, prenom=prenom, role=role, **extra)
    u.set_password("Test1234!")
    u.save()
    print("+ created:", email, "role =", role, "id =", u.id)
    return u

admin = mk("admin@sonatrach.dz", "Admin", "Root", "admin", is_staff=True, is_superuser=True)
vp    = mk("vp@sonatrach.dz", "Benali", "Karim", "vice_presedent")   # spelling intentional
dd    = mk("dd@sonatrach.dz", "Meziane", "Sara", "directeur_direction", direction_id=DIR, activite_id=ACT)
rd    = mk("rd@sonatrach.dz", "Haddad", "Yacine", "responsable_departement", departement_id=DEP, direction_id=DIR)

print("\n>>> NOTE THIS: rd user id =", rd.id, " (needed as RD_ID in Step 3)")
EOF
```

**Write down the `rd` user id it prints** — Step 3 needs it.

## Step 2 (optional) — Seed org structure (service-juridique, MongoDB)

The repo ships one seed script; it creates the **TRC activity tree** (1 Activité `TRC`, 2 Directions d'activité incl. `TRC-DJ` with 4 départements d'activité, 3 Divisions). It does **not** create Directions/Départements "classiques". Safe to run twice (it wipes and recreates only TRC):

```bash
cd /opt/lexora/service-juridique && node seed.js
```

To have real Directions/Départements (so names resolve in the affectation screens), create them through the API as admin — login as `admin@sonatrach.dz`, then `POST /juridique/directions` and `POST /juridique/departements`, and update the test users' `direction_id`/`departement_id` to the returned `_id`s (rerun Step 1's shell with the real ids, or update via Django admin). For pure login/CLM testing you can skip all of this — the fake ids from Step 1 are enough.

## Step 3 — Seed contracts (service_clm, MySQL)

Replace `RD_ID = 4` with the id printed in Step 1.

> If this fails with `(1146, "Table 'clm_sounatrach.clm_contrat' doesn't exist")`, the CLM migrations were never applied on this machine — run `cd /opt/lexora/service_clm && .venv/bin/python manage.py migrate` first, then re-run the block. (Same applies to Step 1 with the auth service.)
>
> If *migrate* then fails with `(1050, "Table 'auth_permission' already exists")`, an earlier migrate was interrupted mid-run (usually Ctrl-C during the Eureka hang at exit) and left half a schema behind. `clm_sounatrach` is used by service_clm only, so just reset it and migrate again:
> `mysql -u lexora -p -e "DROP DATABASE clm_sounatrach; CREATE DATABASE clm_sounatrach CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"`
> Let migrate run to completion — it can hang ~1 min at the end before the harmless Eureka `TimeoutError` noise; don't interrupt it.

```bash
cd /opt/lexora/service_clm
.venv/bin/python manage.py shell <<'EOF'
from clm.models import Contrat, MetadonneeContrat, RisqueContrat
from datetime import date

DEP   = "64a000000000000000000001"   # must equal rd's departement_id (Step 1)
DIR   = "64a000000000000000000002"   # must equal dd's direction_id  (Step 1)
RD_ID = 4                            # <<< REPLACE with the rd id printed in Step 1

c1, _ = Contrat.objects.get_or_create(
    numero_contrat="CTR-2026-001",
    defaults=dict(
        titre="Fourniture equipements de forage",
        type_contrat="fourniture",
        cree_par_id=RD_ID, cree_par_role="responsable_departement",
        departement_id=DEP, direction_id=DIR,
        societe_b_nom="Sarl EquipDZ", pays_partie_b="Algerie",
        objet="Fourniture et livraison d'equipements de forage.",
        montant=12500000, devise="DZD",
        date_signature=date(2026,1,10), date_debut=date(2026,2,1),
        date_fin=date(2027,2,1), delai_livraison_mois=6,
        statut="actif",
    ),
)
c2, _ = Contrat.objects.get_or_create(
    numero_contrat="CTR-2026-002",
    defaults=dict(
        titre="Prestation maintenance industrielle",
        type_contrat="service",
        cree_par_id=RD_ID, cree_par_role="responsable_departement",
        departement_id=DEP, direction_id=DIR,
        societe_b_nom="TotalEnergies Services", pays_partie_b="France",
        objet="Maintenance preventive des installations.",
        montant=800000, devise="EUR",
        date_debut=date(2026,3,1), delai_livraison_mois=3,
        statut="brouillon",
    ),
)
RisqueContrat.objects.get_or_create(contrat=c1, code="R-01", defaults=dict(
    type_risque="retard", description="Retard de livraison potentiel (delai depasse).",
    severite="eleve", article_ref="Art. 9", suggestion="Relancer le fournisseur.",
    niveau_alerte="alert"))
RisqueContrat.objects.get_or_create(contrat=c1, code="I-06", defaults=dict(
    type_risque="imprecision", description="Clause de penalites imprecise.",
    severite="moyen", article_ref="Art. 11", suggestion="Preciser le taux de penalite."))
MetadonneeContrat.objects.get_or_create(contrat=c1, cle="penalites_retard",
    defaults=dict(valeur="0.5% par semaine, plafonne a 10%"))

print("contrats:", Contrat.objects.count(), "| risques:", RisqueContrat.objects.count())
EOF
```

`type_partie`, `is_international`, and `date_limite_livraison` are auto-computed on save — the France contract becomes international automatically. Re-running is safe (`get_or_create` keys on `numero_contrat`).

## Step 4 — Verify (login + data visible end-to-end)

From the VPS or any machine:

```bash
# 1) Login works (the key test)
curl -s -X POST https://lexora.duckdns.org/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"rd@sonatrach.dz","password":"Test1234!"}'
# expect: {"status":"success", ... "access":"...", "role":"responsable_departement", ...}

# 2) Grab the "access" value from that response, then:
ACCESS="<paste access token>"

# rd sees its departement's contracts (2 rows)
curl -s https://lexora.duckdns.org/clm/contrats/ -H "Authorization: Bearer $ACCESS"

# org structure through the gateway (empty list until Step 2, but must be JSON 200, not 401/503)
curl -s https://lexora.duckdns.org/juridique/directions -H "Authorization: Bearer $ACCESS"

# 3) Admin sees everything
curl -s -X POST https://lexora.duckdns.org/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@sonatrach.dz","password":"Test1234!"}'
```

Expected outcomes:
- Both logins return `status: success` with tokens → **auth works**.
- `rd` gets both contracts on `/clm/contrats/`; contract detail `/clm/contrats/<id>/` shows metadata + risks.
- `admin` also sees both (admin sees all), and `vp@sonatrach.dz` appears in `GET /affectation/users/directeurs-activite/non-affectes/` with the admin token.

## Cleanup (when real data arrives)

```bash
# remove test contracts
cd /opt/lexora/service_clm && .venv/bin/python manage.py shell -c \
  "from clm.models import Contrat; Contrat.objects.filter(numero_contrat__startswith='CTR-2026-00').delete()"

# deactivate (or delete) test users
cd /opt/lexora/authentification && .venv/bin/python manage.py shell -c \
  "from api.models import User; User.objects.filter(email__in=['vp@sonatrach.dz','dd@sonatrach.dz','rd@sonatrach.dz']).update(is_active=False)"
```

Keep `admin@sonatrach.dz` (with a changed password) or create your real admin before deactivating it.
