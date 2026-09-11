import { useEffect, useState } from 'react'
import { get } from '../api.js'
import { Card, Loading, Chip, ScoreBadge } from '../ui.jsx'

const STATUS_COLOR = {
  NEW: '#38bdf8', PERSISTENT: '#fbbf24', WORSENING: '#f87171',
  IMPROVING: '#34d399', RESOLVED: '#34d399', RETURNED: '#fb923c',
}

function Delta({ label, v, invert }) {
  if (v == null) return <span className="text-[10px] text-slate-600">{label} —</span>
  const bad = invert ? v < 0 : v > 0
  const c = Math.abs(v) < 5 ? '#94a3b8' : bad ? '#f87171' : '#34d399'
  return (
    <span className="text-[10px] whitespace-nowrap" style={{ color: c }}>
      {label} {v > 0 ? '+' : ''}{v}%
    </span>
  )
}

export default function Assessments({ openEntity }) {
  const [d, setD] = useState(null)
  const [p, setP] = useState(null)
  useEffect(() => {
    get('/assessments').then(setD).catch(() => setD({ error: true }))
    get('/peers').then(setP)
  }, [])
  if (!d) return <Loading />
  if (d.error) return <div className="p-10 text-red-400">Backend unreachable.</div>

  return (
    <div className="space-y-4">
      <div>
        <div className="text-xl font-bold text-slate-100">Assessment-to-assessment comparison</div>
        <div className="text-xs text-slate-400 mt-1 max-w-3xl">
          Four 30-day assessment windows (oldest → latest). Findings are classified
          NEW · PERSISTENT · RETURNED · WORSENING · IMPROVING · RESOLVED, with metric deltas
          between the first and latest window. Sustained concerns generate a review
          recommendation for the human supervisor.
        </div>
      </div>

      <Card title="Longitudinal matrix" sub="attention score by window · issue-family status · deltas (W1 → W4)">
        <div className="overflow-x-auto -mx-4 px-4">
          <table className="w-full text-xs min-w-[900px]">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                <th className="text-left py-1.5 pr-3">CSE</th>
                <th className="text-left py-1.5 pr-3">W1 (90–120d)</th>
                <th className="text-left py-1.5 pr-3">W2 (60–90d)</th>
                <th className="text-left py-1.5 pr-3">W3 (30–60d)</th>
                <th className="text-left py-1.5 pr-3">W4 (0–30d)</th>
                <th className="text-left py-1.5 pr-3">Finding status</th>
                <th className="text-left py-1.5 pr-3">Deltas</th>
                <th className="text-left py-1.5">Concern</th>
              </tr>
            </thead>
            <tbody>
              {d.assessments.map((a) => (
                <tr key={a.id} className="border-b border-slate-800/60 align-top">
                  <td className="py-2 pr-3">
                    <button className="text-sky-300 hover:underline font-semibold"
                      onClick={() => openEntity(a.id)}>{a.id}</button>
                    <div className="text-[10px] text-slate-500">{a.name}</div>
                  </td>
                  {a.windows.map((w, i) => (
                    <td key={i} className="py-2 pr-3">
                      <span className={`font-bold ${w >= 60 ? 'text-red-400' : w >= 30 ? 'text-amber-400' : 'text-emerald-400'}`}>{w}</span>
                    </td>
                  ))}
                  <td className="py-2 pr-3">
                    <div className="flex flex-wrap gap-1 max-w-[260px]">
                      {a.classes.length === 0 && <span className="text-emerald-400">clear</span>}
                      {a.classes.map((cl) => (
                        <Chip key={cl.family} color={STATUS_COLOR[cl.status]}>
                          {cl.family} · {cl.status}
                        </Chip>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 pr-3">
                    <div className="flex flex-col gap-0.5">
                      <Delta label="MTTR" v={a.deltas.mttr} />
                      <Delta label="Esc.rate" v={a.deltas.esc_rate} invert />
                      <Delta label="Backlog" v={a.deltas.backlog} />
                    </div>
                  </td>
                  <td className="py-2">
                    {a.persistent_concern
                      ? <Chip color="#f87171">Persistent supervisory concern</Chip>
                      : <span className="text-[10px] text-slate-600">—</span>}
                    {a.review_trigger.recommended && (
                      <div className="text-[10px] text-amber-300 mt-1 max-w-[200px]">
                        ⚑ {a.review_trigger.note}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {p && (
        <Card title="Peer benchmarking dashboard"
          sub={p.note}
          right={<Chip color="#a78bfa">{p.groups.length} peer groups</Chip>}>
          <div className="overflow-x-auto -mx-4 px-4">
            <table className="w-full text-[11px] min-w-[980px]">
              <thead>
                <tr className="text-[9px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                  <th className="text-left py-1.5 pr-2">CSE</th>
                  <th className="text-left py-1.5 pr-2">Peer group</th>
                  {Object.keys(p.rows[0].cells).map((m) => (
                    <th key={m} className="text-right py-1.5 px-1.5">{m}</th>
                  ))}
                  <th className="text-right py-1.5 px-1.5">Investigation median (min)</th>
                </tr>
              </thead>
              <tbody>
                {p.rows.map((r) => (
                  <tr key={r.id} className="border-b border-slate-800/60">
                    <td className="py-1.5 pr-2 font-mono text-slate-300">{r.id}</td>
                    <td className="py-1.5 pr-2 text-slate-500">{r.group} ({r.members})</td>
                    {Object.entries(r.cells).map(([m, c]) => (
                      <td key={m} className="py-1.5 px-1.5 text-right">
                        <span className="text-slate-200 font-semibold">{c.entity}</span>
                        <span className="text-slate-600"> / {c.median}</span>
                        {c.deviation != null && Math.abs(c.deviation) >= 0.5 && (
                          <span className="ml-1" style={{ color: c.deviation > 0 ? '#f87171' : '#38bdf8' }}>
                            {c.deviation > 0 ? '▲' : '▼'}
                          </span>
                        )}
                      </td>
                    ))}
                    <td className="py-1.5 px-1.5 text-right text-slate-300">
                      {r.inv_median != null ? Math.round(r.inv_median) : '—'}
                      <span className="text-slate-600"> / {r.group_inv_median ?? '—'}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-[10px] text-slate-500 mt-2">
            entity / group median · ▲▼ marks significant deviation (≥50%) from comparable
            entities — an examination prompt, not a judgement.
          </div>
        </Card>
      )}
    </div>
  )
}
