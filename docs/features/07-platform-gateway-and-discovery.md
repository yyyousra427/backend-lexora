# Feature 7 — Platform: Gateway, Discovery & the Auth Contract

| | |
|---|---|
| **Services** | `gateway/` (Spring Cloud Gateway, :8083) · `registry/` (Eureka server, :8761) |
| **Stack** | Spring Boot 3.4.4, Spring Cloud 2024.0.1, Java 21 |

Not a business feature, but the platform every feature rides on. Documented here because its rules constrain all endpoint design.

## 1. Single entry point

The React frontend (:3000) talks **only** to the gateway (:8083). Behind nginx in production, the public origin is `https://api.<domain>` → gateway. Services are never exposed directly (loopback binding + firewall).

## 2. Routing table

| Path predicate | Target | Mechanism |
|---|---|---|
| `/auth/**` | `http://localhost:8010` | fixed port |
| `/affectation/**` | `http://localhost:8011` | fixed port |
| `/clm/**` | `http://localhost:8012` | fixed port |
| `/juridique/**` | `lb://service-juridique` | Eureka |
| `/notifications/**` | `lb://SERVICE-NOTIFICATION` | Eureka |
| `/bib/**`, `/uploads/**` | `lb://bib-juridique` | Eureka |

**Rules that follow from `StripPrefix=0`:**

- The path a client calls is byte-for-byte the path the service must mount. Django services mount `auth/`, `affectation/`, `clm/` in their root `urls.py`; Express apps mount `/juridique`, `/bib`, `/notifications`.
- Adding an endpoint = include the prefix. Adding a prefix = add a gateway route **and rebuild/restart the gateway** (routes live in `application.yml`, compiled into the jar).
- Root-level service endpoints (`/health`, `/info`) are *not* reachable through the gateway — by design they are probed directly on service ports.

## 3. Service discovery (Eureka)

- Registry on :8761, dashboard at `/`; `enable-self-preservation: false` (fast eviction — dev-friendly, production-risky).
- Registered names (exact strings): `gateway-service`, `AUTHENTICATION-SOUNATRACH`, `AFFECTATION-SOUNATRACH`, `CLM-SOUNATRACH`, `service-juridique`, `bib-juridique`, `SERVICE-NOTIFICATION`.
- Clients: `py-eureka-client` (Django — daemon thread started from each app's `AppConfig.ready()`), `eureka-js-client` (Node — after Mongo connects).
- Django-side consumers (`discovery.py` per service) query Eureka's REST API directly with a 60 s cache and fall back to the gateway when `USE_EUREKA=false` — meaning the system can run entirely without Eureka *for Django-originated calls*, but the gateway still needs it for the three `lb://` routes.

## 4. The authentication contract

The platform's most important invariant:

1. **One HS256 secret** — Django `SECRET_KEY` (authentification) = `JWT_SECRET` (all Node services). Five files must agree; see [../deployment/04-configuration.md](../deployment/04-configuration.md#the-shared-jwt-secret).
2. **Token issue**: only authentification issues tokens (simplejwt; access/refresh 1 day, rotation + blacklist).
3. **Token verify**: every service verifies **locally** — no central introspection call. Django via simplejwt, Node via `jsonwebtoken`.
4. **Identity enrichment**: Node middleware resolves the caller's profile/role through gateway `GET /auth/all_users/<id>/` (Bearer forwarded, 10 min in-memory cache).
5. **Authorization vocabulary**: the 11 role strings of the `User` model (feature 1) — matched verbatim in `checkRole(...)`.

Failure signatures: secret drift → 401 on Node routes only; blacklist/rotation issues → 401 everywhere after refresh; cache staleness → role changes take up to 10 min to propagate to Node services.

## 5. CORS

Layered: the gateway applies global CORS (origins `localhost:3000`/`127.0.0.1:3000`, credentials, all methods) **and** each service sets its own headers; a `DedupeResponseHeader` default filter (`RETAIN_FIRST`) prevents the duplicate-header browser error. Changing the frontend origin therefore touches the gateway yml **and** the per-service lists — the full checklist is in [../deployment/04-configuration.md](../deployment/04-configuration.md#5-cors--point-everything-at-the-real-frontend-origin).

## 6. Operational notes

- Gateway and registry ship as jars (`mvnw package`, JDK 21) run under systemd; the gateway unit orders itself after the registry.
- Actuator is on the gateway classpath (default exposure only).
- The registry UI is the fastest system-wide health view: seven clients UP = platform healthy.
