# Step 7 — nginx Reverse Proxy & HTTPS

nginx is the only thing the internet talks to. It terminates TLS and forwards everything to the gateway on `127.0.0.1:8083`.

Prerequisite: the DNS A record for your API hostname (e.g. `api.example.com`) already points at the VPS IP.

## 1. Server block

```bash
sudo nano /etc/nginx/sites-available/lexora
```

```nginx
server {
    listen 80;
    server_name api.example.com;

    # multer document uploads go through here — the nginx default of 1m
    # would reject any real PDF with "413 Request Entity Too Large"
    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:8083;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;   # CLM OCR requests can be slow
    }

    # Socket.IO is not routed by the gateway. Not active today
    # (see 07-node-services.md), but ready for when it is wired up.
    location /socket.io/ {
        proxy_pass http://127.0.0.1:8004;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host       $host;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/lexora /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

At this point `http://api.example.com/juridique/directions` should answer from the internet.

## 2. TLS with Let's Encrypt

```bash
sudo certbot --nginx -d api.example.com
```

Certbot rewrites the server block for 443 and adds the HTTP→HTTPS redirect. Confirm auto-renewal is armed:

```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

## 3. Point the frontend and CORS at the new origin

- The React frontend's API base URL becomes `https://api.example.com`.
- The CORS origin lists from [04-configuration.md](04-configuration.md#5-cors--point-everything-at-the-real-frontend-origin) must contain the frontend's **https** origin — revisit them now if you deployed the frontend after step 3.
- After editing the gateway's `application.yml` CORS list, rebuild and restart it:

```bash
cd /opt/lexora/gateway && ./mvnw -q -DskipTests package
sudo systemctl restart lexora-gateway
```

## Done when

- `https://api.example.com/juridique/directions` answers with valid TLS
- `http://` redirects to `https://`
- A browser call from the frontend origin passes CORS (no preflight failure in the console)
- `sudo certbot renew --dry-run` succeeds

Next: [09-verification.md](09-verification.md)
