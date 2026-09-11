"""SAT-SA analytics core (v3).

Offline supervisory decision-support for NCIIPC.  Analytic signals are
*indicators for human examination*, never confirmed violations; every signal
carries stable key, severity, confidence, observed-vs-benchmark and
machine-readable evidence traceable to DB records.

Capabilities:
  Negative Space   silent_soc, sub_gap, no_esc, blind_spot, no_inv, cat_absent
  Execution Gap    sla, silent_close, backlog, mttr, pattern_repeat
  Anomaly          if_anom (IsolationForest), spike, seasonal, campaign
  Peer             maha (robust Mahalanobis), peer-group benchmarking 2.0
  Supervision      transparent 0-100 Supervisory Attention Score (configurable
                   weights, threshold labels), review-sample prioritization
                   with P@K/R@K validation, longitudinal assessment history,
                   evidence graph builders, tamper-evident notary chain.
"""
import hashlib
import sqlite3
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from . import datagen

CACHE = {}
W_SIG = {"critical": 30, "high": 18, "medium": 10, "low": 4}

DEFAULT_CONFIG = dict(
    sla=0.25, sc=0.15, silent_days=5, gap_days=3, noesc_crit=20,
    backlog_slope=0.15, backlog_min=10, mttr_x=1.6, maha=14.07,
    spike_z=4.0, season_z=4.5, season_count=3, season_z2=3.2,
    season_count2=6, camp_tv=0.25,
    blind_min=1, no_inv_rate=0.5, pattern_min=20,
    w_exec=25, w_neg=20, w_anom=15, w_peer=15, w_crit=15, w_conf=10,
    attn_watch=25, attn_attention=40, attn_high=60, attn_critical=85)
CONFIG = dict(DEFAULT_CONFIG)
PRIMARY_UNIVERSE = None  # filled in recompute


def set_config(patch: dict):
    bad = [k for k in patch if k not in DEFAULT_CONFIG]
    if bad:
        raise ValueError(f"unknown config keys: {bad}")
    for k, v in patch.items():
        CONFIG[k] = float(v)
    recompute()
    return dict(CONFIG)


def _conn():
    return sqlite3.connect(datagen.DB)


def _win_metrics(g, today, lo, hi):
    w = g[(g["date"] > today - timedelta(days=hi)) &
          (g["date"] <= today - timedelta(days=lo))]
    present = len(w)
    crit = int(w["alerts_critical"].sum())
    esc = int(w["escalations"].sum())
    return dict(
        alerts30=int(w["alerts_total"].sum()), crit30=crit, esc30=esc,
        esc_rate=round(esc / crit, 3) if crit else 0.0,
        open_now=int(w["open_critical_end"].iloc[-1]) if present else 0,
        mttr=round(float(w["mttr_hours"].mean()), 1) if present else 0.0,
        sla=round(float(w["sla_violation_rate"].mean()), 3) if present else 0.0,
        sc=round(float(w["silent_close_rate"].mean()), 3) if present else 0.0,
        miss=round(float(w["missing_field_rate"].mean()), 3) if present else 0.0,
        lag=round(float(w["submission_lag_hours"].mean()), 1) if present else 0.0,
        zero_days=int((w["alerts_total"] == 0).sum()),
        gap_days=max(0, min(30, hi - lo) - present),
        backlog_slope=round(float(np.polyfit(np.arange(present),
                                             w["open_critical_end"].values, 1)[0]), 3)
        if present > 3 else 0.0)


def _window_all(daily, today, lo, hi):
    """vectorized per-entity metrics for one window (perf: one pass)."""
    w = daily[(daily["date"] > today - timedelta(days=hi)) &
              (daily["date"] <= today - timedelta(days=lo))]
    span = min(30, hi - lo)
    agg = w.groupby("entity_id").agg(
        alerts30=("alerts_total", "sum"), crit30=("alerts_critical", "sum"),
        esc30=("escalations", "sum"),
        open_now=("open_critical_end", "last"),
        mttr=("mttr_hours", "mean"), sla=("sla_violation_rate", "mean"),
        sc=("silent_close_rate", "mean"), miss=("missing_field_rate", "mean"),
        lag=("submission_lag_hours", "mean"),
        zero_days=("alerts_total", lambda s: int((s == 0).sum())),
        present=("date", "count")).to_dict("index")
    out = {}
    for eid, g in w.groupby("entity_id"):
        m = agg[eid]
        m = dict(m)
        m["esc_rate"] = round(m["esc30"] / m["crit30"], 3) if m["crit30"] else 0.0
        m["gap_days"] = max(0, span - int(m["present"]))
        m["backlog_slope"] = round(float(np.polyfit(
            np.arange(len(g)), g["open_critical_end"].values, 1)[0]), 3) if len(g) > 3 else 0.0
        for k in ["mttr", "sla", "sc", "miss", "lag"]:
            m[k] = round(float(m[k]), 3)
        out[eid] = m
    return out


def _win_score(m, peer):
    c = CONFIG
    s = 0
    if m["zero_days"] >= c["silent_days"] and peer["alerts30"] / 30 > 3:
        s += 30
    if m["gap_days"] >= c["gap_days"]:
        s += 18
    if m["crit30"] >= c["noesc_crit"] and m["esc30"] == 0:
        s += 18
    if m["miss"] > 0.10 or m["lag"] > 24:
        s += 10
    if m["sla"] > c["sla"]:
        s += 18
    if m["sc"] > c["sc"]:
        s += 18
    if m["backlog_slope"] > c["backlog_slope"] and m["open_now"] >= c["backlog_min"]:
        s += 10
    if m["mttr"] > c["mttr_x"] * max(peer["mttr"], 1):
        s += 10
    s += min(15, m["open_now"]) + 5 * min(3.0, m["mttr"] / max(peer["mttr"], 1))
    return min(100, int(round(s)))


