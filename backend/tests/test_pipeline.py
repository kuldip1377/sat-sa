"""End-to-end tests for the SAT-SA pipeline: datagen -> analytics -> API.

Run:  cd backend && python3 -m pytest tests -q
"""
import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import datagen  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

COLS = ["entity_id", "date", "alerts_total", "alerts_critical", "alerts_high",
        "alerts_medium", "alerts_low", "cases_opened", "cases_closed",
        "escalations", "open_critical_end", "ack_min_median", "mttr_hours",
        "sla_violation_rate", "silent_close_rate", "missing_field_rate",
        "submission_lag_hours"]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    datagen.DB = str(tmp_path_factory.mktemp("db") / "test.db")
    datagen.build(force=True)
    from app.main import app
    with TestClient(app) as c:
        yield c


def _day(i):
    return (date.today() - timedelta(days=i)).isoformat()


def test_datagen_shape(client):
    import sqlite3
    con = sqlite3.connect(datagen.DB)
    n_ent = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    n_daily = con.execute("SELECT COUNT(*) FROM daily").fetchone()[0]
    con.close()
    assert n_ent == 12
    assert 12 * 110 < n_daily <= 12 * 120  # TEL-02 seeded drop-days


def test_seeded_scenarios_detected(client):
    ov = client.get("/api/overview").json()
    assert ov["kpis"]["entities"] == 12
    assert ov["kpis"]["signals"] >= 15
    titles = {(s["entity_id"], s["title"])
              for s in client.get("/api/signals").json()["signals"]}
    assert ("PWR-02", "Silent SOC — no telemetry flow") in titles
    assert any(e == "OIL-02" and "escalations" in t for e, t in titles)
    assert any(e == "BNK-02" and "SLA" in t for e, t in titles)
    ents = client.get("/api/entities").json()
    assert ents[0]["id"] == "BNK-02"
    scores = [e["score"] for e in ents]
    assert scores == sorted(scores, reverse=True)
    assert {e["id"]: e for e in ents}["PWR-01"]["signals"] == 0


def test_robust_mahalanobis_flags_bad_actors(client):
    sigs = client.get("/api/signals").json()["signals"]
    maha = [s for s in sigs if "Mahalanobis" in s["title"]]
    assert maha, "robust Mahalanobis peer outlier must fire on seeded bad actors"
    flagged = {s["entity_id"] for s in maha}
    assert flagged & {"BNK-02", "PWR-02", "TEL-02"}
    healthy = {s["entity_id"] for s in maha}
    assert not (healthy & {"PWR-01", "TRN-01", "OIL-01"})


def test_eval_perfect_on_ground_truth(client):
    # must run before any ingest-mutation test: scores detectors vs pristine seed
    ev = client.get("/api/eval").json()
    assert ev["fp"] == 0 and ev["fn"] == 0
    assert ev["precision"] == 1.0 and ev["recall"] == 1.0


def test_ingest_validation(client):
    bad = "entity_id,date,alerts_total\nTRN-01,2026-08-31,5\n"
    r = client.post("/api/ingest", files={"file": ("bad.csv", bad, "text/csv")})
    assert r.status_code == 400
    unk = ",".join(COLS) + "\nXXX-99," + ",".join(
        ["2026-08-31", "5", "1", "1", "2", "1", "1", "1", "0", "1", "10", "5",
         "0.1", "0", "0", "1"]) + "\n"
    r = client.post("/api/ingest", files={"file": ("unk.csv", unk, "text/csv")})
    assert r.status_code == 400


def test_ingest_upsert_and_recompute(client):
    def trn():
        return {e["id"]: e for e in client.get("/api/entities").json()}["TRN-01"]

    before = trn()
    rows = "\n".join(
        ",".join(["TRN-01", _day(i), "500", "60", "120", "200", "120", "150",
                  "140", "30", "80", "40", "12", "0.1", "0.02", "0.01", "4"])
        for i in (1, 2, 3))
    csv = ",".join(COLS) + "\n" + rows + "\n"
    r = client.post("/api/ingest", files={"file": ("t.csv", csv, "text/csv")})
    assert r.status_code == 200 and r.json()["rows"] == 3
    after = trn()
    assert after["alerts30"] > before["alerts30"] + 1000
    assert after["signals"] > 0
    r2 = client.post("/api/ingest", files={"file": ("t.csv", csv, "text/csv")})
    assert r2.status_code == 200
    assert trn()["alerts30"] == after["alerts30"]  # upsert idempotency


def test_explain_endpoint(client):
    sid = client.get("/api/signals").json()["signals"][0]["id"]
    r = client.get(f"/api/explain/{sid}")
    assert r.status_code == 200
    body = r.json()
    # v3: structured explainability (WHAT / WHY / EVIDENCE / HOW UNUSUAL / CONFIDENCE)
    for field in ["what", "why", "evidence", "how_unusual", "confidence",
                  "what_to_review", "disclaimer", "narrative"]:
        assert field in body, field
    assert body["engine"].startswith("structured analytics")
    assert 0 <= body["confidence"]["score"] <= 1
    assert len(body["narrative"]) > 40
    assert client.get("/api/explain/NOPE").status_code == 404


