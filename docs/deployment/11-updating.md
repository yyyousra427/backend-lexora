# Step 9 — Updating a Running VPS (redeploy after a push)

Use this every time `master` receives new commits. The first-time steps (01–08) never need to be repeated; an update is: back up the env files → reset the checkout to `origin/master` → put the env files back → rebuild only what changed → restart → verify. Budget 5–10 minutes, most of it the gateway build when it's needed.

Run everything as the **`lexora`** user (`su - lexora` if you log in as `root`), unless a line starts with `sudo`.

## Why not just `git pull`?

The checkout on the VPS is not clean: the six env files were edited in place with production values (see [04-configuration.md](04-configuration.md)), and until Sept 2026 `node_modules/` and those env files were **tracked** in git. A plain `git pull` either refuses ("your local changes would be overwritten") or silently overwrites production config with whatever a developer last committed. `git reset --hard origin/master` with a backup/restore of the env files is deterministic: afterwards the code is *exactly* `origin/master`, and nothing else on the server (`.venv/`, `node_modules/`, `staticfiles/`, `target/`, `src/uploads/`, `ecosystem.config.js`) is touched, because those are untracked.

## Step 1 — Push from your machine

```bash
git status            # clean, on master
git push origin master
```

## Step 2 — Preview what will change (on the VPS)

```bash
ssh lexora@54.36.206.131
cd /opt/lexora

git fetch origin
OLD=$(git rev-parse HEAD); echo "currently deployed: $OLD"
git log --oneline HEAD..origin/master          # incoming commits
git status --short | grep -v node_modules      # local edits that Step 4 will discard
```

