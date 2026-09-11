import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, Cell,
} from 'recharts'
import { get } from '../api.js'
import { Card, Stat, Loading, ScoreBadge, SevChip, AXIS, TT_STYLE } from '../ui.jsx'
import IndiaMap from '../components/IndiaMap.jsx'

export default function Overview({ openEntity, openBulletin }) {
  const [d, setD] = useState(null)
  const [ents, setEnts] = useState([])
  const [aud, setAud] = useState([])
  const [demo, setDemo] = useState(null)
  useEffect(() => {
    get('/overview').then(setD).catch(() => setD({ error: true }))
    get('/entities').then(setEnts)
    get('/audit').then((r) => setAud(r.audit))
    get('/demo-case').then(setDemo).catch(() => {})
  }, [])
  if (!d) return <Loading />
  if (d.error) return <div className="p-10 text-red-400">Backend unreachable.</div>
  const { kpis } = d
  const maxCat = Math.max(...Object.values(d.signals_by_category), 1)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Stat label="CSEs monitored" value={kpis.entities} sub="critical sector entities" />
        <Stat label="High-priority CSEs" value={kpis.high_priority} color={kpis.high_priority ? '#f87171' : '#34d399'}
          sub={`attention ≥ 60 (threshold configurable) · ${kpis.signals} signals active`} />
        <Stat label="Alerts · 30d" value={kpis.alerts30.toLocaleString('en-IN')} color="#38bdf8"
          sub={`${kpis.open_critical} criticals unresolved`} />
        <Stat label="Negative-space signals" value={kpis.negative_space} color="#fbbf24"
          sub="missing evidence indicators — requires review" />
        <Stat label="Review samples · 30d" value={kpis.samples} color="#a78bfa"
          sub="prioritized on the Review Queue page" />
        <Stat label="Persistent / emerging" value={`${kpis.persistent} / ${kpis.emerging}`} color="#f472b6"
          sub="longitudinal assessment findings" />
        <Stat label="Detector F1 (ground truth)" value={kpis.eval_f1?.toFixed(2)} color="#34d399"
          sub="live eval vs seeded anomalies" />
        <Stat label="Data quality" value={kpis.dq} color={kpis.dq >= 90 ? '#34d399' : '#fbbf24'}
          sub="mean submission-quality score" />
        <Stat label="Reporting compliance" value={`${kpis.compliance_pct}%`} color="#34d399" sub="30-day submission coverage" />
        <Stat label="Peer median MTTR" value={`${kpis.median_mttr}h`} color="#fbbf24" />
        <Stat label="Execution-gap signals" value={kpis.exec_gaps} color="#fb923c" sub="SLA / closure / backlog / MTTR" />
        <Stat label="Signal mix" value={`${kpis.signals_by_sev.critical}c ${kpis.signals_by_sev.high}h ${kpis.signals_by_sev.medium}m`}
          color="#a78bfa" sub="by severity" />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Card title="National alert volume — last 90 days" sub="all CSE SOC submissions, by severity"
          className="lg:col-span-2"
          right={<button onClick={openBulletin}
            className="no-print rounded-lg bg-violet-600 hover:bg-violet-500 px-3 py-1.5 text-[11px] font-semibold text-white">
            ⎙ Weekly bulletin
          </button>}>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={d.trend} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis dataKey="date" {...AXIS} interval={13} />
              <YAxis {...AXIS} />
              <Tooltip contentStyle={TT_STYLE} />
              <Area stackId="1" dataKey="low" stroke="#64748b" fill="#334155" fillOpacity={0.5} name="Low" />
              <Area stackId="1" dataKey="medium" stroke="#facc15" fill="#facc15" fillOpacity={0.35} name="Medium" />
              <Area stackId="1" dataKey="high" stroke="#fb923c" fill="#fb923c" fillOpacity={0.45} name="High" />
              <Area stackId="1" dataKey="critical" stroke="#f87171" fill="#f87171" fillOpacity={0.6} name="Critical" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Supervisory signals" sub="by detection capability">
          <div className="space-y-3 mt-2">
            {Object.entries(d.signals_by_category).map(([cat, n]) => (
              <div key={cat}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-300">{cat}</span>
                  <span className="font-bold text-violet-300">{n}</span>
                </div>
                <div className="h-2 rounded bg-slate-800 overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-violet-600 to-fuchsia-400"
                    style={{ width: `${(n / maxCat) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="text-[11px] text-slate-500 mt-4 leading-relaxed">
            Signals are produced by the rule engine (execution gaps, negative space, data
            hygiene) plus IsolationForest anomaly detection over weekly SOC behaviour.
          </div>
        </Card>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Card title="Average risk score by sector" sub="composite 0–100 supervisory risk">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={d.sectors} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis dataKey="sector" {...AXIS} interval={0} angle={-14} height={44} textAnchor="end" />
              <YAxis {...AXIS} domain={[0, 100]} />
              <Tooltip contentStyle={TT_STYLE} cursor={{ fill: '#1e293b55' }} />
              <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                {d.sectors.map((s, i) => (
                  <Cell key={i} fill={s.score >= 60 ? '#f87171' : s.score >= 30 ? '#fbbf24' : '#34d399'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Priority review queue" sub="highest supervisory risk first — click to drill down" className="lg:col-span-2">
          <div className="divide-y divide-slate-800">
            {d.top.map((e, i) => (
              <button key={e.id} onClick={() => openEntity(e.id)}
                className="w-full flex items-center gap-3 py-2.5 text-left hover:bg-slate-800/40 px-2 rounded transition-colors">
                <span className="text-slate-500 text-xs w-5">#{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-slate-200 truncate">
                    {e.name} <span className="text-slate-500 font-normal">· {e.id} · {e.sector}</span>
                  </div>
                  <div className="text-[11px] text-slate-400 truncate">Top signal: {e.top_signal}</div>
                </div>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap"
                  style={{
                    background: e.label === 'High Priority' ? '#f871711f' : e.label === 'Attention' ? '#fbbf241f' : '#34d3991f',
                    color: e.label === 'High Priority' ? '#f87171' : e.label === 'Attention' ? '#fbbf24' : '#34d399',
                    border: `1px solid ${e.label === 'High Priority' ? '#f8717155' : e.label === 'Attention' ? '#fbbf2455' : '#34d39955'}`,
                  }}>{e.label}</span>
                <ScoreBadge score={e.score} />
              </button>
            ))}
          </div>
        </Card>
      </div>

      {demo && (
        <Card title="Why KPIs alone are not enough — live demo case"
          sub={`${demo.name} (${demo.entity_id}) · every number below is computed from the database at request time`}>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">Conventional KPI view</div>
              <div className="grid grid-cols-2 gap-2 text-center mb-2">
                <div><div className="text-lg font-bold text-emerald-400">{demo.naive.closure_rate_pct}%</div>
                  <div className="text-[10px] text-slate-500">case closure rate</div></div>
                <div><div className="text-lg font-bold text-slate-200">{demo.naive.alerts_handled_30d}</div>
                  <div className="text-[10px] text-slate-500">alerts handled · 30d</div></div>
                <div><div className="text-lg font-bold text-slate-200">{demo.naive.cases_closed_30d}</div>
                  <div className="text-[10px] text-slate-500">cases closed</div></div>
                <div><div className="text-lg font-bold text-slate-200">{demo.naive.ack_min_median} min</div>
                  <div className="text-[10px] text-slate-500">median ack</div></div>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">{demo.naive.narrative}</p>
            </div>
            <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-3">
              <div className="text-[10px] uppercase tracking-wider text-red-400 mb-2">SAT-SA evidence view</div>
              <div className="grid grid-cols-2 gap-2 text-center mb-2">
                <div><div className="text-lg font-bold text-red-400">×{demo.satsa.pattern_count}</div>
                  <div className="text-[10px] text-slate-500">repetitive fast-closure signature</div></div>
                <div><div className="text-lg font-bold text-red-400">{Math.round(demo.satsa.no_inv_rate * 100)}%</div>
                  <div className="text-[10px] text-slate-500">critical cases w/o investigation</div></div>
                <div><div className="text-lg font-bold text-amber-400">{demo.satsa.silent_close_pct}%</div>
                  <div className="text-[10px] text-slate-500">silent closures</div></div>
                <div><div className="text-lg font-bold text-amber-400">{demo.satsa.escalations_30d}</div>
                  <div className="text-[10px] text-slate-500">escalations · 30d</div></div>
              </div>
              <p className="text-[11px] text-slate-300 leading-relaxed">{demo.satsa.narrative}</p>
              <button onClick={() => openEntity(demo.entity_id)}
                className="no-print mt-2 text-[11px] text-violet-300 hover:underline">
                open the evidence trail ↗
              </button>
            </div>
          </div>
          <div className="text-[10px] text-slate-500 mt-2">{demo.lesson}</div>
        </Card>
      )}

      <div className="grid lg:grid-cols-3 gap-4">
        <Card title="Geographic risk posture" sub="stylized map · node size = 30d alerts · click to drill down">
          <div className="h-72">
            <IndiaMap entities={ents} onPick={openEntity} />
          </div>
          <div className="flex gap-4 text-[10px] text-slate-500 mt-1">
            <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full bg-emerald-400" /> &lt;30</span>
            <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full bg-amber-400" /> 30–59</span>
            <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full bg-red-400" /> ≥60 risk</span>
          </div>
        </Card>
        <Card title="Supervisor activity" sub="audit trail — logins, ingests, actions, config changes" className="lg:col-span-2">
          {aud.length === 0 && (
            <div className="text-[11px] text-slate-500 py-4">
              No supervisory actions recorded yet. Act on a signal from the Supervisory Signals
              page and it will appear here with user and timestamp.
            </div>
          )}
          <div className="divide-y divide-slate-800/70 max-h-72 overflow-y-auto">
            {aud.map((a, i) => (
              <div key={i} className="py-2 flex gap-3 text-[11px]">
                <span className="text-slate-500 font-mono shrink-0">{a.ts}</span>
                <span className="text-violet-300 font-semibold shrink-0 w-28">{a.user}</span>
                <span className="text-slate-300 font-semibold shrink-0">{a.event}</span>
                <span className="text-slate-500 truncate">{a.detail}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
