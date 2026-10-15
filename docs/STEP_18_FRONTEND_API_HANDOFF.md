# Step 18 Frontend API Handoff

Date: 2026-10-15
Base URL: `/api/v1`
OpenAPI: 63 paths / 87 operations

## Authentication and farm context

Send the access token as `Authorization: Bearer <token>`. Every milk route embeds
the selected farm UUID: `/farms/{farm_id}/milk/...`. A UUID from another farm is
not a portable object reference; cross-farm lookups return a concealed not-found
or access response. The client must not infer access from cached role names—use
the effective permission response supplied by the existing RBAC module.

Important permission codes are `milk.view`, `milk.record`, `milk.manage`,
`milk.lactation.manage`, `milk.quality.manage`, `milk.correct`,
`milk.analytics.view`, and `milk.bulk.create`.

## Endpoint catalog and screens

- Lactation list/detail/current screen:
  `GET /farms/{farm_id}/milk/lactations`,
  `GET /lactations/active`, and `GET /lactations/{id}`.
- Start/close lactation actions: `POST /lactations` and
  `POST /lactations/{id}/transition`.
- Daily entry/history screen: `POST/GET /sessions` and `GET /sessions/{id}`.
- Grid/batch entry screen: `POST /sessions/bulk` (1–100 records, atomic).
- Quality entry/history screen: `POST/GET /quality` and `GET /quality/{id}`.
- Correction history/action: `POST/GET /corrections`.
- Dashboard: `GET /analytics/production` and `GET /analytics/breakdown`.
- Authorized export: `GET /analytics/dataset`.

The full prefix for each item is `/api/v1/farms/{farm_id}/milk`.

## Core request examples

Start a lactation:

```json
{
  "cattle_id": "00000000-0000-0000-0000-000000000000",
  "sequence_number": 1,
  "start_date": "2026-10-15"
}
```

Record a session:

```json
{
  "cattle_id": "00000000-0000-0000-0000-000000000000",
  "lactation_id": "00000000-0000-0000-0000-000000000000",
  "milking_date": "2026-10-15",
  "session_kind": "MORNING",
  "session_code": "MORNING",
  "recorded_time": "2026-10-15T06:30:00+05:00",
  "volume_liters": "12.375",
  "unit": "L",
  "operator_id": null,
  "notes": null
}
```

For an extra collection use `session_kind: "ADDITIONAL"` and a distinct code
such as `MIDDAY_1`. Zero liters is a valid explicit observation. Omission means
no observation and must not be rendered as zero.

Quality sample:

```json
{
  "session_id": "00000000-0000-0000-0000-000000000000",
  "fat_percent": "4.200",
  "snf_percent": "8.700",
  "protein_percent": "3.300",
  "tested_at": "2026-10-15T07:00:00+05:00",
  "notes": "On-farm instrument reading"
}
```

At least one measurement is required. Optional values are `null`, not invented.
Never label the result safe, certified, or laboratory-verified from this payload.

Correction:

```json
{
  "cattle_id": "00000000-0000-0000-0000-000000000000",
  "target_type": "SESSION",
  "target_id": "00000000-0000-0000-0000-000000000000",
  "reason": "Transcription error confirmed from meter log",
  "replacement_values": {"volume_liters": "12.500"}
}
```

The original record remains immutable. Display `effective_volume_liters` and
`effective_notes` for current session values, and provide audit history to users
with `milk.correct`.

## Filtering and pagination

Collection endpoints use `limit` and `offset`; normal list limits are 1–200.
Sessions also filter by `cattle_id`, `lactation_id`, `date_from`, `date_to`, and
`session_kind`. Quality filters by `cattle_id` and `session_id`. Corrections filter
by target type, target ID, and cattle ID. The dataset limit is 1–5000.

Analytics requires inclusive `date_from` and `date_to`. Production interval is
`daily`, `weekly`, or `monthly`. Weekly buckets start Monday. The response states
`missing_records_are_zero: false`; charts should show gaps rather than fabricated
zeros.

## Errors and retry behavior

- `401`: token absent/invalid or account unavailable.
- `403`: authenticated member lacks the permission.
- `404`: farm-scoped object unavailable; do not disclose guessed foreign IDs.
- `409`: duplicate lactation/session/sample or a concurrent conflict.
- `422`: domain chronology, eligibility, unit, range, or payload validation.
- `500/503`: server/database unavailable; do not automatically replay a write.

Bulk submission is all-or-nothing. A `409` means no batch item was committed.
Retry only after refetching current records; use the stable animal/date/session
identity to avoid accidental duplicates.

## Known incomplete areas

The Step 18 schema is deployed at `a8b3c4d5e6f7`; read-only and transaction-
rolled-back write-path API smoke tests pass. There is no React Native
implementation, offline synchronization protocol,
cursor pagination, push notification flow, feed/weather feature data, or trained
milk-yield model. Frontend implementation should still use the pinned OpenAPI
contract and handle incomplete observations explicitly.
