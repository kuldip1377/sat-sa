"""v3 feature tests: prioritization, evidence graph, history, notary,
validation framework, data-quality routing, transparent attention score.

Read-only tests first; ingest-mutation tests last (they alter the DB).
Run:  cd backend && python3 -m pytest tests -q
"""
import os
import sys
from datetime import date, timedelta

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import datagen, validate  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

COLS = ["entity_id", "date", "alerts_total", "alerts_critical", "alerts_high",
        "alerts_medium", "alerts_low", "cases_opened", "cases_closed",
        "escalations", "open_critical_end", "ack_min_median", "mttr_hours",
        "sla_violation_rate", "silent_close_rate", "missing_field_rate",
        "submission_lag_hours"]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    datagen.DB = str(tmp_path_factory.mktemp("db") / "test_v3.db")
    datagen.build(force=True)
    from app.main import app
    with TestClient(app) as c:
        yield c


def _day(i):
    return (date.today() - timedelta(days=i)).isoformat()


# ---------------- review-sample prioritization ----------------
def test_samples_queue(client):
    r = client.get("/api/samples?k=25")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 25
    assert body["total_candidates"] > 100
    for it in body["items"]:
        assert "gt" not in it                    # ground truth never leaks to the queue
        assert it["reasons"] and it["confidence"] > 0
        assert 0 < it["confidence"] <= 0.95
    scores = [it["score"] for it in body["items"]]
    assert scores == sorted(scores, reverse=True)
    assert "10" in body["metrics"] and "50" in body["metrics"]   # JSON keys are strings


def test_samples_k_clamped(client):
    assert len(client.get("/api/samples?k=5").json()["items"]) == 5
    assert len(client.get("/api/samples?k=999").json()["items"]) == 100


# ---------------- validation framework (live metrics, never hardcoded) ----------------
def test_validation_dashboard(client):
    body = client.get("/api/validation").json()
    ev = body["detector_eval"]
    assert ev["precision"] >= 0.9 and ev["recall"] >= 0.9
    assert ev["f1"] >= 0.9 and ev["fpr"] <= 0.05
    prio = body["prioritization"]
    assert prio["per_k"]["10"]["precision_at_k"] >= 0.8
    assert prio["workload_reduction"] > 0.9
    assert len(body["gt_rows"]) >= 10
    assert body["quarantine"], "seeded malformed rows must be visible"
    assert all(0 <= v <= 100 for v in body["dq"].values())


def test_eval_endpoint_matches_validation(client):
    e1 = client.get("/api/eval").json()
    e2 = client.get("/api/validation").json()["detector_eval"]
    assert e1["f1"] == e2["f1"] and e1["tp"] == e2["tp"]


# ---------------- evidence graph ----------------
def test_graph_finding_has_missing_evidence_nodes(client):
    sig = next(s for s in client.get("/api/signals").json()["signals"]
               if "Repetitive" in s["title"])
    g = client.get(f"/api/graph/finding/{sig['id']}").json()
    types = {n["type"] for n in g["nodes"]}
    assert {"CSE", "Alert", "Case"} <= types
    assert any(n["missing"] for n in g["nodes"])     # expected-but-absent evidence shown
    assert g["pattern"]["count"] >= 20
    for e in g["edges"]:
        assert e["from_"] and e["to"] and e["label"]


def test_graph_blind_spot(client):
    sig = next(s for s in client.get("/api/signals").json()["signals"]
               if "telemetry evidence" in s["title"])
    g = client.get(f"/api/graph/finding/{sig['id']}").json()
    assert any(n["type"] == "Asset" for n in g["nodes"])
    assert any(n["missing"] for n in g["nodes"])


def test_graph_alert_chain(client):
    body = client.get("/api/samples?k=5").json()
    aid = body["items"][0]["id"]
    g = client.get(f"/api/graph/alert/{aid}").json()
    types = {n["type"] for n in g["nodes"]}
    assert "Alert" in types and "CSE" in types
    assert client.get("/api/graph/alert/NOPE").status_code == 404


# ---------------- longitudinal history ----------------
def test_entity_history(client):
    h = client.get("/api/entities/BNK-02/history").json()
    assert len(h["windows"]) == 4
    labels = {cl["status"] for cl in h["classes"]}
    assert labels <= {"NEW", "PERSISTENT", "RESOLVED", "RETURNED", "WORSENING",
                      "IMPROVING"}
    assert any(cl["family"] == "execution" and cl["status"] == "PERSISTENT"
               for cl in h["classes"])
    assert set(h["deltas"]) == {"mttr", "esc_rate", "backlog", "sla"}
    assert "persistent_concern" in h and "review_trigger" in h
    assert client.get("/api/entities/NOPE/history").status_code == 404


