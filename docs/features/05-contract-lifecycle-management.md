# Feature 5 — Contract Lifecycle Management (CLM)

| | |
|---|---|
| **Service** | `service_clm/` — Django 5.1 + DRF, port 8012 |
| **Database** | MySQL `clm_sounatrach`; contract files on Cloudinary (`MediaCloudinaryStorage`) / `contrats/originaux/` |
| **Public prefix** | `/clm` (gateway → `http://localhost:8012`) |
| **Eureka name** | `CLM-SOUNATRACH` |

## What it does

The richest feature of the system: create contracts (from a form or from an uploaded PDF), extract their text (native PDF text or OCR for scans), parse structure and metadata, run a **rule-based risk engine**, generate contract PDFs, and push risk alerts to the notification service.

## Data model

### `Contrat` — the central entity

| Group | Fields (selection) |
|---|---|
| Identification | `numero_contrat` (unique), `titre`, `type_contrat` — `service` / `fourniture` / `travaux` / `partenariat` / `vente` / `transfert` (labels bilingual FR/AR) |
| Lifecycle | `statut` — `brouillon` → `actif` → `expire` / `resilie` |
| Internal org | `cree_par_id` + `cree_par_role` (user from feature 1), `departement_id`, `direction_id`, `direction_centrale_id` (ObjectId strings from feature 3) |
| Parties | Partie A (client) defaults to **SONATRACH**; Partie B (fournisseur) with `pays_partie_b`, `is_international`, `type_partie` (`nationale`/`etrangere`), representatives for both parties |
| Contract terms | `objet`, `date_signature` / `date_debut` / `date_fin`, `montant` (18,2 decimal) + `devise` (default **DZD**), `conditions_paiement` |
| Delivery | `delai_livraison_mois` → `date_limite_livraison` **computed automatically** (= `date_debut` + months, non-editable) |
| Contact/signature articles | Art. 21 notification addresses + fournisseur contacts; Art. 22 signatory names/functions for both parties |
| Document | `fichier_original` (upload to `contrats/originaux/`), `fichier_format`, `texte_extrait` (full extracted text), `moteur_ocr` (`tesseract` implemented; `easyocr`/`azure` reserved), `pdf_url` |

### Companions

- **`MetadonneeContrat`** — key/value metadata extracted by the parser.
- **`RisqueContrat`** — one row per detected risk (type, severity, description) for a contract.

## The analysis pipeline

`POST /clm/contrats/<id>/analyser/` runs, in order:

```
fichier PDF
  → ocr_utils.py     : PyMuPDF native text extraction
                       ↳ if scanned: page → image → pytesseract (lang per config,
                         binary path via optional TESSERACT_CMD setting)
  → contract_parser.py : structure + metadata extraction → MetadonneeContrat
  → risk_engine.py     : rule-based scoring → RisqueContrat rows
  → notification_client.py : POST alerts through the gateway to
                             /notifications/risk-alerts (5 s timeout)
```

The notification call is fire-and-forget with a timeout — analysis succeeds even if the notification service is down (alerts are then only visible via `/clm/contrats/<id>/risques/`).

## Endpoint reference

All paths under `/clm/`, JWT-authenticated (simplejwt).

### Creation

| Method | Path | Purpose |
|---|---|---|
| POST | `/clm/contrats/create/` | create from JSON (simple) |
| POST | `/clm/contrats/create-from-pdf/` | create by uploading a PDF (extraction seeded) |
| POST | `/clm/contrats/upload/` | attach/upload a contract PDF |
| POST | `/clm/contrats/formulaire/` | create from the full structured form |

### Reading

| Method | Path | Purpose |
|---|---|---|
| GET | `/clm/contrats/` | list contracts (scoped by caller's role/org) |
| GET | `/clm/contrats/<id>/` | contract detail |
| GET | `/clm/contrats/<id>/risques/` | detected risks |
| GET | `/clm/contrats/<id>/alertes/` | alerts for the contract |
| GET | `/clm/contrats/<id>/pdf/` | **generate** a formatted contract PDF |

### Lifecycle & analysis

| Method | Path | Purpose |
|---|---|---|
| POST | `/clm/contrats/<id>/analyser/` | run the OCR → parse → risk pipeline |
| PUT | `/clm/contrats/<id>/update/` | edit a contract |
| POST | `/clm/contrats/<id>/submit/` | submit (leave `brouillon`) |

## Integrations

| Direction | With | Mechanism |
|---|---|---|
| out | service-notification | risk alerts via gateway (`NOTIFICATION_SERVICE_URL`, unauthenticated ingestion endpoint — see feature 6) |
| out | Cloudinary | contract media storage (`DEFAULT_FILE_STORAGE`) |
| in | feature 3 ids | `departement_id`/`direction_id` stored as ObjectId strings (no FK enforcement) |
| host | Tesseract binary | must be installed with the **French** language pack; `TESSERACT_CMD` overrides the path |

## Known limitations

- OCR requests are long: gunicorn/nginx timeouts must be ≥300 s (deployment guide) or workers get killed mid-analysis.
- `requirements.txt` is broken (UTF-16 machine freeze) — the curated dependency list lives in [../deployment/06-django-services.md](../deployment/06-django-services.md).
- Only Tesseract is implemented despite the `easyocr`/`azure` model choices.
- Risk alerts arrive at an unauthenticated notification endpoint — anyone reaching the gateway can forge alerts (see feature 6).
