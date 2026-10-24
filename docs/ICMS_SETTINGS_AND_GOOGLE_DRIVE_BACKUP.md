# ICMS Settings and Google Drive Backup Operations

## Scope and safety state

The settings module stores personal display preferences, farm operational preferences, security events, pending verified-email changes, and account-deletion review requests. Existing avatar, notification, staff, invitation, role, and farm-detail workflows remain authoritative and are linked rather than duplicated.

Platform backups are available only to authenticated `SYSTEM_ADMIN` users (`users.is_system_admin`). A farm role never grants backup access. API requests queue work; they do not run `pg_dump` inside a web request. No scheduler is started by FastAPI. Restore tests refuse `icms_db`, `icms_test`, and every destination not named `test_restore_*` or `*_restore_test`. The destination must already exist and be disposable.

Database-only backups do **not** contain uploaded profile pictures, cattle media, environment files, OAuth credentials, or encryption keys. `include_media` must remain disabled until a separately encrypted, version-consistent media pipeline is implemented and tested.

## Environment configuration

Copy placeholders from `backend/.env.example`; never commit `backend/.env`.

- `BACKUP_ENCRYPTION_KEY`: URL-safe base64 encoding of exactly 32 random bytes.
- `BACKUP_KEY_ID`: stable non-secret identifier such as `primary-2026`; retain every historical key needed by old archives.
- `BACKUP_ROOT`: protected local directory for encrypted `.icmsbak` files.
- `PG_DUMP_PATH`, `PG_RESTORE_PATH`: PostgreSQL 18-compatible executables.
- `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET`: OAuth web-client values.
- `GOOGLE_DRIVE_REDIRECT_URI`: exact backend callback URI.
- `GOOGLE_DRIVE_OAUTH_SCOPES`: keep `https://www.googleapis.com/auth/drive.file`.

Generate a key offline without printing it into shared logs:

```powershell
python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Paste it directly into the local secret store/environment. Store an off-device copy in an organization-approved password manager or encrypted removable recovery medium. Record its `BACKUP_KEY_ID`. Never store the plaintext key in Google Drive beside the archives. Losing all copies permanently makes AES-GCM backups unrecoverable. For rotation, configure a new key ID for new backups while retaining old keys in the recovery vault until all archives encrypted by them expire. The current runtime accepts one configured key, so an old key must be temporarily supplied during a historical recovery.

## Google Cloud and OAuth setup

1. Create or select a Google Cloud project and enable **Google Drive API**.
2. Configure the OAuth consent screen. During testing, add the approving Google accounts as test users; Google testing-mode refresh tokens can expire.
3. Create an **OAuth 2.0 Web application** client.
4. Register the exact HTTPS production callback, e.g. `https://api.example.com/api/v1/admin/backups/google/callback`. The localhost URI in `.env.example` is development-only.
5. Configure the client ID/secret only on the backend and restart it.
6. Sign in as System Admin, open **Backup & Recovery → Google Drive Connection**, re-enter the ICMS password, and complete Google's browser consent.

The backend signs short-lived OAuth state, exchanges the code server-side, encrypts refresh/access tokens at rest, and creates or reuses the dedicated `ICMS Encrypted Backups` folder. It requests only `drive.file`, so it can manage files created or explicitly opened by ICMS and cannot enumerate arbitrary personal Drive content. ICMS retention refuses deletion unless both the recorded parent folder and `managedBy=ICMS` application property match.

## Backup worker and scheduling