The `git status` line should list **only** the six env files (and nothing at all once they are git-ignored — see [04-configuration.md § Step 8](04-configuration.md#step-8--stop-tracking-env-files-in-git)). If any *other* tracked file shows as modified (`M gateway/src/main/resources/application.yml`, a `settings.py`, …), someone edited it by hand on the server: save its diff now (`git diff <file> > ~/hand-edit.patch`) and re-apply it after Step 5, or better, commit that change to the repo instead.

## Step 3 — Back up the six env files

```bash
BK=~/lexora-env-backup/$(date +%Y%m%d-%H%M%S)
for f in authentification/.env affectation-service/.env service_clm/.env \
         service-juridique/config.env bib-juridique/config.env service-notification/.env; do
  mkdir -p "$BK/$(dirname "$f")" && cp -a "$f" "$BK/$f"
done
find "$BK" -type f        # must list all six
```

Keep these backups — they are the only copy of the production secrets outside the live files.

## Step 4 — Update the code

```bash
git reset --hard origin/master
git log --oneline -1      # now shows the newest commit
```

## Step 5 — Restore the env files and confirm a clean tree

```bash
cp -a "$BK/." /opt/lexora/
git status --short | grep -v node_modules     # must print nothing
grep -c JWT_SECRET service-juridique/config.env bib-juridique/config.env service-notification/.env   # 1 each
```

If the status is not empty, the restore copied into the wrong place — check `find "$BK" -type f` and repeat the `cp`.

## Step 6 — Rebuild only what changed

```bash
git diff --name-only "$OLD" HEAD -- gateway registry \
  '*/requirements.txt' '*/migrations/*' '*/package.json' '*/package-lock.json' \
  ':!*/node_modules/*' | sort -u
```

Read the list and run the matching rows (skip the rest):

| Listed path | Run |
|---|---|
| anything under `gateway/` | `cd /opt/lexora/gateway && ./mvnw -q -DskipTests package` (~1–3 min) — then restart `lexora-gateway` in Step 7 |
| anything under `registry/` | `cd /opt/lexora/registry && ./mvnw -q -DskipTests package` — then restart `lexora-registry` in Step 7 **before** the gateway |
| `<service>/package.json` or `package-lock.json` | `cd /opt/lexora/<service> && npm ci --omit=dev` |
| `<service>/requirements.txt` | `cd /opt/lexora/<service> && .venv/bin/pip install -r requirements.txt` |
| `<service>/…/migrations/…` | `cd /opt/lexora/<service> && .venv/bin/python manage.py migrate` — let it finish; the Eureka `TimeoutError` noise it prints *after* "Applying …" is harmless, but a Ctrl-C mid-migration leaves a half-migrated schema (recovery: [SEED_TEST_DATA.md](../SEED_TEST_DATA.md) Step 3) |

**First update after 19 Sept 2026 only:** `node_modules/` was tracked in git before that date, so the reset in Step 4 removed the committed copy from disk and left a partial install behind. Reinstall all three once, regardless of the list above:

```bash
for s in service-juridique bib-juridique service-notification; do
  (cd /opt/lexora/$s && npm ci --omit=dev) || echo "npm ci FAILED in $s"
done
```

## Step 7 — Restart

Restart everything whose code changed. When unsure, restart all of them — a full restart costs ~30 s of downtime:

```bash
sudo systemctl restart lexora-gateway            # only if you rebuilt the jar (registry first, if rebuilt)
sudo systemctl restart lexora-auth lexora-affectation lexora-clm
cd /opt/lexora && pm2 restart all
```

Django units and PM2 apps re-read their env file on restart — a changed `.env`/`config.env` needs no rebuild, only this step.

## Step 8 — Verify

The short form of [09-verification.md](09-verification.md):

```bash
systemctl is-active lexora-registry lexora-gateway lexora-auth lexora-affectation lexora-clm
pm2 status                                                     # all online, ↺ column not climbing
curl -s localhost:8084/health; echo
curl -s localhost:8085/health; echo
curl -s localhost:8004/health; echo
curl -s -o /dev/null -w 'auth %{http_code}\n'        localhost:8010/auth/
curl -s -o /dev/null -w 'affectation %{http_code}\n' localhost:8011/affectation/
curl -s -o /dev/null -w 'clm %{http_code}\n'         localhost:8012/clm/
```

Then one authenticated call through the public URL — from the VPS or your own machine (proves nginx → gateway → Eureka → Node and the shared JWT secret):

```bash
BASE=https://lexora.duckdns.org
TOKEN=$(curl -s -X POST $BASE/auth/login/ -H 'Content-Type: application/json' \
  -d '{"email":"<test-email>","password":"<test-password>"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access"])')
curl -s -H "Authorization: Bearer $TOKEN" $BASE/juridique/dashboard/counters; echo
```

Expected: `{"success":true,"data":{"directionsCentrales":…,"directions":…}}`.

## Rollback

`$OLD` from Step 2 is the commit that was running before. To go back:

```bash
cd /opt/lexora
git reset --hard "$OLD"
cp -a "$BK/." /opt/lexora/        # env files again — the old commit may still track dev copies of them
```

then redo Step 6 (rebuild whatever differs between the two commits) and Step 7.

## Update-specific failures

| Symptom | Cause | Fix |
|---|---|---|
| Django unit fails right after restart; `journalctl -u lexora-auth` shows `Access denied for user 'root'@'localhost'` or `Can't connect to MySQL server on 'localhost:3307'` | Env file not restored (settings fell back to defaults), **or** a commit re-hardcoded a developer's local DB block in `settings.py` | Restore from `$BK` (Step 5); check `git show HEAD -- '*/settings.py'` for a `DATABASES` block without `config(...)` and revert it — production values live **only** in `.env` |
| PM2 app restart-loops with `Authentication failed` / `MongoServerError` | `config.env`/`.env` not restored, or the Mongo password's `@` is not URL-encoded as `%40` | Restore from `$BK`; check `MONGODB_URI` |
| PM2 app restart-loops with `Cannot find module` | `node_modules/` is a partial install after the reset | `npm ci --omit=dev` in that service, then `pm2 restart <name>` |
| Step 2 lists `M gateway/mvnw` / `M registry/mvnw`; after the reset `./mvnw` says `Permission denied` | Checkout older than 19 Sept 2026: the wrappers were committed non-executable and were `chmod +x`-ed by hand on the server (git reports the mode change as a modification) | Harmless to discard — from that date the executable bit is committed. On an older checkout: `chmod +x gateway/mvnw registry/mvnw` |
| Gateway behaviour (CORS, routes) unchanged after the update | `application.yml` is compiled into the jar — restarting without rebuilding runs the old jar | Step 6 `mvnw package`, then `sudo systemctl restart lexora-gateway` |
| `git status` after Step 5 still lists a `settings.py` or `application.yml` | A hand edit made on the server, discarded by the reset and re-applied from `~/hand-edit.patch` | Commit that change to the repo (`git apply` locally, push) so the next update doesn't need the patch |

## Done when

- [ ] `git log -1` on the VPS shows the commit you pushed, `git status --short | grep -v node_modules` is empty
- [ ] All systemd units active, all PM2 apps online with a stable restart count
- [ ] Six local health probes answer
- [ ] One authenticated call succeeds through `https://lexora.duckdns.org`
