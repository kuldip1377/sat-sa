"""SAT-SA — Supervisory Analytics Tool for SOC Assessment (SIH 2026 PS 26157).

FastAPI backend: analytics API, CSV ingestion (optionally HMAC-signed),
optional offline auth+RBAC, supervisor actions & audit trail, runtime rule
configuration, ground-truth detector evaluation, and the built React console
(single-process, air-gap friendly).
"""
import base64
import hashlib
import hmac
import json
import math
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import analytics, datagen, validate

FRONT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
SECRET = os.environ.get("SATSA_SECRET", "satsa-airgap-demo-secret").encode()
SIGN_KEY = os.environ.get("SATSA_SIGNING_KEY", "")
AUTH_ON = os.environ.get("SATSA_AUTH", "") == "1"


def _users():
    out = {}
    for spec in os.environ.get(
            "SATSA_USERS",
            "admin:nciipc:admin,supervisor:review:supervisor,"
            "analyst:analyst:analyst,auditor:audit:auditor").split(","):
        u, p, r = (spec.strip().split(":") + ["analyst"])[:3]
        out[u] = (p, r)
    return out


# offline RBAC (spec §13): CSEs never log in — NCIIPC-internal roles only.
# admin: everything · supervisor: ingest/config/actions · analyst: actions ·
# auditor: read-only (evidence examination & audit review)
ROLE_PERMS = {
    "admin": {"ingest", "config", "action", "reset"},
    "supervisor": {"ingest", "config", "action"},
    "analyst": {"action"},
    "auditor": set(),
}


def _can(role, perm):
    return perm in ROLE_PERMS.get(role, set())


def _password_ok(stored, given):
    """Stored passwords may be plaintext (demo) or 'sha256$<hex>' (hardened)."""
    if stored.startswith("sha256$"):
        want = stored.split("$", 1)[1]
        got = hashlib.sha256(given.encode()).hexdigest()
        return hmac.compare_digest(want, got)
    return hmac.compare_digest(stored, given)


class NanSafeJSON(JSONResponse):
    """Serialise NaN / pd.NA as null. Starlette's renderer rejects NaN
    (allow_nan=False), and pandas>=3 surfaces SQL NULLs as float NaN — this
    keeps every endpoint pandas-version-agnostic without changing payloads."""

    def render(self, content) -> bytes:
        def scrub(o):
            if isinstance(o, float) and math.isnan(o):
                return None
            if o is pd.NA:
                return None
            if isinstance(o, dict):
                return {k: scrub(v) for k, v in o.items()}
            if isinstance(o, (list, tuple)):
                return [scrub(v) for v in o]
            return o
        return super().render(scrub(content))


app = FastAPI(title="SAT-SA", version="4.0.0",
              description="Supervisory Analytics Tool for SOC Assessment",
              default_response_class=NanSafeJSON)


# ------------------------- security headers (air-gap proof) -------------------------
@app.middleware("http")
async def secure_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
    return resp


# ------------------------- optional offline auth -------------------------
def _token(user, role):
    payload = base64.urlsafe_b64encode(json.dumps(
        {"u": user, "r": role, "exp": int(time.time()) + 8 * 3600}).encode())
    sig = hmac.new(SECRET, payload, hashlib.sha256).hexdigest()
    return payload.decode() + "." + sig


def _verify(token):
    try:
        payload, sig = token.split(".")
        if not hmac.compare_digest(hmac.new(SECRET, payload.encode(),
                                            hashlib.sha256).hexdigest(), sig):
            return None
        d = json.loads(base64.urlsafe_b64decode(payload))
        return d if d["exp"] > time.time() else None
    except Exception:
        return None


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    if AUTH_ON and request.url.path.startswith("/api/") \
            and request.url.path not in ("/api/health", "/api/login"):
        d = _verify((request.headers.get("authorization") or "").removeprefix("Bearer ").strip())
        if not d:
            return Response('{"detail":"not authenticated"}', status_code=401,
                            media_type="application/json")
        request.state.user = d
    return await call_next(request)


def _who(request: Request):
    if AUTH_ON:
        d = getattr(request.state, "user", None)
        return (d["u"], d["r"]) if d else ("anonymous", "analyst")
    return ("demo-supervisor", "admin")   # offline demo = full NCIIPC console access


