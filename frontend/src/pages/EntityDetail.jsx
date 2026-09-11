import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, Legend, PieChart, Pie, Cell,
} from 'recharts'
import { get } from '../api.js'
import { Card, Stat, Loading, ScoreBadge, SevChip, Chip, AXIS, TT_STYLE, SEV, ExplainBtn, Spark } from '../ui.jsx'
import SignalActions from '../components/SignalActions.jsx'
import EvidenceGraph from '../components/EvidenceGraph.jsx'

function EvidenceGraphBtn({ sid }) {
  const [g, setG] = useState(null)
  const [busy, setBusy] = useState(false)
  async function go() {
    if (g) { setG(null); return }
    setBusy(true)
    try { setG(await get(`/graph/finding/${sid}`)) } finally { setBusy(false) }
  }
  return (
    <div className="mt-1.5 no-print">
      <button onClick={go} className="text-[11px] text-violet-300 hover:underline">
        {g ? 'hide evidence graph' : busy ? 'loading…' : '⛓ evidence graph'}
      </button>
      {g && (
        <div className="mt-2">
          {g.pattern && (
            <div className="text-[10px] text-amber-300 mb-1.5">
              repeated signature ×{g.pattern.count}: {g.pattern.signature}
            </div>
          )}
          <EvidenceGraph graph={g} height={280} />
        </div>
      )}
    </div>
  )
}

