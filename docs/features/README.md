# Lexora Backend — Feature Documentation

One file per business feature. Each documents the owning service, data model, full endpoint reference (paths as seen **through the gateway**), flows, permissions, and known limitations.

| # | Feature | Owning service | Public prefix |
|---|---|---|---|
| 1 | [Authentication & user management](01-authentication-and-user-management.md) | authentification (Django, :8010) | `/auth` |
| 2 | [Role & organizational assignments](02-role-assignments.md) | affectation-service (Django, :8011) | `/affectation` |
| 3 | [Organizational structure](03-organizational-structure.md) | service-juridique (Node, :8084) | `/juridique` |
| 4 | [Legal document library](04-legal-document-library.md) | bib-juridique (Node, :8085) | `/bib`, `/uploads` |
| 5 | [Contract lifecycle management (CLM)](05-contract-lifecycle-management.md) | service_clm (Django, :8012) | `/clm` |
| 6 | [Notifications, messaging & risk alerts](06-notifications-and-messaging.md) | service-notification (Node, :8004) | `/notifications` |
| 7 | [Platform: gateway, discovery & auth contract](07-platform-gateway-and-discovery.md) | gateway + registry | — |

## Reading conventions

- **Auth column**: `JWT` = any authenticated user; `admin` = `checkRole('admin')` or equivalent; `none` = no authentication currently applied (flagged when it looks unintentional).
- Paths include the public prefix because the gateway strips nothing (`StripPrefix=0`) — the path a client calls is exactly the path the service mounts.
- Role names referenced across features are the 11 strings defined by the `User` model (see [feature 1](01-authentication-and-user-management.md#roles)).
- Cross-document IDs: MySQL sides store MongoDB ObjectIds as 24-char strings (e.g. `Contrat.departement_id`) — referential integrity across the SQL/Mongo boundary is by convention, not enforced.

Related: [../TECHNICAL_REPORT.md](../TECHNICAL_REPORT.md) · [../deployment/README.md](../deployment/README.md)
