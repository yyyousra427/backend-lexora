# Step 8 — Verification & Smoke Tests

Run these after every deployment. Together they prove routing, discovery, the shared JWT contract, and the file pipeline — the four things that break silently.

## 1. Process health (on the VPS)

```bash
systemctl is-active lexora-registry lexora-gateway lexora-auth lexora-affectation lexora-clm
pm2 status
sudo systemctl is-active mysql mongod nginx
```

All must report `active` / `online`.

## 2. Eureka registrations

Through an SSH tunnel (`ssh -L 8761:localhost:8761 lexora@<VPS-IP>`), open `http://localhost:8761` and confirm **seven** clients UP:

`GATEWAY-SERVICE`, `AUTHENTICATION-SOUNATRACH`, `AFFECTATION-SOUNATRACH`, `CLM-SOUNATRACH`, `SERVICE-JURIDIQUE`, `BIB-JURIDIQUE`, `SERVICE-NOTIFICATION`

## 3. Service health endpoints (on the VPS)

Health routes live at each service's root and are **not** routed by the gateway — probe the ports directly:

| Command | Expected |
|---|---|
| `curl -s localhost:8084/health` | `{"status":"UP","service":"service-juridique"}` |
| `curl -s localhost:8085/health` | `{"success":true,...,"status":"UP"}` |
| `curl -s localhost:8004/health` | `{"status":"UP","service":"notification"}` |
| `curl -s -o /dev/null -w '%{http_code}' localhost:8010/auth/` | non-5xx from Django |
| `curl -s -o /dev/null -w '%{http_code}' localhost:8011/affectation/` | non-5xx from Django |
| `curl -s -o /dev/null -w '%{http_code}' localhost:8012/clm/` | non-5xx from Django |

## 4. Routing through the public URL

From your own machine:

```bash
BASE=https://api.example.com

# gateway → Django (hardcoded-port route)
curl -s -o /dev/null -w '%{http_code}\n' $BASE/auth/

# gateway → Node via Eureka lb://
curl -s $BASE/juridique/directions | head -c 300
```

## 5. The auth contract, end to end

This is the test that catches JWT-secret drift:

```bash
# 1. login (adjust the endpoint/fields to your auth API)
TOKEN=$(curl -s -X POST $BASE/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"<admin-email>","password":"<password>"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access"])')

# 2. use the Django-issued token against a NODE service
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $TOKEN" $BASE/juridique/directions
```

`200` proves the token signed by Django verifies inside Node — the shared secret is in sync. A `401` **only on Node routes** means one of the five secret locations drifted ([04-configuration.md](04-configuration.md#the-shared-jwt-secret)).

## 6. File pipeline

```bash
# upload a document (authenticated), then fetch it back through /uploads
curl -s -H "Authorization: Bearer $TOKEN" -F "file=@test.pdf" $BASE/bib/...   # adjust to the upload endpoint
curl -s -o /dev/null -w '%{http_code}\n' $BASE/uploads/<returned-filename>
```

Uploading a file larger than a few MB also verifies the nginx `client_max_body_size` setting.

## 7. CLM → notification chain

Trigger a contract analysis that produces a risk alert (via the frontend or `POST` to the CLM API), then:

```bash
curl -s -H "Authorization: Bearer $TOKEN" $BASE/notifications/ | head -c 300
```

The alert created by `service_clm` should appear — this proves the internal `service_clm → gateway → service-notification` call path.

## Full checklist

- [ ] All systemd units active, all PM2 apps online
- [ ] 7 Eureka registrations UP
- [ ] 6 local health probes pass
- [ ] `/auth` and `/juridique` answer through the public URL
- [ ] Django-issued token accepted by a Node service (no secret drift)
- [ ] Upload + `/uploads` fetch round-trip works
- [ ] CLM risk alert reaches `/notifications`
- [ ] Frontend origin passes CORS in a real browser
- [ ] Server reboot test: `sudo reboot`, wait, re-run steps 1–4 (everything must come back by itself)
