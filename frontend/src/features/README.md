# Feature boundaries

Each domain owns its screens, hooks, validation, and domain-specific API
functions. Shared presentation components belong in `src/components`; generic
HTTP behavior belongs in `src/api`; cross-feature state belongs in `src/state`.

Reserved feature directories:

- `auth`
- `farms`
- `permissions`
- `cattle`
- `health`
- `milk`

These directories intentionally contain no simulated data or authentication.
Implementation begins only in later approved Step 19 substeps.
