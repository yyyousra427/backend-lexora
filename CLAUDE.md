# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Polyglot microservices backend (Lexora / "Sonatrach" legal-department app). Three stacks live side by side, one directory per service, tied together by a Eureka registry and a Spring Cloud Gateway. Code comments, log messages, and API messages are largely in French — keep new code consistent with the surrounding service.

## Services and ports

| Directory | Stack | Port | Purpose |
|---|---|---|---|
| `registry/` | Spring Boot (Eureka server) | 8761 | Service discovery |
| `gateway/` | Spring Cloud Gateway | 8083 | Single entry point for the frontend (localhost:3000) |
| `authentification/` | Django + MySQL (`loisonatrach`) | 8010 | Auth service; custom user model `api.User`; issues JWTs (simplejwt) |
| `affectation-service/` | Django + MySQL (`affectation-sonatrach`) | 8011 | Assignments |
| `service_clm/` | Django + MySQL (`clm_sounatrach`) | 8012 | Contract lifecycle mgmt: parsing, OCR (`ocr_utils.py`), risk engine, pushes alerts to service-notification |
| `service-juridique/` | Node/Express + MongoDB | 8084 | Org structure (directions, départements, activités, divisions…) |
| `bib-juridique/` | Node/Express + MongoDB | 8085 | Legal document library; multer uploads served statically at `/uploads` |
| `service-notification/` | Node/Express + MongoDB | 8004 | Notifications: REST + Socket.IO (`socket/socketHandler.js`) |

Gateway routing (`gateway/src/main/resources/application.yml`): `/auth/**` → 8010, `/affectation/**` → 8011, `/clm/**` → 8012 (Django services are routed by **hardcoded localhost port**, not load-balanced), while `/juridique/**`, `/notifications/**`, `/bib/**`, `/uploads/**` use Eureka discovery (`lb://`). All routes use `StripPrefix=0`, so **every service mounts its routes under its public prefix** (Django `urls.py` uses `auth/`, `clm/`; Express apps mount `/juridique`, `/bib`, `/notifications`). If you add a route in a service, it must include that prefix, and a new prefix needs a matching gateway route.

## Cross-service authentication contract

The Django `authentification` service signs HS256 JWTs with its `SECRET_KEY` (`authentification/authentification/settings.py`). Every Node service verifies tokens **locally** with the same value via `JWT_SECRET` in its `config.env`/`.env` — these must stay identical or auth silently breaks across services. Node auth middleware (e.g. `service-juridique/middleware/auth.js`) also fetches the user's profile/role through the gateway at `/auth/all_users/<id>/` and caches it in memory for 10 minutes.

## Running locally

There is no Docker or orchestration in use (Dockerfiles are commented out). Prerequisites: MySQL on localhost:3306 (`root`/`rootpassword` — DB credentials are hardcoded in each Django `settings.py`), MongoDB on localhost:27017 (`admin`/`admin123`, `authSource=admin`), JDK 21 for the Java services.

Start order: registry → gateway → business services.

```powershell
# Registry, then gateway (JDK 21 required; build fails on older JDKs)
cd registry;  .\mvnw.cmd spring-boot:run
cd gateway;   .\mvnw.cmd spring-boot:run

# Each Django service (port must match its .env EUREKA_PORT and the gateway route)
cd authentification;    pip install -r requirements.txt; python manage.py migrate; python manage.py runserver 8010
cd affectation-service; python manage.py runserver 8011
cd service_clm;         python manage.py runserver 8012

# Each Node service (port comes from config.env / .env)
cd service-juridique;   npm install; npm run dev   # nodemon; others: npm start
cd bib-juridique;       npm install; npm start
cd service-notification; npm install; npm start
```

Django services register with Eureka on startup via a background thread (`api/apps.py` → `eureka_client.py`), reading `EUREKA_APP_NAME`/`EUREKA_PORT` from the service's `.env`. Eureka app names (`AUTHENTICATION-SOUNATRACH`, `AFFECTATION-SOUNATRACH`, `CLM-SOUNATRACH`, `SERVICE-JURIDIQUE`…) are referenced by exact string elsewhere (gateway routes, `discovery.py` lookups) — spelling variants like "Sounatrach"/"Sonatrach" are inconsistent across the repo, so always copy the existing string rather than "fixing" it.

There are no real test suites: Django apps have stub `tests.py` (`python manage.py test` runs them), and the Node `test` scripts are placeholders.

## Conventions and gotchas

- Config lives in dotenv files: `.env` for Django services and service-notification, `config.env` for service-juridique and bib-juridique, with committed `*.env.example` templates documenting the shape. Django settings read everything via `python-decouple` (`DEBUG` defaults to False; dev `.env` sets it True). Put new config in env vars, never hardcoded.
- Node services follow the same layout: `app.js` (Express app + routes) / `server.js` (Mongo connect, listen, Eureka register) / `routes/`, `controllers/`, `middleware/`, `models/`, `services/` (Eureka client in `services/eurekaService.js`).
- Django services follow the same pattern as `authentification`: one API app with `serializers.py`, `views.py`, `permissions.py`, plus per-service `discovery.py` (Eureka lookup with 60s cache, falls back to gateway when `USE_EUREKA=false`) for calling other services.
- `bib-juridique` stores uploads on disk under `src/uploads/` and serves them at `/uploads`; the gateway exposes that path publicly.
- `service_clm` sends notifications to `service-notification` via `clm/notification_client.py`; risk alerts land on `/notifications/risk-alerts` (unauthenticated route, unlike the rest of that service).
- Known issues and technical debt are tracked as G-1…G-13 in `docs/TECHNICAL_REPORT.md` §9 — consult it before "discovering" them again. (`docs/archive/CODE_VERIFICATION_REPORT.md` is the superseded pre-hardening snapshot.)
- `docs/deployment/` contains the step-by-step VPS deployment guide, `docs/TECHNICAL_REPORT.md` the full technical inventory, and `docs/features/` per-feature endpoint/domain documentation — keep them in sync when changing ports, env variables, service names, or routes.
