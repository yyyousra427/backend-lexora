# Step 6 — Node Services (PM2)

Three Express services under PM2: **service-juridique** (8084), **bib-juridique** (8085), **service-notification** (8004). Each reads its own `config.env` / `.env` written in [04-configuration.md](04-configuration.md).

## 1. Install dependencies

```bash
cd /opt/lexora/service-juridique && npm ci --omit=dev
cd /opt/lexora/bib-juridique && npm ci --omit=dev
cd /opt/lexora/service-notification && npm ci --omit=dev
```

(`node_modules/` is git-ignored and untracked since 19 Sept 2026; on a checkout older than that, `rm -rf node_modules` first — bib-juridique's committed copy was stale.)

(`npm ci` uses the lockfile where present; if a service lacks `package-lock.json`, fall back to `npm install --omit=dev`.)

## 2. Make sure the uploads directory exists

bib-juridique writes uploaded documents to local disk and serves them at `/uploads`:

```bash
mkdir -p /opt/lexora/bib-juridique/src/uploads
```

This directory is the system's document store — include it in backups (see [03-databases.md](03-databases.md#backups-set-up-now-thank-yourself-later)).

## 3. PM2 ecosystem file

```bash
nano /opt/lexora/ecosystem.config.js
```

```javascript
module.exports = {
  apps: [
    {
      name: 'service-juridique',
      cwd: '/opt/lexora/service-juridique',
      script: 'server.js',
      env: { NODE_ENV: 'production' },
      max_memory_restart: '300M',
    },
    {
      name: 'bib-juridique',
      cwd: '/opt/lexora/bib-juridique',
      script: 'server.js',
      env: { NODE_ENV: 'production' },
      max_memory_restart: '300M',
    },
    {
      name: 'service-notification',
      cwd: '/opt/lexora/service-notification',
      script: 'server.js',
      env: { NODE_ENV: 'production' },
      max_memory_restart: '300M',
    },
  ],
};
```

Ports and Mongo URIs are **not** set here on purpose — each service loads them itself from its `config.env` / `.env` at startup.

## 4. Start, persist, boot-enable

```bash
cd /opt/lexora
pm2 start ecosystem.config.js
pm2 status
pm2 save                      # remember the process list
pm2 startup systemd           # prints one sudo command — run it
```

Each service connects to MongoDB first and **exits immediately if Mongo is unreachable** (PM2 will restart it, so a Mongo outage shows as a restart loop — check `pm2 logs`).

## 5. Verify

```bash
curl -s http://localhost:8084/health    # {"status":"UP","service":"service-juridique"}
curl -s http://localhost:8085/health    # {"success":true,...,"status":"UP"}
curl -s http://localhost:8004/health    # {"status":"UP","service":"notification"}

# through the gateway (Eureka lb:// resolution):
curl -s http://localhost:8083/juridique/directions | head -c 300
```

Eureka dashboard should now show all seven clients: gateway + three Django + **SERVICE-JURIDIQUE**, **BIB-JURIDIQUE**, **SERVICE-NOTIFICATION**.

## Known limitation — real-time notifications

`service-notification` declares Socket.IO and ships a full handler (`socket/socketHandler.js`), but `server.js` **never attaches it** — as deployed, notifications work over REST only (`/notifications/**`). If real-time delivery is wired up later, the nginx `location /socket.io/` block in [08-nginx-and-https.md](08-nginx-and-https.md) is already prepared for it.

## Done when

- `pm2 status` shows all three online with stable uptime (no restart loops)
- All three `/health` endpoints answer locally
- `/juridique/**` works **through the gateway** (proves Eureka discovery end-to-end)

Next: [08-nginx-and-https.md](08-nginx-and-https.md)
