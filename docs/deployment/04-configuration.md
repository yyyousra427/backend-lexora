# Step 3 — Configuration & Secrets

Clone the code, generate fresh secrets, and make every service read its configuration from environment files instead of hardcoded values. This is the longest step; everything after it is mechanical.

## 1. Clone

```bash
sudo mkdir -p /opt/lexora
sudo chown lexora:lexora /opt/lexora
git clone <YOUR-REPO-URL> /opt/lexora
cd /opt/lexora
```

## 2. Generate fresh secrets

The committed dev secrets (Django `SECRET_KEY`, Gmail app password, Cloudinary secret, DB passwords) are in git history — **treat them as leaked, never reuse them**.

```bash
# New Django SECRET_KEY — this is also the cross-service JWT secret
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Also create now, at the providers:

- a **new Gmail app password** (Google account → Security → 2FA → App passwords), and revoke the old one
- a **new Cloudinary API secret** (Cloudinary console → regenerate), and note cloud name + API key

## The shared JWT secret

The generated `SECRET_KEY` must be **byte-identical** in these five places, or token verification fails only in the services that drifted:

| # | File | Variable |
|---|---|---|
| 1 | `authentification/.env` | `SECRET_KEY` |
| 2 | `service-juridique/config.env` | `JWT_SECRET` |
| 3 | `bib-juridique/config.env` | `JWT_SECRET` |
| 4 | `service-notification/.env` | `JWT_SECRET` |
| 5 | any future service verifying tokens | `JWT_SECRET` |

Quoting rule: if the secret contains `$`, `#` or spaces, wrap it in **single quotes** in the env files (dotenv and PowerShell both mangle unquoted specials).

## 3. Django services — settings changes (one-time code edit)

All three Django services hardcode secrets in `settings.py`. Replace the hardcoded blocks with `python-decouple` reads (already a dependency). Apply this pattern in **`authentification/authentification/settings.py`**, **`affectation-service/affectation_service/settings.py`**, and **`service_clm/service_clm/settings.py`**:

```python
from decouple import config

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER', default='lexora'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
    }
}

# static files for admin under gunicorn (used in step 5)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
```

In `authentification` additionally:

```python
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
```

In `authentification` and `service_clm` (Cloudinary):

```python
cloudinary.config(
    cloud_name=config('CLOUDINARY_CLOUD_NAME'),
    api_key=config('CLOUDINARY_API_KEY'),
    api_secret=config('CLOUDINARY_API_SECRET'),
)
```

## 4. Env files — full production contents

### `authentification/.env`

```ini
EUREKA_SERVER=http://localhost:8761/eureka/
EUREKA_APP_NAME=AUTHENTICATION-SOUNATRACH
EUREKA_HOST=localhost
EUREKA_PORT=8010

SECRET_KEY='<GENERATED-SECRET>'
DEBUG=False
ALLOWED_HOSTS=api.example.com,localhost,127.0.0.1

DB_NAME=loisonatrach
DB_PASSWORD=<STRONG-MYSQL-PASSWORD>

EMAIL_HOST_USER=<system-gmail-address>
EMAIL_HOST_PASSWORD=<new-gmail-app-password>

CLOUDINARY_CLOUD_NAME=<cloud-name>
CLOUDINARY_API_KEY=<api-key>
CLOUDINARY_API_SECRET=<new-api-secret>
```

### `affectation-service/.env`

```ini
EUREKA_SERVER=http://localhost:8761/eureka/
EUREKA_APP_NAME=AFFECTATION-SOUNATRACH
EUREKA_HOST=localhost
EUREKA_PORT=8011

SECRET_KEY='<GENERATED-SECRET>'
DEBUG=False
ALLOWED_HOSTS=api.example.com,localhost,127.0.0.1

DB_NAME=affectation-sonatrach
DB_PASSWORD=<STRONG-MYSQL-PASSWORD>
```

### `service_clm/.env`

```ini
EUREKA_SERVER=http://localhost:8761/eureka/
EUREKA_APP_NAME=CLM-SOUNATRACH
EUREKA_HOST=localhost
EUREKA_PORT=8012

SECRET_KEY='<GENERATED-SECRET>'
DEBUG=False
ALLOWED_HOSTS=api.example.com,localhost,127.0.0.1

DB_NAME=clm_sounatrach
DB_PASSWORD=<STRONG-MYSQL-PASSWORD>

CLOUDINARY_CLOUD_NAME=<cloud-name>
CLOUDINARY_API_KEY=<api-key>
CLOUDINARY_API_SECRET=<new-api-secret>

NOTIFICATION_SERVICE_URL=http://localhost:8083
```

### `service-juridique/config.env`

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

### `bib-juridique/config.env`

```ini
PORT=8085
SERVICE_NAME=bib-juridique
MONGODB_URI=mongodb://admin:<STRONG-MONGO-PASSWORD>@localhost:27017/bib_juridique_db?authSource=admin
EUREKA_HOST=localhost
EUREKA_PORT=8761
GATEWAY_URL=http://localhost:8083
JWT_SECRET='<GENERATED-SECRET>'
```

### `service-notification/.env`

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

## 5. CORS — point everything at the real frontend origin

The dev configs pin CORS to `http://localhost:3000`. Add/replace with your real frontend origin (e.g. `https://app.example.com`) in **all** of:

| File | What to change |
|---|---|
| `gateway/src/main/resources/application.yml` | `allowedOrigins` list under `globalcors` |
| `authentification/.../settings.py` | `CORS_ALLOWED_ORIGINS` |
| `affectation-service/.../settings.py` | `CORS_ALLOWED_ORIGINS` |
| `service_clm/.../settings.py` | `CORS_ALLOWED_ORIGINS` |
| `service-notification/app.js` | `cors({ origin: [...] })` array |

(`service-juridique` and `bib-juridique` use open `cors()` — they are only reachable through the gateway, whose CORS applies.)

## 6. Stop committing env files

```bash
cat >> .gitignore <<'EOF'
# environment files — real secrets live only on the server
.env
config.env
**/staticfiles/
EOF
```

Keep a `*.env.example` copy of each file (with placeholder values) in the repo so the shape stays documented.

## Done when

- Fresh `SECRET_KEY` generated; Gmail + Cloudinary credentials rotated at the provider
- All six env files above exist on the server with real values, identical JWT secret in the five places
- The three `settings.py` files read secrets/DB/hosts from env, `DEBUG=False`
- CORS lists contain the production frontend origin
- `git status` shows no env file staged

Next: [05-registry-and-gateway.md](05-registry-and-gateway.md)
