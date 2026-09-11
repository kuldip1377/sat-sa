#!/usr/bin/env python3
"""SAT-SA benchmark CLI (PS 26157 §validation + §performance).

Runs, from the command line, on this machine, with no network:

  1. Seed-dataset detector evaluation      (the dataset thresholds were tuned on)
  2. HELD-OUT detector evaluation          (independent seed, shifted patterns)
  3. Review-sample prioritization quality  (P@K / R@K, workload reduction)
  4. Scaling benchmark                     (12 / 60 / 200 entities)

Every number printed is computed at run time.  Nothing is hardcoded.

Usage:
    cd backend && python3 benchmark.py            # everything
    cd backend && python3 benchmark.py --validation-only
    cd backend && python3 benchmark.py --perf-only
"""
import os
import random
import sqlite3
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import analytics, datagen  # noqa: E402

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE entities(id TEXT PRIMARY KEY, name TEXT, sector TEXT, criticality TEXT,
                      assets INT, soc_maturity TEXT);
CREATE TABLE assets(id TEXT PRIMARY KEY, entity_id TEXT, name TEXT, type TEXT,
                    criticality TEXT, monitoring TEXT);
CREATE TABLE daily(entity_id TEXT, date TEXT, alerts_total INT, alerts_critical INT,
  alerts_high INT, alerts_medium INT, alerts_low INT, cases_opened INT,
  cases_closed INT, escalations INT, open_critical_end INT, ack_min_median REAL,
  mttr_hours REAL, sla_violation_rate REAL, silent_close_rate REAL,
  missing_field_rate REAL, submission_lag_hours REAL, PRIMARY KEY (entity_id, date));
CREATE TABLE alerts(id TEXT PRIMARY KEY, entity_id TEXT, ts TEXT, severity TEXT,
  category TEXT, status TEXT, ack_minutes REAL, case_id TEXT, disposition TEXT,
  asset_id TEXT, gt_review INT DEFAULT 0);
CREATE TABLE cases(id TEXT PRIMARY KEY, entity_id TEXT, alert_id TEXT, opened_ts TEXT,
  closed_ts TEXT, status TEXT, disposition TEXT);
CREATE TABLE investigations(id TEXT PRIMARY KEY, case_id TEXT, entity_id TEXT,
  started_ts TEXT, duration_min REAL, actions INT);
CREATE TABLE escalations(id TEXT PRIMARY KEY, entity_id TEXT, case_id TEXT, ts TEXT,
  reason TEXT);
CREATE TABLE quarantine(id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT,
  raw TEXT, reason TEXT, ts TEXT);
CREATE TABLE notary(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, event TEXT,
  fingerprint TEXT, prev_hash TEXT, hash TEXT);
CREATE TABLE actions(id INTEGER PRIMARY KEY AUTOINCREMENT, signal_id TEXT,
  entity_id TEXT, action TEXT, note TEXT, user TEXT, ts TEXT);
CREATE TABLE audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, user TEXT,
  event TEXT, detail TEXT);
