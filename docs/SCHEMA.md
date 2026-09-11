# SAT-SA Data Schema Documentation

All tables are plain SQL (SQLite in the demo; portable to PostgreSQL by swapping
`DATABASE_URL`). Required = the ingest/seed pipeline rejects or quarantines without it.

## 1. CSE (Critical Sector Entity) — `entities`

| field | type | req | meaning | example |
|---|---|---|---|---|
| id | TEXT PK | ✓ | NCIIPC-assigned entity code | `BNK-02` |
| name | TEXT | ✓ | registered entity name | `National Payments Corp` |
| sector | TEXT | ✓ | critical sector | `Banking & Finance` |
| criticality | TEXT | ✓ | entity criticality tier | `Critical` / `High` / `Medium` |
| assets | INTEGER | ✓ | declared asset inventory size | `3120` |
| soc_maturity | TEXT | – | declared SOC maturity level | `Level 4` |

## 2. Asset — `assets`

| field | type | req | meaning | example |
|---|---|---|---|---|
| id | TEXT PK | ✓ | asset identifier | `AS-BNK-02-0` |
| entity_id | TEXT FK→entities | ✓ | owning CSE | `BNK-02` |
| name | TEXT | ✓ | asset label | `Core Banking DB #1` |
| type | TEXT | – | asset class | `Payment Gateway` |
| criticality | TEXT | ✓ | asset criticality | `Critical` |
| monitoring | TEXT | ✓ | declared monitoring status | `monitored` / `unmonitored` |

## 3. Daily submission (periodic SOC evidence) — `daily`

Ingest contract (CSV header, one row per entity per day). Validation runs BEFORE
analytics; rejects are quarantined, never silently discarded.

| field | type | req | meaning | example |
|---|---|---|---|---|
| entity_id | TEXT FK | ✓ | reporting CSE | `TEL-01` |
| date | DATE | ✓ | reporting day (ISO) | `2026-09-05` |
| alerts_total | INT ≥0 | ✓ | alerts handled that day | `34` |
| alerts_critical | INT ≥0 | ✓ | critical alerts | `4` |
| alerts_high / medium / low | INT ≥0 | ✓ | severity breakdown | `8 / 12 / 10` |
| cases_opened | INT ≥0 | ✓ | cases opened | `12` |
| cases_closed | INT ≥0 | ✓ | cases closed | `10` |
| escalations | INT ≥0 | ✓ | escalations to NCIIPC | `1` |
| open_critical_end | INT ≥0 | ✓ | unresolved criticals at day end | `6` |
| ack_min_median | REAL ≥0 | ✓ | median acknowledge time (min) | `28.5` |
| mttr_hours | REAL ≥0 | ✓ | mean time to resolve (h) | `9.2` |
| sla_violation_rate | REAL 0–1 | ✓ | critical acks beyond 60-min SLA | `0.08` |
| silent_close_rate | REAL 0–1 | ✓ | criticals closed without case | `0.03` |
| missing_field_rate | REAL 0–1 | ✓ | internal record incompleteness | `0.02` |
| submission_lag_hours | REAL ≥0 | ✓ | report submission delay (h) | `5.0` |

## 4. Alert — `alerts`

| field | type | req | meaning | example |
|---|---|---|---|---|
| id | TEXT PK | ✓ | alert identifier | `A-BNK-02-0031` |
| entity_id | TEXT FK | ✓ | reporting CSE | `BNK-02` |
| ts | TIMESTAMP | ✓ | detection time | `2026-09-04T10:31:00` |
| severity | TEXT | ✓ | Critical/High/Medium/Low | `Critical` |
| category | TEXT | ✓ | attack category | `Phishing` |
| status | TEXT | ✓ | lifecycle state | `Open`/`Closed`/`Escalated` |
| ack_minutes | REAL | – | time to acknowledge | `96.4` |
| case_id | TEXT FK→cases | – | linked case (NULL = none opened) | `C-BNK-02-0031` |
| disposition | TEXT | – | closure disposition | `False Positive` |
| asset_id | TEXT FK→assets | – | affected asset | `AS-BNK-02-0` |
| gt_review | INT 0/1 | – | hidden validation label (never served to the queue) | `1` |

## 5. Case — `cases`

