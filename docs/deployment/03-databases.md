# Step 2 — Databases

MySQL 8 for the three Django services, MongoDB for the three Node services. Both bind to localhost only (the Ubuntu defaults), which is what we want.

## MySQL 8

### Install and secure

```bash
sudo apt install -y mysql-server
sudo mysql_secure_installation
sudo systemctl enable --now mysql
```

### Create the app user and the three schemas

Pick a strong password for the `lexora` MySQL user — it goes into the Django `.env` files in [04-configuration.md](04-configuration.md).

```bash
sudo mysql
```

```sql
CREATE USER 'lexora'@'localhost' IDENTIFIED BY '<STRONG-MYSQL-PASSWORD>';

CREATE DATABASE loisonatrach CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE `affectation-sonatrach` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE clm_sounatrach CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES ON loisonatrach.* TO 'lexora'@'localhost';
GRANT ALL PRIVILEGES ON `affectation-sonatrach`.* TO 'lexora'@'localhost';
GRANT ALL PRIVILEGES ON clm_sounatrach.* TO 'lexora'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Two naming traps, both deliberate — the code expects these exact names:

- `affectation-sonatrach` contains a **hyphen** → always backtick-quote it in SQL.
- The spellings are inconsistent on purpose (`loisonatrach`, `-sonatrach`, `_sounatrach`). Do not normalize them.

## MongoDB

### Install (Ubuntu 24.04 → MongoDB 8.0)

```bash
curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | \
  sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list
sudo apt update
sudo apt install -y mongodb-org
sudo systemctl enable --now mongod
```

On Ubuntu 22.04, use the `jammy/mongodb-org/7.0` repo line and the `server-7.0.asc` key instead.

### Create the admin user

The services connect as an admin-database user (their URIs use `authSource=admin`). Pick a strong password — it replaces the `admin123` from the dev configs.

```bash
mongosh
```

```javascript
use admin
db.createUser({
  user: "admin",
  pwd: "<STRONG-MONGO-PASSWORD>",
  roles: [ { role: "root", db: "admin" } ]
})
exit
```

### Enable authentication

```bash
sudo nano /etc/mongod.conf
```

```yaml
security:
  authorization: enabled
```

```bash
sudo systemctl restart mongod
# verify auth works:
mongosh -u admin -p '<STRONG-MONGO-PASSWORD>' --authenticationDatabase admin --eval 'db.adminCommand({ ping: 1 })'
```

The three databases (`juridique_dbb`, `bib_juridique_db`, `notification_base`) are created automatically on first write — no need to pre-create them.

## Backups (set up now, thank yourself later)

```bash
mkdir -p /home/lexora/backups
crontab -e
```

```cron
# 02:00 daily — MySQL (all three schemas) and MongoDB
0 2 * * * mysqldump -u lexora -p'<STRONG-MYSQL-PASSWORD>' --databases loisonatrach affectation-sonatrach clm_sounatrach | gzip > /home/lexora/backups/mysql-$(date +\%F).sql.gz
15 2 * * * mongodump --username admin --password '<STRONG-MONGO-PASSWORD>' --authenticationDatabase admin --archive=/home/lexora/backups/mongo-$(date +\%F).archive --gzip
30 2 * * * find /home/lexora/backups -mtime +14 -delete
```

Also include `bib-juridique/src/uploads/` in whatever off-server backup you use — uploaded legal documents live only there.

## Done when

- `sudo mysql -u lexora -p` connects and `SHOW DATABASES;` lists the three schemas
- `mongosh -u admin -p ... --authenticationDatabase admin` pings successfully
- Unauthenticated `mongosh` commands are rejected

Next: [04-configuration.md](04-configuration.md)
