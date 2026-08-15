# VPS Requirements

What the server needs before deployment starts. All eight services plus both databases run on one VPS.

## Sizing

| | Minimum (will run, tight) | Recommended |
|---|---|---|
| vCPU | 2 | **4** |
| RAM | 4 GB + 2 GB swap | **8 GB** |
| Disk | 40 GB SSD | **80 GB SSD** |
| OS | Ubuntu 22.04 LTS | **Ubuntu 24.04 LTS** (x86_64) |

### Where the memory goes (steady state)

| Process | RAM (approx.) |
|---|---|
| registry (JVM) | 300–500 MB |
| gateway (JVM) | 300–500 MB |
| authentification (gunicorn ×2 workers) | 150–300 MB |
| affectation-service (gunicorn ×2) | 150–300 MB |
| service_clm (gunicorn ×2) | 200–400 MB — **spikes +0.5–1 GB during OCR** of scanned PDFs |
| service-juridique (Node) | 100–150 MB |
| bib-juridique (Node) | 100–150 MB |
| service-notification (Node) | 100–150 MB |
| MySQL 8 | 400–800 MB |
| MongoDB | 500 MB–1 GB |
| nginx | ~20 MB |

Steady total ≈ 2.5–4 GB; OCR peaks push toward 5–6 GB. That is why 8 GB is the comfortable target and 4 GB needs swap.

### Disk growth to plan for

- **bib-juridique uploads** (`bib-juridique/src/uploads/`) — legal PDFs accumulate here on local disk; this is the main growth item. Include it in backups.
- MySQL + MongoDB data directories.
- Logs (journald, PM2, nginx).
- Build artifacts: two Spring Boot jars (~60 MB each), three Python venvs (~400 MB total), three `node_modules` (~300 MB total).

## Software the VPS must have

Installed in [02-server-setup.md](02-server-setup.md) — listed here so you can check a provider image against it.

| Software | Version | Why |
|---|---|---|
| OpenJDK | **21** (hard requirement) | registry + gateway target Java 21; older JDKs fail with *"release version 21 not supported"* |
| Python | 3.11+ (+ `python3-venv`, `python3-dev`) | three Django services |
| MySQL client headers | `default-libmysqlclient-dev`, `pkg-config`, `build-essential` | building the `mysqlclient` pip package |
| Node.js | 20 LTS | three Node services (Express 5 / Mongoose 9) |
| PM2 | latest (global npm) | process manager for the Node services |
| MySQL Server | 8.x | Django databases |
| MongoDB | 7.0 (Ubuntu 22.04) / 8.0 (24.04) | Node databases |
| Tesseract OCR | with **`tesseract-ocr-fra`** language pack | service_clm scanned-PDF OCR — contracts are in French |
| nginx | any current | reverse proxy + TLS termination |
| certbot | `python3-certbot-nginx` | Let's Encrypt certificates |
| git | any current | deploy from the repository |

## Network / firewall

Only three ports are open to the internet. Everything else stays loopback-only.

| Port | Exposure | Purpose |
|---|---|---|
| 22 | Public (restrict to your IP if possible) | SSH |
| 80 | Public | HTTP → redirects to HTTPS |
| 443 | Public | HTTPS → nginx → gateway |
| 8083 | **localhost only** | gateway (nginx proxies to it) |
| 8761 | **localhost only** | Eureka dashboard (view via SSH tunnel) |
| 8010–8012 | **localhost only** | Django services |
| 8084, 8085, 8004 | **localhost only** | Node services |
| 3306, 27017 | **localhost only** | MySQL, MongoDB |

A DNS **A record** for your API hostname (e.g. `api.example.com`) must point at the VPS IP before the TLS step.

## External accounts needed

| Account | Used by | Notes |
|---|---|---|
| Cloudinary | authentification, service_clm | media storage; you need cloud name, API key, API secret |
| Gmail app password | authentification | sends agent credentials by email; a dedicated Google account with 2FA + app password |
| Domain registrar | nginx/TLS | one subdomain for the API is enough |

> **Rotate before deploying:** the Cloudinary secret, Gmail app password, and Django `SECRET_KEY` currently sit in the repository's git history. Treat them as leaked — create fresh values as part of [04-configuration.md](04-configuration.md) and never reuse the committed ones.