def test_export_csv(client):
    r = client.get("/api/signals/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("id,entity_id,category")
    assert len(lines) >= 16


def test_entity_detail_shape(client):
    d = client.get("/api/entities/PWR-02").json()
    assert {"series", "signals", "benchmark", "recent_alerts", "funnel", "traj"} <= set(d)
    assert len(d["traj"]) == 4
    assert client.get("/api/entities/NOPE").status_code == 404


def test_trajectory_shows_deterioration(client):
    ents = {e["id"]: e for e in client.get("/api/entities").json()}
    assert ents["PWR-02"]["traj"][-1] > ents["PWR-02"]["traj"][0] + 10  # went silent
    assert ents["BNK-02"]["traj"][-1] > 60                             # chronically bad


def test_new_detectors(client):
    sigs = client.get("/api/signals").json()["signals"]
    keys = {(s["entity_id"], s["key"]) for s in sigs}
    assert ("TEL-01", "campaign") in keys          # phishing category shift
    assert ("GOV-01", "seasonal") in keys          # ack pattern breaks
    assert ("PWR-02", "seasonal") in keys          # sustained silence
    camp = next(s for s in sigs if s["key"] == "campaign")
    assert camp["evidence"]["category"] == "Phishing"


def test_config_tunable(client):
    r = client.get("/api/config")
    assert r.status_code == 200 and "sla" in r.json()["config"]
    client.put("/api/config", json={"sla": 0.5})
    n_loose = sum(1 for s in client.get("/api/signals").json()["signals"]
                  if s["key"] == "sla")
    client.put("/api/config", json={"sla": 0.25})
    n_def = sum(1 for s in client.get("/api/signals").json()["signals"]
                if s["key"] == "sla")
    assert n_loose == 0 and n_def >= 1
    assert client.put("/api/config", json={"nope": 1}).status_code == 400


def test_actions_and_audit(client):
    sid = client.get("/api/signals").json()["signals"][0]["id"]
    r = client.post(f"/api/signals/{sid}/action",
                    json={"action": "reviewed", "note": "checked case files"})
    assert r.status_code == 200
    s = next(x for x in client.get("/api/signals").json()["signals"] if x["id"] == sid)
    assert s["action"]["action"] == "reviewed"
    aud = client.get("/api/audit").json()["audit"]
    assert any(a["event"] == "signal_action" for a in aud)
    assert client.post(f"/api/signals/{sid}/action",
                       json={"action": "bogus"}).status_code == 400


def test_bulletin(client):
    b = client.get("/api/bulletin").json()
    assert {"week", "alerts7", "top_risk", "signals_by_category"} <= set(b)
    assert b["alerts7"] > 0


def test_csp_headers(client):
    r = client.get("/api/health")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_auth_optional(client, monkeypatch):
    from app import main
    assert client.get("/api/entities").status_code == 200      # auth off by default
    monkeypatch.setattr(main, "AUTH_ON", True)
    assert client.get("/api/entities").status_code == 401
    assert client.get("/api/health").status_code == 200        # allowlisted
    bad = client.post("/api/login", json={"user": "admin", "password": "wrong"})
    assert bad.status_code == 401
    tok = client.post("/api/login",
                      json={"user": "admin", "password": "nciipc"}).json()["token"]
    assert client.get("/api/entities",
                      headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    atok = client.post("/api/login",
                       json={"user": "analyst", "password": "analyst"}).json()["token"]
    assert client.put("/api/config", json={"sla": 0.3},
                      headers={"Authorization": f"Bearer {atok}"}).status_code == 403


def test_signed_ingest(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "SIGN_KEY", "testkey")
    rows = ",".join(COLS) + "\nTRN-01," + ",".join(
        [_day(1), "5", "1", "1", "2", "1", "1", "1", "0", "1", "10", "5",
         "0.1", "0", "0", "1"]) + "\n"
    body = rows.encode()
    f = {"file": ("s.csv", body, "text/csv")}
    assert client.post("/api/ingest", files=f).status_code == 401   # unsigned rejected
    import hashlib
    import hmac as h
    sig = h.new(b"testkey", body, hashlib.sha256).hexdigest()
    r = client.post("/api/ingest", files=f, headers={"X-SATSA-Signature": sig})
    assert r.status_code == 200


def test_reset_reseeds(client):
    r = client.post("/api/reset")
    assert r.status_code == 200 and r.json()["entities"] == 12
    ev = client.get("/api/eval").json()
    assert ev["f1"] == 1.0                      # pristine seed restored
    sigs = client.get("/api/signals").json()["signals"]
    assert all(s["action"] is None for s in sigs)  # actions cleared by reseed