def _audit(user, event, detail=""):
    con = sqlite3.connect(datagen.DB)
    con.execute("INSERT INTO audit (ts, user, event, detail) VALUES (?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), user, event, detail))
    con.commit()
    con.close()


# ------------------------- boot -------------------------
@app.on_event("startup")
def _boot():
    # schema v3+: rebuild seeded DB when it predates the current schema
    datagen.build(force=not datagen.schema_current())
    con = sqlite3.connect(datagen.DB)  # idempotent schema additions for old DBs
    con.executescript("""
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, signal_id TEXT, entity_id TEXT,
            action TEXT, note TEXT, user TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, user TEXT,
            event TEXT, detail TEXT);""")
    con.close()
    analytics.recompute()


# ------------------------- core API -------------------------
@app.get("/api/health")
def health():
    return dict(status="ok", tool="SAT-SA", mode="offline-demo",
                entities=len(analytics.CACHE.get("ents", [])),
                auth_enabled=AUTH_ON, signing_enabled=bool(SIGN_KEY))


@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    u, p = body.get("user", ""), body.get("password", "")
    rec = _users().get(u)
    if not rec or not _password_ok(rec[0], p):
        raise HTTPException(401, "invalid credentials")
    _audit(u, "login", "authenticated")
    return dict(token=_token(u, rec[1]), user=u, role=rec[1])


@app.get("/api/overview")
def overview():
    return analytics.overview()


@app.get("/api/eval")
def evalr():
    return analytics.CACHE["evalr"]


@app.get("/api/config")
def get_config():
    return dict(config=analytics.CONFIG, defaults=analytics.DEFAULT_CONFIG)


@app.put("/api/config")
async def put_config(request: Request):
    user, role = _who(request)
    if not _can(role, "config"):
        raise HTTPException(403, "admin/supervisor role required")
    try:
        cfg = analytics.set_config(await request.json())
    except ValueError as e:
        raise HTTPException(400, str(e))
    _audit(user, "config", json.dumps(cfg))
    return dict(config=cfg, status="recomputed")


@app.get("/api/entities")
def entities():
    return analytics.entity_list()


@app.get("/api/entities/{eid}")
def entity(eid: str):
    d = analytics.entity_detail(eid)
    if d is None:
        raise HTTPException(404, f"Unknown entity {eid}")
    con = sqlite3.connect(datagen.DB)
    acts = {sid: dict(action=action, note=note, user=user, ts=ts)
            for sid, action, note, user, ts in con.execute(
                "SELECT signal_id, action, note, user, ts FROM actions ORDER BY id")}
    con.close()
    for s in d["signals"]:
        if s["id"] in acts:
            s["action"] = acts[s["id"]]
    return d


@app.get("/api/bulletin")
def bulletin():
    return analytics.bulletin()


@app.get("/api/signals")
def signals(category: str = "", severity: str = ""):
    sigs = [dict(s) for s in analytics.CACHE["signals"]]
    con = sqlite3.connect(datagen.DB)
    acts = {}
    for sid, entity_id, action, note, user, ts in con.execute(
            "SELECT signal_id, entity_id, action, note, user, ts FROM actions "
            "ORDER BY id"):
        acts[sid] = dict(action=action, note=note, user=user, ts=ts, entity_id=entity_id)
    con.close()
    for s in sigs:
        s["action"] = acts.get(s["id"])
    if category:
        sigs = [s for s in sigs if s["category"] == category]
    if severity:
        sigs = [s for s in sigs if s["severity"] == severity]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sigs = sorted(sigs, key=lambda s: (order[s["severity"]], s["entity_id"]))
    return dict(signals=sigs, categories=sorted(
        {s["category"] for s in analytics.CACHE["signals"]}))


@app.post("/api/signals/{sid}/action")
async def signal_action(sid: str, request: Request):
    user, role = _who(request)
    if not _can(role, "action"):
        raise HTTPException(403, "analyst or above required")
    sig = next((s for s in analytics.CACHE["signals"] if s["id"] == sid), None)
    if sig is None:
        raise HTTPException(404, f"Unknown signal {sid}")
    body = await request.json()
    act = body.get("action", "")
    if act not in ("reviewed", "request_info", "escalate", "dismiss"):
        raise HTTPException(400, "action must be one of reviewed|request_info|escalate|dismiss")
    note = str(body.get("note", ""))[:500]
    con = sqlite3.connect(datagen.DB)
    con.execute("INSERT INTO actions (signal_id, entity_id, action, note, user, ts) "
                "VALUES (?,?,?,?,?,?)",
                (sid, sig["entity_id"], act, note, user,
                 datetime.now().isoformat(timespec="seconds")))
    con.commit()
    con.close()
    _audit(user, "signal_action", f"{sid} {act} {note}")
    return dict(status="recorded", signal=sid, action=act)


@app.get("/api/audit")
def audit(limit: int = 30):
    con = sqlite3.connect(datagen.DB)
    rows = con.execute("SELECT ts, user, event, detail FROM audit ORDER BY id DESC LIMIT ?",
                       (limit,)).fetchall()
    con.close()
    return dict(audit=[dict(ts=r[0], user=r[1], event=r[2], detail=r[3]) for r in rows])


@app.get("/api/signals/export")
def export_signals():
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "entity_id", "category", "severity", "title", "observed", "benchmark"])
    for s in analytics.CACHE["signals"]:
        w.writerow([s["id"], s["entity_id"], s["category"], s["severity"],
                    s["title"], s["observed"], s["benchmark"]])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=sat-sa-signals.csv"})


