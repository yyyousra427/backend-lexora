# Step 5 — Django Services (gunicorn + systemd)

Three services, same recipe each: virtualenv → dependencies → migrate → collectstatic → gunicorn unit. Ports are fixed by the gateway routes: **8010** authentification, **8011** affectation-service, **8012** service_clm.

## 0. Fix `service_clm/requirements.txt` first (one-time)

The committed file is a UTF-16 `pip freeze` of an entire dev machine (~190 packages incl. TensorFlow and Jupyter). `pip install -r` fails on it. Replace it entirely:

```bash
cat > /opt/lexora/service_clm/requirements.txt <<'EOF'
Django>=5.1,<5.2
djangorestframework>=3.15,<3.16
djangorestframework-simplejwt>=5.3,<5.4
mysqlclient>=2.2,<3.0
django-cors-headers>=4.4,<4.5
python-decouple==3.8
py-eureka-client==0.11.8
requests>=2.32
cloudinary>=1.39,<2.0
django-cloudinary-storage==0.3.0
Pillow>=10.0,<11.0
PyMuPDF>=1.26
pytesseract>=0.3.13
whitenoise>=6.7
gunicorn>=22.0
EOF
```

If a later `ImportError` names a missing package, add that one package — do not restore the old file.

## 1. authentification (port 8010)

```bash
cd /opt/lexora/authentification
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt gunicorn whitenoise
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser        # first admin account
```

Enable WhiteNoise so admin static files work with `DEBUG=False` — in `authentification/authentification/settings.py`, add to `MIDDLEWARE` directly after `SecurityMiddleware`:

```python
'whitenoise.middleware.WhiteNoiseMiddleware',
```

(Repeat this middleware line in the other two services as well.)

```bash
sudo nano /etc/systemd/system/lexora-auth.service
```

```ini
[Unit]
Description=Lexora authentification (Django, port 8010)
After=network.target mysql.service lexora-registry.service

[Service]
User=lexora
WorkingDirectory=/opt/lexora/authentification
ExecStart=/opt/lexora/authentification/.venv/bin/gunicorn authentification.wsgi:application \
  --bind 127.0.0.1:8010 --workers 2 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 2. affectation-service (port 8011)

```bash
cd /opt/lexora/affectation-service
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt gunicorn whitenoise
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
```

```bash
sudo nano /etc/systemd/system/lexora-affectation.service
```

```ini
[Unit]
Description=Lexora affectation-service (Django, port 8011)
After=network.target mysql.service lexora-registry.service

[Service]
User=lexora
WorkingDirectory=/opt/lexora/affectation-service
ExecStart=/opt/lexora/affectation-service/.venv/bin/gunicorn affectation_service.wsgi:application \
  --bind 127.0.0.1:8011 --workers 2 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Note the module name: the **directory** is `affectation-service` but the **Python package** is `affectation_service` (underscore).

## 3. service_clm (port 8012)

```bash
cd /opt/lexora/service_clm
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
```

```bash
sudo nano /etc/systemd/system/lexora-clm.service
```

```ini
[Unit]
Description=Lexora service_clm (Django + OCR, port 8012)
After=network.target mysql.service lexora-registry.service

[Service]
User=lexora
WorkingDirectory=/opt/lexora/service_clm
ExecStart=/opt/lexora/service_clm/.venv/bin/gunicorn service_clm.wsgi:application \
  --bind 127.0.0.1:8012 --workers 2 --timeout 300
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`--timeout 300` is deliberate: OCR of a long scanned contract can exceed gunicorn's default 30 s and would otherwise kill the worker mid-request.

## 4. Start everything

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lexora-auth lexora-affectation lexora-clm
systemctl status lexora-auth lexora-affectation lexora-clm
```

## 5. Verify

```bash
curl -s http://localhost:8010/auth/ -o /dev/null -w '%{http_code}\n'   # DRF response, not 502
curl -sI http://localhost:8011/affectation/ | head -1
curl -sI http://localhost:8012/clm/ | head -1
```

Then check the Eureka dashboard (SSH tunnel): **AUTHENTICATION-SOUNATRACH**, **AFFECTATION-SOUNATRACH**, **CLM-SOUNATRACH** all UP. Each gunicorn worker registers the same instance — duplicate registrations of the same host:port are harmless.

## Done when

- Three units `active (running)`, three Eureka names UP
- `curl http://localhost:8083/auth/...` through the gateway reaches Django

Next: [07-node-services.md](07-node-services.md)
