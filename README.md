# SAT-SA — Supervisory Analytics Tool for SOC Assessment

**Smart India Hackathon 2026 · Problem Statement 26157 (NTRO) · Software / Smart Automation**

## 1. Problem statement

NCIIPC periodically assesses the SOC posture of Critical Sector Entities (CSEs) from
structured evidence the CSEs submit. Examiners must decide, per assessment cycle:

1. Which entities deserve attention?
2. Which operational areas may contain weaknesses?
3. Which alerts/cases are most valuable for manual review?
4. What evidence caused a finding — and what expected evidence is missing?
5. Whether weaknesses are improving, persisting, or worsening?

## 2. What SAT-SA is (and is not)

SAT-SA is an **offline, evidence-driven supervisory decision-support system**. It is
**not** a SOC, a SIEM, a real-time monitoring platform, a log-collection system, or a
replacement for human examiners. Every output is an *indicator for supervisory
examination* — hedged wording throughout, never a confirmed violation. CSEs submit
data; the NCIIPC-controlled SAT-SA processes it; human supervisors decide.

## 3. Architecture

```
┌────────────────────────────  NCIIPC air-gapped enclave  ────────────────────────────┐
│                                                                                      │
│  CSE submissions ──► DATA QUALITY GATE ──► FEATURE ENGINEERING (per entity/window)   │
│  (CSV/JSON,           validate.py          daily aggregates + evidence layer         │
│   optional HMAC)      quarantine+warn      (alerts→cases→investigations→escalations) │
│                              │                                                       │
│                              ▼                                                       │
│              RULE + STATISTICS ENGINE (15 detectors)                                 │
│              execution gaps · negative space · hygiene                               │
│                              │                                                       │
│                              ▼                                                       │
│              ANOMALY/OUTLIER CONTEXT (IsolationForest, robust Mahalanobis)           │
│                              │                                                       │
│                              ▼                                                       │
│              PEER BENCHMARKING 2.0 ──► SUPERVISORY ATTENTION SCORE (transparent,     │
│              (relevance groups)        6 weighted parts, configurable bands)         │
│                              │                                                       │
│                              ▼                                                       │
│         CSE PRIORITIZATION ──► INTELLIGENT SAMPLE PRIORITIZATION (top-K, P@K/R@K)    │
│                              │                                                       │
│                              ▼                                                       │
│         EVIDENCE GRAPH ──► EXPLAINABLE FINDING (6-question template) ──►             │
│                              │                                                       │
│                              ▼                                                       │
│                    HUMAN NCIIPC SUPERVISOR  (audit trail + notary chain)             │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Single process: FastAPI serves the API **and** the built React console on one origin.
SQLite by default (swap `DATABASE_URL` for PostgreSQL in production — plain SQL schema).
No CDNs, no cloud, no outbound calls; CSP `connect-src 'self'`.

## 4. Repository layout & run

```
backend/app/         datagen.py (seed + held-out datasets) · validate.py (DQ gate)
                     analytics.py (detectors, scoring, graphs, validation) · main.py (API)
