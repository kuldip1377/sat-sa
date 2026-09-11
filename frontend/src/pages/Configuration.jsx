import { useCallback, useEffect, useState } from 'react'
import { get, put } from '../api.js'
import { Card, Loading, Chip } from '../ui.jsx'

const WEIGHTS = [
  ['w_exec', 'Execution Gap'], ['w_neg', 'Negative Space'], ['w_anom', 'Anomaly'],
  ['w_peer', 'Peer Deviation'], ['w_crit', 'Criticality'], ['w_conf', 'Evidence Confidence'],
]
const BANDS = [
  ['attn_watch', 'Watch from'], ['attn_attention', 'Attention from'],
  ['attn_high', 'High Priority from'], ['attn_critical', 'Critical Attention from'],
]
const THRESHOLDS = [
  ['sla', 'SLA breach rate'], ['sc', 'Silent-close rate'], ['silent_days', 'Zero-alert days'],
  ['gap_days', 'Missing submission days'], ['noesc_crit', 'Min criticals (escalation check)'],
  ['backlog_slope', 'Backlog slope /day'], ['backlog_min', 'Min open backlog'],
  ['mttr_x', 'MTTR × peer'], ['maha', 'Mahalanobis χ²'], ['spike_z', 'Volume spike z'],
  ['season_z', 'Pattern break z (extreme)'], ['season_count', '…min extreme days'],
  ['season_z2', 'Pattern break z (sustained)'], ['season_count2', '…min sustained days'],
  ['camp_tv', 'Campaign TV distance'], ['blind_min', 'Min silent critical assets'],
  ['no_inv_rate', 'Uninvestigated-case rate'], ['pattern_min', 'Min pattern repetitions'],
]

export default function Configuration() {
  const [cfg, setCfg] = useState(null)
  const [defaults, setDefaults] = useState(null)
  const [top, setTop] = useState([])
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  const reload = useCallback(() => {
    get('/config').then((r) => { setCfg({ ...r.config }); if (!defaults) setDefaults({ ...r.config }) })
    get('/entities').then((e) => setTop(e.slice(0, 3)))
  }, [defaults])
  useEffect(() => { reload() }, [reload])
  if (!cfg) return <Loading />

  const wSum = WEIGHTS.reduce((s, [k]) => s + Number(cfg[k] || 0), 0)
  const set = (k, v) => setCfg({ ...cfg, [k]: Number(v) })

  async function save() {
    setBusy(true); setMsg(null)
    try {
      const patch = {}
      Object.keys(cfg).forEach((k) => { patch[k] = Number(cfg[k]) })
      const r = await put('/config', patch)
      setCfg({ ...r.config })
      const e = await get('/entities')
      const before = top.map((t) => `${t.id} ${t.score}`).join(' · ')
      const after = e.slice(0, 3).map((t) => `${t.id} ${t.score}`).join(' · ')
      setTop(e.slice(0, 3))
      setMsg(`saved & recomputed · recorded in audit trail\nranking before: ${before || '—'}\nranking after:  ${after}`)
    } catch (err) { setMsg('error: ' + err.message) }
    finally { setBusy(false) }
  }

  function normalize() {
    const next = { ...cfg }
    WEIGHTS.forEach(([k]) => { next[k] = Math.round(Number(cfg[k]) / wSum * 100) })
    next[WEIGHTS[0][0]] += 100 - WEIGHTS.reduce((s, [k]) => s + next[k], 0)
    setCfg(next)
  }

  return (
    <div className="space-y-4">
      <div>
        <div className="text-xl font-bold text-slate-100">Configuration</div>
        <div className="text-xs text-slate-400 mt-1 max-w-3xl">
          Detection thresholds and score weights are deliberately separate controls. Every
          save recomputes all analytics and is written to the audit trail with user and
          timestamp — no silent parameter changes.
        </div>
      </div>

      <Card title="Score weights" sub="Supervisory Attention Score composition — must total 100"
        right={
          <div className="flex items-center gap-2 no-print">
            <Chip color={Math.abs(wSum - 100) < 0.5 ? '#34d399' : '#f87171'}>Σ = {wSum}</Chip>
            <button onClick={normalize} className="text-[11px] text-sky-300 border border-sky-800/60 rounded-full px-2.5 py-1 hover:bg-sky-900/30">
              normalize to 100
            </button>
          </div>
        }>
        <div className="grid md:grid-cols-2 gap-x-6 gap-y-3">
          {WEIGHTS.map(([k, label]) => (
            <label key={k} className="block">
              <div className="flex justify-between text-[11px] mb-1">
                <span className="text-slate-300">{label}</span>
                <span className="font-mono text-violet-300">{cfg[k]}</span>
              </div>
              <input type="range" min="0" max="60" step="1" value={cfg[k]}
                onChange={(e) => set(k, e.target.value)} className="w-full accent-violet-500" />
            </label>
          ))}
        </div>
        <div className="text-[10px] text-slate-500 mt-3">
          Defaults: {WEIGHTS.map(([k]) => `${k.replace('w_', '')} ${defaults[k]}`).join(' · ')}
        </div>
      </Card>

      <Card title="Attention score bands" sub="score → supervisory category (0–100)">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {BANDS.map(([k, label]) => (
            <label key={k} className="block">
              <span className="text-[10px] text-slate-400">{label}</span>
              <input type="number" min="0" max="100" value={cfg[k]}
                onChange={(e) => set(k, e.target.value)}
                className="w-full mt-0.5 rounded bg-slate-950 border border-slate-700 px-2 py-1 text-xs text-slate-200" />
            </label>
          ))}
        </div>
        <div className="text-[10px] text-slate-500 mt-2">
          Normal &lt; {cfg.attn_watch} · Watch &lt; {cfg.attn_attention} · Attention &lt; {cfg.attn_high} ·
          High Priority &lt; {cfg.attn_critical} · Critical Attention above.
        </div>
      </Card>

      <Card title="Detection thresholds" sub="rule-engine triggers — changes here alter which signals fire, not how they are weighted">
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
          {THRESHOLDS.map(([k, label]) => (
            <label key={k} className="block">
              <span className="text-[10px] text-slate-400">{label}</span>
              <input type="number" step="0.05" value={cfg[k]}
                onChange={(e) => set(k, e.target.value)}
                className="w-full mt-0.5 rounded bg-slate-950 border border-slate-700 px-2 py-1 text-xs text-slate-200" />
            </label>
          ))}
        </div>
      </Card>

      <div className="no-print flex flex-wrap items-center gap-3">
        <button onClick={save} disabled={busy}
          className="rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 px-4 py-2 text-xs font-semibold text-white">
          {busy ? 'recomputing…' : 'save & recompute'}
        </button>
        <button onClick={() => setCfg({ ...defaults })}
          className="rounded-lg border border-slate-700 px-4 py-2 text-xs text-slate-300 hover:bg-slate-800">
          reset to defaults
        </button>
        {msg && <pre className="text-[11px] text-emerald-300 whitespace-pre-wrap">{msg}</pre>}
      </div>

      <div className="text-[11px] text-slate-500">
        Role requirement: administrator or supervisor. Analysts and auditors have read-only
        access; auditors cannot modify configuration.
      </div>
    </div>
  )
}
