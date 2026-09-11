import { useCallback, useEffect, useState } from 'react'
import { get, put } from '../api.js'
import { Card, Loading, SevChip, Chip, ExplainBtn } from '../ui.jsx'
import SignalActions from '../components/SignalActions.jsx'

const LABELS = {
  sla: 'SLA breach rate trigger', sc: 'Silent-close rate trigger',
  silent_days: 'Zero-alert days (silent SOC)', gap_days: 'Missing submission days',
  noesc_crit: 'Min criticals for escalation check', backlog_slope: 'Backlog slope /day',
  backlog_min: 'Min open backlog', mttr_x: 'MTTR × peer multiplier',
  maha: 'Mahalanobis χ² critical', spike_z: 'Volume spike z',
  season_z: 'Pattern break z (extreme)', season_count: '…min extreme days',
  season_z2: 'Pattern break z (sustained)', season_count2: '…min sustained days',
  camp_tv: 'Campaign TV distance',
}

export default function Signals({ openEntity }) {
  const [d, setD] = useState(null)
  const [cfg, setCfg] = useState(null)
  const [cat, setCat] = useState('')
  const [sev, setSev] = useState('')
  const [meth, setMeth] = useState('')
  const [showCfg, setShowCfg] = useState(false)
  const [saved, setSaved] = useState(null)

  const reload = useCallback(() => { get('/signals').then(setD) }, [])
  useEffect(() => { reload(); get('/config').then((r) => setCfg(r.config)) }, [reload])
  if (!d || !cfg) return <Loading />

  const rows = d.signals.filter((s) =>
    (!cat || s.category === cat) && (!sev || s.severity === sev) &&
    (!meth || (s.method || '').startsWith(meth)))
  const methods = [...new Set(d.signals.map((s) => s.method).filter(Boolean))]

  async function save() {
    const patch = {}
    Object.keys(cfg).forEach((k) => { patch[k] = Number(cfg[k]) })
    const r = await put('/config', patch)
    setCfg(r.config)
    setSaved('thresholds applied — analytics recomputed')
    reload()
    setTimeout(() => setSaved(null), 3000)
  }

  return (
    <div className="space-y-4">
      <Card title="Rule engine configuration" sub="live thresholds — changes recompute every detector and the eval board"
        right={
          <button onClick={() => setShowCfg(!showCfg)}
            className="text-[11px] text-violet-300 border border-violet-700/60 rounded-full px-3 py-1 hover:bg-violet-900/30">
            {showCfg ? 'hide' : '⚙ tune thresholds'}
          </button>
        }>
        {showCfg ? (
          <div>
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
              {Object.entries(cfg).map(([k, v]) => (
                <label key={k} className="block">
                  <span className="text-[10px] text-slate-400">{LABELS[k] || k}</span>
                  <input type="number" step="0.05" value={v}
                    onChange={(e) => setCfg({ ...cfg, [k]: e.target.value })}
                    className="w-full mt-0.5 rounded bg-slate-950 border border-slate-700 px-2 py-1 text-xs text-slate-200" />
                </label>
              ))}
            </div>
            <div className="flex items-center gap-3 mt-3">
              <button onClick={save}
                className="rounded-lg bg-violet-600 hover:bg-violet-500 px-4 py-1.5 text-xs font-semibold text-white">
                Apply & recompute
              </button>
              {saved && <span className="text-[11px] text-emerald-400">{saved}</span>}
            </div>
          </div>
        ) : (
          <div className="text-[11px] text-slate-500">
            {Object.entries(cfg).map(([k, v]) => `${k}=${v}`).join(' · ')}
          </div>
        )}
      </Card>

      <Card title="Supervisory signals — prioritized findings"
        sub="every signal carries observed vs benchmark, evidence, explanation and supervisor actions">
        <div className="flex flex-wrap gap-2 mb-4">
          <select value={cat} onChange={(e) => setCat(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200">
            <option value="">All capabilities</option>
            {d.categories.map((c) => <option key={c}>{c}</option>)}
          </select>
          <select value={sev} onChange={(e) => setSev(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200">
            <option value="">All severities</option>
            {['critical', 'high', 'medium', 'low'].map((s) => <option key={s}>{s}</option>)}
          </select>
          <select value={meth} onChange={(e) => setMeth(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200">
            <option value="">All detection methods</option>
            {methods.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <span className="text-xs text-slate-500 self-center ml-auto mr-2">{rows.length} shown</span>
          <a href="/api/signals/export" download
            className="self-center rounded-lg bg-emerald-700 hover:bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white">
             Export CSV
          </a>
        </div>

        <div className="space-y-3">
          {rows.map((s) => (
            <div key={s.id} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3.5">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-[10px] text-slate-500">{s.id}</span>
                <SevChip sev={s.severity} />
                <Chip color="#a78bfa">{s.category}</Chip>
                {s.method && (
                  <span title={s.method}>
                    <Chip color="#22d3ee">{s.method.split(' — ')[0]}</Chip>
                  </span>
                )}
                <button onClick={() => openEntity(s.entity_id)}
                  className="text-xs font-semibold text-sky-300 hover:underline">
                  {s.entity_id} ↗
                </button>
                <span className="text-sm font-semibold text-slate-100 ml-1">{s.title}</span>
              </div>
              {s.method && <div className="text-[10px] text-cyan-400/70 mt-1">method: {s.method}</div>}
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">{s.detail}</p>
              <div className="flex gap-4 mt-2 text-[11px]">
                <span className="text-slate-500">observed: <b className="text-slate-200">{s.observed}</b></span>
                <span className="text-slate-500">benchmark: <b className="text-slate-200">{s.benchmark}</b></span>
              </div>
              <details className="mt-2">
                <summary className="text-[11px] text-violet-300">examine evidence ▾</summary>
                <pre className="mt-1.5 text-[11px] text-slate-300 bg-slate-900 border border-slate-800 rounded p-2 overflow-x-auto">
                  {JSON.stringify(s.evidence, null, 2)}
                </pre>
              </details>
              <ExplainBtn sid={s.id} />
              <SignalActions sid={s.id} current={s.action} onChanged={reload} />
            </div>
          ))}
          {rows.length === 0 && <div className="text-sm text-slate-500 py-6">No signals match the current filter.</div>}
        </div>
      </Card>
    </div>
  )
}