export default function EntityDetail({ eid, back, openReport }) {
  const [d, setD] = useState(null)
  useEffect(() => { setD(null); get(`/entities/${eid}`).then(setD) }, [eid])
  if (!d) return <Loading />
  const m = d.metrics

  return (
    <div className="space-y-4">
      <button onClick={back} className="text-xs text-slate-400 hover:text-slate-200">
        ← All entities
      </button>

      <Card>
        <div className="flex flex-wrap items-center gap-4">
          <div className="mr-auto">
            <div className="text-xl font-bold text-slate-100">{d.name}</div>
            <div className="flex flex-wrap gap-2 mt-2">
              <Chip color="#38bdf8">{d.id}</Chip>
              <Chip color="#34d399">{d.sector}</Chip>
              <Chip color="#fbbf24">{d.criticality} asset · {d.assets.toLocaleString('en-IN')} assets</Chip>
              <Chip color="#64748b">SOC maturity {d.maturity}</Chip>
            </div>
          </div>
          <div className="text-right">
            <div className="no-print flex items-center justify-end gap-2 mb-2">
              <span className="text-[10px] text-slate-500">trajectory</span>
              <Spark data={d.traj} color="#a78bfa" w={72} h={22} />
              <button onClick={() => openReport(eid)}
                className="rounded-lg bg-violet-600 hover:bg-violet-500 px-3 py-1.5 text-[11px] font-semibold text-white">
                ⎙ Supervisor report
              </button>
            </div>
            <div className="text-[11px] uppercase tracking-wider text-slate-400">
              Supervisory risk · rank #{d.rank}
            </div>
            <div className="text-3xl font-extrabold mt-1">
              <ScoreBadge score={d.score} />
              <span className="text-slate-600 text-base font-semibold"> /100</span>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Stat label="Alerts · 30d" value={m.alerts30.toLocaleString('en-IN')} color="#38bdf8" />
        <Stat label="Critical · 30d" value={m.crit30} color="#f87171" />
        <Stat label="Open criticals" value={m.open_now} color={m.open_now > 10 ? '#f87171' : '#34d399'} />
        <Stat label="MTTR" value={`${m.mttr}h`} color="#fbbf24" sub={`peer median ${d.benchmark[0].peer}h`} />
        <Stat label="SLA compliance" value={`${Math.round((1 - m.sla) * 100)}%`} color="#34d399" sub="critical ack ≤ 60 min" />
        <Stat label="Escalation rate" value={`${Math.round(m.esc_rate * 100)}%`} color="#a78bfa" sub={`peer ${Math.round(d.benchmark[2].peer * 100)}%`} />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Card title="Supervisory Attention Score — breakdown"
          sub={`${d.score}/100 · ${d.label} · weights configurable under Architecture`}
          right={<Chip color={d.label === 'High Priority' ? '#f87171' : d.label === 'Attention' ? '#fbbf24' : '#34d399'}>{d.label}</Chip>}>
          <div className="space-y-2">
            {d.attn.parts.map((p) => (
              <div key={p.name}>
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-slate-400">{p.name}</span>
                  <span className="font-semibold text-slate-200">{p.points} pts</span>
                </div>
                <div className="h-1.5 bg-slate-800 rounded overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-violet-600 to-fuchsia-400"
                    style={{ width: `${(p.points / 25) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="text-[10px] text-slate-500 mt-3 leading-relaxed">
            Every point is traceable: execution gaps, negative space, anomaly, peer deviation,
            criticality and evidence confidence — no black-box scoring.
          </div>
        </Card>

        <Card title="Longitudinal assessment" sub="4 × 30-day assessment windows, oldest → latest">
          <div className="grid grid-cols-4 gap-2 mb-3">
            {d.history.windows.map((w) => (
              <div key={w.label} className="rounded-lg border border-slate-800 bg-slate-950/50 p-2 text-center">
                <div className="text-[9px] text-slate-500">{w.label}</div>
                <div className={`text-lg font-extrabold ${w.score >= 60 ? 'text-red-400' : w.score >= 30 ? 'text-amber-400' : 'text-emerald-400'}`}>
                  {w.score}
                </div>
                <div className="flex flex-wrap gap-0.5 justify-center mt-1">
                  {w.families.map((f) => (
                    <span key={f} className="text-[8px] px-1 rounded bg-slate-800 text-slate-400">{f}</span>
                  ))}
                  {w.families.length === 0 && <span className="text-[8px] text-emerald-500">clear</span>}
                </div>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {d.history.classes.length === 0 &&
              <span className="text-[11px] text-emerald-400">No persistent or emerging issue families.</span>}
            {d.history.classes.map((cl) => (
              <Chip key={cl.family}
                color={{ WORSENING: '#f87171', PERSISTENT: '#fbbf24', RETURNED: '#fb923c',
                  NEW: '#38bdf8', IMPROVING: '#34d399', RESOLVED: '#34d399' }[cl.status] || '#94a3b8'}>
                {cl.family} · {cl.status}
              </Chip>
            ))}
          </div>
          <div className="flex flex-wrap gap-3 mt-2.5 text-[10px] text-slate-400">
            {Object.entries(d.history.deltas).map(([k, v]) => (
              <span key={k}>
                {k} {v == null ? '—' :
                  <b style={{ color: Math.abs(v) < 5 ? '#94a3b8' : v > 0 ? '#f87171' : '#34d399' }}>
                    {v > 0 ? '+' : ''}{v}%
                  </b>}
              </span>
            ))}
            <span className="text-slate-600">(W1 → W4)</span>
          </div>
          {d.history.persistent_concern && (
            <div className="mt-2 rounded-lg border border-red-900/60 bg-red-950/30 p-2 text-[11px] text-red-300">
              ⚑ Persistent Supervisory Concern
            </div>
          )}
          {d.history.review_trigger?.recommended && (
            <div className="mt-2 rounded-lg border border-amber-900/60 bg-amber-950/30 p-2 text-[11px] text-amber-300">
              {d.history.review_trigger.note}
            </div>
          )}
        </Card>

        <Card title="Peer group benchmarking 2.0"
          sub={`group: ${d.peer_group.group} · ${d.peer_group.members.length} members · medians`}>
          <table className="w-full text-xs">
            <tbody>
              {Object.entries(d.peer_group.medians).map(([k, v]) => (
                <tr key={k} className="border-b border-slate-800/60">
                  <td className="py-1.5 text-slate-400">{k}</td>
                  <td className="py-1.5 text-right font-semibold text-slate-200">{v ?? '—'}</td>
                </tr>
              ))}
              <tr className="border-b border-slate-800/60">
                <td className="py-1.5 text-slate-400">This entity — investigation median</td>
                <td className="py-1.5 text-right font-semibold text-slate-200">
                  {d.inv_median != null ? `${Math.round(d.inv_median)} min` : 'no investigations'}
                </td>
              </tr>
              <tr>
                <td className="py-1.5 text-slate-400">Data-quality score</td>
                <td className="py-1.5 text-right font-semibold" style={{ color: d.dq >= 90 ? '#34d399' : '#fbbf24' }}>
                  {d.dq}
                </td>
              </tr>
            </tbody>
          </table>
          <div className="text-[10px] text-slate-500 mt-2">
            Deviation from group medians indicates review priority, not automatically poor security.
          </div>
        </Card>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Card title="Daily alerts vs peer median" sub="last 90 days" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={250}>
            <ComposedChart data={d.series} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis dataKey="date" {...AXIS} interval={13} />
              <YAxis {...AXIS} />
              <Tooltip contentStyle={TT_STYLE} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="alerts" fill="#38bdf8" fillOpacity={0.55} name="Entity alerts" radius={[2, 2, 0, 0]} />
              <Line dataKey="critical" stroke="#f87171" dot={false} strokeWidth={1.5} name="Critical" />
              <Line dataKey="peer" stroke="#fbbf24" strokeDasharray="5 4" dot={false} strokeWidth={1.5} name="Peer median" />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Severity mix · 30d" sub="alert distribution">
          <ResponsiveContainer width="100%" height={190}>
            <PieChart>
              <Pie data={d.sevmix} dataKey="value" nameKey="severity" innerRadius={45} outerRadius={70}
                paddingAngle={3} stroke="none">
                {d.sevmix.map((s, i) => (
                  <Cell key={i} fill={SEV[s.severity.toLowerCase()]} fillOpacity={0.85} />
                ))}
              </Pie>
              <Tooltip contentStyle={TT_STYLE} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-3 text-[11px] text-slate-400">
            {d.sevmix.map((s) => (
              <span key={s.severity} className="flex items-center gap-1">
                <i className="w-2 h-2 rounded-full" style={{ background: SEV[s.severity.toLowerCase()] }} />
                {s.severity} {s.value}
              </span>
            ))}
          </div>
          <div className="mt-4">
            <div className="text-[11px] uppercase tracking-wider text-slate-400 mb-2">Triage funnel · 30d</div>
            {[['Alerts', d.funnel.alerts, '#38bdf8'], ['Cases opened', d.funnel.cases, '#34d399'],
              ['Escalated to NCIIPC', d.funnel.escalations, '#a78bfa']].map(([l, v, c]) => (
              <div key={l} className="mb-1.5">
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-slate-400">{l}</span><span className="font-semibold" style={{ color: c }}>{v}</span>
                </div>
                <div className="h-1.5 bg-slate-800 rounded overflow-hidden">
                  <div className="h-full" style={{ width: `${(v / Math.max(d.funnel.alerts, 1)) * 100}%`, background: c }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Peer benchmarking" sub="percentile vs all supervised CSEs (higher percentile = worse)">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                <th className="text-left py-1.5">Metric</th>
                <th className="text-right py-1.5">Entity</th>
                <th className="text-right py-1.5">Peer median</th>
                <th className="text-left py-1.5 pl-4 w-40">Percentile</th>
              </tr>
            </thead>
            <tbody>
              {d.benchmark.map((b) => (
                <tr key={b.metric} className="border-b border-slate-800/60">
                  <td className="py-2 text-slate-300">{b.metric}</td>
                  <td className="py-2 text-right font-semibold text-slate-200">{b.entity}</td>
                  <td className="py-2 text-right text-slate-400">{b.peer}</td>
                  <td className="py-2 pl-4">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-slate-800 rounded overflow-hidden">
                        <div className="h-full" style={{
                          width: `${b.percentile}%`,
                          background: b.percentile > 75 ? '#f87171' : b.percentile > 50 ? '#fbbf24' : '#34d399',
                        }} />
                      </div>
                      <span className="text-[11px] text-slate-400 w-8">P{b.percentile}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <Card title="Supervisory signals on this entity" sub={`${d.signals.length} active`}>
          {d.signals.length === 0 && (
            <div className="text-sm text-emerald-400 py-4">No active supervisory signals — operating within peer norms.</div>
          )}
          <div className="space-y-2.5">
            {d.signals.map((s) => (
              <div key={s.id} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <SevChip sev={s.severity} />
                  <Chip color="#a78bfa">{s.category}</Chip>
                  <span className="text-sm font-semibold text-slate-200">{s.title}</span>
                </div>
                <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">{s.detail}</p>
                <details className="mt-1.5">
                  <summary className="text-[11px] text-violet-300">view evidence ▾</summary>
                  <pre className="mt-1.5 text-[11px] text-slate-300 bg-slate-900 border border-slate-800 rounded p-2 overflow-x-auto">
                    {JSON.stringify({ observed: s.observed, benchmark: s.benchmark, ...s.evidence }, null, 2)}
                  </pre>
                </details>
                <EvidenceGraphBtn sid={s.id} />
                <ExplainBtn sid={s.id} />
                <SignalActions sid={s.id} current={s.action} onChanged={() =>
                  get(`/entities/${eid}`).then(setD)} />
              </div>
            ))}
          </div>
        </Card>
      </div>

      {d.samples.length > 0 && (
        <Card title="Priority review samples for this CSE"
          sub="top of the entity's slice of the national review queue — full reasoning on the Review Queue page">
          <div className="space-y-1.5">
            {d.samples.map((s) => (
              <div key={s.id} className="flex flex-wrap items-center gap-2 text-[11px] border-b border-slate-800/60 pb-1.5">
                <span className="font-mono text-slate-400">{s.id}</span>
                <SevChip sev={s.severity.toLowerCase()} />
                <span className="text-slate-300">{s.category}</span>
                <span className="text-violet-300 font-bold ml-auto">{s.score} pts</span>
                <span className="text-slate-500 w-full sm:w-auto sm:max-w-[520px] truncate">
                  {s.reasons.join(' · ')}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card title="Recent alert-level records" sub="sampled from structured CSE submissions — evidence trail">
        <div className="overflow-x-auto -mx-4 px-4">
          <table className="w-full text-xs min-w-[760px]">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                {['Alert ID', 'Timestamp', 'Severity', 'Category', 'Status', 'Ack (min)', 'Case', 'Disposition'].map((h) => (
                  <th key={h} className="text-left py-1.5 pr-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.recent_alerts.map((a) => (
                <tr key={a.id} className="border-b border-slate-800/60">
                  <td className="py-1.5 pr-3 font-mono text-slate-400">{a.id}</td>
                  <td className="py-1.5 pr-3 text-slate-400">{a.ts.replace('T', ' ')}</td>
                  <td className="py-1.5 pr-3"><SevChip sev={a.severity.toLowerCase()} /></td>
                  <td className="py-1.5 pr-3 text-slate-300">{a.category}</td>
                  <td className="py-1.5 pr-3 text-slate-300">{a.status}</td>
                  <td className="py-1.5 pr-3 text-slate-300">{a.ack_minutes}</td>
                  <td className="py-1.5 pr-3 font-mono text-slate-400">{a.case_id || '—'}</td>
                  <td className="py-1.5 text-slate-400">{a.disposition || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