backend/benchmark.py reproducible validation + scaling benchmark CLI
backend/tests/       44 automated tests
frontend/            React + Vite + Tailwind + Recharts console
docs/SCHEMA.md       full field-level data schema documentation
Dockerfile, docker-compose.yml, run.sh
```

```bash
./run.sh                                   # http://localhost:8000
docker compose up --build                  # air-gapped container
cd backend && python3 -m pytest tests -q   # 44 tests
cd backend && python3 benchmark.py         # validation + scaling numbers below
```

## 5. Input schema

Seventeen-column daily submission per entity (see `docs/SCHEMA.md` for the complete
field-level spec of every table: CSE, asset, alert, case, investigation, escalation,
disposition, assessment, finding, audit event, quarantine, notary):

`entity_id, date, alerts_total, alerts_critical, alerts_high, alerts_medium,
alerts_low, cases_opened, cases_closed, escalations, open_critical_end,
ack_min_median, mttr_hours, sla_violation_rate, silent_close_rate,
missing_field_rate, submission_lag_hours`

Plus alert-level evidence records (severity, category, status, ack, case, asset).
Uploads are limited to `.csv` ≤ 8 MB; optionally HMAC-SHA256-signed for provenance.

## 6. Data quality (pre-analytics)

Submission → validation → quality score → accepted / warning / rejected → analytics.
Checks: schema validity, missing values, invalid dates, negative values, out-of-range
rates, intra-file duplicates, severity-sum consistency, late submissions, high
missing-field rates, reporting gaps. Five scored dimensions (schema .25, completeness
.25, consistency .2, timeliness .15, uniqueness .15) roll up to a 0–100 score per
entity and overall. Rejected rows are quarantined with machine-readable reasons and
exportable; nothing is silently discarded.

## 7. Analytics methodology

- **Execution gaps** — SLA breach rate, silent closures (criticals with no case),
  growing critical backlog, MTTR vs peer multiple, repetitive suspicious closure
  pattern (same signature ≥ 20×: case opened → closed fast → no investigation →
  no escalation).
- **Negative space** — silent SOC (zero-telemetry days), submission gaps, suppressed
  escalations, blind spots (critical monitored assets with zero alert records),
  cases without investigations, sector-expected category absent.
- **Anomaly detection (explicit method attribution)** — statistical (robust z-score
  vs own baseline), pattern (day-of-week two-regime rule; category-mix TV distance),
  behavioural (IsolationForest — ML *context only*), multivariate peer outlier
  (robust Mahalanobis, median/MAD, χ² envelope). Each anomaly signal states which
  method produced it.
- **Peer benchmarking 2.0** — relevance-based peer groups (sector when ≥ 3 members,
  else size-tier × criticality) with medians for MTTR, SLA, escalation rate, open
  backlog, closure rate, alert volume, critical share, investigation duration.
  Wording is neutral: deviation is an examination prompt, not a judgement.
- **Supervisory Attention Score** — transparent 0–100 sum of six visible parts
  (execution, negative space, anomaly, peer deviation, criticality, evidence
  confidence) with runtime-configurable weights normalized to 100 and configurable
  bands: Normal / Watch / Attention / High Priority / Critical Attention. Score and
  category are always displayed together with the full breakdown.
- **Explainability (6 questions)** — every finding answers WHAT / WHY / EVIDENCE
  (DB table references + raw values) / HOW UNUSUAL (observed vs benchmark, percentile,
  peer group) / CONFIDENCE (score + basis) / WHAT TO REVIEW NEXT. An optional local
  LLM (Ollama, offline) may rewrite narratives only — it never influences scores.
- **Review prioritization** — multi-factor supervisory value per alert sample
  (severity, asset criticality, missing workflow evidence, pattern/campaign
  membership, SLA context) with visible "why selected" reasons and confidence;
  validated with P@K/R@K (ground truth never leaks into the queue).
- **Assessment-to-assessment comparison** — four 30-day windows per CSE; findings
  classified NEW / PERSISTENT / RETURNED / WORSENING / IMPROVING / RESOLVED with
  metric deltas (MTTR, escalation rate, backlog, SLA). Sustained high attention
  generates a "Persistent Supervisory Concern" indicator and a recommendation to
  consider earlier supervisory review — a recommendation for the human supervisor,
  never an automated regulatory decision.

## 8. Validation methodology (never hardcoded)

Two datasets, both scored live:

- **Seed dataset** — scenarios on which detector thresholds were tuned (optimistic by
  construction; reported separately for honesty).
- **Held-out dataset** — independent seed with *shifted* pattern placements,
  magnitudes and categories (different silence window, different campaign category,
  different surge days, 24× vs 30× closure pattern, 7-day vs 4-day outage) plus
  false-positive-prone healthy entities (near-threshold silent-close rate, missing
  days outside the assessment window, elevated-but-acceptable MTTR). Never used for
  tuning.

Rule/statistics detectors are scored against ground truth; IsolationForest and
Mahalanobis are deliberately **excluded** — the reported recall is not attributable
to ML. Latest actual run (reproduce with `python3 backend/benchmark.py`):

```
1. SEED DATASET        P 1.000  R 1.000  F1 1.000  FPR 0.000   (20 tp / 0 fp / 0 fn / 160 tn)
   prioritization      P@10 1.000 · P@25 1.000 · P@50 0.880 · R@50 0.629 · workload −95.0%
2. HELD-OUT DATASET    P 1.000  R 1.000  F1 1.000  FPR 0.000   (20 tp / 0 fp / 0 fn / 160 tn)
   prioritization      P@10 1.000 · P@25 1.000 · P@50 0.800 · R@50 0.667 · workload −94.6%
   confusion matrix    actual POS → pred POS 20, pred NEG 0 · actual NEG → pred POS 0, pred NEG 160
4. DATA-QUALITY GATE   schema 99 · completeness 93 · consistency 99 · timeliness 94 ·
                       uniqueness 100 → overall 97/100 (355 records: 331 valid, 21 warning, 3 rejected)

SCALING (single node)  entities/daily/alerts → recompute · overview · detail · graph
        12     2,160    10,800 → 0.48s · 7ms · 8ms · 11ms
        60    10,800    54,000 → 1.90s · 8ms · 12ms · 35ms
       200    36,000   180,000 → 6.69s · 11ms · 24ms · 121ms
