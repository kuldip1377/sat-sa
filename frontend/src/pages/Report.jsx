import { useEffect, useState } from 'react'
import { get } from '../api.js'
import { Loading, SevChip } from '../ui.jsx'

const L = 'py-1 pr-3 text-slate-600'
const R = 'py-1 text-right font-semibold text-slate-900'

// Static, transparent crosswalk. Deliberately hedged: SAT-SA does not certify
// compliance and claims no official NCIIPC/CAF mapping.
const CROSSWALK = {
  sla: ['Incident response timeliness', 'Critical-alert acknowledgement against stated SLA (alerts.ack_minutes)'],
  silent_close: ['Case management discipline', 'Critical alerts disposed without case records (daily.silent_close_rate)'],
  backlog: ['Sustained response capacity', 'Trend of unresolved critical backlog (daily.open_critical_end)'],
  mttr: ['Incident resolution effectiveness', 'Time-to-resolve vs comparable entities (daily.mttr_hours)'],
  no_esc: ['Escalation & information sharing', 'Critical volume with no NCIIPC escalation records (escalations)'],
  silent_soc: ['Monitoring continuity', 'Zero-telemetry days vs peer activity (daily.alerts_total)'],
  sub_gap: ['Reporting discipline', 'Missing periodic submission days (daily)'],
  blind_spot: ['Coverage of critical assets', 'Critical monitored assets without alert records (assets × alerts)'],
  no_inv: ['Investigation depth', 'Critical cases lacking investigation records (investigations)'],
  cat_absent: ['Detection breadth', 'Sector-typical attack category absent from recent alerts (alerts.category)'],
  pattern_repeat: ['Process integrity', 'Repeated fast-closure signature (alerts × cases × investigations)'],
  spike: ['Threat surge handling', 'Volume deviation vs own baseline (weekly aggregates)'],
  seasonal: ['Operational consistency', 'Day-of-week pattern breaks (daily baselines)'],
  campaign: ['Coordinated-campaign response', 'Category-mix shift vs prior period (alerts.category)'],
  hygiene: ['Data governance', 'Missing-field rates and submission lag (daily)'],
}

