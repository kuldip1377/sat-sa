import { useEffect, useState } from 'react'
import { get } from '../api.js'
import { Card, Loading, Chip, SevChip } from '../ui.jsx'
import EvidenceGraph from '../components/EvidenceGraph.jsx'

export default function EvidenceExplorer({ openEntity }) {
  const [ents, setEnts] = useState([])
  const [sigs, setSigs] = useState([])
  const [eid, setEid] = useState('')
  const [sid, setSid] = useState('')
  const [aid, setAid] = useState('')
  const [g, setG] = useState(null)
  const [title, setTitle] = useState('')

  useEffect(() => {
    get('/entities').then((e) => { setEnts(e); setEid(e[0].id) })
    get('/signals').then((s) => setSigs(s.signals))
  }, [])
  const list = sigs.filter((s) => !eid || s.entity_id === eid)

  async function showFinding(id) {
    setSid(id)
    const sig = sigs.find((s) => s.id === id)
    setTitle(`Finding ${id} — ${sig ? sig.title : ''}`)
    setG(null)
    try { setG(await get(`/graph/finding/${id}`)) } catch { setG({ nodes: [], edges: [] }) }
  }
  async function showAlert() {
    if (!aid) return
    setTitle(`Alert ${aid}`)
    setSid('')
    setG(null)
    try { setG(await get(`/graph/alert/${aid.trim()}`)) }
    catch { setG({ nodes: [], edges: [] }) }
  }

  return (
    <div className="space-y-4">
      <div>
        <div className="text-xl font-bold text-slate-100">Evidence graph explorer</div>
        <div className="text-xs text-slate-400 mt-1 max-w-3xl">
          CSE → Asset → Alert → Case → Investigation → Escalation → Resolution. Every node is a
          real database record (click to inspect the stored row); dashed red nodes are
          expected-but-absent evidence — the negative-space view. No relationship is inferred
          or fabricated.
        </div>
      </div>

      <Card>
        <div className="flex flex-wrap gap-3 items-end no-print">
          <label className="block">
            <span className="text-[10px] text-slate-400">CSE</span>
            <select value={eid} onChange={(e) => { setEid(e.target.value); setSid(''); setG(null) }}
              className="block mt-0.5 rounded bg-slate-950 border border-slate-700 px-2 py-1.5 text-xs text-slate-200 min-w-[200px]">
              {ents.map((e) => <option key={e.id} value={e.id}>{e.id} — {e.name}</option>)}
            </select>
          </label>
          <label className="block flex-1 min-w-[260px]">
            <span className="text-[10px] text-slate-400">Finding</span>
            <select value={sid} onChange={(e) => e.target.value && showFinding(e.target.value)}
              className="block mt-0.5 rounded bg-slate-950 border border-slate-700 px-2 py-1.5 text-xs text-slate-200 w-full">
              <option value="">select a finding on {eid}…</option>
              {list.map((s) => (
                <option key={s.id} value={s.id}>{s.id} · {s.title}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-[10px] text-slate-400">…or jump to an alert ID</span>
            <span className="flex mt-0.5 gap-1.5">
              <input value={aid} onChange={(e) => setAid(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && showAlert()}
                placeholder="A-BNK-02-0001"
                className="rounded bg-slate-950 border border-slate-700 px-2 py-1.5 text-xs text-slate-200 w-44 font-mono" />
              <button onClick={showAlert}
                className="rounded bg-violet-600 hover:bg-violet-500 px-3 py-1.5 text-[11px] font-semibold text-white">
                trace
              </button>
            </span>
          </label>
        </div>
      </Card>

      {!g && (
        <Card title="Findings on this CSE" sub="click any row to render its evidence chain">
          <div className="space-y-1.5">
            {list.map((s) => (
              <button key={s.id} onClick={() => showFinding(s.id)}
                className="w-full flex items-center gap-2 text-left rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 hover:border-violet-700">
                <SevChip sev={s.severity} />
                <span className="text-xs font-semibold text-slate-200">{s.title}</span>
                <span className="text-[10px] text-slate-500 ml-auto font-mono">{s.id}</span>
              </button>
            ))}
            {list.length === 0 && (
              <div className="text-sm text-emerald-400 py-3">
                No active findings on this CSE — nothing to trace.
              </div>
            )}
          </div>
        </Card>
      )}

      {g && (
        <Card title={title}
          sub={sid ? 'finding evidence chain — sample records' : 'single-alert evidence chain'}
          right={
            <span className="flex gap-2 no-print">
              {eid && <button onClick={() => openEntity(eid)} className="text-[11px] text-sky-300 hover:underline">open CSE ↗</button>}
              <button onClick={() => { setG(null); setSid('') }} className="text-xs text-slate-400 hover:text-slate-200">✕ close</button>
            </span>
          }>
          {g.pattern && (
            <div className="mb-2 flex items-center gap-2">
              <Chip color="#fbbf24">signature ×{g.pattern.count}</Chip>
              <span className="text-[11px] text-slate-400">{g.pattern.signature}</span>
            </div>
          )}
          <EvidenceGraph graph={g} height={420} />
        </Card>
      )}
    </div>
  )
}
