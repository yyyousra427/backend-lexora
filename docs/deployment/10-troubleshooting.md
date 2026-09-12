# Troubleshooting

Symptom → cause → fix, for the failure modes this specific stack actually produces.

## Build & install

| Symptom | Cause | Fix |
|---|---|---|
| Maven: `release version 21 not supported` | Shell is using a JDK older than 21 | `sudo apt install openjdk-21-jdk`, then `sudo update-alternatives --config java`; verify `java -version` → 21.x |
| `pip install -r requirements.txt` fails in `service_clm` with a Unicode/parse error | The committed file is UTF-16 and lists ~190 unrelated packages | Replace it with the minimal list in [06-django-services.md](06-django-services.md#0-fix-service_clmrequirementstxt-first-one-time) |
| `mysqlclient` fails to build (`mysql_config not found` / missing headers) | Missing system packages | `sudo apt install build-essential pkg-config default-libmysqlclient-dev python3-dev` |
| `npm ci` fails in bib-juridique | Stale committed `node_modules` conflicting | `rm -rf node_modules package-lock.json && npm install --omit=dev` |

## Auth

| Symptom | Cause | Fix |
|---|---|---|
| Login works, but **Node routes** (`/juridique`, `/bib`, `/notifications`) return 401 while Django routes work | JWT secret drift — Node's `JWT_SECRET` ≠ Django's `SECRET_KEY` | Make all five locations byte-identical ([04-configuration.md](04-configuration.md#the-shared-jwt-secret)); watch quoting of `$`/`#` in env files; restart the affected services |
| Every route returns 401 after redeploy | `SECRET_KEY` rotated → all old tokens invalid (expected) | Log in again for a fresh token |
| Node middleware logs `/auth/all_users/<id>/ échoué` | Gateway or authentification down, or `GATEWAY_URL` wrong in the Node env file | Check `systemctl status lexora-gateway lexora-auth`; verify `GATEWAY_URL=http://localhost:8083` |

## Discovery & routing

| Symptom | Cause | Fix |
|---|---|---|
| Gateway 503 on `/juridique`, `/bib`, or `/notifications` | Eureka `lb://` can't resolve — service not registered or name mismatch | Check the dashboard (SSH tunnel to 8761). Names are exact strings; a service that died after registering takes ~90 s to be evicted |
| Gateway 502 on `/auth`, `/affectation`, or `/clm` | Django service not listening on its hardcoded route port | `curl localhost:8010/8011/8012` directly; gunicorn `--bind` port must equal the gateway route **and** the `.env` `EUREKA_PORT` |
| Service shows UP in Eureka but requests fail | Registered with a wrong instance host/port | On a single VPS all `EUREKA_HOST` values must stay `localhost` |
| A new endpoint 404s through the gateway but works on the service port | Route prefix missing — gateway uses `StripPrefix=0` | Mount the route under its public prefix (`/auth`, `/clm`, `/juridique`, …) or add a gateway route for the new prefix, rebuild, restart |

## Databases

| Symptom | Cause | Fix |
|---|---|---|
| Node service in a PM2 restart loop, logs show Mongo auth error | Wrong URI credentials or missing `authSource=admin` | URI shape: `mongodb://admin:<pw>@localhost:27017/<db>?authSource=admin` |
| Django `(1049, "Unknown database ...")` | Schema not created | Create it — remember backticks around `affectation-sonatrach` ([03-databases.md](03-databases.md)) |
| Django `(1045, "Access denied ...")` | Wrong `DB_USER`/`DB_PASSWORD` in `.env`, or grants missing | Re-check grants for `'lexora'@'localhost'` on all three schemas |

## Web layer

| Symptom | Cause | Fix |
|---|---|---|
| Browser CORS/preflight errors | Frontend origin missing from one of the five CORS lists | Update all lists in [04-configuration.md](04-configuration.md#5-cors--point-everything-at-the-real-frontend-origin); the gateway needs a rebuild + restart after its yml changes |
| CORS error only from a developer's machine (preflight answers `403`) | The tab is not on `http://localhost:<port>` / `http://127.0.0.1:<port>` (e.g. `https://localhost`, a LAN IP like `192.168.x.x`), or the API base is `http://` and the 301 to HTTPS fails the preflight | Any localhost port is accepted by the pattern rules; open the app on `http://localhost:<port>` and use `https://lexora.duckdns.org` as API base. `curl -si -X OPTIONS https://lexora.duckdns.org/auth/login/ -H 'Origin: http://localhost:5173' -H 'Access-Control-Request-Method: POST'` must answer `200` with `Access-Control-Allow-Origin` |
| `413 Request Entity Too Large` on document upload | nginx default 1 MB body limit | `client_max_body_size 50m;` in the server block, `sudo systemctl reload nginx` |
| Upload/OCR request dies at ~30–60 s | gunicorn or nginx timeout | CLM unit uses `--timeout 300`; nginx `proxy_read_timeout 300s` |
| Django admin loads without CSS | `DEBUG=False` and static files not served | WhiteNoise middleware + `STATIC_ROOT` + `collectstatic` ([06-django-services.md](06-django-services.md)) |
| Django 400 on every request | Host missing from `ALLOWED_HOSTS` | Add the API hostname to the service's `.env` `ALLOWED_HOSTS` |

## OCR

| Symptom | Cause | Fix |
|---|---|---|
| `TesseractNotFoundError` | Binary missing or not on PATH for the service user | `sudo apt install tesseract-ocr tesseract-ocr-fra`; or set `TESSERACT_CMD` in `service_clm/.env` |
| OCR returns garbage/empty text for French contracts | French language pack missing (default lang is `fra+eng` — both packs required) | `sudo apt install tesseract-ocr-fra`; verify `tesseract --list-langs` shows `fra` and `eng` |
| Large scanned contract analysis dies with 502/504 after ~5 min | OCR at 300 DPI takes ~5–15 s/page on 2 vCores; a 30+-page scan can exceed the 300 s gunicorn/nginx timeouts | Set `PDF_OCR_DPI=200` in `service_clm/.env` (≈2× faster, still readable), or raise `--timeout` in `lexora-clm.service` and `proxy_read_timeout` in nginx to 600 |

## Where the logs are

```bash
journalctl -u lexora-registry -f        # or -gateway, -auth, -affectation, -clm
pm2 logs service-juridique              # or bib-juridique, service-notification
sudo tail -f /var/log/nginx/error.log
sudo journalctl -u mysql -f
sudo tail -f /var/log/mongodb/mongod.log
```
