# Step 4 — Eureka Registry & Gateway

Build the two Spring Boot jars once, then run them as systemd services so they start on boot in the right order.

## 1. Build the jars

```bash
cd /opt/lexora/registry
./mvnw -q -DskipTests package        # → target/registry-0.0.1-SNAPSHOT.jar

cd /opt/lexora/gateway
./mvnw -q -DskipTests package        # → target/gateway-0.0.1-SNAPSHOT.jar
```

If either build fails with *"release version 21 not supported"*, your shell is not using JDK 21 — see [10-troubleshooting.md](10-troubleshooting.md).

On first run `mvnw` downloads Maven and all dependencies (~2–5 min); later builds are fast.

## 2. systemd unit — registry

```bash
sudo nano /etc/systemd/system/lexora-registry.service
```

```ini
[Unit]
Description=Lexora Eureka registry (port 8761)
After=network.target

[Service]
User=lexora
ExecStart=/usr/bin/java -Xms128m -Xmx512m -jar /opt/lexora/registry/target/registry-0.0.1-SNAPSHOT.jar
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 3. systemd unit — gateway

The gateway waits for the registry so services can be discovered as soon as it is up.

```bash
sudo nano /etc/systemd/system/lexora-gateway.service
```

```ini
[Unit]
Description=Lexora Spring Cloud Gateway (port 8083)
After=network.target lexora-registry.service
Wants=lexora-registry.service

[Service]
User=lexora
ExecStart=/usr/bin/java -Xms128m -Xmx512m -jar /opt/lexora/gateway/target/gateway-0.0.1-SNAPSHOT.jar
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 4. Start and enable

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lexora-registry
# wait ~20s for the registry to come up, then:
sudo systemctl enable --now lexora-gateway

systemctl status lexora-registry lexora-gateway
```

## 5. Verify

Port 8761 is firewalled from the internet (correct). View the Eureka dashboard through an SSH tunnel from your own machine:

```bash
ssh -L 8761:localhost:8761 lexora@<VPS-IP>
# then open http://localhost:8761 in your local browser
```

On the server itself:

```bash
curl -s http://localhost:8761/actuator/health   # or just: curl -sI http://localhost:8761
curl -sI http://localhost:8083                  # gateway answers (404 is fine — no route matches /)
```

The dashboard will show **GATEWAY-SERVICE** registered. The other services appear as steps 5–6 bring them up.

Logs, when needed:

```bash
journalctl -u lexora-registry -f
journalctl -u lexora-gateway -f
```

## Done when

- Both units are `active (running)` and enabled
- Eureka dashboard reachable through the tunnel, gateway registered

Next: [06-django-services.md](06-django-services.md)
