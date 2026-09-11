"""Data-quality validation layer.

Every inbound daily submission passes through validate_daily() BEFORE
analytics.  Invalid rows are never silently discarded: they are returned as
structured issues and quarantined with a reason, so the supervisor can see
exactly what arrived and what was held back (PS 26157 §data quality).
"""
import pandas as pd

REQUIRED = ["entity_id", "date", "alerts_total", "alerts_critical", "alerts_high",
            "alerts_medium", "alerts_low", "cases_opened", "cases_closed",
            "escalations", "open_critical_end", "ack_min_median", "mttr_hours",
            "sla_violation_rate", "silent_close_rate", "missing_field_rate",
            "submission_lag_hours"]
NUMERIC = REQUIRED[2:]


def validate_daily(df: pd.DataFrame):
    """Return (clean_df, issues, warnings).

    issues   -> row REJECTED, quarantined with a reason (never silently dropped)
    warnings -> row ACCEPTED but flagged for the data-quality dashboard
    """
    issues = []
    warnings = []
    df = df.copy()

    missing_cols = [c for c in REQUIRED if c not in df.columns]
    if missing_cols:
        raise ValueError(f"missing columns: {missing_cols}")

    # unknown / empty entity ids
    bad = df["entity_id"].isna() | (df["entity_id"].astype(str).str.strip() == "")
    for i in df[bad].index:
        issues.append(dict(index=int(i), entity_id=None, reason="missing entity_id"))
    df = df[~bad]

    # invalid timestamps
    try:  # pandas>=2: mixed formats without per-element dateutil warnings
        ts = pd.to_datetime(df["date"], errors="coerce", format="mixed")
    except (ValueError, TypeError):
        ts = pd.to_datetime(df["date"], errors="coerce")
    bad = ts.isna()
    for i in df[bad].index:
        issues.append(dict(index=int(i), entity_id=str(df.loc[i, "entity_id"]),
                           reason=f"invalid timestamp {df.loc[i, 'date']!r}"))
    df = df[~bad]

    # non-numeric / negative values in numeric fields
    for col in NUMERIC:
        v = pd.to_numeric(df[col], errors="coerce")
        bad = v.isna() | (v < 0)
        for i in df[bad].index:
            issues.append(dict(index=int(i), entity_id=str(df.loc[i, "entity_id"]),
                               reason=f"invalid value for {col}: {df.loc[i, col]!r}"))
        df = df[~bad]

    # duplicate (entity_id, date) inside the file -> keep first, quarantine rest
    dup = df.duplicated(subset=["entity_id", "date"], keep="first")
    for i in df[dup].index:
        issues.append(dict(index=int(i), entity_id=str(df.loc[i, "entity_id"]),
                           reason=f"duplicate record for {df.loc[i, 'date']}"))
    df = df[~dup]

    # rates must be within [0, 1]
    for col in ["sla_violation_rate", "silent_close_rate", "missing_field_rate"]:
        bad = (df[col] < 0) | (df[col] > 1)
        for i in df[bad].index:
            issues.append(dict(index=int(i), entity_id=str(df.loc[i, "entity_id"]),
                               reason=f"{col} outside [0,1]"))
        df = df[~bad]

    # ---- soft checks: accepted but flagged (data-quality dashboard) ----
    parts = (pd.to_numeric(df["alerts_critical"], errors="coerce")
             + pd.to_numeric(df["alerts_high"], errors="coerce")
             + pd.to_numeric(df["alerts_medium"], errors="coerce")
             + pd.to_numeric(df["alerts_low"], errors="coerce"))
    mismatch = parts != pd.to_numeric(df["alerts_total"], errors="coerce")
    for i in df[mismatch].index:
        warnings.append(dict(index=int(i), entity_id=str(df.loc[i, "entity_id"]),
                             reason="severity breakdown does not sum to alerts_total"))
    for i in df[pd.to_numeric(df["missing_field_rate"], errors="coerce") > 0.2].index:
        warnings.append(dict(index=int(i), entity_id=str(df.loc[i, "entity_id"]),
                             reason="high missing-field rate (>20%)"))
    for i in df[pd.to_numeric(df["submission_lag_hours"], errors="coerce") > 24].index:
        warnings.append(dict(index=int(i), entity_id=str(df.loc[i, "entity_id"]),
                             reason="late submission (>24h lag)"))

    return df, issues, warnings
