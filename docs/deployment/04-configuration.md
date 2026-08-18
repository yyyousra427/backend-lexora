# Step 3 — Configuration & Secrets

Clone the code, generate fresh secrets, and make every service read its configuration from environment files instead of hardcoded values. This is the longest step; everything after it is mechanical.

Run everything below as the **`lexora`** user (`su - lexora` if you're still on `root`), unless a line starts with `sudo`.

## Step 1 — Clone the repo

```bash
sudo mkdir -p /opt/lexora
sudo chown lexora:lexora /opt/lexora
git clone <YOUR-REPO-URL> /opt/lexora
cd /opt/lexora
```

## Step 2 — Generate the shared secret

This single value becomes the Django `SECRET_KEY` **and** the cross-service JWT secret — you'll paste the exact same string into 5 files in Step 4.

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the printed value somewhere safe for the next step (a scratch file, your password manager — just not committed anywhere).

⚠ Quoting rule: if the generated secret contains `$`, `#`, or spaces, wrap it in **single quotes** when you paste it into the env files below.

## Step 3 — Gmail + Cloudinary credentials

The committed dev secrets (Gmail app password, Cloudinary API secret) are in git history — treat them as leaked.

- **Recommended:** create a **new Gmail app password** (Google account → Security → 2FA → App passwords) and revoke the old one; create a **new Cloudinary API secret** (Cloudinary console → regenerate), noting the cloud name + API key.
- **Faster path:** reuse the existing dev values from your local `authentification/.env` / `service_clm/.env` (not `.env.example`, which only has placeholders) — acceptable to get running sooner, but rotate before this repo/history is ever shared or made public.

Either way, have these four values ready before Step 4: `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`.

## Step 4 — Write the six env files

The shared secret from Step 2 goes into all five `SECRET_KEY`/`JWT_SECRET` fields below — **byte-identical**, or token verification breaks silently between services. `DB_PASSWORD` is the `lexora` MySQL password from [03-databases.md](03-databases.md); `MONGODB_URI` passwords are the MongoDB `admin` password from the same file.

**4.1 — `authentification/.env`**

```bash
nano /opt/lexora/authentification/.env
```

```ini
EUREKA_SERVER=http://localhost:8761/eureka/
EUREKA_APP_NAME=AUTHENTICATION-SOUNATRACH
EUREKA_HOST=localhost
EUREKA_PORT=8010

SECRET_KEY='<GENERATED-SECRET>'
DEBUG=False
ALLOWED_HOSTS=lexora.duckdns.org,localhost,127.0.0.1

DB_NAME=loisonatrach
DB_USER=lexora
DB_PASSWORD=<STRONG-MYSQL-PASSWORD>

EMAIL_HOST_USER=<gmail-address>
EMAIL_HOST_PASSWORD=<gmail-app-password>

CLOUDINARY_CLOUD_NAME=<cloud-name>
CLOUDINARY_API_KEY=<api-key>
CLOUDINARY_API_SECRET=<cloudinary-api-secret>
```

Save: `Ctrl+O`, Enter, `Ctrl+X`.

**4.2 — `affectation-service/.env`**

```bash
nano /opt/lexora/affectation-service/.env
```

```ini
EUREKA_SERVER=http://localhost:8761/eureka/
EUREKA_APP_NAME=AFFECTATION-SOUNATRACH
EUREKA_HOST=localhost
EUREKA_PORT=8011

SECRET_KEY='<GENERATED-SECRET>'
DEBUG=False
ALLOWED_HOSTS=lexora.duckdns.org,localhost,127.0.0.1

DB_NAME=affectation-sonatrach
DB_USER=lexora
DB_PASSWORD=<STRONG-MYSQL-PASSWORD>
```

**4.3 — `service_clm/.env`**

```bash
nano /opt/lexora/service_clm/.env
```

```ini
EUREKA_SERVER=http://localhost:8761/eureka/
EUREKA_APP_NAME=CLM-SOUNATRACH
EUREKA_HOST=localhost
EUREKA_PORT=8012

SECRET_KEY='<GENERATED-SECRET>'
DEBUG=False
ALLOWED_HOSTS=lexora.duckdns.org,localhost,127.0.0.1

DB_NAME=clm_sounatrach
DB_USER=lexora
DB_PASSWORD=<STRONG-MYSQL-PASSWORD>

CLOUDINARY_CLOUD_NAME=<cloud-name>
CLOUDINARY_API_KEY=<api-key>
CLOUDINARY_API_SECRET=<cloudinary-api-secret>

NOTIFICATION_SERVICE_URL=http://localhost:8083
```

**4.4 — `service-juridique/config.env`**

```bash
nano /opt/lexora/service-juridique/config.env
```

```ini
PORT=8084
NODE_ENV=production
SERVICE_NAME=service-juridique
MONGODB_URI=mongodb://admin:<STRONG-MONGO-PASSWORD>@localhost:27017/juridique_dbb?authSource=admin
EUREKA_HOST=localhost
EUREKA_PORT=8761
EUREKA_URL=http://localhost:8761/eureka
GATEWAY_URL=http://localhost:8083
JWT_SECRET='<GENERATED-SECRET>'
```

**4.5 — `bib-juridique/config.env`**

```bash
nano /opt/lexora/bib-juridique/config.env
```

```ini
PORT=8085
SERVICE_NAME=bib-juridique
MONGODB_URI=mongodb://admin:<STRONG-MONGO-PASSWORD>@localhost:27017/bib_juridique_db?authSource=admin
EUREKA_HOST=localhost
EUREKA_PORT=8761
GATEWAY_URL=http://localhost:8083
JWT_SECRET='<GENERATED-SECRET>'
```

**4.6 — `service-notification/.env`**

```bash
nano /opt/lexora/service-notification/.env
```

```ini
PORT=8004
NODE_ENV=production
MONGODB_URI=mongodb://admin:<STRONG-MONGO-PASSWORD>@localhost:27017/notification_base?authSource=admin
EUREKA_HOST=localhost
EUREKA_PORT=8761
EUREKA_SERVICE_NAME=service-notification
EUREKA_INSTANCE_HOST=localhost
EUREKA_URL=http://localhost:8761/eureka
GATEWAY_URL=http://localhost:8083
JWT_SECRET='<GENERATED-SECRET>'
```

## Step 5 — Verify the shared secret matches everywhere

```bash
grep -h -E "SECRET_KEY|JWT_SECRET" \
  /opt/lexora/authentification/.env \
  /opt/lexora/service-juridique/config.env \
  /opt/lexora/bib-juridique/config.env \
  /opt/lexora/service-notification/.env
```

All 4 lines printed must carry the identical value inside the quotes (the 5th place is `affectation-service`, which only needs it as `SECRET_KEY` for its own token signing — same check applies if it verifies tokens).

## Step 6 — Django settings (nothing to do)

✅ Already applied in the repo (Aug 2026): `authentification/authentification/settings.py`, `affectation-service/affectation_service/settings.py`, and `service_clm/service_clm/settings.py` all read `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, and the `DATABASES` block through `python-decouple`, plus WhiteNoise/`STATIC_ROOT` for serving admin static files under gunicorn. This step is just confirmation — the env files from Step 4 are what actually configure them.

## Step 7 — CORS: point at the real frontend origin

The dev configs allow `http://localhost:3000` (plus a few other localhost ports). You need your **frontend's** production origin — not the backend domain (`lexora.duckdns.org` is the backend and belongs in `ALLOWED_HOSTS` above). If the frontend ends up served from `https://lexora.duckdns.org` itself, same-origin requests need no CORS entry at all and you can skip this step.

Decide `<YOUR-FRONTEND-URL>` first (e.g. `https://app.example.com`), then edit all 5 spots:

**7.1 — Gateway** (`gateway/src/main/resources/application.yml`)

```bash
nano /opt/lexora/gateway/src/main/resources/application.yml
```

Find:
```yaml
            allowedOrigins:
              - "http://localhost:3000"
              - "http://127.0.0.1:3000"
```
Add your production origin as a new line in that list (keep or drop the localhost lines depending on whether you still need local testing against this server).

**7.2 / 7.3 / 7.4 — the three Django services**

```bash
nano /opt/lexora/authentification/authentification/settings.py
nano /opt/lexora/affectation-service/affectation_service/settings.py
nano /opt/lexora/service_clm/service_clm/settings.py
```

Each has an identical block near the end of the file:
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8083",
]
```
Add `"<YOUR-FRONTEND-URL>",` as a new entry in each of the three files.

**7.5 — `service-notification`** (`service-notification/app.js`)

```bash
nano /opt/lexora/service-notification/app.js
```

Find:
```javascript
app.use(cors({
    origin: ['http://localhost:3000', 'http://localhost:8083'],
    credentials: true
}));
```
Add `'<YOUR-FRONTEND-URL>'` to the `origin` array.

(`service-juridique` and `bib-juridique` use an open `cors()` with no allow-list — they're only reachable through the gateway, whose CORS rules apply first. Nothing to edit there.)

## Step 8 — Stop tracking env files in git

✅ Already applied: `.gitignore` covers `.env`/`config.env`, and every service ships a committed `*.env.example` / `config.env.example` template. One manual step remains — these files are still *tracked* from before `.gitignore` was added:

```bash
cd /opt/lexora
git rm --cached authentification/.env affectation-service/.env service_clm/.env \
  service-juridique/config.env bib-juridique/config.env service-notification/.env
git commit -m "stop tracking env files"
```

⚠ Anyone who pulls this commit elsewhere will have their local `.env` files deleted by git — they should copy them aside first, or recreate from the `*.env.example` templates.

## Done when

- [ ] Fresh `SECRET_KEY` generated (Step 2); Gmail + Cloudinary credentials either rotated or knowingly reused (Step 3)
- [ ] All six env files exist on the server with real values (Step 4), identical shared secret in the five JWT/SECRET_KEY spots (Step 5)
- [ ] The three `settings.py` files read secrets/DB/hosts from env, `DEBUG=False` (Step 6 — already true)
- [ ] CORS lists in all 5 places contain the production frontend origin (Step 7)
- [ ] `git status` shows no env file staged (Step 8)

Next: [05-registry-and-gateway.md](05-registry-and-gateway.md)