export default function Report({ eid, back }) {
  const [d, setD] = useState(null)
  useEffect(() => { setD(null); get(`/entities/${eid}`).then(setD) }, [eid])
  if (!d) return <Loading />
  const m = d.metrics
  const today = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })

  return (
    <div className="max-w-3xl mx-auto">
      <div className="no-print flex gap-2 mb-4">
        <button onClick={back} className="text-xs text-slate-400 hover:text-slate-200">← Console</button>
        <button onClick={() => window.print()}
          className="ml-auto rounded-lg bg-violet-600 hover:bg-violet-500 px-4 py-1.5 text-xs font-semibold text-white">
           Print / Save as PDF
        </button>
      </div>

      <div className="bg-white text-slate-900 rounded-xl p-8 shadow-xl print:shadow-none">
        <div className="border-2 border-slate-900 text-center text-[10px] font-bold tracking-[0.25em] py-1 mb-5">
          NCIIPC · SUPERVISORY ASSESSMENT REPORT · OFFLINE ENCLAVE COPY
        </div>

        <div className="flex items-start justify-between border-b-2 border-slate-900 pb-3">
          <div>
            <div className="text-2xl font-black tracking-wide">SAT-SA</div>
            <div className="text-[11px] text-slate-600">Supervisory Analytics Tool for SOC Assessment</div>
          </div>
          <div className="text-right text-[11px] text-slate-600">
            <div>Report date: <b className="text-slate-900">{today}</b></div>
            <div>Reference: <b className="text-slate-900">SAT-SA/{d.id}/30D</b></div>
            <div>SIH 2026 · PS 26157</div>
          </div>
        </div>

        <h2 className="text-lg font-bold mt-5">{d.name} <span className="text-slate-500 font-normal">({d.id})</span></h2>
        <div className="text-[12px] text-slate-600 mt-0.5">
          Sector: {d.sector} · Asset criticality: {d.criticality} · Declared SOC maturity: {d.maturity} ·
          Assets in inventory: {d.assets.toLocaleString('en-IN')}
        </div>

        <div className="flex items-center gap-6 mt-4 border border-slate-400 rounded p-3">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Composite supervisory risk</div>
            <div className="text-4xl font-black">{d.score}<span className="text-base text-slate-500">/100</span></div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Priority rank</div>
            <div className="text-2xl font-bold">#{d.rank} <span className="text-sm text-slate-500">of 12 supervised CSEs</span></div>
          </div>
          <div className="ml-auto text-[11px] text-slate-600">
            Active supervisory signals: <b className="text-slate-900">{d.signals.length}</b>
          </div>
        </div>

        <h3 className="text-sm font-bold mt-6 mb-1 border-b border-slate-400">1. Operational metrics (last 30 days)</h3>
        <table className="w-full text-[12px]">
          <tbody>
            <tr><td className={L}>Total alerts / critical alerts</td><td className={R}>{m.alerts30.toLocaleString('en-IN')} / {m.crit30}</td></tr>
            <tr><td className={L}>Open critical backlog (current)</td><td className={R}>{m.open_now}</td></tr>
            <tr><td className={L}>Median acknowledge time (critical SLA ≤ 60 min)</td><td className={R}>{m.ack} min</td></tr>
            <tr><td className={L}>Mean time to resolve (peer median {d.benchmark[0].peer}h)</td><td className={R}>{m.mttr} h</td></tr>
            <tr><td className={L}>Critical SLA violation rate</td><td className={R}>{(m.sla * 100).toFixed(0)}%</td></tr>
            <tr><td className={L}>Escalation rate on criticals (peer {Math.round(d.benchmark[2].peer * 100)}%)</td><td className={R}>{Math.round(m.esc_rate * 100)}%</td></tr>
            <tr><td className={L}>Submission gaps / zero-telemetry days</td><td className={R}>{m.gap_days} / {m.zero_days}</td></tr>
          </tbody>
        </table>

        <h3 className="text-sm font-bold mt-6 mb-2 border-b border-slate-400">2. Supervisory findings & evidence</h3>
        {d.signals.length === 0 && (
          <p className="text-[12px] text-slate-700">No active supervisory signals. Entity operates within peer norms.</p>
        )}
        {d.signals.map((s, i) => (
          <div key={s.id} className="mb-3 break-inside-avoid">
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-bold">2.{i + 1} {s.title}</span>
              <SevChip sev={s.severity} />
              <span className="text-[10px] text-slate-500">{s.category}</span>
            </div>
            <p className="text-[11px] text-slate-700 mt-0.5">{s.detail}</p>
            <p className="text-[11px] text-slate-600 mt-0.5">
              Observed: <b>{s.observed}</b> · Benchmark: <b>{s.benchmark}</b> ·
              Evidence: <span className="font-mono text-[10px]">{JSON.stringify(s.evidence)}</span>
            </p>
          </div>
        ))}

        <h3 className="text-sm font-bold mt-6 mb-1 border-b border-slate-400">3. Recommended supervisory actions</h3>
        {d.signals.length > 0 && (
          <div className="mt-6">
            <div className="text-[11px] font-bold tracking-widest uppercase border-b border-slate-400 pb-1">
              Assessment-context crosswalk (indicative)
            </div>
            <table className="w-full text-[11px] mt-2">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-300">
                  <th className="py-1 pr-2">SAT-SA finding</th>
                  <th className="py-1 pr-2">Potentially relevant capability area</th>
                  <th className="py-1">Evidence type</th>
                </tr>
              </thead>
              <tbody>
                {d.signals.map((s) => CROSSWALK[s.key] && (
                  <tr key={s.id} className="border-b border-slate-200 align-top">
                    <td className="py-1 pr-2 font-semibold text-slate-800">{s.title}</td>
                    <td className="py-1 pr-2 text-slate-700">{CROSSWALK[s.key][0]}</td>
                    <td className="py-1 text-slate-600">{CROSSWALK[s.key][1]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[9px] text-slate-500 mt-1.5 leading-snug">
              Traditional assessment establishes whether controls and governance arrangements
              exist and are being represented as implemented; SAT-SA adds an
              operational-evidence layer that can help supervisors assess whether observed SOC
              processes appear to operate as expected between formal assessment cycles. This
              crosswalk is indicative only — SAT-SA does not certify compliance and makes no
              claim of official mapping to any regulatory framework.
            </p>
          </div>
        )}

        <ol className="list-decimal ml-5 text-[12px] text-slate-700 space-y-1 mt-6">
          {d.signals.length === 0 && <li>Continue routine periodic assessment.</li>}
          {d.signals.some((s) => s.category === 'Negative Space') &&
            <li>Issue a data-call to {d.id} for internal SOC logs covering the silent/gap window; verify sensor and submission pipeline integrity.</li>}
          {d.signals.some((s) => s.category === 'Execution Gap') &&
            <li>Require a remediation timeline for SLA/closure process breaches; re-assess in 30 days.</li>}
          {d.signals.some((s) => s.severity === 'critical') &&
            <li>Elevate to immediate supervisory review given a critical-severity finding.</li>}
          <li>Attach this report and the machine-readable evidence export to the entity's assessment file.</li>
        </ol>

        <div className="grid grid-cols-2 gap-10 mt-12 text-[11px] text-slate-600">
          <div className="border-t border-slate-500 pt-1">Prepared by (SAT-SA automated analysis)</div>
          <div className="border-t border-slate-500 pt-1">NCIIPC Supervisor — examination & decision</div>
        </div>
        <p className="text-[10px] text-slate-500 mt-6">
          Generated inside the NCIIPC air-gapped enclave from structured CSE SOC submissions.
          Figures reflect the last 30-day assessment window. This copy is for supervisory use only.
        </p>
      </div>
    </div>
  )
}