ACTION = {
    "Negative Space": "Treat absence as evidence: verify the reporting pipeline and sensor "
        "connectivity for the gap window, and request the entity's internal SOC logs before "
        "drawing conclusions.",
    "Execution Gap": "Pull the underlying case records for the breached window and determine "
        "whether the cause is staffing, tooling or process; require a remediation timeline "
        "from the entity.",
    "Anomaly & Pattern": "Correlate the flagged window with change logs and threat intelligence "
        "to decide whether the pattern is an incident, a drill, or a reporting artefact.",
    "Data Hygiene": "Quarantine low-quality submissions, require schema-conformant "
        "resubmission, and factor reporting discipline into the next assessment cycle.",
    "Peer Comparison & Benchmarking": "Schedule a comparative review against sector peers to "
        "validate whether the deviation reflects risk posture or operational context.",
}


@app.get("/api/explain/{sid}")
def explain(sid: str):
    import urllib.request
    out = analytics.explain(sid)
    if out is None:
        raise HTTPException(404, f"Unknown signal {sid}")
    out["engine"] = "structured analytics (offline, deterministic)"
    url = os.environ.get("OLLAMA_URL")  # optional local LLM inside the enclave;
    if url:                             # narrative only — NEVER affects scoring
        try:
            req = urllib.request.Request(
                url.rstrip("/") + "/api/generate",
                data=json.dumps({
                    "model": os.environ.get("OLLAMA_MODEL", "llama3"),
                    "stream": False,
                    "prompt": "In three sentences, explain this SOC supervisory finding to an "
                              f"NCIIPC examiner: {out['what']} {out['why']}",
                }).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                out["narrative"] = json.load(r)["response"]
                out["narrative_engine"] = "ollama local LLM (optional)"
        except Exception:
            out["narrative"] = (f"{out['what']} {out['why']}")
            out["narrative_engine"] = "template fallback"
    else:
        out["narrative"] = f"{out['what']} {out['why']}"
        out["narrative_engine"] = "template (no local LLM configured)"
    return out


# ------------------------- v3: prioritization, graphs, history, integrity -------------------------
@app.get("/api/samples")
def samples(k: int = 25):
    """Prioritized review queue: which samples to examine first, and why."""
    k = max(1, min(int(k), 100))
    rows = analytics.CACHE["samples"]
    prio = analytics.CACHE["evalr"]["prioritization"]
    return dict(k=k, total_candidates=len(rows),
                items=[{kk: vv for kk, vv in r.items() if kk != "gt"}
                       for r in rows[:k]],          # gt stays hidden from the queue
                metrics=prio["per_k"], gt_total=prio["gt_total"],
                workload_reduction=prio["workload_reduction"])


@app.get("/api/graph/alert/{aid}")
def graph_alert_ep(aid: str):
    g = analytics.graph_alert(aid)
    if g is None:
        raise HTTPException(404, f"Unknown alert {aid}")
    return g


@app.get("/api/graph/finding/{sid}")
def graph_finding_ep(sid: str):
    g = analytics.graph_finding(sid)
    if g is None:
        raise HTTPException(404, f"Unknown signal {sid}")
    return g


@app.get("/api/entities/{eid}/history")
def entity_history(eid: str):
    h = analytics.CACHE["history"].get(eid)
    if h is None:
        raise HTTPException(404, f"Unknown entity {eid}")
    return dict(entity_id=eid, **h)


@app.get("/api/notary")
def notary():
    return analytics.notary_chain()


@app.get("/api/validation")
def validation():
    """Validation dashboard payload — every number computed live from ground truth."""
    c = analytics.CACHE
    con = sqlite3.connect(datagen.DB)
    q = [dict(entity_id=r[0], reason=r[1], ts=r[2]) for r in con.execute(
        "SELECT entity_id, reason, ts FROM quarantine ORDER BY id DESC LIMIT 50")]
    con.close()
    ev = c["evalr"]
    return dict(detector_eval={k: v for k, v in ev.items()
                               if k not in ("gt_rows", "prioritization")},
                prioritization=ev["prioritization"],
                gt_rows=ev["gt_rows"], quarantine=q, dq=c["dq"],
                note="Computed live against the seeded ground-truth scenarios; "
                     "no metric in this payload is hardcoded.")


# ------------------------- v4: held-out validation, data quality, assessments -------------------------
@app.get("/api/holdout")
def holdout():
    """Held-out validation run (independent seed, shifted patterns). Cached per
    process; ~2s on first call. Metrics are computed, never hardcoded."""
    if "holdout" not in analytics.CACHE:
        _audit(_who_safe(), "holdout-eval", "held-out validation run executed")
        return analytics.run_holdout()
    return analytics.CACHE["holdout"]


def _who_safe():
    return "system"


@app.get("/api/dataquality")
def dataquality():
    return analytics.dataquality()


@app.get("/api/dataquality/export")
def dataquality_export():
    import io
    dq = analytics.dataquality()
    rows = [dict(record_type="quarantined", entity_id=q["entity_id"], detail=q["reason"],
                 ts=q["ts"]) for q in dq["quarantine"]]
    rows += [dict(record_type="warning", entity_id=f["entity_id"],
                  detail=f"{f['flag']} (missing {f['missing_field_rate']:.0%}, "
                         f"lag {f['submission_lag_hours']:.0f}h)", ts=f["date"])
             for f in dq["flagged"]]
    buf = io.StringIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition":
                             "attachment; filename=satsa_flagged_records.csv"})


