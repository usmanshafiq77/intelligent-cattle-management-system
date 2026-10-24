# ICMS SMTP Configuration

## Supported modes

- `console`: local/development only; action links appear in the developer console.
- `smtp`: real SMTP using STARTTLS or implicit TLS, timeouts, authentication, and bounded retries.
- `memory`: tests only through the test dependency override.

Production settings reject console mode.

The current local `.env` intentionally selects `APP_ENV=development` and
`EMAIL_DELIVERY_MODE=console`, which is why verification and password-reset
links are logged instead of delivered. Switching to SMTP is an environment
configuration change after provider setup; no token-service rewrite is needed.

## Recommended provider for the FYP

Use **Brevo transactional SMTP** for the first staging integration. Its free
plan currently allows 300 email sends per day, it supports a standard SMTP
relay, and ICMS can use it without a provider-specific SDK. That is enough for
an FYP demonstration while keeping the application portable. Use Postmark when
the priority shifts to paid, transaction-only deliverability and operational
analytics; use Gmail SMTP only for a very small private demonstration because
consumer-account policy and sending limits make it a weaker deployment choice.

Brevo references:

- Pricing and free-plan limits: https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans
- SMTP setup: https://help.brevo.com/hc/en-us/articles/7924908994450-Send-transactional-emails-using-Brevo-SMTP

## Brevo manual account setup

These steps require the project owner or domain administrator; the application
cannot perform them automatically:

1. Create a Brevo account and complete any sender-approval checks.
2. Add a dedicated sending domain or subdomain, such as `mail.example.com`.
3. Copy the exact DKIM and DMARC DNS records shown by Brevo into the domain's
   DNS provider, wait for propagation, and confirm authentication in Brevo.
4. Create and verify a transactional sender such as `ICMS <no-reply@example.com>`.
5. In Brevo's SMTP page, generate an **SMTP key**, not an API key. Record the
   displayed SMTP login separately; it may differ from the account email.
6. Put the SMTP login/key in the deployment secret manager or the ignored local
   `.env`. Never place them in `.env.example`, source control, screenshots, or
   support logs.
7. Use `smtp-relay.brevo.com`, port 587, and STARTTLS as shown below. Configure
   an HTTPS frontend public URL whose verification and reset routes are live.

```dotenv
APP_ENV=staging
EMAIL_DELIVERY_MODE=smtp
FRONTEND_PUBLIC_URL=https://staging.example.com
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=brevo-smtp-login-from-provider
SMTP_PASSWORD=brevo-smtp-key-from-secret-store
SMTP_USE_STARTTLS=true
SMTP_USE_SSL=false
SMTP_SENDER_EMAIL=no-reply@example.com
SMTP_SENDER_NAME=ICMS
SMTP_TIMEOUT_SECONDS=10
SMTP_MAX_ATTEMPTS=3
SMTP_RETRY_DELAY_SECONDS=0.5
```

Both TLS settings cannot be enabled together, and SMTP mode cannot disable both.

## Required application URLs

Set one public frontend origin:

```dotenv
FRONTEND_PUBLIC_URL=https://icms.example.com
```

ICMS derives:

- `https://icms.example.com/auth/verify-email`
- `https://icms.example.com/reset-password`
- `https://icms.example.com/invitations/accept`

Optional per-action overrides exist for deployments that need them:

```dotenv
EMAIL_VERIFICATION_BASE_URL=
PASSWORD_RESET_BASE_URL=
INVITATION_ACCEPT_BASE_URL=
```

Production action URLs must use HTTPS and may not contain credentials, queries, or fragments.

## Gmail-compatible STARTTLS example

Use a provider-approved credential. For Gmail accounts with 2-Step Verification, create an App Password; do not use or share the normal account password.

```dotenv
EMAIL_DELIVERY_MODE=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=sender@example.com
SMTP_PASSWORD=provider-issued-app-password
SMTP_USE_STARTTLS=true
SMTP_USE_SSL=false
SMTP_SENDER_EMAIL=sender@example.com
SMTP_SENDER_NAME=ICMS
SMTP_TIMEOUT_SECONDS=10
SMTP_MAX_ATTEMPTS=3
SMTP_RETRY_DELAY_SECONDS=0.5
```

For implicit TLS, normally port 465:

```dotenv
SMTP_PORT=465
SMTP_USE_STARTTLS=false
SMTP_USE_SSL=true
```

STARTTLS and implicit SSL cannot both be enabled. Username and password must be supplied together. Store credentials in a deployment secret manager or an ignored environment file; never commit them.

## Delivery behavior

- Verification, invitation, and password-reset messages use frontend action links.
- Tokens are URL-encoded.
- Production logs contain delivery status/errors but not raw tokens or passwords.
- Network timeouts, disconnects, connection errors, and SMTP 4xx responses receive bounded retries.
- Authentication, sender, recipient, unsupported-command, and SMTP 5xx failures are not retried blindly.
- API responses remain sanitized. Forgot-password and resend responses do not disclose account existence.

## Verification journey

1. Registration creates a hashed, expiring, single-use token.
2. SMTP delivers a frontend link.
3. Expo Web or mobile deep linking opens `/auth/verify-email?token=...`.
4. The route captures the token and removes it from route parameters.
5. The screen submits the token once to POST `/api/v1/auth/verify-email`.
6. The backend activates the account and consumes the token.
7. Invalid, expired, or reused tokens receive safe recovery guidance.

Invitation links prefill the acceptance token but do not auto-accept membership. Password reset links open the existing reset screen.

## Safe activation checklist

1. Configure a staging sender and HTTPS frontend URL.
2. Confirm SPF/DKIM/DMARC with the chosen provider/domain.
3. Start with a controlled internal mailbox only.
4. Confirm verification, resend, invitation, and reset delivery.
5. Verify raw tokens and credentials do not appear in centralized logs.
6. Test provider timeout and invalid credential alerts.
7. Obtain explicit approval before sending any real message from this project environment.

No real email was sent during P0 implementation.

## Send one verification email after explicit approval

Use an isolated staging database at the current application migration head; do
not point this procedure at `icms_db` or a GUI test schema.

1. Complete the provider/domain steps above and deploy the HTTPS frontend routes.
2. Configure the backend with `APP_ENV=staging`, `EMAIL_DELIVERY_MODE=smtp`, and
   secrets supplied outside source control.
3. Start the backend and confirm `/api/v1/health/db` reports ready.
4. Obtain explicit approval naming one internal recipient mailbox.
5. Register that one staging test account through the normal signup screen. This
   creates the existing secure token and sends exactly one verification message.
6. Check the provider activity log for one accepted message; do not copy its raw
   token into application logs or the issue tracker.
7. Open the delivered link, verify that the frontend removes the query token,
   submits `POST /api/v1/auth/verify-email`, and then confirm login succeeds.
8. Stop if delivery fails. Inspect only the sanitized application error and the
   provider event ID before deciding whether another approved send is necessary.

After that verification succeeds, password-reset delivery can be checked with a
separate approval by submitting the verified staging account to the normal
Forgot Password screen. The Reset Password endpoint consumes the emailed token;
it does not send another message.

## Durable outbox decision

The staging baseline uses synchronous delivery with up to three attempts. Account/invitation state remains committed when delivery fails, and users can resend or reissue safely.

A durable outbox is deferred because it requires a new migration beyond the currently reviewed protected upgrade. Before multi-instance production or a guaranteed-delivery SLA, add an outbox table, idempotent worker, retry schedule, dead-letter visibility, and delivery metrics.
