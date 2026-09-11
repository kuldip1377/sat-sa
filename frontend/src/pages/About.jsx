import { useEffect, useState } from 'react'
import { Card, Chip } from '../ui.jsx'
import { get } from '../api.js'

const CAPS = [
  ['Execution Gap Detection', 'SLA breaches, silent closures without case trails, growing unresolved critical backlogs, MTTR outliers, and repetitive suspicious closure patterns (same signature repeated ≥ 20×).'],
  ['Negative Space Detection', 'Silent SOCs, submission gaps, suppressed escalations, blind spots (critical monitored assets with zero telemetry), cases without investigations, and sector-expected alert categories that never appear — what is NOT reported is analysed too.'],
  ['Anomaly & Pattern Detection', 'IsolationForest over weekly behavioural vectors, robust z-score volume spikes, two-regime day-of-week seasonality, and category-mix campaign detection.'],
  ['Review-Sample Prioritization', 'Ranked top-10/25/50/100 examination queue with per-sample reasons and confidence, validated live with P@K/R@K against hidden ground truth (~95% workload reduction).'],
  ['Transparent Attention Score', '0–100 supervisory attention score = six visible weighted parts (execution, negative space, anomaly, peer deviation, criticality, confidence) with runtime-configurable weights and thresholds.'],
  ['Evidence Graph & Traceability', 'CSE → Asset → Alert → Case → Investigation / Escalation → Resolution; every node is a real DB record, absent expected evidence renders as a flagged virtual node. SHA-256 notary chain fingerprints every recompute.'],
  ['Peer Comparison 2.0 & Longitudinal', 'Relevance-based peer groups with medians and percentiles, plus four-window assessment history classifying findings as persistent, emerging or resolved.'],
  ['Validation & Data Quality', 'Detectors self-score against seeded ground truth (P/R/F1/FPR live, never hardcoded); every inbound row is validated and rejects are quarantined with reasons — never silently discarded.'],
  ['Explainability & Reports', 'Structured WHAT / WHY / EVIDENCE / HOW UNUSUAL / CONFIDENCE / WHAT TO REVIEW per finding; printable supervisor reports, CSV export, optional local-LLM narrative (never scoring).'],
]

const STACK = [
  ['Frontend', 'React + Tailwind CSS'],
  ['Backend', 'Python + FastAPI'],
  ['Data Analytics', 'Pandas / Polars + NumPy'],
  ['ML / Anomaly Detection', 'Scikit-learn (IsolationForest)'],
  ['Database', 'PostgreSQL (SQLite in demo)'],
  ['Visualization', 'Recharts / Plotly'],
  ['Rules / Supervisory Signals', 'Python-based custom rule engine'],
  ['Optional Local AI', 'Ollama + local LLM (explainability copilot)'],
  ['Deployment', 'Docker (single-container offline build)'],
  ['Operating Environment', 'Offline / Air-gapped (NCIIPC controlled)'],
]

const FLOW = [
  ['CSE', 'Critical Sector Entity', '#2563eb', 'Operates critical infrastructure; generates alerts, cases, investigations, escalations, dispositions.'],
  ['SOC', 'Security Operations Centre', '#16a34a', 'Monitors, detects, investigates; produces structured operational records.'],
  ['SAT-SA', 'Supervisory Analytics Tool', '#7c3aed', 'Analyses SOC data; detects supervisory signals, scores and prioritizes risk.'],
  ['NCIIPC', 'Supervisor / Examiner', '#0e7490', 'Reviews prioritized findings, drills into evidence, takes supervisory decisions.'],
]

