# Feature 4 — Legal Document Library (Bibliothèque Juridique)

| | |
|---|---|
| **Service** | `bib-juridique/` — Node, Express 5.2, Mongoose 9.7, multer 2.1, port 8085 |
| **Database** | MongoDB `bib_juridique_db` + **local filesystem** `src/uploads/` |
| **Public prefixes** | `/bib` (API) and `/uploads` (static files) — both `lb://bib-juridique` |
| **Eureka name** | `bib-juridique` |

## What it does

A library of legal reference documents (laws, decrees, templates): upload a PDF with its metadata, browse, full-text search over metadata, download. The PDF binary lands on **local disk**; MongoDB stores the metadata document (`DocumentJuridique`) including the file's public URL.

## Storage model

| Piece | Where | Notes |
|---|---|---|
| PDF binary | `bib-juridique/src/uploads/` | written by multer (`upload.single("pdf")`), served statically |
| Metadata | `DocumentJuridique` collection | title/description/category fields + `pdf` URL pointing at `/uploads/<filename>` |
| Public access | `GET /uploads/<filename>` through the gateway | Express static handler |

`fix-document-urls.js` is a one-off maintenance script that rewrites stored URLs (e.g. after a host/port change).

## Endpoint reference

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/bib/documents` | JWT | create document — multipart form, file field **`pdf`** + metadata fields |
| GET | `/bib/documents` | JWT | list all documents |
| GET | `/bib/search?q=…` | JWT | search documents |
| GET | `/bib/documents/:id` | JWT | document detail |
| PUT | `/bib/documents/:id` | JWT | update metadata and optionally replace the PDF (`pdf` field) |
| DELETE | `/bib/documents/:id` | admin | delete document |
| GET | `/uploads/<filename>` | none | download/serve the PDF (static; stays public for direct rendering) |
| GET | `/health` | none | liveness — returns an uploads file count |

## Upload flow

1. Client `POST /bib/documents` (multipart, `pdf` + metadata).
2. multer writes the file to `src/uploads/` with a generated filename.
3. Controller saves a `DocumentJuridique` with the metadata and the `/uploads/...` URL.
4. Clients render/download via the returned URL — the gateway forwards `/uploads/**` to this service's static handler.

Uploads above ~1 MB require the nginx `client_max_body_size 50m` setting from the deployment guide; without it the proxy rejects real PDFs with HTTP 413.

## Known limitations (all verified in code)

- ~~No authentication on `/bib` routes~~ **Fixed (Aug 2026)**: all `/bib` endpoints now require a JWT; `DELETE` additionally requires the `admin` role. If other roles should be allowed to delete, adjust `checkRole("admin")` in `documentRoutes.js`.
- `/uploads/<filename>` (the static PDFs themselves) remains **public by design** so documents render via direct link; the filenames are random multer-generated names. Put it behind auth too if document confidentiality requires it.
- Files live on **local disk**: lost if the host dies, unshareable across multiple instances, and invisible to Mongo backups. Back up `src/uploads/` explicitly (deployment guide, step 2) or move to object storage.
- No file-type/size validation is enforced at the route level beyond multer's field name; treat uploaded content as untrusted.
