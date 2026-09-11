import { useEffect, useState } from 'react'
import { get } from '../api.js'
import { Card, Stat, Loading, SevChip, Chip } from '../ui.jsx'
import EvidenceGraph from '../components/EvidenceGraph.jsx'

const KS = [10, 25, 50, 100]

export default function ReviewQueue({ openEntity }) {
  const [k, setK] = useState(25)
  const [d, setD] = useState(null)
  const [graph, setGraph] = useState(null)
  const [graphId, setGraphId] = useState(null)
  useEffect(() => { setD(null); get(`/samples?k=${k}`).then(setD) }, [k])
  if (!d) return <Loading />
  const mk = d.metrics[String(k)] || d.metrics[k] || {}

  async function showGraph(id) {
    setGraphId(id)
    setGraph(null)
    try { setGraph(await get(`/graph/alert/${id}`)) } catch { setGraph({ nodes: [], edges: [] }) }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="mr-auto">
          <div className="text-xl font-bold text-slate-100">Review-sample prioritization</div>
          <div className="text-xs text-slate-400 mt-1 max-w-2xl">
            Which evidence samples an examiner should open first, and why. Every row shows its
            selection reasons and a confidence value; the ranking never hides its inputs.
          </div>
        </div>
        <div className="flex gap-1.5 no-print">
          {KS.map((v) => (
            <button key={v} onClick={() => setK(v)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${
                k === v ? 'bg-violet-600 border-violet-500 text-white'
                        : 'border-slate-700 text-slate-400 hover:text-slate-200'}`}>
              top {v}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Stat label={`Precision @${k}`} value={mk.precision_at_k != null ? `${Math.round(mk.precision_at_k * 100)}%` : '—'}
          color="#34d399" sub="share that truly needs review" />
        <Stat label={`Recall @${k}`} value={mk.recall_at_k != null ? `${Math.round(mk.recall_at_k * 100)}%` : '—'}
          color="#38bdf8" sub={`of ${d.gt_total} ground-truth samples`} />
        <Stat label="Candidates · 30d" value={d.total_candidates.toLocaleString('en-IN')} color="#a78bfa"
          sub="critical/high + campaign alerts" />
        <Stat label="Workload reduction" value={`${Math.round(d.workload_reduction * 100)}%`} color="#fbbf24"
          sub="vs reviewing everything" />
        <Stat label="Showing" value={d.items.length} color="#e2e8f0" sub={`requested top ${k}`} />
      </div>

      <Card title={`Prioritized queue — top ${d.items.length}`}
        sub="score = severity + asset criticality + workflow-evidence gaps + pattern/campaign membership">
        <div className="overflow-x-auto -mx-4 px-4">
          <table className="w-full text-xs min-w-[880px]">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                {['#', 'Alert', 'Entity', 'Severity', 'Category', 'Score', 'Confidence', 'Why selected', ''].map((h) => (
                  <th key={h} className="text-left py-1.5 pr-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.items.map((s, i) => (
                <tr key={s.id} className="border-b border-slate-800/60 align-top">
                  <td className="py-2 pr-3 text-slate-500 font-mono">{i + 1}</td>
                  <td className="py-2 pr-3">
                    <div className="font-mono text-slate-300">{s.id}</div>
                    <div className="text-[10px] text-slate-500">{s.ts.replace('T', ' ').slice(0, 16)}</div>
                  </td>
                  <td className="py-2 pr-3">
                    <button className="text-sky-300 hover:underline font-mono"
                      onClick={() => openEntity(s.entity_id)}>{s.entity_id}</button>
                  </td>
                  <td className="py-2 pr-3"><SevChip sev={s.severity.toLowerCase()} /></td>
                  <td className="py-2 pr-3 text-slate-300">{s.category}</td>
                  <td className="py-2 pr-3 font-bold text-violet-300">{s.score}</td>
                  <td className="py-2 pr-3 text-slate-300">{Math.round(s.confidence * 100)}%</td>
                  <td className="py-2 pr-3">
                    <div className="flex flex-wrap gap-1 max-w-[380px]">
                      {s.reasons.map((r, j) => <Chip key={j} color="#64748b">{r}</Chip>)}
                    </div>
                  </td>
                  <td className="py-2 no-print">
                    <button onClick={() => showGraph(s.id)}
                      className="text-[11px] text-violet-300 hover:underline whitespace-nowrap">
                      evidence graph
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {graphId && (
        <Card title={`Evidence graph — ${graphId}`} sub="CSE → Asset → Alert → Case → Investigation / Escalation → Resolution · dashed red = expected evidence absent"
          right={<button onClick={() => setGraphId(null)} className="text-xs text-slate-400 hover:text-slate-200 no-print">✕ close</button>}>
          {graph ? <EvidenceGraph graph={graph} /> : <Loading />}
        </Card>
      )}

      <div className="text-[11px] text-slate-500 leading-relaxed">
        Ground-truth labels stay hidden from the queue; precision/recall are computed live on
        the Validation page against the seeded examination scenarios. Selection reasons are
        indicators for supervisory review — not confirmed violations.
      </div>
    </div>
  )
}