"""
SECTORS = list(datagen.SECTOR_EXPECT_CAT)
CATS = list(datagen.CATEGORIES)
SEVS = ["Critical", "High", "Medium", "Low"]


# =====================================================================
# validation
# =====================================================================
def _print_eval(title, ev, prio):
    print(f"\n{title}")
    print("-" * len(title))
    print(f"  true positives   {ev['tp']:4d}      false positives  {ev['fp']:4d}")
    print(f"  false negatives  {ev['fn']:4d}      true negatives   {ev['negatives']:4d}")
    print(f"  precision        {ev['precision']:.3f}     recall           {ev['recall']:.3f}")
    print(f"  F1               {ev['f1']:.3f}     FPR              {ev['fpr']:.3f}")
    if ev["missed"]:
        print(f"  missed:  {', '.join(ev['missed'])}")
    if ev["extras"]:
        print(f"  extras:  {', '.join(ev['extras'])}")
    print(f"  prioritization ({prio['gt_total']} ground-truth samples "
          f"in {prio['candidates']} candidates):")
    for k in sorted(prio["per_k"], key=int):
        v = prio["per_k"][k]
        print(f"     K={k:>3}   P@K {v['precision_at_k']:.3f}   R@K {v['recall_at_k']:.3f}")
    print(f"  workload reduction vs full review: {prio['workload_reduction']:.1%}")
    print("  per-detector tp/fp/fn:")
    for k, v in sorted(ev["per_key"].items()):
        print(f"     {k:<16} {v['tp']:>2} / {v['fp']:>2} / {v['fn']:>2}")


def validation():
    print("=" * 72)
    print("SAT-SA VALIDATION BENCHMARK")
    print(f"run: {date.today().isoformat()}   python {sys.version.split()[0]}   "
          "offline / single node")
    print("=" * 72)
    primary = datagen.DB
    datagen.DB = os.path.join(os.path.dirname(primary), "satsa_seed_bench.db")
    try:
        datagen.build(force=True)
        c = analytics.recompute()
        _print_eval("1. SEED DATASET — thresholds were tuned on this data "
                    "(optimistic by construction)", c["evalr"],
                    c["evalr"]["prioritization"])
    finally:
        if os.path.exists(datagen.DB):
            os.remove(datagen.DB)
        datagen.DB = primary
    h = analytics.run_holdout()
    _print_eval("2. HELD-OUT DATASET — independent seed, shifted pattern placements, "
                "magnitudes\n   and categories; never used for tuning (honest estimate)",
                h, h["prioritization"])
    cf = h["confusion"]
    print("\n   held-out confusion matrix (entity × detector-key decisions)")
    print("                     predicted POS   predicted NEG")
    print(f"     actual POS      {cf['tp']:>13}   {cf['fn']:>13}")
    print(f"     actual NEG      {cf['fp']:>13}   {cf['tn']:>13}")
    print("\n3. SIGNAL-CLASS ATTRIBUTION")
    print("-" * 34)
    print("   Rule/statistics detectors (sla, silent_close, backlog, mttr, no_esc,")
    print("   silent_soc, sub_gap, blind_spot, no_inv, cat_absent, pattern_repeat,")
    print("   spike, seasonal, campaign, hygiene)  -> SCORED above.")
    print("   ML context signals (if_anom=IsolationForest, maha=robust Mahalanobis)")
    print("   -> deliberately EXCLUDED from the ground-truth score. They corroborate")
    print("      and prioritize; the reported recall is NOT attributable to them.")
    print("\n4. DATA-QUALITY GATE (pre-analytics)")
    print("-" * 41)
    datagen.build(force=True)
    analytics.recompute()
    dq = analytics.dataquality()
    print(f"   dimensions: " + "  ".join(f"{k} {v:.0f}" for k, v in dq["dimensions"].items()))
    print(f"   overall {dq['overall']:.0f}/100   records {dq['totals']['records']} "
          f"(valid {dq['totals']['valid']}, warning {dq['totals']['warning']}, "
          f"rejected {dq['totals']['rejected']})")


# =====================================================================
# scaling / performance
# =====================================================================
def _gen(path, n_ent, days=180, alerts_per_ent=900):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.execute("INSERT INTO meta VALUES ('schema_version', '3')")
    today = date.today()
    dates = [(today - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
    ents, assets, daily, alerts, cases, invs = [], [], [], [], [], []
    for e in range(n_ent):
        eid = f"B-{e:04d}"
        ents.append((eid, f"Bench CSE {e}", SECTORS[e % len(SECTORS)], "High", 1000,
                     "Level 3"))
        aids = []
        for a in range(8):
            aid = f"AS-{eid}-{a}"
            aids.append(aid)
            assets.append((aid, eid, f"srv-{a}", "Server",
                           "Critical" if a < 2 else "Medium", "monitored"))
        for d in dates:
            tot = max(0, int(random.gauss(20, 4)))
            crit, high = int(tot * 0.08), int(tot * 0.2)
            med = int(tot * 0.3)
            daily.append((eid, d, tot, crit, high, med, tot - crit - high - med,
                          int(tot * 0.3), int(tot * 0.25), int(crit * 0.3), crit,
                          30 + random.random() * 20, 10 + random.random() * 5,
                          0.1, 0.05, 0.03, 6))
        for j in range(alerts_per_ent):
            day = random.randint(0, days - 1)
            sev = random.choices(SEVS, [0.08, 0.22, 0.35, 0.35])[0]
            aid, cid = f"A-{eid}-{j:05d}", f"C-{eid}-{j:05d}"
            alerts.append((aid, eid, f"{dates[day]}T{random.randint(0,23):02d}:00:00",
                           sev, random.choice(CATS),
                           random.choice(["Open", "Closed", "Escalated"]),
                           round(random.uniform(5, 200), 1), cid,
                           "resolved" if random.random() < 0.5 else None,
                           random.choice(aids), 0))
            closed = random.random() < 0.7
            cases.append((cid, eid, aid, f"{dates[day]}T10:00:00",
                          f"{dates[min(day+2, days-1)]}T10:00:00" if closed else None,
                          "Closed" if closed else "Open",
                          "resolved" if closed else None))
            if random.random() < 0.6:
                invs.append((f"I-{eid}-{j:05d}", cid, eid, f"{dates[day]}T11:00:00",
                             round(random.uniform(20, 90), 1), random.randint(1, 5)))
    con.executemany("INSERT INTO entities VALUES (?,?,?,?,?,?)", ents)
    con.executemany("INSERT INTO assets VALUES (?,?,?,?,?,?)", assets)
    con.executemany("INSERT INTO daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", daily)
    con.executemany("INSERT INTO alerts VALUES (?,?,?,?,?,?,?,?,?,?,?)", alerts)
    con.executemany("INSERT INTO cases VALUES (?,?,?,?,?,?,?)", cases)
    con.executemany("INSERT INTO investigations VALUES (?,?,?,?,?,?)", invs)
    con.commit()
    n_daily, n_alerts = len(daily), len(alerts)
    con.close()
    return n_daily, n_alerts


def perf():
    print("\n" + "=" * 72)
    print("SCALING BENCHMARK — single node, SQLite, no distributed infrastructure")
    print("=" * 72)
    print(f"  {'entities':>9} {'daily rows':>11} {'alert rows':>11} {'signals':>8} "
          f"{'recompute':>10} {'overview':>9} {'detail':>8} {'graph':>7}")
    primary = datagen.DB
    random.seed(7)
    try:
        for n in (12, 60, 200):
            path = f"/tmp/satsa_bench_{n}.db"
            n_daily, n_alerts = _gen(path, n)
            datagen.DB = path
            t0 = time.perf_counter()
            c = analytics.recompute()
            t1 = time.perf_counter()
            t2 = time.perf_counter(); analytics.overview(); t3 = time.perf_counter()
            t4 = time.perf_counter(); analytics.entity_detail(c["ranked"][0])
            t5 = time.perf_counter()
            t6 = time.perf_counter()
            if c["signals"]:
                analytics.graph_finding(c["signals"][0]["id"])
            t7 = time.perf_counter()
            print(f"  {n:>9} {n_daily:>11,} {n_alerts:>11,} {len(c['signals']):>8} "
                  f"{t1-t0:>9.2f}s {t3-t2:>8.3f}s {t5-t4:>7.3f}s {t7-t6:>6.3f}s")
            os.remove(path)
    finally:
        datagen.DB = primary
        datagen.build(force=True)
        analytics.recompute()
    print("\n  recompute is the only O(data) pass and runs once per ingest; every")
    print("  interactive view is served from the in-memory cache. Production scaling")
    print("  path: batched ingest, indexed PostgreSQL, parallel window aggregation —")
    print("  none of it required at prototype scale.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--perf-only" in args:
        perf()
    elif "--validation-only" in args:
        validation()
    else:
        validation()
        perf()
