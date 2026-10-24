# ICMS RBAC Permission Matrix

Audit date: 2026-10-22
Authority: `backend/app/core/permissions.py` and `backend/app/api/dependencies/permissions.py`

## Interpretation rules

- The backend is authoritative. Frontend visibility is not authorization.
- Permissions require an active membership in the addressed farm.
- `FARM_OWNER` receives the complete permission catalog only when membership ownership matches `farm.owner_id`; a mismatched owner membership is rejected.
- Predefined non-owner permissions are additive with assigned custom farm-role permissions.
- `health.manage` implies all granular health-management permissions.
- `milk.manage` implies lactation, quality, correction, analytics, and bulk-create management permissions.
- System administrator is a platform-level user flag, not a farm role. It currently grants global breed creation where explicitly checked; it does not bypass farm membership requirements generally.

## Permission catalog by domain

### Farm and staff

- `farm.view`
- `farm.manage`
- `staff.view`
- `staff.manage`
- `roles.manage`

### Cattle

- `cattle.view`
- `cattle.create`
- `cattle.update`
- `cattle.delete`

### Health

- `health.view`
- `health.manage`
- `health.create`
- `health.diagnosis`
- `health.vaccination.manage`
- `health.vaccination.administer`
- `health.treatment.manage`
- `health.medication.administer`
- `health.visit.manage`
- `health.audit.view`

### Milk

- `milk.view`
- `milk.record`
- `milk.manage`
- `milk.lactation.manage`
- `milk.quality.manage`
- `milk.correct`
- `milk.analytics.view`
- `milk.bulk.create`

### Planned domains

- `feed.view`, `feed.manage`
- `breeding.view`, `breeding.manage`
- `finance.view`, `finance.manage`
- `salary.view`, `salary.manage`
- `reports.view`, `reports.export`

There are **37 permission codes**, not 32. Several planned-domain permissions have no corresponding implementation yet.

## Built-in role grants

### Farm owner

Allowed: all 37 permissions, subject to the authoritative owner check.

Practical UI state: owner dashboard is partially complete. Farm, staff, and cattle functions are exposed; health and milk are placeholders; several allowed domains do not exist.

### Farm manager

Allowed directly:

- Farm: `farm.view`
- Staff: `staff.view`
- Cattle: `cattle.view`, `cattle.create`, `cattle.update`
- Health: all health permissions through direct grants, including `health.manage`
- Milk: all milk permissions through direct grants, including `milk.manage`
- Feed: `feed.view`, `feed.manage`
- Breeding: `breeding.view`, `breeding.manage`
- Reports: `reports.view`, `reports.export`

Not granted by default:

- `farm.manage`, `staff.manage`, `roles.manage`, `cattle.delete`
- `finance.view`, `finance.manage`, `salary.view`, `salary.manage`

Practical UI state: **broken**. `DashboardScreen` has no `FARM_MANAGER` branch and returns an unsupported-role error.

### Worker

Allowed directly:

- `farm.view`
- `cattle.view`
- `health.view`
- `milk.view`, `milk.record`, `milk.bulk.create`
- `feed.view`

All other permissions are denied unless added through a custom role assignment.

Practical UI state: cattle visibility works; health reporting and daily-task workflows are placeholders. Milk backend permissions are more capable than the UI.

### Veterinarian

Allowed directly:

- `farm.view`
- `cattle.view`
- All health permissions, including audit view
- `milk.view`
- `breeding.view`

All staff, role, cattle mutation, milk mutation, feed, finance, salary, and report permissions are denied unless added through a custom role assignment.

Practical UI state: cattle summary works; clinical workflows are placeholders despite the full health backend.

### System administrator

Platform authority:

- May create global breed-catalog entries through the explicit backend system-admin check.
- Does not automatically acquire farm permissions or active farm membership.

Practical UI state: only a “Global Breed Catalog” coming-soon card is shown; there is no operational administration route.

## Compact access comparison

The following summarizes default built-in access. “All” means every permission in that domain; “View” means read-only domain access; “Selected” means the exact subset described above; “None” means no predefined grant. Custom farm roles can add permissions to non-owner memberships.

- Farm owner: Farm **All**; Staff/Roles **All**; Cattle **All**; Health **All**; Milk **All**; Feed **All**; Breeding **All**; Finance/Salary **All**; Reports **All**.
- Farm manager: Farm **View**; Staff **View**; Roles **None**; Cattle **View/Create/Update**; Health **All**; Milk **All**; Feed **All**; Breeding **All**; Finance/Salary **None**; Reports **All**.
- Worker: Farm **View**; Staff/Roles **None**; Cattle **View**; Health **View**; Milk **View/Record/Bulk**; Feed **View**; Breeding/Finance/Salary/Reports **None**.
- Veterinarian: Farm **View**; Staff/Roles **None**; Cattle **View**; Health **All**; Milk **View**; Breeding **View**; Feed/Finance/Salary/Reports **None**.
- System administrator: no implicit farm-domain access; explicit platform breed-catalog authority only.

## Custom-role behavior

Custom roles are farm-scoped. A membership can be associated with custom roles whose permission codes are unioned with its predefined permissions. This permits additive access but not removal of built-in grants. Consequently:

- A custom role cannot make a manager less privileged than the predefined manager baseline.
- Permission assignment must validate codes against the catalog.
- Cross-farm role or membership associations must remain prohibited.
- UI decisions should use the effective-permissions endpoint rather than infer access from role name.

## Frontend alignment gaps

The frontend catalog currently represents only:

- `farm.view`, `farm.manage`
- `staff.view`, `staff.manage`
- `cattle.view`, `cattle.create`, `cattle.update`, `cattle.delete`
- `health.view`
- `milk.view`

It omits the granular health/milk permissions and all role/feed/breeding/finance/salary/report permissions. This does not weaken backend enforcement, but it prevents accurate action-level UI composition.

Recommended correction:

1. Generate or centrally synchronize frontend permission constants from the backend catalog/OpenAPI contract.
2. Gate each action—not only each module—on effective permissions.
3. Add tests proving hidden/disabled UI matches representative effective-permission payloads.
4. Add a real farm-manager dashboard that is permission-driven.
5. Build a custom-role editor only after the full permission catalog can be safely displayed and explained.

## Security invariants to retain

- Never accept a farm ID, role, or permission claim from the client as proof of access.
- Resolve the current user, active membership, farm, and effective permissions on every protected request.
- Keep owner authority tied to `farm.owner_id`.
- Keep platform administration separate from farm tenancy.
- Deny unknown permission codes and inactive memberships.
- Test every mutating endpoint for no membership, inactive membership, wrong farm, insufficient permission, and valid permission.
