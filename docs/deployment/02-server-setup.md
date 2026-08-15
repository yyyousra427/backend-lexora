# Step 1 — Server Setup

Fresh Ubuntu VPS → hardened box with the full toolchain. Run everything here as root (or with `sudo`) unless stated otherwise.

## 1. Create the deploy user

```bash
adduser lexora
usermod -aG sudo lexora
# copy your SSH key
rsync --archive --chown=lexora:lexora ~/.ssh /home/lexora
```

Log back in as `lexora` for the rest of the deployment.

## 2. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Nothing else gets opened — all service ports stay on loopback (see the port table in [01-vps-requirements.md](01-vps-requirements.md#network--firewall)).

## 3. System update + base packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential pkg-config unzip
```

## 4. JDK 21 (hard requirement)

```bash
sudo apt install -y openjdk-21-jdk
java -version   # must print 21.x
```

If `java -version` shows an older JDK (multiple installed), select 21:

```bash
sudo update-alternatives --config java
```

## 5. Python toolchain

```bash
sudo apt install -y python3 python3-venv python3-dev default-libmysqlclient-dev
python3 --version   # 3.11+ expected
```

`default-libmysqlclient-dev` + `build-essential` + `pkg-config` are required to build the `mysqlclient` package — without them the Django installs in step 5 fail.

## 6. Node.js 20 + PM2

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version   # v20.x
sudo npm install -g pm2
```

## 7. Tesseract OCR (for service_clm)

```bash
sudo apt install -y tesseract-ocr tesseract-ocr-fra
tesseract --version
tesseract --list-langs   # must include: fra
```

The French language pack matters — the contracts service OCRs French documents. If Tesseract ends up outside PATH, set `TESSERACT_CMD` in `service_clm` settings (read by `clm/ocr_utils.py`).

## 8. nginx + certbot

```bash
sudo apt install -y nginx
sudo apt install -y certbot python3-certbot-nginx
```

Configuration comes later in [08-nginx-and-https.md](08-nginx-and-https.md).

## 9. Swap (only if RAM ≤ 4 GB)

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## Done when

- `java -version` → 21.x
- `python3 --version` → 3.11+
- `node --version` → 20.x, `pm2 --version` works
- `tesseract --list-langs` includes `fra`
- `sudo ufw status` shows only OpenSSH, 80, 443

Next: [03-databases.md](03-databases.md)
