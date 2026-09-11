"""Synthetic SOC operational data generator for the SAT-SA demo (schema v3).

Seeds an offline SQLite database with 120 days of structured SOC records for
12 fictional CSEs, including a full EVIDENCE LAYER:

    CSE -> Asset -> Alert -> Case -> Investigation -> Escalation -> Resolution

Every relationship is generated from an explicit foreign key, so every graph
node/edge is traceable to a database record (no fabricated links).

Seeded supervisory scenarios (ground truth in EXPECTED):
  BNK-02  execution-gap cluster + repetitive suspicious closure pattern +
          cases without investigation
  PWR-02  silent SOC (negative space) -> monitoring blind spots
  TEL-02  submission gaps + data hygiene (incl. quarantined malformed rows)
  TEL-01  alert-volume spike + phishing campaign
  OIL-02  criticals investigated but never escalated
  OIL-01  healthy, except one critical asset that silently lost telemetry
  TRN-02  growing unresolved critical backlog
  GOV-02  MTTR outlier + expected alert category absent
  GOV-01  ack-time pattern breaks (seasonal anomaly)

`gt_review` marks alerts an expert examiner would pull for manual review;
it is used ONLY by /api/eval to score the prioritization engine (P@K/R@K).
"""
import os
import random
import sqlite3
from datetime import date, timedelta

import pandas as pd

from . import validate

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "satsa.db")
SCHEMA_VERSION = 3
DAYS = 120
TODAY = date.today()

ASSET_TYPES = {
    "Power": ["SCADA/EMS Server", "RTU Gateway", "Historian DB", "Substation PLC"],
    "Banking & Finance": ["Core Banking DB", "Payment Gateway", "SWIFT Interface", "ATM Switch"],
    "Telecom": ["Core Router", "HLR/HSS", "Session Border Ctrl", "Billing DB"],
    "Transportation": ["Signalling Controller", "Ops Database", "Radio Network", "Freight Mgmt"],
    "Oil & Gas": ["DCS Server", "Pipeline SCADA", "Tank Gauging", "Safety PLC"],
    "Government": ["Citizen Portal", "Identity DB", "Records Store", "Mail Gateway"],
}
SECTOR_EXPECT_CAT = {
    "Power": "Intrusion Attempt", "Banking & Finance": "Phishing", "Telecom": "DDoS",
    "Transportation": "Misconfiguration", "Oil & Gas": "Malware", "Government": "Phishing",
}
CATEGORIES = ["Malware", "Phishing", "Intrusion Attempt", "DDoS",
              "Insider Threat", "Vulnerability Exploit", "Misconfiguration"]
DISPOSITIONS = ["Contained & Resolved", "False Positive", "Referred to NCIIPC",
                "Patched", "Under Monitoring"]

ENTITIES = [
    ("PWR-01", "National Grid Corporation", "Power", "Critical",
     dict(base=22, crit=0.10, ack=25, mttr=8, sla=0.06, sc=0.02, esc=0.35, miss=0.01, lag=4)),
    ("PWR-02", "State Power Utilities Ltd", "Power", "Critical",
     dict(base=18, crit=0.10, ack=35, mttr=12, sla=0.10, sc=0.04, esc=0.25, miss=0.02, lag=6,
          silent=(95, 120))),
    ("BNK-01", "Union State Bank", "Banking & Finance", "Critical",
     dict(base=45, crit=0.12, ack=18, mttr=6, sla=0.05, sc=0.02, esc=0.40, miss=0.01, lag=3)),
    ("BNK-02", "National Payments Corp", "Banking & Finance", "Critical",
     dict(base=40, crit=0.12, ack=95, mttr=30, sla=0.38, sc=0.24, esc=0.20, miss=0.03, lag=10,
          backlog=0.8, no_inv=True)),
    ("TEL-01", "Bharat Telecom Link", "Telecom", "Critical",
     dict(base=30, crit=0.10, ack=28, mttr=9, sla=0.08, sc=0.03, esc=0.30, miss=0.02, lag=5,
          spike=(75, 95, 3.0), campaign=(100, 120, "Phishing", 0.65))),
    ("TEL-02", "Metro Fibre Networks", "Telecom", "High",
     dict(base=26, crit=0.09, ack=40, mttr=14, sla=0.12, sc=0.05, esc=0.22, miss=0.26, lag=30,
          drops=6, dirty=True, recent_drops=(116, 119))),
    ("TRN-01", "Railway Systems Corp", "Transportation", "High",
     dict(base=15, crit=0.08, ack=30, mttr=10, sla=0.09, sc=0.03, esc=0.28, miss=0.02, lag=5)),
    ("TRN-02", "Coastal Ports Authority", "Transportation", "High",
     dict(base=14, crit=0.11, ack=45, mttr=16, sla=0.14, sc=0.06, esc=0.24, miss=0.03, lag=8,
          backlog=1.2)),
    ("OIL-01", "Petrogas India", "Oil & Gas", "Critical",
     dict(base=12, crit=0.10, ack=22, mttr=7, sla=0.06, sc=0.02, esc=0.33, miss=0.01, lag=4,
          blind_asset=True)),
    ("OIL-02", "Strategic Reserves Corp", "Oil & Gas", "Critical",
     dict(base=16, crit=0.12, ack=30, mttr=11, sla=0.10, sc=0.04, esc=0.0, miss=0.02, lag=6)),
    ("GOV-01", "e-Governance Services", "Government", "High",
     dict(base=10, crit=0.08, ack=50, mttr=16, sla=0.20, sc=0.08, esc=0.20, miss=0.04, lag=12,
          ack_surge=(101, 108, 115))),
    ("GOV-02", "Land Records Bureau", "Government", "Medium",
     dict(base=9, crit=0.07, ack=35, mttr=26, sla=0.10, sc=0.04, esc=0.22, miss=0.02, lag=6,
          cat_absent=True)),
]

