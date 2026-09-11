# Changelog

## v4.0 — SIH-final hardening (25-section upgrade spec)

Built incrementally on v3; all 33 v3 tests preserved (44 total now).

### Held-out validation (spec §1 — highest priority)
- Second ground-truth dataset in `datagen.py` (`VARIANT_ENTITIES`, seed 1337):
  same scenario families with shifted placements, magnitudes and categories
  (different silence window, Ransomware campaign instead of Phishing, 24× closure
  pattern, 7-day outage, x6 ack surge at new positions) **plus false-positive-prone
  healthy entities** (near-threshold silent-close rate, missing days outside the
  assessment window, elevated-but-acceptable MTTR).
- `analytics.run_holdout()` + `GET /api/holdout`: full detector stack re-run on the
  held-out set with confusion matrix; primary cache restored afterwards.
- `backend/benchmark.py` CLI: seed vs held-out evaluation, confusion matrix,
  prioritization, ML-attribution statement, data-quality gate, scaling table.
  README §8 shows the actual latest output — nothing hardcoded.
- The held-out run exposed and fixed a real boundary bug: `cat_absent` suppression
  started at day 90 while the analytics 30-day window includes day-89 intra-day
  timestamps (`day >= 89` now).

### Data Quality module (spec §2)
- `validate.py` v2: warning tier alongside rejects (severity-sum consistency,
  high missing-field rate, late submission); rows are accepted-but-flagged or
  quarantined — never silently discarded.
- `analytics.dataquality()`: five scored dimensions (schema/completeness/consistency/
  timeliness/uniqueness, weighted 0–100), per-entity scores, totals (valid/warning/
  rejected), duplicate & invalid counts, reporting gaps, flagged-record list.
- New endpoints `GET /api/dataquality` + `/api/dataquality/export` (CSV download);
  new **Data Quality** console page.

### Assessment-to-assessment comparison (spec §5, §12)
- Six statuses per issue family: NEW / PERSISTENT / RETURNED / WORSENING / IMPROVING /
  RESOLVED, driven by window presence + per-family intensity trends.
- Metric deltas W1→W4 (MTTR, escalation rate, backlog, SLA, in %).
- "Persistent Supervisory Concern" indicator + review-trigger recommendation
  ("consider earlier supervisory review / re-assessment" — human decision only).
- New `GET /api/assessments` + **Assessments** console page (longitudinal matrix).

### Anomaly/outlier presentation (spec §6)
- Every anomaly signal now carries an explicit `method` attribution (statistical
  z-score / IsolationForest / robust Mahalanobis / day-of-week pattern / TV-distance
  campaign); Signals page gains a method filter and per-signal method line.

### Score bands & configuration (spec §8, §9)
- Fifth band: Critical Attention (`attn_critical`, default 85); all band thresholds
  configurable.
- New **Configuration** page: score-weight sliders with normalize-to-100 and reset,
  band thresholds, detection thresholds — clearly separated; saves recompute and are
  audited; before/after ranking impact shown.

### Peer benchmarking expansion (spec §10)
- Group medians extended: closure rate, alert volume, critical share (+ existing MTTR,
  SLA, escalation rate, backlog, investigation duration).
- New `GET /api/peers` + peer dashboard on the Assessments page with ▲▼ significant-
  deviation markers and neutral wording.

### CAF crosswalk & positioning (spec §11)
- Static, hedged crosswalk (finding → "potentially relevant" capability area →
  evidence type) rendered in the printable Supervisor Report.
- Positioning statement + no-compliance-certification disclaimer on the Architecture
  page; SAT-SA positioned as an operational-evidence layer between assessment cycles.

### Boundary, roles & security (spec §13, §14)
- Internal 4-role model: Administrator / Supervisor / Analyst / Auditor with distinct
  permissions (reset is admin-only; auditors read-only). No CSE-facing portal.
- Passwords may be stored as `sha256$<hex>`; uploads restricted to `.csv` ≤ 8 MB
  (415/413 responses); config/ingest/reset/action permission checks centralized.

### Evidence graph & demo case (spec §3, §17)
- Dedicated **Evidence Graph explorer** page (pick CSE → finding → chain, or trace any
  alert ID); graph engine unchanged from v3.
- `GET /api/demo-case` + Overview card: live "conventional KPI vs SAT-SA evidence"
  comparison on the planted closure-pattern entity (82.6% closure KPI vs ×39
  repetitive fast-closure signature) — the before/after demo story.

### Performance & docs (spec §18, §20, §21)
- Database indexes on all hot paths (alerts/cases/investigations/escalations/assets);
  12-entity recompute 1.4 s → 0.5 s; scaling table in README §8 from the real run.
- New `docs/SCHEMA.md`: field-level documentation for every entity type.
- README fully rewritten (14 sections incl. architecture diagram, hardware baseline,
  known limitations, demo script, PS mapping).

### UI navigation (spec §19)
Overview · Entities · Signals · Review Queue · Evidence Graph · Data Quality ·
Assessments · Benchmark & Validation · Configuration · Audit · Ingest · Architecture.

### Fix: pandas 3.x compatibility (found via user's Docker run)
- pandas 3.0 (now installed by `pandas>=2.2`) returns SQL NULLs as float NaN;
  starlette's `allow_nan=False` renderer 500'd every `/api/entities/{id}` detail.
  Fixed at the root (`entity_detail` coerces NaN→None) plus a global
  `NanSafeJSON` response class so no endpoint can 500 on this class of error.
  Full suite (44/44) verified under pandas 2.2.3 **and** 3.0.5.

