# ICMS Deployment Guide

## Scope

This guide covers the reproducible staging baseline in `compose.staging.yml`. It does not publish services, configure DNS, or create a production TLS endpoint.

Docker was unavailable in the implementation environment. Compose YAML, application tests, Expo compatibility, and production exports were validated; container image/runtime validation must be completed on a Docker-capable host.

## Components

- PostgreSQL 18 with a persistent volume.
- FastAPI backend running as a non-root user.
- Expo Web static export served by unprivileged nginx.
- Persistent cattle-media volume.
- A profile-gated one-shot Alembic service that never runs during normal backend startup.

Host ports bind to loopback by default. Use a reviewed reverse proxy for any external exposure.

## Configure staging

```powershell
Set-Location D:\ICMS_Project
Copy-Item .\deploy\.env.example .\deploy\.env
```

Edit `deploy/.env` and replace every placeholder. At minimum:

- Unique database password.
- Random JWT secret of at least 32 characters.
- Explicit CORS origin.
- Public frontend URL.
- Approved SMTP values.
- Correct `FORWARDED_ALLOW_IPS` for the actual trusted proxy.

`deploy/.env` is ignored by Git. Never place secrets in `EXPO_PUBLIC_*` values because they are embedded into client bundles.

## Build and initialize

Validate configuration:

```powershell
docker compose --env-file .\deploy\.env -f .\compose.staging.yml config
```

Start the database:

```powershell
docker compose --env-file .\deploy\.env -f .\compose.staging.yml up -d postgres
```

Run the explicit migration service:

```powershell
docker compose --env-file .\deploy\.env -f .\compose.staging.yml --profile tools run --rm migrate
```

Start application services:

```powershell
docker compose --env-file .\deploy\.env -f .\compose.staging.yml up -d backend frontend
```

Normal backend startup does not migrate or recreate the database. Readiness remains unhealthy if the schema revision is wrong.

## Health and readiness

- Liveness: `GET /api/v1/health` — process is serving requests.
- Readiness: `GET /api/v1/health/db` — database connection works and revision matches `b7c9d2e4f601`.
- Frontend container: `GET /healthz`.

Do not route traffic to a backend whose readiness endpoint returns 503.

## Production requirements

Before production:

1. Terminate TLS at a reviewed reverse proxy/load balancer.
2. Use `APP_ENV=production`.
3. Use only HTTPS CORS and frontend/action URLs.
4. Restrict database and backend ports to private networks.
5. Set `FORWARDED_ALLOW_IPS` to explicit trusted proxy addresses, never `*` on an internet-reachable host.
6. Use a secret manager for database, JWT, and SMTP credentials.
7. Set `LOG_FORMAT=json` and collect stdout centrally.
8. Alert on 5xx rate, readiness failure, authentication throttling, SMTP failure, database saturation, backup failure, and disk/media capacity.
9. Run the protected migration runbook and backup verification.
10. Repair media ownership and validate a real media backup/restore.
11. Add Redis-backed rate limiting before scaling to multiple API processes/hosts.
12. Resolve or formally accept the documented Expo/Metro/Jest transitive dependency advisories through an Expo-compatible upgrade.

## Logging and privacy

Backend request logs include timestamp, level, logger, method, path, status, duration, and a generated request ID in JSON mode. They do not log request bodies, authorization headers, SMTP credentials, or action tokens.

Security headers include content-type sniffing protection, frame denial, no-referrer policy, auth response no-store, request ID, and production HSTS.

## Monitoring baseline

At minimum collect:

- Container/process availability.
- `/api/v1/health/db` status.
- Request count, latency, and status distribution.
- PostgreSQL connections, storage, locks, and slow queries.
- SMTP attempts/failures without message tokens.
- Backup age, size, and verification outcome.
- Media-volume capacity and permission failures.

The repository provides structured logs and health signals, not a hosted monitoring system.

## Rollback

- Application rollback: deploy the previously tested image without changing the database when schema-compatible.
- Database rollback: follow `ICMS_DATABASE_MIGRATION_RUNBOOK.md`; prefer restore over destructive downgrade after reset traffic begins.
- Frontend rollback: restore the previous immutable static image/export.