# ---- ground-truth manifests (primary detector keys per entity) ----
EXPECTED_SEED = {
    "PWR-01": set(), "BNK-01": set(), "TRN-01": set(),
    "OIL-01": {"blind_spot"},
    "PWR-02": {"silent_soc", "seasonal", "blind_spot"},
    "TEL-02": {"sub_gap", "hygiene"},
    "OIL-02": {"no_esc"},
    "BNK-02": {"sla", "silent_close", "backlog", "mttr", "no_inv", "pattern_repeat"},
    "TRN-02": {"backlog"},
    "GOV-02": {"mttr", "cat_absent"},
    "TEL-01": {"spike", "campaign", "seasonal"},
    "GOV-01": {"seasonal"},
}
EXPECTED = EXPECTED_SEED           # active manifest (swapped by build(variant=…))
AUX_KEYS = {"if_anom", "maha"}

# ---------------------------------------------------------------------------
# HELD-OUT VALIDATION DATASET (spec §1)
# Same scenario FAMILIES as the tuning dataset, but independently seeded and
# with shifted placements, magnitudes and categories.  Detector thresholds
# were tuned ONLY on the seed dataset; this one measures generalization.
# It also contains false-positive-prone healthy entities (short silence below
# threshold, early-window gaps, near-threshold silent-close rate).
# ---------------------------------------------------------------------------
VARIANT_ENTITIES = [
    ("PWR-01", "Northern Grid Trust", "Power", "Critical",
     dict(base=20, crit=0.10, ack=24, mttr=9, sla=0.07, sc=0.12, esc=0.34, miss=0.02, lag=5)),
    # ^ FP-prone: silent-close rate 0.12 sits just under the 0.15 trigger
    ("PWR-02", "Regional Power Board", "Power", "Critical",
     dict(base=20, crit=0.10, ack=33, mttr=13, sla=0.11, sc=0.04, esc=0.26, miss=0.02, lag=6,
          silent=(100, 119))),          # silence placed differently than seed
    ("BNK-01", "Coastal Commerce Bank", "Banking & Finance", "Critical",
     dict(base=42, crit=0.12, ack=19, mttr=7, sla=0.05, sc=0.02, esc=0.38, miss=0.01, lag=3,
          drops=3, drop_zone=(30, 60))),
    # ^ FP-prone: 3 missing days, but OUTSIDE the 30-day assessment window
    ("BNK-02", "National Clearing House", "Banking & Finance", "Critical",
     dict(base=38, crit=0.12, ack=110, mttr=26, sla=0.35, sc=0.20, esc=0.22, miss=0.03, lag=11,
          backlog=1.0, no_inv=True, force_n=24)),   # pattern repeated 24x (seed: 30x)
    ("TEL-01", "Deccan Comms Ltd", "Telecom", "Critical",
     dict(base=28, crit=0.10, ack=30, mttr=10, sla=0.09, sc=0.03, esc=0.31, miss=0.02, lag=5,
          spike=(85, 100, 2.6), campaign=(95, 119, "Ransomware", 0.62))),
    # ^ different spike window/magnitude and a DIFFERENT campaign category
    #   (spike deliberately straddles the recent window, unlike the seed dataset)
    ("TEL-02", "Harbour Fibre Co", "Telecom", "High",
     dict(base=24, crit=0.09, ack=42, mttr=15, sla=0.13, sc=0.05, esc=0.23, miss=0.22, lag=34,
          drops=4, dirty=True, recent_drops=(112, 118))),   # 7-day outage (seed: 4)
    ("TRN-01", "Metro Rail Operations", "Transportation", "High",
     dict(base=16, crit=0.08, ack=28, mttr=18, sla=0.10, sc=0.04, esc=0.27, miss=0.02, lag=6)),
    # ^ FP-prone: elevated MTTR but under the peer-multiplier trigger
    ("TRN-02", "Northern Freightways", "Transportation", "High",
     dict(base=13, crit=0.11, ack=47, mttr=17, sla=0.15, sc=0.06, esc=0.25, miss=0.03, lag=9,
          backlog=1.6)),
    ("OIL-01", "Refinery Networks India", "Oil & Gas", "Critical",
     dict(base=11, crit=0.10, ack=23, mttr=8, sla=0.06, sc=0.02, esc=0.32, miss=0.01, lag=4,
          blind_asset=True)),
    ("OIL-02", "Gas Grid Custodian", "Oil & Gas", "Critical",
     dict(base=17, crit=0.12, ack=31, mttr=12, sla=0.10, sc=0.04, esc=0.0, miss=0.02, lag=6)),
    ("GOV-01", "Public Services Portal", "Government", "High",
     dict(base=11, crit=0.08, ack=48, mttr=15, sla=0.19, sc=0.07, esc=0.21, miss=0.04, lag=11,
          ack_surge=(95, 102, 112))),    # surge days at different positions, x6
    ("GOV-02", "Municipal Records Cell", "Government", "Medium",
     dict(base=10, crit=0.07, ack=36, mttr=30, sla=0.11, sc=0.04, esc=0.23, miss=0.02, lag=6,
          cat_absent=True)),
]
EXPECTED_HOLDOUT = {
    "PWR-01": set(), "BNK-01": set(), "TRN-01": set(),
    "OIL-01": {"blind_spot"},
    "PWR-02": {"silent_soc", "seasonal", "blind_spot"},
    "TEL-02": {"sub_gap", "hygiene"},
    "OIL-02": {"no_esc"},
    "BNK-02": {"sla", "silent_close", "backlog", "mttr", "no_inv", "pattern_repeat"},
    "TRN-02": {"backlog"},
    "GOV-02": {"mttr", "cat_absent"},
    "TEL-01": {"spike", "campaign", "seasonal"},
    "GOV-01": {"seasonal"},
}


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def build(force=True, variant=False):
    """Build the demo database.  variant=True generates the HELD-OUT
    validation dataset (independent seed, shifted pattern parameters)."""
    global EXPECTED
    EXPECTED = EXPECTED_HOLDOUT if variant else EXPECTED_SEED
    if os.path.exists(DB) and not force:
        return DB
    if os.path.exists(DB):
        os.remove(DB)
    random.seed(1337 if variant else 42)
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE entities (
            id TEXT PRIMARY KEY, name TEXT, sector TEXT,
            criticality TEXT, assets INTEGER, soc_maturity TEXT);
        CREATE TABLE assets (
            id TEXT PRIMARY KEY, entity_id TEXT, name TEXT, type TEXT,
            criticality TEXT, monitoring TEXT);
        CREATE TABLE daily (
            entity_id TEXT, date TEXT,
            alerts_total INTEGER, alerts_critical INTEGER, alerts_high INTEGER,
            alerts_medium INTEGER, alerts_low INTEGER,
            cases_opened INTEGER, cases_closed INTEGER, escalations INTEGER,
            open_critical_end INTEGER, ack_min_median REAL, mttr_hours REAL,
            sla_violation_rate REAL, silent_close_rate REAL,
            missing_field_rate REAL, submission_lag_hours REAL,
            PRIMARY KEY (entity_id, date));
        CREATE TABLE alerts (
            id TEXT PRIMARY KEY, entity_id TEXT, ts TEXT, severity TEXT,
            category TEXT, status TEXT, ack_minutes REAL, case_id TEXT,
            disposition TEXT, asset_id TEXT, gt_review INTEGER);
        CREATE TABLE cases (
            id TEXT PRIMARY KEY, entity_id TEXT, alert_id TEXT, opened_ts TEXT,
            closed_ts TEXT, status TEXT, disposition TEXT);
        CREATE TABLE investigations (
            id TEXT PRIMARY KEY, case_id TEXT, entity_id TEXT, started_ts TEXT,
            duration_min REAL, actions INTEGER);
        CREATE TABLE escalations (
            id TEXT PRIMARY KEY, entity_id TEXT, case_id TEXT, ts TEXT, reason TEXT);
        CREATE TABLE quarantine (
            id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT, raw TEXT,
            reason TEXT, ts TEXT);
        CREATE TABLE notary (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, event TEXT,
            fingerprint TEXT, prev_hash TEXT, hash TEXT);
        CREATE TABLE actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, signal_id TEXT, entity_id TEXT,
            action TEXT, note TEXT, user TEXT, ts TEXT);
        CREATE TABLE audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, user TEXT,
            event TEXT, detail TEXT);
        CREATE INDEX IF NOT EXISTS ix_daily_ent ON daily (entity_id, date);
        CREATE INDEX IF NOT EXISTS ix_alerts_ent ON alerts (entity_id, ts);
        CREATE INDEX IF NOT EXISTS ix_alerts_case ON alerts (case_id);
        CREATE INDEX IF NOT EXISTS ix_alerts_asset ON alerts (asset_id);
        CREATE INDEX IF NOT EXISTS ix_cases_ent ON cases (entity_id);
        CREATE INDEX IF NOT EXISTS ix_cases_alert ON cases (alert_id);
        CREATE INDEX IF NOT EXISTS ix_inv_case ON investigations (case_id);
        CREATE INDEX IF NOT EXISTS ix_esc_case ON escalations (case_id);
        CREATE INDEX IF NOT EXISTS ix_assets_ent ON assets (entity_id, criticality);
        """)
    cur.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))

    maturity = {"Critical": "Level 4", "High": "Level 3", "Medium": "Level 2"}
    for eid, name, sector, crit_lv, p in (VARIANT_ENTITIES if variant else ENTITIES):
        types = ASSET_TYPES[sector]
        n_assets = random.randint(6, 10)
        asset_ids, crit_assets = [], []
        for a in range(n_assets):
            aid = f"{eid}-A{a+1}"
            acrit = "Critical" if a < 2 else random.choice(["High", "High", "Medium"])
            mon = "monitored"
            if p.get("blind_asset") and a == 0:
                mon = "monitored"  # claimed monitored, but telemetry goes silent
            asset_ids.append(aid)
            if acrit == "Critical":
                crit_assets.append(aid)
            cur.execute("INSERT INTO assets VALUES (?,?,?,?,?,?)",
                        (aid, eid, f"{types[a % len(types)]} #{a+1}", types[a % len(types)],
                         acrit, mon))
        cur.execute("INSERT INTO entities VALUES (?,?,?,?,?,?)",
                    (eid, name, sector, crit_lv, random.randint(400, 4200),
                     maturity[crit_lv]))
        n_assets_db = n_assets
        blind = crit_assets[0] if p.get("blind_asset") else None

        silent = p.get("silent")
        spike = p.get("spike")
        surges = set(p.get("ack_surge", ()))
        zone = p.get("drop_zone", (DAYS - 40, DAYS - 5))
        drops = set(random.sample(range(zone[0], zone[1]),
                                  min(p["drops"], zone[1] - zone[0]))
                    if p.get("drops") else [])
        expect_cat = SECTOR_EXPECT_CAT[sector]
        open_crit = float(random.randint(0, 4))
        back_carry = 0.0
        k = 0

        def pick_asset(sev, day):
            if blind and day >= 75:           # blind asset loses telemetry recently
                return random.choice([a for a in asset_ids if a != blind])
            if sev == "Critical" and crit_assets and random.random() < 0.7:
                return random.choice(crit_assets)
            return random.choice(asset_ids)

        def pick_cat(day, cat_bias=None):
            if cat_bias and random.random() < cat_bias[1]:
                return cat_bias[0]
            # day >= 89: the analytics 30-day window is `ts > today-30d` (midnight),
            # so intra-day timestamps of day 89 already fall inside it
            if p.get("cat_absent") and day >= 89:   # recent window: expected cat absent
                return random.choice([c for c in CATEGORIES if c != expect_cat])
            return random.choice(CATEGORIES)

        def emit(day, cat_bias=None, force_pattern=False):
            nonlocal k
            ts = (TODAY - timedelta(days=DAYS - 1 - day)).isoformat() + \
                 f"T{random.randint(0,23):02d}:{random.randint(0,59):02d}:00"
            r = random.random()
            sev = ("Critical" if r < p["crit"] else "High" if r < p["crit"] + 0.25
                   else "Medium" if r < p["crit"] + 0.6 else "Low")
            cat = pick_cat(day, cat_bias)
            asset = pick_asset(sev, day)
            gt = 0
            opened = random.random() < 0.55
            closed = opened and random.random() < 0.8
            escalated = False
            inv = None
            case_id = None
            if force_pattern:
                sev = "Critical"   # the planted repetitive pattern is a critical pattern
            if force_pattern or (p.get("no_inv") and sev == "Critical" and opened):
                # repetitive suspicious closure: fast close, 1 action, no investigation,
                # no escalation — scenario ground truth: review-worthy sample
                opened, closed, escalated = True, True, False
                gt = 1
                inv = None
            elif opened:
                if sev == "Critical":
                    escalated = random.random() < p["esc"]
                    if p["esc"] == 0.0 and random.random() < 0.9:
                        gt = 1          # investigated critical never escalated
                    inv = None if (p.get("no_inv") and random.random() < 0.7) else \
                        (random.uniform(30, 90), random.randint(2, 6))
                else:
                    escalated = random.random() < p["esc"] * 0.5
                    inv = (random.uniform(20, 80), random.randint(1, 5)) \
                        if random.random() < 0.8 else None
            if cat_bias and cat_bias[0] == cat and sev in ("Critical", "High") \
                    and random.random() < 0.8:
                gt = 1                  # campaign alerts are review-worthy samples
            status = "Closed" if closed else ("Escalated" if escalated else "Open")
            if opened:
                case_id = f"C-{eid}-{k:04d}"
            cur.execute(
                "INSERT INTO alerts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (f"A-{eid}-{k:04d}", eid, ts, sev, cat, status,
                 round(p["ack"] * random.lognormvariate(0, 0.4), 1),
                 case_id, random.choice(DISPOSITIONS) if closed else None,
                 asset, gt))
            if opened:
                opened_ts = ts  # case opened at alert time + ack in reality
                closed_ts = None
                if closed:
                    closed_ts = (pd.Timestamp(ts) +
                                 timedelta(hours=float(p["mttr"]))).isoformat()
                cur.execute("INSERT INTO cases VALUES (?,?,?,?,?,?,?)",
                            (case_id, eid, f"A-{eid}-{k:04d}", opened_ts, closed_ts,
                             "Closed" if closed else "Open",
                             random.choice(DISPOSITIONS) if closed else None))
                if inv:
                    cur.execute("INSERT INTO investigations VALUES (?,?,?,?,?,?)",
                                (f"I-{eid}-{k:04d}", case_id, eid, opened_ts,
                                 round(inv[0], 1), inv[1]))
                if escalated:
                    cur.execute("INSERT INTO escalations VALUES (?,?,?,?,?)",
                                (f"E-{eid}-{k:04d}", eid, case_id, opened_ts,
                                 "critical severity policy"))
            k += 1

        # ---- daily aggregate rows ----
        rd = p.get("recent_drops")
        for i in range(DAYS):
            if i in drops:
                continue
            if rd and rd[0] <= i <= rd[1]:
                continue        # recent submission outage (alerts kept: negative space)
            d = (TODAY - timedelta(days=DAYS - 1 - i)).isoformat()
            mult = spike[2] if (spike and spike[0] <= i <= spike[1]) else 1.0
            if silent and silent[0] <= i <= silent[1]:
                total = random.choice([0, 0, 0, 1])
            else:
                total = max(0, int(random.gauss(p["base"], p["base"] * 0.18) * mult))
            n_crit = sum(random.random() < p["crit"] for _ in range(total))
            n_high = sum(random.random() < 0.25 for _ in range(total - n_crit))
            n_med = sum(random.random() < 0.45 for _ in range(total - n_crit - n_high))
            n_low = total - n_crit - n_high - n_med
            cases_op = int(total * random.uniform(0.25, 0.40))
            cases_cl = int(cases_op * random.uniform(0.75, 1.0))
            esc = sum(random.random() < p["esc"] * random.uniform(0.7, 1.3)
                      for _ in range(n_crit))
            closed_crit = n_crit + (1 if open_crit > 1 and random.random() < 0.5 else 0)
            back_carry += p.get("backlog", 0.0)
            add_back = int(back_carry)
            back_carry -= add_back
            open_crit = max(0.0, open_crit + n_crit - closed_crit + add_back)
            ack = p["ack"] * (6.0 if i in surges else 1.0)
            cur.execute(
                "INSERT INTO daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (eid, d, total, n_crit, n_high, n_med, n_low, cases_op, cases_cl,
                 esc, int(open_crit),
                 round(ack * random.lognormvariate(0, 0.25), 1),
                 round(p["mttr"] * random.lognormvariate(0, 0.2), 1),
                 round(_clip(p["sla"] * random.uniform(0.75, 1.25)), 3),
                 round(_clip(p["sc"] * random.uniform(0.7, 1.3)), 3),
                 round(_clip(p["miss"] * random.uniform(0.7, 1.4)), 3),
                 round(p["lag"] * random.uniform(0.7, 1.4), 1)))

        # ---- alert-level evidence records ----
        for _ in range(160):
            day = random.randint(0, 99)
            if not (silent and silent[0] <= day <= silent[1]):
                emit(day)
        for _ in range(70):
            day = random.randint(100, 119)
            if not (silent and silent[0] <= day <= silent[1]):
                emit(day)
        if p.get("campaign"):
            c0, c1, ccat, cshare = p["campaign"]
            for _ in range(130):
                emit(random.randint(c0, min(c1, 119)), (ccat, cshare))
        if p.get("no_inv"):
            for _ in range(int(p.get("force_n", 30))):   # repetitive closure pattern
                emit(random.randint(90, 119), force_pattern=True)

        # ---- seeded malformed submissions -> quarantine (via validate layer) ----
        if p.get("dirty"):
            from datetime import datetime
            good_date = (TODAY - timedelta(days=3)).isoformat()
            bad = pd.DataFrame([
                dict(entity_id=eid, date="2026-13-45", alerts_total=5, alerts_critical=1,
                     alerts_high=1, alerts_medium=2, alerts_low=1, cases_opened=1,
                     cases_closed=1, escalations=0, open_critical_end=0, ack_min_median=10,
                     mttr_hours=5, sla_violation_rate=0.1, silent_close_rate=0.0,
                     missing_field_rate=0.0, submission_lag_hours=2),
                dict(entity_id=eid, date=good_date, alerts_total=None, alerts_critical=1,
                     alerts_high=1, alerts_medium=2, alerts_low=1, cases_opened=1,
                     cases_closed=1, escalations=0, open_critical_end=0, ack_min_median=10,
                     mttr_hours=5, sla_violation_rate=0.1, silent_close_rate=0.0,
                     missing_field_rate=0.0, submission_lag_hours=2),
                dict(entity_id=eid, date=good_date, alerts_total=7, alerts_critical=1,
                     alerts_high=1, alerts_medium=2, alerts_low=1, cases_opened=1,
                     cases_closed=1, escalations=0, open_critical_end=0, ack_min_median=10,
                     mttr_hours=5, sla_violation_rate=0.1, silent_close_rate=0.0,
                     missing_field_rate=2.5, submission_lag_hours=2),
            ])
            _, issues, _ = validate.validate_daily(bad)
            for iss in issues:        # only rows validate actually rejects get seeded
                row = bad.loc[iss["index"]]
                cur.execute("INSERT INTO quarantine (entity_id, raw, reason, ts) "
                            "VALUES (?,?,?,?)",
                            (eid, row.to_json(), iss["reason"],
                             datetime.now().isoformat(timespec="seconds")))
    con.commit()
    con.close()
    return DB


def schema_current():
    if not os.path.exists(DB):
        return False
    con = sqlite3.connect(DB)
    try:
        v = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    except sqlite3.OperationalError:
        v = None
    con.close()
    return bool(v) and int(v[0]) == SCHEMA_VERSION


if __name__ == "__main__":
    print("DB built at", build(force=True))