def test_history_in_entity_detail(client):
    d = client.get("/api/entities/PWR-02").json()
    assert "history" in d and "attn" in d and "peer_group" in d
    assert d["attn"]["score"] == d["score"]


# ---------------- transparent attention score ----------------
def test_attention_breakdown(client):
    ents = client.get("/api/entities").json()
    for e in ents:
        d = client.get(f"/api/entities/{e['id']}").json()
        parts = d["attn"]["parts"]
        assert len(parts) == 6
        assert sum(p["points"] for p in parts) == min(100, d["score"]) or d["score"] == 100
        assert d["label"] in {"Normal", "Watch", "Attention", "High Priority"}
    worst = client.get("/api/entities/BNK-02").json()
    exec_part = next(p for p in worst["attn"]["parts"] if p["name"] == "Execution Gap")
    assert exec_part["strength"] == 1.0          # BNK-02 saturates the execution axis


def test_config_weights_live(client):
    r = client.put("/api/config", json={"w_exec": 30, "w_neg": 15})
    assert r.status_code == 200
    d = client.get("/api/entities/BNK-02").json()
    exec_part = next(p for p in d["attn"]["parts"] if p["name"] == "Execution Gap")
    assert exec_part["points"] == 30             # saturated axis follows new weight
    assert client.put("/api/config", json={"w_exec": 25, "w_neg": 20}).status_code == 200
    assert client.put("/api/config", json={"bogus": 1}).status_code == 400


# ---------------- notary / integrity ----------------
def test_notary_chain(client):
    n1 = client.get("/api/notary").json()
    assert n1["intact"] and n1["length"] >= 1
    client.put("/api/config", json={"spike_z": 4.0})   # triggers recompute -> new entry
    n2 = client.get("/api/notary").json()
    assert n2["length"] > n1["length"] and n2["intact"]
    assert n2["chain"][-1]["prev_hash"] == n2["chain"][-2]["hash"]


# ---------------- overview v3 KPIs ----------------
def test_overview_v3_kpis(client):
    k = client.get("/api/overview").json()["kpis"]
    for field in ["high_priority", "negative_space", "samples", "persistent",
                  "emerging", "dq", "eval_f1"]:
        assert field in k, field
    assert k["eval_f1"] >= 0.9


# ---------------- validate module units ----------------
def _row(eid, day, **over):
    r = dict(entity_id=eid, date=_day(day), alerts_total=5, alerts_critical=1,
             alerts_high=1, alerts_medium=2, alerts_low=1, cases_opened=1,
             cases_closed=1, escalations=0, open_critical_end=0, ack_min_median=10,
             mttr_hours=5, sla_violation_rate=0.1, silent_close_rate=0.0,
             missing_field_rate=0.0, submission_lag_hours=2)
    r.update(over)
    return r


def test_validate_rejects_bad_rows():
    df = pd.DataFrame([
        _row("PWR-01", 1),                       # clean
        _row("PWR-01", 2, date="not-a-date"),    # bad timestamp
        _row("PWR-01", 3, alerts_total=-4),      # negative count
        _row("PWR-01", 4, sla_violation_rate=1.7),  # rate out of [0,1]
        _row("PWR-01", 5),                       # duplicate of nothing; ok
        _row("PWR-01", 5, alerts_total=9),       # intra-file duplicate date
        dict(entity_id=None, date=_day(6)),      # missing entity
    ])
    clean, issues, _ = validate.validate_daily(df)
    reasons = [i["reason"] for i in issues]
    assert len(clean) == 2 and len(issues) == 5
    assert any("timestamp" in r for r in reasons)
    assert any("invalid value" in r for r in reasons)
    assert any("outside [0,1]" in r for r in reasons)
    assert any("duplicate" in r for r in reasons)
    assert any("entity_id" in r for r in reasons)


# ---------------- ingest routes bad rows to quarantine (never silently drops) -------
def test_ingest_quarantines_bad_rows(client):
    import io
    rows = [dict(zip(COLS, ["TEL-01", _day(0), 12, 2, 3, 4, 3, 4, 3, 1, 5,
                            30, 8, 0.1, 0.02, 0.01, 4])),
            dict(zip(COLS, ["TEL-01", "bad-date", 12, 2, 3, 4, 3, 4, 3, 1, 5,
                            30, 8, 0.1, 0.02, 0.01, 4]))]
    csv = pd.DataFrame(rows).to_csv(index=False)
    before = client.get("/api/validation").json()["quarantine"]
    r = client.post("/api/ingest", files={"file": ("s.csv", io.BytesIO(csv.encode()),
                                                   "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] == 1 and body["quarantined"] == 1
    after = client.get("/api/validation").json()["quarantine"]
    assert len(after) == len(before) + 1
    assert any("timestamp" in q["reason"] for q in after if q["entity_id"] == "TEL-01")