```

Recompute is the only O(data) pass (once per ingest); all interactive views are served
from cache. Production scaling path: batched ingest, indexed PostgreSQL (indexes ship
in the schema), parallel window aggregation — none required at prototype scale.

## 9. Console navigation

Overview · CSE Entities (drill-down: score breakdown, longitudinal history, peer group,
samples, evidence graphs) · Supervisory Signals (method attribution, structured
explanations, actions) · Review Queue (top 10/25/50/100 with why-selected + P@K) ·
Evidence Graph explorer · Data Quality · Assessments (comparison matrix + peer
dashboard) · Benchmark & Validation (seed vs held-out, confusion matrix) ·
Configuration (score weights ≠ detection thresholds ≠ bands; audited saves) · Audit
(+ notary chain) · Data Ingest · Architecture (CAF positioning, role model).

## 10. Offline deployment & security

- Air-gap: no runtime network calls; CSP `connect-src 'self'`; zero CDN/font/telemetry
  references; optional AI is a *local* Ollama endpoint (narratives only).
- Security headers, optional login + offline RBAC (Administrator / Supervisor /
  Analyst / Auditor — CSEs never log in), HMAC-signed submissions, audit trail on
  every privileged action, SHA-256 notary chain over the evidence base per recompute
  (documented extension point for a permissioned ledger; no sensitive data on-chain),
  password fields support `sha256$<hex>` storage, `.csv`-only uploads ≤ 8 MB.
- Hardware baseline (measured here): Python 3.13 / Node 20, 2 vCPU, ~2 GB RAM,
  SSD — comfortably runs 200 entities / 180 k alerts with sub-8 s recompute.

## 11. Tests

`cd backend && python3 -m pytest tests -q` — **44 tests**: pipeline end-to-end,
seeded-scenario detection, live eval integrity, prioritization (order, reasons, hidden
ground truth), evidence graphs incl. missing-evidence nodes, history statuses & deltas,
attention arithmetic, bands, live weights, held-out validation, data-quality gate &
export, warning tier, RBAC roles, upload limits, notary chaining, validate.py units.

## 12. Known limitations

- SQLite + in-process cache targets single-node deployment; multi-node NCIIPC rollout
  needs PostgreSQL and a job queue for recompute (documented, not built).
- Detector thresholds are tuned on synthetic scenario families; real-world CSE data
  will require a supervised calibration cycle with NCIIPC examiners.
- The held-out dataset shares scenario *families* with the seed set (shifted
  parameters) — it tests generalization of placement/magnitude/category, not entirely
  novel attack-process archetypes.
- Peer groups are only as meaningful as the entity registry metadata (sector, size,
  criticality).
- No real NCIIPC operational data is used or implied anywhere in this prototype.

## 13. Demo script (5 minutes)

1. **Overview** — national KPIs; the "Why KPIs alone are not enough" card contrasts
   BNK-02's healthy closure-rate KPI with the ×39 repetitive fast-closure signature
   (all numbers live).
2. **Review Queue** — top-25 with reasons; open the evidence graph on a BNK-02 sample:
   dashed-red *missing investigation / missing escalation* nodes.
3. **Entities → BNK-02** — attention breakdown, "execution · PERSISTENT", review-trigger
   recommendation; open the Supervisor Report (prints to PDF) with the indicative
   assessment-context crosswalk.
4. **Assessments** — longitudinal matrix + peer dashboard.
5. **Data Quality** — quarantine with reasons; upload a CSV with a bad date on the
   Ingest page and watch it quarantine.
6. **Benchmark & Validation** — held-out numbers generated live in the browser.
7. **Audit** — every action you just took, plus the intact notary chain.

## 14. Mapping to PS 26157

| PS requirement | where |
|---|---|
| SOC effectiveness assessment | execution-gap + negative-space detectors, attention score |
| Entity prioritization | ranked entities, attention bands, persistent-concern flags |
| Sample prioritization | Review Queue, P@K/R@K, workload reduction |
| Evidence traceability | evidence graph, per-finding DB refs, audit trail, notary chain |
| Peer comparison | peer groups 2.0 dashboard, Mahalanobis context |
| Trend / longitudinal analysis | 4-window assessments, six statuses, deltas, review trigger |
| Explainability | 6-question structured template, method attribution |
| Data quality | pre-analytics gate, quarantine, DQ scores & export |
| Validation | seed + held-out evaluation, confusion matrix, live metrics only |
| Offline / air-gapped | single process, no outbound calls, Docker, CSP |
| Security & governance | RBAC (4 roles), audit, HMAC, upload limits, hashed passwords |
| Scalability | benchmarked to 200 entities / 180 k alerts on one node |
| Human-in-the-loop | hedged wording everywhere, recommendations only |

Changelog: see [CHANGELOG.md](CHANGELOG.md).