### Deliberately not added (spec §24)
No blockchain beyond the existing notary extension point, no cloud/external AI, no
multi-tenant CSE portal, no distributed infrastructure, no hardcoded metrics.

## v3.0 — production-oriented supervisory platform (spec §1–§18)

Built incrementally on top of v2 — no functionality removed; every v2 endpoint, page
and test kept working (18/18 v2 tests still pass, now 33 tests total).

### Evidence model & integrity (spec §1, §11)
- **Schema v3** (`datagen.py`): new tables `assets`, `cases`, `investigations`,
  `escalations`, `quarantine`, `notary`; `alerts` gained `asset_id` and a hidden
  `gt_review` ground-truth flag. Old databases are detected (`schema_current()`) and
  rebuilt automatically at boot.
- **Evidence graph** (`analytics.graph_alert` / `graph_finding`,
  `/api/graph/*`, `EvidenceGraph.jsx`): CSE → Asset → Alert → Case → Investigation /
  Escalation → Resolution, every node backed by a stored DB row (click-through), with
  *virtual missing nodes* for expected-but-absent evidence.
- **Notary chain**: SHA-256 fingerprint of the evidence base per recompute, hash-chained
  rows, `/api/notary` integrity verification — the safe, non-buzzword blockchain
  extension point.

### Prioritization (spec §2)
- Review-sample engine: critical/high + campaign alerts scored with visible reasons and
  confidence; `/api/samples?k=` and the **Review Queue** page (top 10/25/50/100).
- Live P@K/R@K for K ∈ {10, 25, 50} + workload-reduction metric against hidden ground
  truth; ground truth never leaks into the queue payload.

### Negative space (spec §3)
- New detectors: `blind_spot` (critical monitored assets with zero telemetry — includes
  the silent-SOC inference), `no_inv` (critical cases without investigation records),
  `cat_absent` (sector-expected category missing from an active CSE), `pattern_repeat`
  (same suspicious closure signature repeated ≥ threshold). All hedged wording.

### Transparent attention score (spec §4)
- 0–100 Supervisory Attention Score = weighted sum of six visible parts (execution,
  negative space, anomaly, peer deviation, criticality, evidence confidence); weights
  and label thresholds configurable at runtime (`PUT /api/config`), breakdown rendered
  on entity pages.

### Peer benchmarking 2.0 (spec §5)
- Relevance-based peer groups (sector when ≥ 3 members, else size-tier × criticality),
  group medians incl. investigation duration, neutral deviation wording.

### Longitudinal assessment (spec §6)
- Four 30-day assessment windows per CSE with issue-family tracking and
  persistent / emerging / resolved classes (`/api/entities/{id}/history`, entity page).

### Structured explainability (spec §7, §8)
- `analytics.explain()`: WHAT / WHY / EVIDENCE (DB table references + raw values) /
  HOW UNUSUAL (observed vs benchmark, percentile, peer group) / CONFIDENCE (score +
  basis) / WHAT TO REVIEW. Optional local-LLM narrative rewrite; LLM never scores.

### Validation framework (spec §9)
- `/api/validation` + **Validation** page: live detector matrix vs seeded ground truth
  (P/R/F1/FPR, per-family tp/fp/fn), P@K table, workload reduction, per-entity DQ
  scores, quarantine log, expected-vs-detected matrix. Current live numbers:
  P = R = F1 = 1.000, FPR = 0, P@10 = P@25 = 1.00, workload reduction 95 %.
- Ground-truth scenarios extended: blind asset, missing-investigation pattern (×30
  planted closures), absent category, quarantined malformed submissions, recent
  submission outage, phishing campaign ground-truth samples.

### Data quality (spec §13)
- `validate.py` single gate for ingest + seeding: bad timestamps, non-numeric/negative
  values, out-of-range rates, intra-file duplicates, missing entity ids → quarantine
  with reasons (surfaced in UI), never silently dropped. Per-entity DQ score.

### Performance (spec §14)
- Vectorized per-window aggregation (single groupby pass per window).
- `scripts/benchmark.py`: 200 entities / 36 k daily rows / 180 k alerts → recompute
  7.9 s, interactive views ≤ 111 ms. Single node, no extra infrastructure.

### Tests (spec §16)
- 33 tests (`tests/test_pipeline.py` 18 v2 + `tests/test_v3.py` 15 new): prioritization,
  graphs (incl. missing-evidence nodes), history classes, attention arithmetic, live
  weights, notary chaining, validation dashboard, quarantine routing, validate units.

### Deliberately not added (spec §17)
- No Kubernetes/microservices/cloud services, no real-time SIEM features, no
  ledger-for-buzzword, no auto-remediation. Human-in-the-loop stays authoritative.

## v2.0 — supervisory prototype
- 12-CSE seeded dataset with planted scenarios; 11 detectors (silent SOC, submission
  gaps, missing escalations, SLA, silent closures, backlog, MTTR, hygiene, spike,
  seasonal two-regime, campaign); IsolationForest + robust Mahalanobis; ground-truth
  evaluation endpoint; React console with dashboard, drill-down, signals, ingest,
  bulletin, report, tour, India map; optional auth/RBAC/audit; HMAC-signed ingest;
  CSP-hardened single-process offline deployment; Docker.

## v1.0 — initial prototype
- FastAPI + SQLite + pandas/numpy/scikit-learn pipeline; CSV ingest with upsert;
  rule-engine signals; React + Tailwind + Recharts console.