Apply migration `b3d5f7a9c210` only through the separately approved migration procedure. After configuration, a supervised scheduler (Windows Task Scheduler, systemd timer, container CronJob, or equivalent) may invoke the repository wrapper from any working directory:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "D:\ICMS_Project\scripts\run-backup-worker.ps1"
```

The wrapper resolves the backend directory, uses its existing virtual environment, and returns a non-zero exit code when the worker fails. The backend loads its local, Git-ignored environment configuration. The one-shot command evaluates the persistent daily/weekly schedule, enqueues an idempotent date-based job, and processes at most one pending job. A PostgreSQL session advisory lock prevents overlapping workers. In Windows Task Scheduler, use the command above as the action, select an approved service account with access to the project, secret configuration, PostgreSQL, and backup directory, configure retry/event-log monitoring, and do not select overlapping execution. Start scheduler activation only after an operator-approved dry run against non-protected data. Default retention is 7 daily and 4 distinct weekly records; the current API reports deletion candidates but does not silently delete local or cloud files.

Preparing this command does not activate scheduling. Scheduler creation, production credentials, and the first protected-data run require separate operator approval.

Job states are `PENDING`, `RUNNING`, `RETRY_PENDING`, `COMPLETED_LOCALLY`, `UPLOAD_PENDING`, `VERIFIED`, `FAILED`, and `RESTORE_TESTED`. A failed worker attempt is persisted and retried with bounded exponential delay up to three total attempts; the final failure remains alertable. `VERIFIED` requires Drive response metadata to match encrypted file size and SHA-256. Google transient errors also use bounded request-level backoff; authorization, quota, and terminal failures remain visible without credentials in the error text.

## Verification and isolated recovery

1. Confirm the source job shows an encrypted SHA-256 and either a verified local file or Drive object.
2. Create a new disposable PostgreSQL database named `test_restore_<purpose>` or `<purpose>_restore_test`. Never reuse `icms_db` or `icms_test`.
3. Ensure its host, owner, emptiness, permissions, and PostgreSQL version are correct independently.
4. In Backup Details, reauthenticate and run integrity verification.
5. Enter the exact isolated database name and request the recovery test. If the local artifact is absent, the backend downloads only the job's recorded Drive object, verifies SHA-256, authenticates/decrypts AES-256-GCM, validates the archive catalog, and restores to the isolated destination.
6. The worker compares restored `users`, `farms`, `farm_members`, and `cattle` counts with metadata captured at backup time, then records database identity, PostgreSQL server version, total table count, Alembic revision, and result status. Perform deeper application smoke tests before declaring a rehearsal successful.

The automated path never creates, drops, truncates, or cleans the destination. Operators own disposable database lifecycle outside the application.

## Production disaster recovery runbook

Production replacement is intentionally not exposed by an API. Obtain incident authorization; stop application writes; preserve a fresh backup and checksums; verify database host/name/schema and PostgreSQL tooling; retrieve the correct off-device recovery key; download and verify the chosen encrypted artifact; rehearse into an isolated database; validate critical counts, constraints, Alembic revision, authentication, and media reconciliation; then follow an independently reviewed cutover plan with rollback. Never overwrite the live database as the first restore attempt.

If the original server is lost, provision a clean trusted host, install compatible PostgreSQL/Python tooling, restore the application configuration from the secret manager, retrieve the historical key matching the archive header key ID, configure a new OAuth client or authorize Drive again, download the ICMS-managed archive, and follow the isolated rehearsal before cutover.

## Settings permissions and behavior

- All active users can update their name, supported contact phone, English-only language preference, IANA timezone, date/time display, theme, and notification preferences.
- Password and email changes require the current password. Password changes and completed email changes increment JWT token version, invalidating issued access tokens.
- Email change keeps the old login address active until the new address verifies through the existing secure, expiring hashed-token flow.
- Stateless JWT architecture cannot list individual devices. “Revoke sessions” truthfully revokes all existing access tokens, including the caller.
- Deactivation is blocked while the user remains an active Farm Owner. Deletion creates a review request and never cascades farm, audit, finance, or other users' data.
- Farm preferences require `farm.view`; changes require `farm.manage` on the active farm. Existing membership, invitation, last-owner, and cross-farm protections remain in their existing APIs.
- Themes remain the single existing provider: Emerald, Midnight Teal, and Royal Indigo. Only English is offered because no other localization bundle exists.

## Troubleshooting

- **OAuth redirect mismatch:** make the Google Console URI byte-for-byte identical to `GOOGLE_DRIVE_REDIRECT_URI`.
- **Authorization expired/revoked:** reconnect through the admin screen; do not paste tokens into configuration.
- **Quota exceeded:** free space in the authorized account or choose another approved account; ICMS does not delete unrelated files.
- **`pg_dump` failure:** verify executable version/path, database connectivity, permissions, and free protected local space. Passwords are passed through process environment, not command arguments.
- **Wrong/corrupt key:** select the historical key matching header key ID. Authentication failure is expected for modified ciphertext or the wrong key.
- **Scheduler says not running:** schedule configuration is not process supervision. Inspect the external scheduler and one-shot worker logs.
- **Media absent after restore:** database-only archives intentionally exclude media; restore the independently encrypted media set from the same recovery point when that pipeline becomes available.