export default function About() {
  const [ev, setEv] = useState(null)
  useEffect(() => { get('/eval').then(setEv).catch(() => {}) }, [])
  return (
    <div className="space-y-4">
      {ev && (
        <Card title="Live detector evaluation" sub="detectors scored against the seeded ground-truth manifest (datagen.EXPECTED)">
          <div className="grid grid-cols-3 gap-3 max-w-sm">
            {[['Precision', ev.precision], ['Recall', ev.recall], ['F1', ev.f1]].map(([l, v]) => (
              <div key={l} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-center">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">{l}</div>
                <div className="text-2xl font-black text-emerald-400">{v.toFixed(2)}</div>
              </div>
            ))}
          </div>
          <div className="text-[11px] text-slate-500 mt-3">
            {ev.tp} true positives · {ev.fp} false positives · {ev.fn} false negatives.
            Auxiliary triangulators (IsolationForest, Mahalanobis) corroborate but are not scored.
          </div>
          <div className="overflow-x-auto mt-3">
            <table className="w-full text-[11px] min-w-[420px]">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                  <th className="text-left py-1 pr-3">Detector</th>
                  <th className="text-right py-1 pr-3">TP</th>
                  <th className="text-right py-1 pr-3">FP</th>
                  <th className="text-right py-1">FN</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(ev.per_key).map(([k, v]) => (
                  <tr key={k} className="border-b border-slate-800/60">
                    <td className="py-1 pr-3 font-mono text-slate-300">{k}</td>
                    <td className="py-1 pr-3 text-right text-emerald-400">{v.tp}</td>
                    <td className="py-1 pr-3 text-right text-red-400">{v.fp}</td>
                    <td className="py-1 text-right text-amber-400">{v.fn}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      <Card title="Solution workflow" sub="SIH 2026 · PS 26157 · Supervisory Analytics Tool for SOC Assessment (SAT-SA)">
        <div className="grid md:grid-cols-7 gap-3 items-stretch">
          {FLOW.map(([abbr, full, color, desc], i) => (
            <div key={abbr} className={i < 3 ? 'md:col-span-2 md:contents' : 'md:col-span-1'} style={{ display: 'contents' }}>
              <div className="rounded-xl border p-3 h-full" style={{ borderColor: color + '66', background: color + '14' }}>
                <div className="font-extrabold" style={{ color }}>{abbr}</div>
                <div className="text-[10px] text-slate-400 mb-1.5">{full}</div>
                <div className="text-[11px] text-slate-300 leading-snug">{desc}</div>
              </div>
              {i < 3 && (
                <div className="hidden md:flex items-center justify-center text-slate-500 text-lg">→</div>
              )}
            </div>
          ))}
        </div>
        <div className="mt-3 rounded-lg border border-amber-700/40 bg-amber-900/15 px-3 py-2 text-[11px] text-amber-300">
          🔒 All operations are performed in a secure, offline (air-gapped) environment controlled by NCIIPC.
          No external network calls; optional AI runs as a local LLM (Ollama) inside the enclave.
        </div>
      </Card>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Positioning within the assessment ecosystem"
          sub="complementary to formal assessment processes — never a replacement">
          <p className="text-[11px] text-slate-300 leading-relaxed">
            Traditional assessment establishes whether controls and governance arrangements
            exist and are being represented as implemented; SAT-SA adds an operational-evidence
            layer that can help supervisors assess whether observed SOC processes appear to
            operate as expected between formal assessment cycles.
          </p>
          <p className="text-[11px] text-slate-400 leading-relaxed mt-2">
            SAT-SA does not certify compliance, makes no claim of official mapping to any
            regulatory framework, and never converts an analytical signal into a statement of
            confirmed failure. Findings are indicators for human examination — the supervisory
            decision always belongs to the NCIIPC examiner.
          </p>
        </Card>

        <Card title="System boundary & internal role model"
          sub="CSEs submit data; NCIIPC-controlled SAT-SA processes it; human supervisors decide">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                <th className="text-left py-1.5 pr-3">Role</th>
                <th className="text-left py-1.5">Permissions</th>
              </tr>
            </thead>
            <tbody>
              {[['Administrator', 'everything, incl. reseed & configuration'],
                ['Supervisor', 'ingest submissions, tune configuration, act on findings'],
                ['Analyst / Reviewer', 'examine evidence, act on findings (read + actions)'],
                ['Auditor', 'read-only: findings, evidence, audit trail, notary chain']].map(([r, p]) => (
                <tr key={r} className="border-b border-slate-800/60">
                  <td className="py-1.5 pr-3 text-slate-200 font-semibold">{r}</td>
                  <td className="py-1.5 text-slate-400">{p}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[11px] text-slate-500 mt-2 leading-relaxed">
            No public-facing CSE portal: the prototype boundary stays entirely inside the
            NCIIPC-controlled enclave. Submissions arrive as periodic CSV/JSON files,
            optionally HMAC-signed for provenance.
          </p>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Key capabilities" sub="mapped from the problem statement">
          <div className="space-y-2.5">
            {CAPS.map(([t, d]) => (
              <div key={t} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                <div className="text-xs font-bold text-violet-300">{t}</div>
                <div className="text-[11px] text-slate-400 mt-1 leading-relaxed">{d}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Toolkit / technology" sub="reference stack for production deployment">
          <table className="w-full text-xs">
            <tbody>
              {STACK.map(([k, v]) => (
                <tr key={k} className="border-b border-slate-800/60">
                  <td className="py-2 pr-3 text-slate-400 w-44">{k}</td>
                  <td className="py-2 text-slate-200 font-medium">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-4 space-y-1.5 text-[11px] text-slate-500 leading-relaxed">
            <div>· Demo build runs single-process (FastAPI serves the built React app) with SQLite so it works fully offline; switching <code className="text-slate-300">DATABASE_URL</code> to PostgreSQL is a one-line change for production.</div>
            <div>· Docker image bundles frontend + backend + rule engine for drop-in deployment inside the NCIIPC enclave.</div>
            <div>· The optional Ollama module can narrate each signal in natural language for the examiner without any data leaving the enclave.</div>
          </div>
        </Card>
      </div>
    </div>
  )
}
