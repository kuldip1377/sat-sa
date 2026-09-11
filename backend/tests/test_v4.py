"""v4 feature tests: held-out validation, data-quality module, assessment
comparison, peer dashboard, demo case, score bands, weights, RBAC, upload limits.

Read-only tests first; mutation tests (config/auth/ingest) last.
Run:  cd backend && python3 -m pytest tests -q
"""
import io
import os
import sys
from datetime import date, timedelta

import pandas as pd
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
    datagen.DB = str(tmp_path_factory.mktemp("db") / "test_v4.db")
    datagen.build(force=True)
    from app.main import app
    with TestClient(app) as c:
        yield c


def _day(i):
    return (date.today() - timedelta(days=i)).isoformat()


# ---------------- held-out validation ----------------
def test_holdout_validation(client):
    h = client.get("/api/holdout").json()
    assert "held-out" in h["dataset"]
    assert h["f1"] >= 0.9 and h["fpr"] <= 0.05
    cf = h["confusion"]
    assert cf["tp"] + cf["fn"] == cf["actual_positive"]
    assert cf["fp"] + cf["tn"] == cf["actual_negative"]
    assert h["prioritization"]["per_k"]["10"]["precision_at_k"] >= 0.8
    assert "excluded" in h["note"].lower()  # ML-context attribution disclaimer
    # cached on second call
    assert client.get("/api/holdout").json()["f1"] == h["f1"]


# ---------------- data quality ----------------
def test_dataquality_endpoint(client):
    dq = client.get("/api/dataquality").json()
    assert set(dq["dimensions"]) == {"Schema validity", "Completeness", "Consistency",
                                     "Timeliness", "Uniqueness"}
    assert 0 <= dq["overall"] <= 100
    assert dq["totals"]["rejected"] >= 3          # seeded malformed TEL-02 rows
    t = dq["totals"]
    assert t["records"] == t["valid"] + t["warning"] + t["rejected"]
    assert "never silently discarded" in dq["note"]


def test_dataquality_export(client):
    r = client.get("/api/dataquality/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "quarantined" in r.text and "TEL-02" in r.text


def test_ingest_warning_tier(client):
    # severity breakdown (1+1+2+1=5) does not sum to alerts_total=9 -> warning, not reject
    row = ["TEL-01", _day(1), 9, 1, 1, 2, 1, 3, 2, 0, 2, 30, 8, 0.1, 0.02, 0.01, 4]
    csv = pd.DataFrame([dict(zip(COLS, row))]).to_csv(index=False)
    r = client.post("/api/ingest", files={"file": ("w.csv", io.BytesIO(csv.encode()),
                                                  "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] == 1 and body["warnings"] >= 1
    assert any("sum" in w for w in body["warning_reasons"])


# ---------------- assessments / history ----------------
def test_assessments_endpoint(client):
    body = client.get("/api/assessments").json()
    a = {x["id"]: x for x in body["assessments"]}
    assert len(a) == 12
    bnk = a["BNK-02"]
    assert len(bnk["windows"]) == 4
    assert set(bnk["deltas"]) == {"mttr", "esc_rate", "backlog", "sla"}
    assert any(cl["status"] == "PERSISTENT" for cl in bnk["classes"])
    assert bnk["persistent_concern"] is True
    assert bnk["review_trigger"]["recommended"] is True
    for x in body["assessments"]:
        for cl in x["classes"]:
            assert cl["status"] in {"NEW", "PERSISTENT", "RESOLVED", "RETURNED",
                                    "WORSENING", "IMPROVING"}


# ---------------- peers & demo case ----------------
def test_peers_endpoint(client):
    p = client.get("/api/peers").json()
    assert len(p["rows"]) == 12 and len(p["groups"]) >= 2
    row = p["rows"][0]
    for metric, cell in row["cells"].items():
        assert "entity" in cell and "median" in cell
    assert "judgement" in p["note"]          # neutral wording requirement


def test_demo_case(client):
    d = client.get("/api/demo-case").json()
    assert d["entity_id"] == "BNK-02"
    assert d["naive"]["closure_rate_pct"] > 50
    assert d["satsa"]["pattern_count"] >= 20
    assert d["satsa"]["findings"]
    assert "not a confirmed failure" in d["satsa"]["narrative"]


# ---------------- method attribution ----------------
def test_signals_carry_method(client):
    sigs = client.get("/api/signals").json()["signals"]
    by_key = {s["key"]: s for s in sigs}
    for k in ("spike", "seasonal", "campaign"):
        if k in by_key:
            assert "method" in by_key[k]
    assert "method" not in by_key.get("sla", {})   # rule signals have no ML method


# ---------------- bands & weights (mutation; run late) ----------------
def test_bands_and_weights(client):
    d = client.get("/api/entities/BNK-02").json()
    assert d["label"] in {"Normal", "Watch", "Attention", "High Priority",
                          "Critical Attention"}
    base_score = d["score"]
    # saturate execution weight -> score must rise (BNK-02 saturates that axis)
    r = client.put("/api/config", json={"w_exec": 50, "attn_critical": 20,
                                        "attn_high": 10})
    assert r.status_code == 200
    d2 = client.get("/api/entities/BNK-02").json()
    assert d2["score"] > base_score
    assert d2["label"] == "Critical Attention"
    exec_part = next(p for p in d2["attn"]["parts"] if p["name"] == "Execution Gap")
    assert exec_part["points"] == 50
    # restore defaults
    r = client.put("/api/config", json={"w_exec": 25, "attn_critical": 85,
                                        "attn_high": 60})
    assert r.status_code == 200
    assert client.get("/api/entities/BNK-02").json()["score"] == base_score


# ---------------- RBAC & upload limits (mutation; run last) ----------------
def test_rbac_roles(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "AUTH_ON", True)

    def tok(u, p):
        return client.post("/api/login", json={"user": u, "password": p}).json()["token"]

    ah = {"Authorization": f"Bearer {tok('analyst', 'analyst')}"}
    uh = {"Authorization": f"Bearer {tok('auditor', 'audit')}"}
    sh = {"Authorization": f"Bearer {tok('supervisor', 'review')}"}
    dh = {"Authorization": f"Bearer {tok('admin', 'nciipc')}"}
    # analyst: read yes, config/ingest/reset no
    assert client.get("/api/entities", headers=ah).status_code == 200
    assert client.put("/api/config", json={"sla": 0.3}, headers=ah).status_code == 403
    assert client.post("/api/reset", headers=sh).status_code == 403   # supervisor ≠ admin
    # auditor: read yes, actions no
    assert client.get("/api/audit", headers=uh).status_code == 200
    sid = client.get("/api/signals", headers=uh).json()["signals"][0]["id"]
    assert client.post(f"/api/signals/{sid}/action", headers=uh,
                       json={"action": "ack", "note": ""}).status_code == 403
    # supervisor: ingest+config yes
    assert client.put("/api/config", json={"sla": 0.25}, headers=sh).status_code == 200
    # admin: reset yes
    assert client.post("/api/reset", headers=dh).status_code == 200
    monkeypatch.setattr(main, "AUTH_ON", False)


def test_upload_type_limit(client):
    r = client.post("/api/ingest", files={"file": ("evil.txt", b"x", "text/plain")})
    assert r.status_code == 415
