# ICMS Security Audit

Audit date: 2026-10-24

## Result

No confirmed critical vulnerability or authentication/farm-isolation bypass was found. The application has strong baseline controls, but production activation still depends on infrastructure configuration and dependency remediation.

## Controls verified

- Secrets come from ignored environment files through `SecretStr`; production rejects short/placeholder JWT secrets (`backend/app/core/config.py`).
- Passwords are hashed; JWTs expire and carry a token version used for revocation (`core/security.py`).
- Verification/reset/invitation tokens are random, hashed at rest, expiring and single-use.
- Login, verification and reset routes use a thread-safe rate limiter. `InMemoryRateLimiter` is explicitly single-process.
- CORS accepts only explicit HTTP(S) origins and production requires HTTPS.
- Server-side RBAC validates active membership and explicit permissions; system-admin status does not bypass farm isolation.
- Uploads validate size, filename, detected content type and resolved storage path. Marketplace/finance downloads send private caching and `nosniff` headers.
- Finance spreadsheet output prefixes formula-triggering cells.
- API error paths avoid returning secrets, reset tokens, raw SMTP errors or private storage keys.
- Candidate-source scanning found no private keys, GitHub/AWS/payment tokens, local environment values, dumps or upload data selected for Git delivery.

## Findings

| Severity | Finding | Disposition |
|---|---|---|
| HIGH | `npm audit` reports five high transitive advisories in the Expo toolchain (`node-forge`, `zod` dependency paths). | OPEN. Suggested `--force` remediation proposes incompatible Expo changes; upgrade only through an Expo-supported SDK release, then rerun all tests/exports. Runtime exposure should be assessed because findings are primarily CLI/toolchain dependencies. |
| MEDIUM | Three moderate transitive advisories include `decode-uri-component` through `query-string`/`expo-router`. | OPEN for the same controlled Expo upgrade. Do not use `npm audit fix --force`. |
| MEDIUM | Authentication throttling is process-local and will not coordinate multiple workers/instances. | OPEN. Use a shared Redis-backed limiter before horizontally scaled production. |
| MEDIUM | Production SMTP, HTTPS origins, DNS sender authentication and hosting secrets are not activated/verified. | OPERATIONAL BLOCKER. Follow `ICMS_SMTP_CONFIGURATION.md` and deployment guide. |
| LOW | Finance receipt responses previously lacked explicit private/no-store and nosniff headers. | FIXED with regression coverage. |
| LOW | Bandit B105/B106 flagged the OAuth scheme string `bearer` and a generic reset response as possible passwords. | FALSE POSITIVES; neither is a credential. Bandit result: 0 high, 0 medium, 2 low. |

## Dependency evidence

- `npm audit`: 8 findings (5 high, 3 moderate), all requiring a breaking forced resolution according to npm.
- `pip check`: no broken Python requirements.
- `pip-audit`: blocked because the installed Windows Python 3.13 distribution lacks the standard-library `venv` module required when `pip-audit` imports. Run it in CI's standard CPython image before release.
- Expo dependency alignment: up to date; Expo Doctor: 21/21.

## Production security actions

1. Migrate only after backup/recovery approval and deploy the exact reviewed migration chain.
2. Configure HTTPS, narrow CORS origins, SMTP credentials and verified SPF/DKIM/DMARC without committing secrets.
3. Adopt a shared rate limiter and centralized structured log/alert sink.
4. Upgrade the Expo SDK/dependency chain in a dedicated branch and verify `npm audit`, Jest, Doctor, and both exports.
5. Run Python dependency auditing in CI and add recurring dependency/security scans.