@app.get("/api/assessments")
def assessments():
    return dict(assessments=analytics.assessments())


@app.get("/api/peers")
def peers(group: str = ""):
    return analytics.peers(group)


@app.get("/api/demo-case")
def demo_case():
    return analytics.demo_case()


# ------------------------- ingestion -------------------------
INGEST_COLS = ["entity_id", "date", "alerts_total", "alerts_critical", "alerts_high",
               "alerts_medium", "alerts_low", "cases_opened", "cases_closed",
               "escalations", "open_critical_end", "ack_min_median", "mttr_hours",
               "sla_violation_rate", "silent_close_rate", "missing_field_rate",
               "submission_lag_hours"]


@app.get("/api/schema")
def schema():
    return dict(columns=INGEST_COLS,
                formats=["CSV", "JSON", "DB export"],
                signing_enabled=bool(SIGN_KEY),
                known_entities=sorted(analytics.CACHE["names"].keys()))


@app.post("/api/ingest")
async def ingest(request: Request, file: UploadFile = File(...),
                 x_satsa_signature: str = Header(default="")):
    user, role = _who(request)
    if not _can(role, "ingest"):
        raise HTTPException(403, "supervisor role required")
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "only .csv submissions are accepted")
    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(413, "submission exceeds the 8 MB offline ingest limit")
    if SIGN_KEY:  # offline HMAC provenance check over the submission payload
        want = hmac.new(SIGN_KEY.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(want, x_satsa_signature or ""):
            raise HTTPException(401, "invalid submission signature")
    import io
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(400, f"Unreadable CSV: {exc}")
    missing = [c for c in INGEST_COLS if c not in df.columns]
    if missing:
        raise HTTPException(400, f"Missing columns: {missing}")
    known = set(analytics.CACHE["names"])
    unknown = set(df["entity_id"].dropna().unique()) - known
    if unknown:
        raise HTTPException(400, f"Unknown entity ids: {sorted(unknown)}")
    clean, issues, warns = validate.validate_daily(df)   # never silently discard rows
    con = sqlite3.connect(datagen.DB)
    cur = con.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    for iss in issues:
        row = df.loc[iss["index"]]
        cur.execute("INSERT INTO quarantine (entity_id, raw, reason, ts) VALUES (?,?,?,?)",
                    (iss["entity_id"] or "unknown", row.to_json(), iss["reason"], now))
    if len(clean):
        cur.executemany(
            f"INSERT OR REPLACE INTO daily ({','.join(INGEST_COLS)}) "
            f"VALUES ({','.join('?' * len(INGEST_COLS))})",
            clean[INGEST_COLS].values.tolist())
    con.commit()
    con.close()
    analytics.recompute()
    _audit(user, "ingest",
           f"{len(clean)} accepted, {len(warns)} warnings, {len(issues)} quarantined, "
           f"entities={sorted(set(df['entity_id'].dropna()))}")
    return dict(rows=int(len(df)), accepted=int(len(clean)), quarantined=len(issues),
                warnings=len(warns),
                warning_reasons=[w["reason"] for w in warns][:10],
                quarantine_reasons=[i["reason"] for i in issues][:10],
                entities=sorted(set(df["entity_id"].dropna())),
                status="ingested; analytics recomputed"
                       + ("; some rows quarantined for review" if issues else ""))


@app.post("/api/reset")
def reset(request: Request):
    user, role = _who(request)
    if not _can(role, "reset"):
        raise HTTPException(403, "admin role required")
    datagen.build(force=True)
    analytics.recompute()
    _audit(user, "reset", "demo database reseeded")
    return dict(status="reseeded", entities=len(analytics.CACHE["ents"]))


# ------------------------- static frontend -------------------------
if (FRONT_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONT_DIST / "assets"), name="assets")


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404)
    index = FRONT_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return FileResponse(__file__)
