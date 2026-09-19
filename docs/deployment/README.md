# Lexora Backend — Deployment Guide

Step-by-step guide for deploying the full Lexora microservices backend on a single VPS (Ubuntu 22.04 / 24.04 LTS). Follow the files **in numeric order** — each step assumes the previous ones are done.

## Guide index

| Step | File | What it covers |
|---|---|---|
| — | [01-vps-requirements.md](01-vps-requirements.md) | VPS sizing, OS, software inventory, firewall ports, external accounts |
| 1 | [02-server-setup.md](02-server-setup.md) | User, firewall, JDK 21, Python, Node, PM2, nginx, Tesseract |
| 2 | [03-databases.md](03-databases.md) | MySQL 8 + MongoDB install, users, the three schemas |
| 3 | [04-configuration.md](04-configuration.md) | Clone, secrets rotation, env files per service, production settings |
| 4 | [05-registry-and-gateway.md](05-registry-and-gateway.md) | Build the Spring Boot jars, systemd units |
| 5 | [06-django-services.md](06-django-services.md) | The three Django services under gunicorn + systemd |
| 6 | [07-node-services.md](07-node-services.md) | The three Node services under PM2 |
| 7 | [08-nginx-and-https.md](08-nginx-and-https.md) | Reverse proxy, TLS with certbot, upload sizes, WebSocket |
| 8 | [09-verification.md](09-verification.md) | Smoke tests — prove every route and the auth contract |
| — | [10-troubleshooting.md](10-troubleshooting.md) | Symptom → cause → fix for the known failure modes |
| 9 | [11-updating.md](11-updating.md) | **Redeploying after a push** — the only step you repeat: env-file backup, reset to `origin/master`, rebuild what changed, restart, verify |

## Target environment

| | |
|---|---|
| **VPS IP** | `54.36.206.131` |
| **Backend domain** | `lexora.duckdns.org` (DuckDNS; A record → 54.36.206.131, verified 16 Aug 2026) |
| **Public base URL** | `https://lexora.duckdns.org` after step 7 (TLS) |

If the VPS IP ever changes, update it in the [DuckDNS dashboard](https://www.duckdns.org) for the `lexora` subdomain — nothing else in the stack hardcodes the IP.

## What you are deploying

Eight services behind a Spring Cloud Gateway, discovered via Eureka. The React frontend is the only intended client and talks exclusively to the gateway.

| Service | Stack | Port | Datastore | Public route |
|---|---|---|---|---|
| registry | Spring Boot (Eureka) | 8761 | — | — (internal) |
| gateway | Spring Cloud Gateway | 8083 | — | all traffic |
| authentification | Django | 8010 | MySQL `loisonatrach` | `/auth/**` |
| affectation-service | Django | 8011 | MySQL `affectation-sonatrach` | `/affectation/**` |
| service_clm | Django (OCR) | 8012 | MySQL `clm_sounatrach` | `/clm/**` |
| service-juridique | Node/Express | 8084 | Mongo `juridique_dbb` | `/juridique/**` |
| bib-juridique | Node/Express | 8085 | Mongo `bib_juridique_db` | `/bib/**`, `/uploads/**` |
| service-notification | Node/Express | 8004 | Mongo `notification_base` | `/notifications/**` |

Start order on the server: **databases → registry → gateway → Django services → Node services**. The systemd/PM2 setup in steps 4–6 encodes this order so it survives reboots.

## Three invariants — break one and the system half-works

1. **One shared JWT secret.** Django `authentification` signs tokens with its `SECRET_KEY`; every Node service verifies them locally against `JWT_SECRET`. The value must be identical in all five places (see [04-configuration.md](04-configuration.md#the-shared-jwt-secret)). Drift shows up as 401s in only some services.
2. **Django port = `EUREKA_PORT` = gateway route port.** The gateway routes `/auth`, `/affectation`, `/clm` to hardcoded ports 8010/8011/8012. Each Django service must actually listen on that port and advertise it in its `.env`.
3. **Eureka app names are exact strings** — including the inconsistent spellings (`AUTHENTICATION-SOUNATRACH`, `affectation-sonatrach` DB, `clm_sounatrach` DB). Copy them verbatim; never "fix" the spelling.