| field | type | req | meaning | example |
|---|---|---|---|---|
| id | TEXT PK | ✓ | case identifier | `C-BNK-02-0031` |
| entity_id | TEXT FK | ✓ | owning CSE | `BNK-02` |
| alert_id | TEXT FK→alerts | ✓ | originating alert | `A-BNK-02-0031` |
| opened_ts | TIMESTAMP | ✓ | case creation time | `2026-09-04T10:33:00` |
| closed_ts | TIMESTAMP | – | closure time | `2026-09-04T10:38:00` |
| status | TEXT | ✓ | `Open` / `Closed` | `Closed` |
| disposition | TEXT | – | outcome | `Contained & Resolved` |

## 6. Investigation — `investigations`

| field | type | req | meaning | example |
|---|---|---|---|---|
| id | TEXT PK | ✓ | investigation identifier | `I-BNK-02-0031` |
| case_id | TEXT FK→cases | ✓ | investigated case | `C-BNK-02-0031` |
| entity_id | TEXT FK | ✓ | performing CSE | `BNK-02` |
| started_ts | TIMESTAMP | ✓ | start time | `2026-09-04T10:34:00` |
| duration_min | REAL | ✓ | analyst minutes spent | `42.0` |
| actions | INT | ✓ | investigative actions recorded | `5` |

## 7. Escalation — `escalations`

| field | type | req | meaning | example |
|---|---|---|---|---|
| id | TEXT PK | ✓ | escalation identifier | `E-OIL-02-0007` |
| entity_id | TEXT FK | ✓ | escalating CSE | `OIL-02` |
| case_id | TEXT FK→cases | ✓ | escalated case | `C-OIL-02-0007` |
| ts | TIMESTAMP | ✓ | escalation time | `2026-08-30T14:12:00` |
| reason | TEXT | – | escalation basis | `critical severity policy` |

## 8. Disposition / closure

Represented on `cases.disposition` + `cases.closed_ts` and mirrored on
`alerts.disposition` (values: `Contained & Resolved`, `False Positive`,
`Referred to NCIIPC`, `Patched`, `Under Monitoring`). The evidence graph renders it
as the Resolution node.

## 9. Assessment (window) — computed, not stored

Assessment windows are four consecutive 30-day windows over `daily`, recomputed on
every analytics run. Per window SAT-SA records: attention score, active issue
families (execution / negative-space / anomaly / data-quality) and per-family
intensity; assessment-to-assessment statuses (NEW / PERSISTENT / RETURNED /
WORSENING / IMPROVING / RESOLVED) and metric deltas are derived from them.

## 10. Finding (supervisory signal) — computed, not stored

| field | type | meaning |
|---|---|---|
| id | TEXT | `SIG-nnn` per recompute |
| entity_id | TEXT | CSE under examination |
| key | TEXT | detector key (`sla`, `blind_spot`, `pattern_repeat`, …) |
| category | TEXT | Execution Gap / Negative Space / Anomaly & Pattern / Data Hygiene / Peer |
| severity | TEXT | critical / high / medium / low |
| title, detail | TEXT | hedged supervisory wording |
| observed, benchmark | TEXT | measured value vs comparison basis |
| evidence | JSON | machine-readable evidence values (traceable to DB rows) |
| confidence | REAL 0–1 | evidence confidence |
| method | TEXT | detection method (anomaly signals only) |

Supervisor dispositions on findings are stored in `actions`
(signal_id, entity_id, action, note, user, ts).

## 11. Audit event — `audit`

| field | type | req | meaning | example |
|---|---|---|---|---|
| id | INTEGER PK | auto | sequence | `12` |
| ts | TIMESTAMP | ✓ | event time | `2026-09-10T09:41:07` |
| user | TEXT | ✓ | acting user | `admin` |
| event | TEXT | ✓ | login / ingest / config / signal_action / reset / holdout-eval | `config` |
| detail | TEXT | – | structured detail | `{"w_exec": 30, …}` |

## 12. Supporting tables

- **`quarantine`** (entity_id, raw JSON, reason, ts) — rejected submissions with
  machine-readable reasons; exported from the Data Quality page.
- **`notary`** (ts, event, fingerprint, prev_hash, hash) — SHA-256 evidence-base
  fingerprint per analytics recompute, hash-chained (tamper-evident).
- **`meta`** (key, value) — `schema_version = 3`; the server auto-rebuilds the seeded
  demo database when the on-disk schema is older than the code.