def recompute():
    con = _conn()
    daily = pd.read_sql("SELECT * FROM daily", con)
    ents = pd.read_sql("SELECT * FROM entities", con)
    alerts = pd.read_sql("SELECT * FROM alerts", con)
    assets = pd.read_sql("SELECT * FROM assets", con)
    cases = pd.read_sql("SELECT * FROM cases", con)
    invs = pd.read_sql("SELECT * FROM investigations", con)
    escs = pd.read_sql("SELECT * FROM escalations", con)
    quar = pd.read_sql("SELECT entity_id, reason FROM quarantine", con)
    con.close()
    daily["date"] = pd.to_datetime(daily["date"])
    alerts["ts"] = pd.to_datetime(alerts["ts"])
    today = daily["date"].max()
    c = CONFIG
    last30 = daily[daily["date"] > today - timedelta(days=30)]
    a30 = alerts[alerts["ts"] > today - timedelta(days=30)]

    # ---------------- per-entity metrics ----------------
    metrics, weekly_frames = {}, {}
    for eid, g in daily.groupby("entity_id"):
        m = _win_metrics(g, today, 0, 30)
        m["cases30"] = int(last30[last30.entity_id == eid]["cases_opened"].sum())
        m["cases_cl30"] = int(last30[last30.entity_id == eid]["cases_closed"].sum())
        m["closure_rate"] = round(m["cases_cl30"] / max(1, m["cases30"]), 3)
        m["crit_frac"] = round(m["crit30"] / max(1, m["alerts30"]), 3)
        m["ack"] = round(float(last30[last30.entity_id == eid]["ack_min_median"].mean()), 1) \
            if len(last30[last30.entity_id == eid]) else 0.0
        metrics[eid] = m
        wk = g.copy()
        wk["week"] = wk["date"].dt.to_period("W").astype(str)
        weekly_frames[eid] = wk.groupby("week").agg(
            alerts=("alerts_total", "sum"), crit=("alerts_critical", "sum"),
            esc=("escalations", "sum"), cases_closed=("cases_closed", "sum"),
            cases_opened=("cases_opened", "sum"),
            mttr=("mttr_hours", "mean")).reset_index()

    peer = {k: round(float(np.median([m[k] for m in metrics.values()])), 3)
            for k in ["alerts30", "crit30", "open_now", "mttr", "ack", "sla",
                      "sc", "miss", "lag", "zero_days", "esc_rate"]}

    # ---------------- evidence-layer joins ----------------
    inv_cases = set(invs["case_id"])
    esc_cases = set(escs["case_id"])
    crit_alerts = alerts[alerts["severity"] == "Critical"]
    opened_crit = crit_alerts[crit_alerts["case_id"].notna()]
    no_inv = opened_crit[~opened_crit["case_id"].isin(inv_cases)]
    no_inv_rate = {eid: round(len(no_inv[no_inv.entity_id == eid]) /
                              max(1, len(opened_crit[opened_crit.entity_id == eid])), 2)
                   for eid in metrics}
    sig_pat = opened_crit[(opened_crit["status"] == "Closed") &
                          (~opened_crit["case_id"].isin(inv_cases)) &
                          (~opened_crit["case_id"].isin(esc_cases))]
    pattern = {eid: dict(count=int(len(sig_pat[sig_pat.entity_id == eid])),
                         examples=sig_pat[sig_pat.entity_id == eid]["id"].head(3).tolist())
               for eid in metrics}
    # investigation duration per entity (peer 2.0 metric)
    inv_dur = invs.assign(dur=invs["duration_min"]).groupby("entity_id")["dur"].median()
    # blind spots: critical monitored assets with zero alerts in 30d
    recent_asset_ids = set(a30["asset_id"].dropna())
    silent30 = {}
    for eid, g in daily.groupby("entity_id"):
        g30_ = g[g["date"] > today - timedelta(days=30)]
        silent30[eid] = len(g30_) and int((g30_["alerts_total"] == 0).sum()) >= c["silent_days"]
    blind = {}
    for eid, a in assets.groupby("entity_id"):
        miss = a[(a["criticality"] == "Critical") & (a["monitoring"] == "monitored") &
                 (~a["id"].isin(recent_asset_ids))]
        if silent30.get(eid):
            # a silent SOC necessarily leaves ALL its critical assets without evidence
            miss = a[(a["criticality"] == "Critical") & (a["monitoring"] == "monitored")]
        if len(miss) >= c["blind_min"]:
            blind[eid] = miss[["id", "name", "type"]].to_dict("records")
    # category absence vs sector expectation
    campaigns = {}
    cat_absent = {}
    for eid, a in alerts.groupby("entity_id"):
        rec = a[a["ts"] > today - timedelta(days=30)]
        base = a[(a["ts"] > today - timedelta(days=90)) &
                 (a["ts"] <= today - timedelta(days=30))]
        sector = dict(zip(ents["id"], ents["sector"]))[eid]
        exp = datagen.SECTOR_EXPECT_CAT[sector]
        if len(rec) >= 50 and (rec["category"] == exp).sum() == 0 and \
                (base["category"] == exp).sum() >= 3:
            cat_absent[eid] = dict(category=exp,
                                   baseline=int((base["category"] == exp).sum()))
        if len(rec) < 50 or len(base) < 50:
            continue
        pr = rec["category"].value_counts(normalize=True)
        pb = base["category"].value_counts(normalize=True)
        cats = set(pr.index) | set(pb.index)
        tv = 0.5 * sum(abs(pr.get(x, 0) - pb.get(x, 0)) for x in cats)
        if tv > c["camp_tv"]:
            top = pr.idxmax()
            growth = float(pr.get(top, 0)) - float(pb.get(top, 0))
            if growth < 0.10:     # a *rise* in one category — not merely a shift
                continue
            campaigns[eid] = dict(category=top,
                                  recent_share=round(float(pr.get(top, 0)), 2),
                                  baseline_share=round(float(pb.get(top, 0)), 2),
                                  tv=round(float(tv), 2), n_recent=int(len(rec)))

    # ---------------- anomaly detectors ----------------
    feat_rows = []
    for eid, wk in weekly_frames.items():
        for _, r in wk.iterrows():
            co = r["cases_opened"]
            feat_rows.append(dict(eid=eid, week=r["week"], alerts=float(r["alerts"]),
                                  crit_frac=float(r["crit"] / r["alerts"]) if r["alerts"] else 0,
                                  esc_rate=float(r["esc"] / r["crit"]) if r["crit"] else 0,
                                  closure=float(min(1.0, r["cases_closed"] / co)) if co else 0,
                                  mttr=float(r["mttr"])))
    feats = pd.DataFrame(feat_rows)
    flagged_weeks = {}
    try:
        from sklearn.ensemble import IsolationForest
        iso = IsolationForest(contamination=0.08, random_state=42)
        preds = iso.fit_predict(feats[["alerts", "crit_frac", "esc_rate",
                                       "closure", "mttr"]].to_numpy())
        for row, p in zip(feat_rows, preds):
            if p == -1:
                flagged_weeks.setdefault(row["eid"], []).append(row["week"])
    except Exception:
        pass

    spikes, week_flag = {}, {}
    for eid, wk in weekly_frames.items():
        s = wk["alerts"].astype(float)
        med = s.median()
        mad = (s - med).abs().median() * 1.4826
        if mad > 0:
            z = (s - med) / mad
            week_flag[eid] = dict(zip(wk["week"], (z > c["spike_z"]).tolist()))
            hit = wk.loc[z > c["spike_z"]]
            if len(hit):
                spikes[eid] = [(r["week"], int(r["alerts"]), round(float(z.iloc[i]), 1))
                               for i, (_, r) in enumerate(hit.iterrows())]

    seasonal = {}
    season_days = {}
    for eid, g in daily.groupby("entity_id"):
        g30 = g[g["date"] > today - timedelta(days=30)]
        hits, n1, n2 = [], 0, 0
        for col, label in [("alerts_total", "alert volume"),
                           ("ack_min_median", "ack time")]:
            dow = g.copy()
            dow["dow"] = dow["date"].dt.dayofweek
            med = dow.groupby("dow")[col].median()
            mad = dow.groupby("dow")[col].apply(lambda s: (s - s.median()).abs().median())
            for _, r in g30.iterrows():
                m_ = med[r["date"].dayofweek]
                sd_ = (mad[r["date"].dayofweek] * 1.4826) or 1e-9
                z = (r[col] - m_) / sd_
                az = abs(z)
                n1 += az > c["season_z"]
                n2 += az > c["season_z2"]
                if az > c["season_z2"]:
                    hits.append(dict(date=r["date"].strftime("%d %b"),
                                     iso=r["date"].isoformat(), field=label,
                                     value=round(float(r[col]), 1), z=round(float(z), 1)))
        if n1 >= c["season_count"] or n2 >= c["season_count2"]:
            seasonal[eid] = sorted(hits, key=lambda h: -abs(h["z"]))
            season_days[eid] = {h["iso"] for h in hits}

    # ---------------- robust Mahalanobis ----------------
    keys = ["mttr", "sla", "sc", "miss", "lag", "open_now", "zero_days"]
    ids = list(metrics)
    X = np.array([[metrics[e][k] for k in keys] for e in ids], dtype=float)
    medv = np.median(X, axis=0)
    madv = np.abs(X - medv).mean(axis=0) + 1e-9
    Z = (X - medv) / madv
    maha = {e: dict(d2=float((Z[i] ** 2).sum()),
                    top=sorted(((k, round(abs(Z[i][j]), 1)) for j, k in enumerate(keys)),
                               key=lambda t: -t[1])[:3])
            for i, e in enumerate(ids)}

    # ---------------- rule engine -> signals ----------------
    signals = []

    def add(eid, key, cat, sev, title, detail, observed, benchmark, evidence, conf):
        signals.append(dict(id=f"SIG-{len(signals)+1:03d}", entity_id=eid, key=key,
                            category=cat, severity=sev, title=title, detail=detail,
                            observed=observed, benchmark=benchmark, evidence=evidence,
                            confidence=round(min(1.0, conf), 2)))

    name = dict(zip(ents["id"], ents["name"]))
    for eid, m in metrics.items():
        if eid in seasonal:
            hs = seasonal[eid]
            add(eid, "seasonal", "Anomaly & Pattern", "medium",
                "Day-of-week pattern break",
                f"{name[eid]} deviates beyond {c['season_z']:.0f}σ from its own day-of-week "
                f"baseline on {len(hs)} days in 30d ("
                + ", ".join(f"{h['date']} {h['field']} z={h['z']}" for h in hs[:3]) +
                "). Potential reporting/process anomaly — requires supervisory review.",
                f"{len(hs)} off-pattern days", "0-1 (normal variation)",
                {"off_pattern_days": hs}, max(hs and abs(hs[0]["z"]) / 8, 0.5))
        if eid in campaigns:
            cp = campaigns[eid]
            add(eid, "campaign", "Anomaly & Pattern", "high",
                f"Suspected {cp['category'].lower()} campaign",
                f"Category mix shifted: {cp['category']} rose from {cp['baseline_share']:.0%} "
                f"to {cp['recent_share']:.0%} of alerts (TV distance {cp['tv']:.2f} > "
                f"{c['camp_tv']}). Consistent with a coordinated campaign; examiner review "
                f"of related samples recommended.",
                f"{cp['category']} {cp['recent_share']:.0%} of recent alerts",
                f"{cp['baseline_share']:.0%} baseline", dict(cp),
                min(1.0, cp["tv"] / 0.4))
        if eid in cat_absent:
            ca = cat_absent[eid]
            add(eid, "cat_absent", "Negative Space", "medium",
                f"Expected alert category absent ({ca['category']})",
                f"No '{ca['category']}' alerts for {name[eid]} in 30 days although "
                f"{ca['baseline']} occurred in the prior 60 and sector peers report this "
                f"category. Potential monitoring blind spot for this attack class — "
                f"requires supervisory review.",
                "0 recent occurrences", f"{ca['baseline']} in prior 60d",
                dict(ca), 0.7)
        if eid in blind:
            add(eid, "blind_spot", "Negative Space", "high",
                "Critical asset without telemetry evidence",
                f"{len(blind[eid])} critical asset(s) declared monitored produced zero "
                f"alert-level records in 30 days: "
                + ", ".join(b["name"] for b in blind[eid]) +
                ". Potential missing evidence / monitoring blind spot — not a confirmed "
                "failure; verify sensor pipeline.",
                f"{len(blind[eid])} silent critical asset(s)", "0 expected",
                {"assets": blind[eid]}, 0.8)
        if no_inv_rate.get(eid, 0) > c["no_inv_rate"] and \
                len(opened_crit[opened_crit.entity_id == eid]) >= 8:
            add(eid, "no_inv", "Negative Space", "high",
                "Critical cases lacking investigation records",
                f"{no_inv_rate[eid]:.0%} of critical cases at {name[eid]} have no "
                f"investigation record although one is expected by workflow. Potential "
                f"missing evidence — requires supervisory review.",
                f"{no_inv_rate[eid]:.0%} without investigation", "< 20% expected",
                {"no_investigation_rate": no_inv_rate[eid],
                 "examples": no_inv[no_inv.entity_id == eid]["id"].head(3).tolist()},
                no_inv_rate[eid])
        if eid in pattern and pattern[eid]["count"] >= c["pattern_min"]:
            pt = pattern[eid]
            add(eid, "pattern_repeat", "Execution Gap", "high",
                "Repetitive suspicious closure pattern",
                f"{pt['count']} critical alerts at {name[eid]} share one signature: case "
                f"opened, closed fast, exactly minimal activity, no investigation, no "
                f"escalation. Same pattern repeated {pt['count']} times — potential "
                f"process bypass; review the highest-priority samples.",
                f"{pt['count']} repetitions", "< 5 typical",
                dict(pt), min(1.0, pt["count"] / 30))
        if m["zero_days"] >= c["silent_days"] and peer["alerts30"] / 30 > 3:
            zd = daily[(daily.entity_id == eid) & (daily.alerts_total == 0) &
                       (daily.date > today - timedelta(days=30))]["date"].dt.strftime("%d %b")
            add(eid, "silent_soc", "Negative Space", "critical",
                "Silent SOC — no telemetry flow",
                f"{name[eid]} reported zero alerts on {m['zero_days']} of the last 30 days "
                f"while the peer median entity reports ~{peer['alerts30'] // 30}/day. "
                f"Absence of signal is itself a supervisory indicator: sensors may be down "
                f"or reporting suppressed.",
                f"{m['zero_days']} zero-alert days / 30", "0 (peer median)",
                {"zero_alert_dates": zd.tolist()[:12],
                 "peer_median_daily_alerts": peer["alerts30"] // 30},
                min(1.0, m["zero_days"] / 10))
        if m["gap_days"] >= c["gap_days"]:
            add(eid, "sub_gap", "Negative Space", "high",
                "Submission gaps in periodic reporting",
                f"{m['gap_days']} days in the last 30 have no submission record at all.",
                f"{m['gap_days']} missing days", "0 missing days",
                {"expected_days": 30, "received_days": 30 - m["gap_days"]},
                min(1.0, m["gap_days"] / 5))
        if m["crit30"] >= c["noesc_crit"] and m["esc30"] == 0:
            add(eid, "no_esc", "Negative Space", "high",
                "Zero escalations despite critical volume",
                f"{m['crit30']} critical alerts in 30 days, none escalated to NCIIPC "
                f"(peer escalation rate {peer['esc_rate']:.0%}). Potential missing "
                f"escalation evidence.",
                f"0 / {m['crit30']} escalated", f"peer rate {peer['esc_rate']:.0%}",
                {"critical_alerts_30d": m["crit30"], "escalations_30d": 0},
                min(1.0, m["crit30"] / 40))
        if m["miss"] > 0.10 or m["lag"] > 24:
            add(eid, "hygiene", "Data Hygiene", "medium", "Degraded submission quality",
                f"Average missing-field rate {m['miss']:.0%} and submission lag {m['lag']:.0f}h "
                f"(peers: {peer['miss']:.0%} / {peer['lag']:.0f}h).",
                f"miss {m['miss']:.0%}, lag {m['lag']:.0f}h",
                f"miss {peer['miss']:.0%}, lag {peer['lag']:.0f}h",
                {"missing_field_rate": m["miss"], "submission_lag_hours": m["lag"]},
                min(1.0, m["miss"] * 4))
        if m["sla"] > c["sla"]:
            add(eid, "sla", "Execution Gap", "high", "Critical-alert SLA breaches",
                f"{m['sla']:.0%} of critical alerts acknowledged beyond the 60-min SLA "
                f"(peer {peer['sla']:.0%}); median ack {m['ack']:.0f} min.",
                f"{m['sla']:.0%} breach rate", f"{peer['sla']:.0%} peer",
                {"ack_min_median": m["ack"], "sla_violation_rate": m["sla"]},
                min(1.0, m["sla"] / 0.5))
        if m["sc"] > c["sc"]:
            add(eid, "silent_close", "Execution Gap", "high",
                "Criticals closed without case records",
                f"{m['sc']:.0%} of critical alerts disposed with no case opened — no audit "
                f"trail. Potential missing evidence.",
                f"{m['sc']:.0%} silent closures", f"{peer['sc']:.0%} peer",
                {"silent_close_rate": m["sc"]}, min(1.0, m["sc"] / 0.4))
        if m["backlog_slope"] > c["backlog_slope"] and m["open_now"] >= c["backlog_min"]:
            add(eid, "backlog", "Execution Gap", "medium",
                "Growing unresolved critical backlog",
                f"Open critical backlog rising ~{m['backlog_slope']:.2f}/day; "
                f"{m['open_now']} currently open.",
                f"{m['open_now']} open, slope {m['backlog_slope']}",
                f"{peer['open_now']} open (peer)",
                {"open_critical_now": m["open_now"], "slope_per_day": m["backlog_slope"]},
                min(1.0, m["backlog_slope"] / 0.5))
        if m["mttr"] > c["mttr_x"] * max(peer["mttr"], 1):
            add(eid, "mttr", "Execution Gap", "medium", "MTTR far above peer median",
                f"Mean time to resolve {m['mttr']}h vs peer median {peer['mttr']}h.",
                f"{m['mttr']}h", f"{peer['mttr']}h peer",
                {"mttr_hours": m["mttr"], "peer_mttr": peer["mttr"]},
                min(1.0, (m["mttr"] / max(peer["mttr"], 1)) / 3))
        if len(set(flagged_weeks.get(eid, []))) >= 2:
            add(eid, "if_anom", "Anomaly & Pattern", "high",
                "Behavioural anomaly (IsolationForest)",
                f"Weekly behaviour vector (volume, severity mix, escalation & closure rates, "
                f"MTTR) flagged anomalous in: {', '.join(sorted(set(flagged_weeks[eid])))}.",
                f"{len(set(flagged_weeks[eid]))} anomalous week(s)", "0 flagged weeks",
                {"flagged_weeks": sorted(set(flagged_weeks[eid]))}, 0.7)
        if eid in spikes:
            wk_txt = ", ".join(f"{w} ({a} alerts, z={z})" for w, a, z in spikes[eid])
            add(eid, "spike", "Anomaly & Pattern", "medium",
                "Alert-volume spike vs own baseline",
                f"Weekly alert volume deviates >{c['spike_z']:.0f} robust-sigma from the "
                f"entity's own baseline: {wk_txt}.",
                wk_txt, f"z <= {c['spike_z']:.0f}",
                {"spike_weeks": [{"week": w, "alerts": a, "z": z}
                                 for w, a, z in spikes[eid]]},
                min(1.0, max(z for _, _, z in spikes[eid]) / 6))
        mi = maha.get(eid)
        if mi and mi["d2"] > c["maha"]:
            sev = "high" if mi["d2"] > 24 else "medium"
            add(eid, "maha", "Peer Comparison & Benchmarking", sev,
                "Multivariate peer outlier (Mahalanobis)",
                f"Behavioural vector lies far outside the robust peer cloud "
                f"(d²={mi['d2']:.1f} vs χ² critical {c['maha']:.1f}, 7 dof). Largest "
                f"deviations: " + ", ".join(f"{k} {v}σ" for k, v in mi["top"]) +
                ". Deviation indicates review, not automatically poor security.",
                f"d²={mi['d2']:.1f}", f"{c['maha']:.1f} (χ², 7 dof, 95%)",
                {"mahalanobis_d2": round(mi["d2"], 1), "top_deviations": dict(mi["top"])},
                min(1.0, mi["d2"] / 40))

    # ---------------- method attribution for anomaly signals (spec §6) ----------------
    METHOD = {
        "spike": "Statistical anomaly — robust z-score (median/MAD) vs the entity's own "
                 "weekly baseline",
        "seasonal": "Pattern anomaly — day-of-week baseline deviation (two-regime rule)",
        "campaign": "Pattern anomaly — category-mix shift (total-variation distance vs "
                    "prior 60 days)",
        "if_anom": "Behavioural anomaly — IsolationForest over weekly behaviour vectors "
                   "(ML context; never sole evidence)",
        "maha": "Multivariate peer outlier — robust Mahalanobis (median/MAD) vs the peer "
                "cloud",
    }
    for s in signals:
        if s["key"] in METHOD:
            s["method"] = METHOD[s["key"]]

    # ---------------- peer groups 2.0 ----------------
    size_tier = {e: ("large" if int(r["assets"]) >= 2000 else "small")
                 for e, r in ents.set_index("id").iterrows()}
    sec_counts = ents["sector"].value_counts()
    peer_group = {}
    for e, r in ents.set_index("id").iterrows():
        peer_group[e] = r["sector"] if sec_counts[r["sector"]] >= 3 else \
            f"{size_tier[e]}·{r['criticality']}"
    group_metrics = {}
    for e in metrics:
        gmembers = [e2 for e2 in metrics if peer_group[e2] == peer_group[e]]
        gm = {}
        for k, label in [("mttr", "MTTR (h)"), ("sla", "SLA breach rate"),
                         ("esc_rate", "Escalation rate"), ("open_now", "Open backlog"),
                         ("closure_rate", "Case closure rate"),
                         ("alerts30", "Alert volume (30d)"),
                         ("crit_frac", "Critical-alert share")]:
            gm[label] = round(float(np.median([metrics[e2][k] for e2 in gmembers])), 2)
        durs = [inv_dur.get(e2, np.nan) for e2 in gmembers]
        gm["Investigation median (min)"] = round(float(np.nanmedian(durs)), 1) \
            if np.isfinite(np.nanmedian(durs)) else None
        group_metrics[e] = dict(group=peer_group[e], members=gmembers, medians=gm)

    # ---------------- attention score (transparent) ----------------
    crit_share = {e: round(float(((assets[assets.entity_id == e]["criticality"] == "Critical")
                                  .mean())), 2) for e in metrics}
    attn = {}
    for e, m in metrics.items():
        sk = {s["key"]: s for s in signals if s["entity_id"] == e}
        exec_s = min(1, 0.35 * ("sla" in sk) + 0.30 * ("silent_close" in sk) +
                     0.20 * ("backlog" in sk) + 0.15 * ("mttr" in sk) +
                     0.2 * ("pattern_repeat" in sk) + 0.1 * ("no_inv" in sk))
        neg_s = min(1, 0.40 * ("silent_soc" in sk) + 0.25 * ("sub_gap" in sk) +
                    0.20 * ("no_esc" in sk) + 0.25 * ("blind_spot" in sk) +
                    0.20 * ("no_inv" in sk) + 0.15 * ("cat_absent" in sk))
        anom_s = min(1, 0.40 * ("campaign" in sk) + 0.25 * ("spike" in sk) +
                     0.35 * ("seasonal" in sk) + 0.2 * ("if_anom" in sk))
        peer_s = min(1, (maha[e]["d2"] / 40) if maha[e]["d2"] > c["maha"] else
                     0.3 * max(0, (m["mttr"] / max(peer["mttr"], 1)) - 1))
        ent_crit = {"Critical": 1.0, "High": 0.7, "Medium": 0.4}[
            dict(zip(ents["id"], ents["criticality"]))[e]]
        crit_s = 0.5 * ent_crit + 0.5 * crit_share[e]
        confs = [s["confidence"] for s in signals if s["entity_id"] == e]
        conf_s = (sum(confs) / len(confs)) if confs else 0.2
        parts = [
            ("Execution Gap", round(c["w_exec"] * exec_s), exec_s),
            ("Negative Space", round(c["w_neg"] * neg_s), neg_s),
            ("Anomaly", round(c["w_anom"] * anom_s), anom_s),
            ("Peer Deviation", round(c["w_peer"] * peer_s), peer_s),
            ("Criticality", round(c["w_crit"] * crit_s), crit_s),
            ("Evidence Confidence", round(c["w_conf"] * conf_s), conf_s),
        ]
        score = min(100, sum(p[1] for p in parts))
        label = ("Critical Attention" if score >= c["attn_critical"] else
                 "High Priority" if score >= c["attn_high"] else
                 "Attention" if score >= c["attn_attention"] else
                 "Watch" if score >= c["attn_watch"] else "Normal")
        attn[e] = dict(score=score, label=label,
                       parts=[dict(name=n, points=pts, strength=round(st, 2))
                              for n, pts, st in parts])

    scores = {e: attn[e]["score"] for e in attn}
    ranked = sorted(scores, key=scores.get, reverse=True)

    pct = {}
    for k in ["mttr", "sla", "esc_rate", "miss", "open_now"]:
        vals = [metrics[e][k] for e in metrics]
        for e in metrics:
            rank = sum(1 for v in vals if v <= metrics[e][k]) / len(vals)
            pct.setdefault(e, {})[k] = int(round(rank * 100))

    # ---------------- trajectory + longitudinal history ----------------
    windows = [(90, 120), (60, 90), (30, 60), (0, 30)]
    win_all = {w: _window_all(daily, today, *w) for w in windows}
    traj, history = {}, {}
    win_peer = {w: {k: float(np.median([win_all[w][e2][k] for e2 in win_all[w]]))
                  for k in ["alerts30", "mttr"]} for w in windows}
    for e in metrics:
        series = [_win_score(win_all[w][e], win_peer[w]) for w in windows]
        traj[e] = series
        fams, intensity = [], {"execution": [], "negative-space": [],
                               "anomaly": [], "data-quality": []}
        for (lo, hi), wm in zip(windows, [win_all[w][e] for w in windows]):
            fam = []
            if wm["sla"] > c["sla"] or wm["sc"] > c["sc"] or \
                    (wm["backlog_slope"] > c["backlog_slope"] and wm["open_now"] >= c["backlog_min"]) or \
                    wm["mttr"] > c["mttr_x"] * max(win_peer[(lo, hi)]["mttr"], 1):
                fam.append("execution")
            intensity["execution"].append(round(wm["sla"] + wm["sc"], 3))
            if wm["zero_days"] >= c["silent_days"] or wm["gap_days"] >= c["gap_days"] or \
                    (wm["crit30"] >= c["noesc_crit"] and wm["esc30"] == 0):
                fam.append("negative-space")
            intensity["negative-space"].append(int(wm["zero_days"] + wm["gap_days"]))
            if wm["miss"] > 0.10 or wm["lag"] > 24:
                fam.append("data-quality")
            intensity["data-quality"].append(round(wm["miss"] + wm["lag"] / 100, 3))
            wstart = today - timedelta(days=hi)
            n_anom = sum(1 for wk2 in
                         [str((wstart + timedelta(days=i)).to_period("W")) for i in range(0, 30, 7)]
                         if week_flag.get(e, {}).get(wk2, False))
            n_anom += sum(1 for d in season_days.get(e, set())
                          if d in [(today - timedelta(days=x)).isoformat()
                                   for x in range(lo, hi, 5)])
            if n_anom or (e in campaigns and lo == 0):
                fam.append("anomaly")
            intensity["anomaly"].append(int(n_anom))
            fams.append(fam)
        # six-status assessment-to-assessment classification (spec §5)
        classes = []
        for fam in ["execution", "negative-space", "anomaly", "data-quality"]:
            present = [fam in f for f in fams]
            inten = intensity[fam]
            status = None
            if present[-1] and not any(present[:-1]):
                status = "NEW"
            elif present[-1] and sum(present) >= 3:
                if len([p for p in present if p]) >= 2 and inten[-1] > inten[-2] * 1.2:
                    status = "WORSENING"
                elif inten[-1] < inten[-2] * 0.8:
                    status = "IMPROVING"
                else:
                    status = "PERSISTENT"
            elif present[-1] and present[-2]:
                status = "IMPROVING" if inten[-1] < inten[-2] * 0.8 else "PERSISTENT"
            elif present[-1] and any(present[:2]) and not present[-2]:
                status = "RETURNED"
            elif any(present[:3]) and not present[-1]:
                status = "RESOLVED"
            if status:
                classes.append(dict(family=fam, status=status,
                                    intensity=inten,
                                    detail=f"intensity by window: {inten}"))
        w0, w3 = win_all[windows[0]][e], win_all[windows[-1]][e]

        def _pct(a, b):
            return round(100 * (b - a) / a, 1) if a else None
        deltas = dict(mttr=_pct(w0["mttr"], w3["mttr"]),
                      esc_rate=_pct(w0["esc_rate"], w3["esc_rate"]),
                      backlog=_pct(max(w0["open_now"], 1), w3["open_now"]),
                      sla=_pct(w0["sla"], w3["sla"]))
        persistent_concern = any(cl["status"] in ("PERSISTENT", "WORSENING")
                                 for cl in classes) and series[-1] >= c["attn_attention"]
        high_streak = sum(1 for s in series if s >= c["attn_high"])
        trigger = (high_streak >= 3 or (persistent_concern and series[-1] >= c["attn_high"]))
        history[e] = dict(windows=[dict(label=f"W{i+1} ({hi}–{lo}d ago)",
                                        score=series[i], families=fams[i])
                                   for i, (lo, hi) in enumerate(windows)],
                          classes=classes, deltas=deltas,
                          persistent_concern=persistent_concern,
                          review_trigger=dict(
                              recommended=bool(trigger),
                              high_score_windows=high_streak,
                              note=("Potential sustained supervisory concern — consider "
                                    "earlier supervisory review / re-assessment "
                                    "(recommendation for the human supervisor, not an "
                                    "automated decision)." if trigger else None)))

    # ---------------- review-sample prioritization ----------------
    def sample_rows():
        mask = a30["severity"].isin(["Critical", "High"])
        for e, cp in campaigns.items():
            mask |= (a30["entity_id"] == e) & (a30["category"] == cp["category"])
        cand = a30[mask].copy()
        if len(cand) == 0:
            return []
        asset_crit = dict(zip(assets["id"], assets["criticality"]))
        rows = []
        for _, a in cand.iterrows():
            e = a["entity_id"]
            score = 3.0 if a["severity"] == "Critical" else 1.5
            ac = asset_crit.get(a["asset_id"], "Medium")
            score += {"Critical": 2, "High": 1, "Medium": 0.5}[ac]
            reasons = [f"{a['severity']} severity alert", f"{ac}-criticality asset"]
            cid = a["case_id"]
            has_inv = cid in inv_cases
            has_esc = cid in esc_cases
            if e in pattern and pattern[e]["count"] >= c["pattern_min"] and \
                    cid and not has_inv and not has_esc and a["status"] == "Closed":
                score += 2
                reasons.append(f"matches repetitive closure pattern ×{pattern[e]['count']}")
            if e in campaigns and a["category"] == campaigns[e]["category"]:
                score += 2
                reasons.append(f"part of suspected {campaigns[e]['category'].lower()} campaign")
            if a["severity"] == "Critical" and not has_esc:
                score += 1
                reasons.append("critical without escalation evidence")
            if cid and not has_inv:
                score += 1
                reasons.append("case lacks investigation record")
            if any(s["key"] in ("sla",) for s in signals
                   if s["entity_id"] == e) and a["ack_minutes"] > 60:
                score += 1
                reasons.append("ack beyond SLA at entity with SLA findings")
            conf = round(min(0.95, 0.4 + 0.15 * len(reasons)), 2)
            rows.append(dict(id=a["id"], entity_id=e, ts=a["ts"].isoformat(),
                             severity=a["severity"], category=a["category"],
                             asset_id=a["asset_id"], case_id=cid,
                             score=round(score, 2), confidence=conf,
                             reasons=reasons, gt=int(a["gt_review"])))
        return sorted(rows, key=lambda r: -r["score"])

    samples_all = sample_rows()

    def prio_metrics():
        gt_total = sum(r["gt"] for r in samples_all) or 1
        out = {}
        for k in (10, 25, 50):
            topk = samples_all[:k]
            hit = sum(r["gt"] for r in topk)
            out[k] = dict(precision_at_k=round(hit / k, 3),
                          recall_at_k=round(hit / gt_total, 3))
        return dict(per_k=out, gt_total=gt_total,
                    candidates=len(samples_all),
                    workload_reduction=round(1 - 25 / max(len(samples_all), 1), 3))

    # ---------------- ground-truth detector evaluation ----------------
    detected = {e: {s["key"] for s in signals if s["entity_id"] == e
                    and s["key"] not in datagen.AUX_KEYS} for e in metrics}
    universe = sorted(set().union(*[datagen.EXPECTED[e] for e in datagen.EXPECTED],
                                  *[detected.get(e, set()) for e in detected]))
    tp = fp = fn = 0
    per_key, missed, extras = {}, [], []
    for e in datagen.EXPECTED:
        got, want = detected.get(e, set()), datagen.EXPECTED[e]
        for k in got & want:
            tp += 1
            per_key.setdefault(k, [0, 0, 0])
            per_key[k][0] += 1
        for k in got - want:
            fp += 1
            per_key.setdefault(k, [0, 0, 0])
            per_key[k][1] += 1
            extras.append(f"{e}:{k}")
        for k in want - got:
            fn += 1
            per_key.setdefault(k, [0, 0, 0])
            per_key[k][2] += 1
            missed.append(f"{e}:{k}")
    negatives = sum(len(universe) - len(datagen.EXPECTED[e]) for e in datagen.EXPECTED) - fp
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    evalr = dict(tp=tp, fp=fp, fn=fn,
                 negatives=int(max(negatives, 0)),
                 fpr=round(fp / (fp + max(negatives, 0)), 3) if fp + negatives else 0.0,
                 precision=round(precision, 3), recall=round(recall, 3),
                 f1=round(2 * precision * recall / (precision + recall), 3)
                 if precision + recall else 0.0,
                 per_key={k: dict(tp=v[0], fp=v[1], fn=v[2]) for k, v in per_key.items()},
                 missed=missed, extras=extras,
                 gt_rows=[dict(entity=e, expected=sorted(datagen.EXPECTED[e]),
                               detected=sorted(detected.get(e, set()) &
                                               set(universe)),
                               correct=sorted(datagen.EXPECTED[e] & detected.get(e, set())),
                               wrong=sorted((detected.get(e, set()) - datagen.EXPECTED[e]) |
                                            (datagen.EXPECTED[e] - detected.get(e, set()))))
                          for e in sorted(datagen.EXPECTED)],
                 prioritization=prio_metrics())

    # ---------------- data quality ----------------
    dq = {}
    for e in metrics:
        q = len(quar[quar.entity_id == e])
        recv = 30 - metrics[e]["gap_days"]
        dq[e] = round(100 * (1 - min(1, 0.5 * q / 5 + 0.5 * metrics[e]["miss"])), 1)

    CACHE.update(dict(
        daily=daily, ents=ents, alerts=alerts, assets=assets, cases=cases, invs=invs,
        escs=escs, quar=quar, metrics=metrics, peer=peer, signals=signals, scores=scores,
        ranked=ranked, pct=pct, weekly=weekly_frames, today=today, traj=traj, evalr=evalr,
        names=dict(zip(ents["id"], ents["name"])), config=dict(CONFIG), attn=attn,
        history=history, samples=samples_all, group_metrics=group_metrics,
        peer_group=peer_group, dq=dq, inv_dur=inv_dur.to_dict(), pattern=pattern,
        blind=blind, campaigns=campaigns, no_inv_rate=no_inv_rate,
        season_days=season_days, week_flag=week_flag))
    _notarize()
    return CACHE


# ---------------- notary (tamper-evident hash chain) ----------------
def _fingerprint():
    con = _conn()
    h = hashlib.sha256()
    for row in con.execute("SELECT entity_id, date, alerts_total, open_critical_end "
                           "FROM daily ORDER BY entity_id, date"):
        h.update("|".join(map(str, row)).encode())
    n = con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    con.close()
    h.update(str(n).encode())
    return h.hexdigest()


def _notarize():
    con = _conn()
    last = con.execute("SELECT hash FROM notary ORDER BY id DESC LIMIT 1").fetchone()
    prev = last[0] if last else "0" * 64
    fp = _fingerprint()
    ts = datetime.now().isoformat(timespec="seconds")
    new = hashlib.sha256(f"{prev}{fp}{ts}".encode()).hexdigest()
    con.execute("INSERT INTO notary (ts, event, fingerprint, prev_hash, hash) "
                "VALUES (?,?,?,?,?)", (ts, "assessment-recompute", fp, prev, new))
    con.commit()
    con.close()


def notary_chain():
    con = _conn()
    rows = [dict(ts=r[0], event=r[1], fingerprint=r[2], prev_hash=r[3], hash=r[4])
            for r in con.execute("SELECT ts, event, fingerprint, prev_hash, hash "
                                 "FROM notary ORDER BY id")]
    con.close()
    ok = all(r["prev_hash"] == (rows[i - 1]["hash"] if i else "0" * 64)
             for i, r in enumerate(rows))
    return dict(chain=rows[-8:], intact=ok, length=len(rows))


# ---------------- evidence graph builders ----------------
def graph_alert(aid):
    c = CACHE
    a = c["alerts"][c["alerts"]["id"] == aid]
    if len(a) == 0:
        return None
    a = a.iloc[0]
    nodes, edges = [], []

    def node(nid, ntype, label, ts=None, meta=None, missing=False):
        nodes.append(dict(id=nid, type=ntype, label=label, ts=ts,
                          meta=meta or {}, missing=missing))

    node(a["entity_id"], "CSE", c["names"][a["entity_id"]],
         meta=dict(sector=dict(zip(c["ents"]["id"], c["ents"]["sector"]))[a["entity_id"]]))
    if pd.notna(a["asset_id"]):
        ast = c["assets"][c["assets"]["id"] == a["asset_id"]]
        if len(ast):
            ast = ast.iloc[0]
            node(ast["id"], "Asset", f"{ast['name']} ({ast['criticality']})",
                 meta=ast.to_dict())
            edges.append(dict(from_=a["entity_id"], to=ast["id"],
                              label="assets.entity_id"))
            node(a["id"], "Alert", f"{a['severity']} · {a['category']}", ts=str(a["ts"]),
                 meta=a.to_dict())
            edges.append(dict(from_=a["asset_id"], to=a["id"], label="alerts.asset_id"))
        else:
            node(a["id"], "Alert", f"{a['severity']} · {a['category']}", ts=str(a["ts"]),
                 meta=a.to_dict())
            edges.append(dict(from_=a["entity_id"], to=a["id"], label="alerts.entity_id"))
    else:
        node(a["id"], "Alert", f"{a['severity']} · {a['category']}", ts=str(a["ts"]),
             meta=a.to_dict())
        edges.append(dict(from_=a["entity_id"], to=a["id"], label="alerts.entity_id"))
    if pd.notna(a["case_id"]):
        cs = c["cases"][c["cases"]["id"] == a["case_id"]]
        if len(cs):
            cs = cs.iloc[0]
            node(cs["id"], "Case", f"Case {cs['status']}", ts=cs["opened_ts"],
                 meta=cs.to_dict())
            edges.append(dict(from_=a["id"], to=cs["id"], label="alerts.case_id"))
            iv = c["invs"][c["invs"]["case_id"] == cs["id"]]
            if len(iv):
                iv = iv.iloc[0]
                node(iv["id"], "Investigation",
                     f"Investigation · {iv['duration_min']} min · {iv['actions']} action(s)",
                     ts=iv["started_ts"], meta=iv.to_dict())
                edges.append(dict(from_=cs["id"], to=iv["id"],
                                  label="investigations.case_id"))
            elif a["severity"] == "Critical":
                node(f"missing-inv-{a['id']}", "Investigation",
                     "Expected investigation record — MISSING", missing=True)
                edges.append(dict(from_=cs["id"], to=f"missing-inv-{a['id']}",
                                  label="expected evidence absent"))
            es = c["escs"][c["escs"]["case_id"] == cs["id"]]
            if len(es):
                es = es.iloc[0]
                node(es["id"], "Escalation", "Escalated to NCIIPC", ts=es["ts"],
                     meta=es.to_dict())
                edges.append(dict(from_=cs["id"], to=es["id"],
                                  label="escalations.case_id"))
            elif a["severity"] == "Critical":
                node(f"missing-esc-{a['id']}", "Escalation",
                     "Expected escalation evidence — MISSING", missing=True)
                edges.append(dict(from_=cs["id"], to=f"missing-esc-{a['id']}",
                                  label="expected evidence absent"))
            if cs["status"] == "Closed":
                node(f"res-{cs['id']}", "Resolution", f"Closed · {cs['disposition']}",
                     ts=cs["closed_ts"], meta=dict(disposition=cs["disposition"]))
                edges.append(dict(from_=cs["id"], to=f"res-{cs['id']}",
                                  label="cases.closure"))
    elif a["severity"] == "Critical":
        node(f"missing-case-{a['id']}", "Case", "Expected case record — MISSING",
             missing=True)
        edges.append(dict(from_=a["id"], to=f"missing-case-{a['id']}",
                          label="expected evidence absent"))
    return dict(nodes=nodes, edges=edges)


def graph_finding(sid):
    c = CACHE
    sig = next((s for s in c["signals"] if s["id"] == sid), None)
    if sig is None:
        return None
    e = sig["entity_id"]
    a = c["alerts"]
    pick = []
    k = sig["key"]
    if k in ("silent_close", "pattern_repeat", "no_inv"):
        sel = a[(a.entity_id == e) & (a.severity == "Critical") &
                (a.status == "Closed")]
        pick = sel["id"].head(3).tolist()
    elif k == "no_esc":
        sel = a[(a.entity_id == e) & (a.severity == "Critical") &
                (a.case_id.notna())]
        pick = sel["id"].head(3).tolist()
    elif k == "campaign":
        cat = sig["evidence"].get("category")
        sel = a[(a.entity_id == e) & (a.category == cat)]
        pick = sel["id"].head(3).tolist()
    elif k == "blind_spot":
        nodes, edges = [], []
        nodes.append(dict(id=e, type="CSE", label=c["names"][e], meta={}, missing=False))
        for b in sig["evidence"]["assets"]:
            nodes.append(dict(id=b["id"], type="Asset",
                              label=f"{b['name']} ({'Critical'})", meta=b, missing=False))
            edges.append(dict(from_=e, to=b["id"], label="assets.entity_id"))
            nodes.append(dict(id=f"miss-{b['id']}", type="Alert",
                              label="Expected telemetry — MISSING (30d)", missing=True))
            edges.append(dict(from_=b["id"], to=f"miss-{b['id']}",
                              label="expected evidence absent"))
        return dict(nodes=nodes, edges=edges,
                    pattern=dict(signature="critical monitored asset, zero records",
                                 count=len(sig["evidence"]["assets"])))
    else:
        sel = a[(a.entity_id == e) & (a.severity.isin(["Critical", "High"]))]
        pick = sel["id"].head(3).tolist()
    graphs = [graph_alert(p) for p in pick]
    nodes, edges, seen = [], [], set()
    for g in graphs:
        if not g:
            continue
        for n in g["nodes"]:
            if n["id"] not in seen:
                seen.add(n["id"])
                nodes.append(n)
        edges.extend(g["edges"])
    pat = c["pattern"].get(e, dict(count=0))
    return dict(nodes=nodes, edges=edges,
                pattern=dict(signature="critical · closed · no investigation · no escalation",
                             count=pat["count"]))


# ---------------- public views ----------------
def overview():
    c = CACHE
    m30 = c["daily"][c["daily"]["date"] > c["today"] - timedelta(days=30)]
    sev_by = c["signals"]
    neg_keys = {"silent_soc", "sub_gap", "no_esc", "blind_spot", "no_inv", "cat_absent"}
    persist = sum(1 for e in c["history"]
                  for cl in c["history"][e]["classes"]
                  if cl["status"] in ("PERSISTENT", "WORSENING"))
    emerging = sum(1 for e in c["history"]
                   for cl in c["history"][e]["classes"]
                   if cl["status"] in ("NEW", "RETURNED"))
    kpis = dict(
        entities=len(c["ents"]),
        high_priority=sum(1 for e in c["attn"]
                          if c["attn"][e]["label"] == "High Priority"),
        alerts30=int(m30["alerts_total"].sum()),
        open_critical=int(sum(c["metrics"][e]["open_now"] for e in c["metrics"])),
        signals=len(sev_by),
        signals_by_sev={s: sum(1 for x in sev_by if x["severity"] == s)
                        for s in ["critical", "high", "medium", "low"]},
        negative_space=sum(1 for x in sev_by if x["key"] in neg_keys),
        exec_gaps=sum(1 for x in sev_by if x["category"] == "Execution Gap"),
        samples=len(c["samples"]),
        persistent=persist, emerging=emerging,
        dq=round(float(np.mean(list(c["dq"].values()))), 1),
        median_mttr=c["peer"]["mttr"],
        compliance_pct=round(100 * (1 - sum(c["metrics"][e]["gap_days"]
                                            for e in c["metrics"])
                                    / (30 * len(c["metrics"]))), 1),
        eval_f1=c["evalr"]["f1"],
    )
    trend_df = c["daily"][c["daily"]["date"] > c["today"] - timedelta(days=90)] \
        .groupby("date")[["alerts_critical", "alerts_high", "alerts_medium",
                          "alerts_low"]].sum().reset_index()
    trend = [dict(date=r["date"].strftime("%d %b"), critical=int(r.alerts_critical),
                  high=int(r.alerts_high), medium=int(r.alerts_medium),
                  low=int(r.alerts_low)) for _, r in trend_df.iterrows()]
    sectors = (c["ents"].assign(score=c["ents"]["id"].map(c["scores"]))
               .groupby("sector")["score"].mean().round(0).reset_index())
    sectors = [dict(sector=r.sector, score=int(r.score)) for _, r in sectors.iterrows()]
    top = []
    for eid in c["ranked"][:6]:
        sigs = [x for x in sev_by if x["entity_id"] == eid]
        top.append(dict(id=eid, name=c["names"][eid], sector=dict(
            zip(c["ents"]["id"], c["ents"]["sector"]))[eid], score=c["scores"][eid],
            label=c["attn"][eid]["label"],
            top_signal=sigs[0]["title"] if sigs else "No active signals"))
    cats = {}
    for x in sev_by:
        cats[x["category"]] = cats.get(x["category"], 0) + 1
    return dict(kpis=kpis, trend=trend, sectors=sectors, top=top,
                signals_by_category=cats)


def entity_list():
    c = CACHE
    out = []
    for rank, eid in enumerate(c["ranked"], 1):
        m = c["metrics"][eid]
        wk = c["weekly"][eid].tail(10)
        e = c["ents"][c["ents"]["id"] == eid].iloc[0]
        sigs = [x for x in c["signals"] if x["entity_id"] == eid]
        worst = (["critical", "high", "medium", "low"] + [None])
        wsev = next((s for s in worst if any(x["severity"] == s for x in sigs)), None)
        t = c["traj"][eid]
        out.append(dict(id=eid, name=e["name"], sector=e["sector"],
                        criticality=e["criticality"], rank=rank, score=c["scores"][eid],
                        label=c["attn"][eid]["label"],
                        alerts30=m["alerts30"], open_now=m["open_now"], mttr=m["mttr"],
                        sla_ok_pct=round(100 * (1 - m["sla"])), esc_rate=m["esc_rate"],
                        signals=len(sigs), worst=wsev, traj=t, delta=t[-1] - t[-2],
                        dq=c["dq"][eid],
                        spark=[int(v) for v in wk["alerts"].tolist()]))
    return out


def entity_detail(eid):
    c = CACHE
    if eid not in c["metrics"]:
        return None
    m, e = c["metrics"][eid], c["ents"][c["ents"]["id"] == eid].iloc[0]
    g = c["daily"][c["daily"]["entity_id"] == eid]
    g90 = g[g["date"] > c["today"] - timedelta(days=90)]
    allm = c["daily"][c["daily"]["date"] > c["today"] - timedelta(days=90)]
    peer_daily = allm.groupby("date")["alerts_total"].median()
    series = []
    for _, r in g90.iterrows():
        series.append(dict(date=r["date"].strftime("%d %b"), alerts=int(r.alerts_total),
                           critical=int(r.alerts_critical),
                           peer=int(peer_daily.get(r["date"], 0))))
    g30 = g[g["date"] > c["today"] - timedelta(days=30)]
    funnel = dict(alerts=int(g30["alerts_total"].sum()),
                  cases=int(g30["cases_opened"].sum()),
                  escalations=int(g30["escalations"].sum()))
    sevmix = [dict(severity="Critical", value=int(g30["alerts_critical"].sum())),
              dict(severity="High", value=int(g30["alerts_high"].sum())),
              dict(severity="Medium", value=int(g30["alerts_medium"].sum())),
              dict(severity="Low", value=int(g30["alerts_low"].sum()))]
    sigs = [x for x in c["signals"] if x["entity_id"] == eid]
    bench = []
    for k, label in [("mttr", "MTTR (h)"), ("sla", "SLA breach rate"),
                     ("esc_rate", "Escalation rate"), ("miss", "Missing-field rate"),
                     ("open_now", "Open criticals")]:
        bench.append(dict(metric=label, entity=m[k], peer=c["peer"][k],
                          percentile=c["pct"][eid][k]))
    con = _conn()
    rec = pd.read_sql(
        f"SELECT id, ts, severity, category, status, ack_minutes, case_id, disposition, "
        f"asset_id FROM alerts WHERE entity_id='{eid}' ORDER BY ts DESC LIMIT 15", con)
    con.close()
    rec = rec.astype(object).where(rec.notna(), None)   # pandas>=3 returns NaN for SQL NULLs
    gm = c["group_metrics"][eid]
    return dict(id=eid, name=e["name"], sector=e["sector"],
                criticality=e["criticality"], assets=int(e["assets"]),
                maturity=e["soc_maturity"], score=c["scores"][eid],
                label=c["attn"][eid]["label"], attn=c["attn"][eid],
                rank=c["ranked"].index(eid) + 1, metrics=m, series=series,
                funnel=funnel, sevmix=sevmix, signals=sigs, benchmark=bench,
                traj=c["traj"][eid], history=c["history"][eid], dq=c["dq"][eid],
                peer_group=gm,
                inv_median=c["inv_dur"].get(eid),
                recent_alerts=rec.to_dict("records"),
                samples=[s for s in c["samples"] if s["entity_id"] == eid][:10])


def bulletin():
    c = CACHE
    w7 = c["daily"][c["daily"]["date"] > c["today"] - timedelta(days=7)]
    movers = sorted(c["traj"].items(), key=lambda kv: kv[1][-1] - kv[1][0],
                    reverse=True)
    return dict(
        week=c["today"].strftime("%d %b %Y"),
        alerts7=int(w7["alerts_total"].sum()),
        critical7=int(w7["alerts_critical"].sum()),
        escalations7=int(w7["escalations"].sum()),
        compliance=overview()["kpis"]["compliance_pct"],
        signals_by_category=overview()["signals_by_category"],
        top_risk=[dict(id=e, name=c["names"][e], score=c["scores"][e],
                       label=c["attn"][e]["label"]) for e in c["ranked"][:5]],
        deteriorating=[dict(id=e, name=c["names"][e], before=t[0], now=t[-1],
                            delta=t[-1] - t[0]) for e, t in movers[:3]
                       if t[-1] - t[0] >= 5],
        improving=[dict(id=e, name=c["names"][e], before=t[0], now=t[-1],
                        delta=t[-1] - t[0]) for e, t in reversed(movers)
                   if t[-1] - t[0] < 0][:3])


# ---------------- structured explainability (spec: WHAT/WHY/EVIDENCE/...) ----------------
_REVIEW = {
    "Negative Space": ["Confirm the evidence gap with the CSE's SOC lead (sensor down, "
                       "pipeline break, or genuinely no events).",
                       "Request the missing records for the identified window.",
                       "If records cannot be produced, log the gap in the assessment file."],
    "Execution Gap": ["Pull the listed alert/case records and verify the workflow steps.",
                      "Check whether closures follow the CSE's documented SOP.",
                      "Escalate to a targeted examination if the pattern is confirmed."],
    "Anomaly & Pattern": ["Review the flagged samples against the entity's own baseline.",
                          "Ask the CSE for an operational explanation (drill, migration, "
                          "reporting change).",
                          "Decide whether the pattern is an incident, a drill, or an artefact."],
    "Data Hygiene": ["Quarantine low-quality submissions and require schema-conformant "
                     "resubmission.",
                     "Factor reporting discipline into the next assessment cycle."],
    "Peer Comparison & Benchmarking": ["Schedule a comparative review against the peer group.",
                                       "Validate whether the deviation reflects risk posture "
                                       "or operational context."],
}
_EVIDENCE_TABLE = {
    "silent_soc": "daily (zero-alert days)", "sub_gap": "daily (missing dates)",
    "no_esc": "alerts + escalations (critical alerts, zero escalation rows)",
    "blind_spot": "assets (critical, monitored) × alerts (no records)",
    "no_inv": "alerts → cases × investigations (missing investigation rows)",
    "cat_absent": "alerts (category counts, 30d vs prior 60d)",
    "pattern_repeat": "alerts + cases + investigations + escalations (shared signature)",
    "sla": "alerts (ack_minutes > 60) + daily.sla_violation_rate",
    "silent_close": "daily.silent_close_rate (criticals with no case row)",
    "backlog": "daily.open_critical_end (rising trend)",
    "mttr": "daily.mttr_hours vs peer median",
    "hygiene": "daily.missing_field_rate / submission_lag_hours + quarantine",
    "spike": "daily.alerts_total (weekly robust z)",
    "seasonal": "daily (day-of-week baseline deviations)",
    "campaign": "alerts.category mix (30d vs prior 60d)",
}


def explain(sid):
    """Structured, fully data-derived explanation of one finding.

    Every field is traceable to DB records; no generated prose beyond templates.
    """
    c = CACHE
    sig = next((s for s in c["signals"] if s["id"] == sid), None)
    if sig is None:
        return None
    e = sig["entity_id"]
    m, attn = c["metrics"][e], c["attn"][e]
    name = c["names"][e]
    key = sig["key"]
    # concrete record references
    refs = [dict(table="daily", ref=f"entity_id='{e}' last 30 days",
                 note="periodic aggregate submissions")]
    if key in ("no_inv", "pattern_repeat", "silent_close", "sla", "no_esc", "campaign",
               "cat_absent"):
        refs.append(dict(table="alerts", ref=f"entity_id='{e}' (30d)",
                         note="alert-level evidence records"))
    if key in ("no_inv", "pattern_repeat"):
        refs += [dict(table="cases", ref="alert.case_id", note="case lifecycle rows"),
                 dict(table="investigations", ref="case_id", note="expected workflow step"),
                 dict(table="escalations", ref="case_id", note="NCIIPC escalation records")]
    if key == "blind_spot":
        refs.append(dict(table="assets", ref=f"entity_id='{e}', criticality='Critical'",
                         note="declared-monitored critical assets"))
    ex = [dict(id=r["id"], ts=str(r["ts"]), severity=r["severity"])
          for _, r in c["alerts"][(c["alerts"].entity_id == e) &
                                  (c["alerts"].severity == "Critical")].head(3).iterrows()]
    pct = c["pct"].get(e, {})
    basis = ("Rule threshold(s) from the configurable rule engine: "
             + ", ".join(f"{k}={c['config'][k]}" for k in
                         ["sla", "silent_days", "gap_days", "noesc_crit", "mttr_x",
                          "spike_z", "season_z", "camp_tv", "pattern_min", "no_inv_rate"]
                         if k in c["config"]) + ".")
    return dict(
        signal_id=sid, entity_id=e, entity_name=name, key=key,
        category=sig["category"], severity=sig["severity"],
        what=f"{name} ({e}): {sig['title']}.",
        why=sig["detail"],
        evidence=[dict(source=_EVIDENCE_TABLE.get(key, "daily"), references=refs,
                       example_records=ex, observed=sig["observed"],
                       benchmark=sig["benchmark"], raw=sig["evidence"])],
        how_unusual=dict(observed=sig["observed"], benchmark=sig["benchmark"],
                         percentiles=pct,
                         peer_group=c["group_metrics"][e]["group"],
                         group_medians=c["group_metrics"][e]["medians"],
                         attention=dict(score=attn["score"], label=attn["label"],
                                        parts=attn["parts"])),
        confidence=dict(score=sig["confidence"],
                        interpretation=("strong" if sig["confidence"] >= 0.8 else
                                        "moderate" if sig["confidence"] >= 0.55 else
                                        "weak — corroborate before acting"),
                        basis=basis),
        what_to_review=_REVIEW.get(sig["category"], ["Review the evidence and schedule a "
                                                     "supervisory follow-up."]),
        disclaimer="Indicator for supervisory examination — not a confirmed violation.")


# ---------------- data-quality module (spec §2, pre-analytics) ----------------
def dataquality():
    """Live data-quality view: dimensions, counts, flagged records, gaps."""
    c = CACHE
    con = _conn()
    quar = pd.read_sql("SELECT entity_id, raw, reason, ts FROM quarantine ORDER BY id", con)
    con.close()
    d30 = c["daily"][c["daily"]["date"] > c["today"] - timedelta(days=30)]
    rows = len(d30)
    dims = {}
    # schema validity: rows arriving with all 17 columns & parseable (rejections had not)
    rejected = len(quar)
    dims["Schema validity"] = round(100 * rows / max(1, rows + rejected), 1)
    # completeness: received days vs expected + missing-field rate
    expected = 30 * len(c["metrics"])
    recv = sum(30 - c["metrics"][e]["gap_days"] for e in c["metrics"])
    miss = float(np.mean([c["metrics"][e]["miss"] for e in c["metrics"]]))
    dims["Completeness"] = round(100 * (0.7 * recv / expected + 0.3 * (1 - min(1, miss * 4))), 1)
    # consistency: quarantine mix-ratio consistency failures + silent-close coherence
    inconsist = len(quar[quar["reason"].str.contains("outside|invalid value", na=False)])
    dims["Consistency"] = round(100 * (1 - inconsist / max(1, rows + rejected)), 1)
    # timeliness: mean submission lag vs 24h target
    lag = float(np.mean([c["metrics"][e]["lag"] for e in c["metrics"]]))
    dims["Timeliness"] = round(max(0.0, 100 * (1 - max(0, lag - 6) / 48)), 1)
    # uniqueness: duplicate rejections
    dups = len(quar[quar["reason"].str.contains("duplicate", na=False)])
    dims["Uniqueness"] = round(100 * (1 - dups / max(1, rows + rejected)), 1)
    w = [0.25, 0.25, 0.2, 0.15, 0.15]
    overall = round(sum(v * wi for v, wi in zip(dims.values(), w)), 1)
    # warning records: accepted but degraded (high missing-field rate or late)
    warn = d30[(d30["missing_field_rate"] > 0.2) | (d30["submission_lag_hours"] > 24)]
    flagged = [dict(entity_id=r.entity_id, date=str(r.date.date()),
                    missing_field_rate=r.missing_field_rate,
                    submission_lag_hours=r.submission_lag_hours,
                    flag=("high missing-field rate" if r.missing_field_rate > 0.2
                          else "late submission"))
               for _, r in warn.iterrows()]
    per_entity = {e: c["dq"][e] for e in c["metrics"]}
    miss_fields = {e: round(c["metrics"][e]["miss"] * 100, 1) for e in c["metrics"]
                   if c["metrics"][e]["miss"] > 0.05}
    gaps = {e: c["metrics"][e]["gap_days"] for e in c["metrics"]
            if c["metrics"][e]["gap_days"] > 0}
    return dict(dimensions=dims, overall=overall,
                totals=dict(records=rows + rejected, valid=rows - len(warn),
                            warning=len(warn), rejected=rejected),
                missing_fields_pct=miss_fields, duplicates=dups,
                invalid_values=inconsist, reporting_gaps=gaps,
                per_entity=per_entity, flagged=flagged[:200],
                quarantine=[dict(entity_id=r.entity_id, reason=r.reason, ts=r.ts)
                            for _, r in quar.iterrows()],
                note="Validation runs BEFORE analytics; rejected rows are quarantined "
                     "with reasons and never silently discarded.")


# ---------------- assessments / history overview (spec §5) ----------------
def assessments():
    c = CACHE
    out = []
    for e in c["ranked"]:
        h = c["history"][e]
        out.append(dict(id=e, name=c["names"][e], score=c["scores"][e],
                        label=c["attn"][e]["label"],
                        windows=[w["score"] for w in h["windows"]],
                        classes=[dict(family=cl["family"], status=cl["status"])
                                 for cl in h["classes"]],
                        deltas=h["deltas"],
                        persistent_concern=h["persistent_concern"],
                        review_trigger=h["review_trigger"]))
    return out


# ---------------- peer benchmarking dashboard (spec §10) ----------------
def peers(group: str = ""):
    c = CACHE
    keys = [("mttr", "MTTR (h)"), ("sla", "SLA breach rate"),
            ("esc_rate", "Escalation rate"), ("open_now", "Open backlog"),
            ("closure_rate", "Case closure rate"), ("alerts30", "Alert volume (30d)"),
            ("crit_frac", "Critical-alert share")]
    rows = []
    for e in c["ranked"]:
        gm = c["group_metrics"][e]
        if group and gm["group"] != group:
            continue
        cells = {}
        for k, label in keys:
            ent_v = c["metrics"][e][k]
            med = gm["medians"].get(label)
            dev = None
            if med not in (None, 0):
                dev = round((ent_v - med) / med, 2)
            cells[label] = dict(entity=round(float(ent_v), 3), median=med, deviation=dev)
        rows.append(dict(id=e, name=c["names"][e], group=gm["group"],
                         members=len(gm["members"]), cells=cells,
                         inv_median=c["inv_dur"].get(e),
                         group_inv_median=gm["medians"].get("Investigation median (min)")))
    groups = sorted({c["peer_group"][e] for e in c["metrics"]})
    return dict(rows=rows, groups=groups,
                note="Deviation from comparable entities is an examination prompt, not a "
                     "judgement — operational context differs between CSEs.")


# ---------------- before/after demo case (spec §17) ----------------
def demo_case():
    """Live 'naive KPI vs SAT-SA' comparison for the planted closure-pattern CSE.
    Every number is computed from the database at request time."""
    c = CACHE
    eid = max(c["pattern"], key=lambda e: c["pattern"][e]["count"])
    m = c["metrics"][eid]
    sigs = [s for s in c["signals"] if s["entity_id"] == eid]
    naive = dict(
        closure_rate_pct=round(100 * m["closure_rate"], 1),
        alerts_handled_30d=m["alerts30"],
        cases_opened_30d=m["cases30"],
        cases_closed_30d=m["cases_cl30"],
        ack_min_median=m["ack"],
        narrative=f"{c['names'][eid]} closes {m['closure_rate']:.0%} of its cases and "
                  f"handled {m['alerts30']} alerts in 30 days. On closure-rate and "
                  f"volume KPIs alone, operations look busy and productive.")
    satsa = dict(
        pattern_count=c["pattern"][eid]["count"],
        no_inv_rate=c["no_inv_rate"].get(eid, 0),
        silent_close_pct=round(100 * m["sc"], 1),
        sla_breach_pct=round(100 * m["sla"], 1),
        escalations_30d=m["esc30"],
        findings=[dict(key=s["key"], title=s["title"], severity=s["severity"],
                       observed=s["observed"], benchmark=s["benchmark"]) for s in sigs],
        narrative="SAT-SA finds a potential execution gap behind the healthy KPIs: a "
                  f"repetitive fast-closure signature ({c['pattern'][eid]['count']} "
                  "criticals closed with minimal activity, no investigation, no "
                  "escalation). Requires supervisory review — not a confirmed failure.")
    return dict(entity_id=eid, name=c["names"][eid], naive=naive, satsa=satsa,
                lesson="Aggregate KPIs measure activity; SAT-SA examines the evidence "
                       "trail behind the activity.")


# ---------------- held-out validation runner (spec §1) ----------------
def run_holdout():
    """Run the full analytics stack over the HELD-OUT variant dataset (independent
    seed, shifted pattern parameters — never used for threshold tuning) and return
    metrics + confusion matrix.  The primary database/cache is restored afterwards."""
    import os
    import tempfile
    primary_db = datagen.DB
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(tmp)
    try:
        datagen.DB = tmp
        datagen.build(force=True, variant=True)
        recompute()
        ev = CACHE["evalr"]
        out = dict(
            dataset="held-out (seed 1337, shifted placements/magnitudes/categories)",
            tp=ev["tp"], fp=ev["fp"], fn=ev["fn"], negatives=ev["negatives"],
            precision=ev["precision"], recall=ev["recall"], f1=ev["f1"], fpr=ev["fpr"],
            per_key=ev["per_key"], missed=ev["missed"], extras=ev["extras"],
            gt_rows=ev["gt_rows"], prioritization=ev["prioritization"],
            confusion=dict(actual_positive=ev["tp"] + ev["fn"],
                           actual_negative=ev["negatives"] + ev["fp"],
                           predicted_positive=ev["tp"] + ev["fp"],
                           predicted_negative=ev["fn"] + ev["negatives"],
                           tp=ev["tp"], fp=ev["fp"], fn=ev["fn"], tn=ev["negatives"]),
            note="Rule/statistics detectors are scored here; IsolationForest and "
                 "Mahalanobis are ML CONTEXT signals and are intentionally excluded "
                 "from the ground-truth score.")
    finally:
        datagen.DB = primary_db
        if os.path.exists(tmp):
            os.remove(tmp)
        recompute()   # restore primary cache
    CACHE["holdout"] = out
    return out
