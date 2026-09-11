import { useMemo, useState } from 'react'

const LAYERS = ['CSE', 'Asset', 'Alert', 'Case', 'Investigation', 'Escalation', 'Resolution']
const TYPE_COLOR = {
  CSE: '#38bdf8', Asset: '#34d399', Alert: '#fb923c', Case: '#a78bfa',
  Investigation: '#22d3ee', Escalation: '#f472b6', Resolution: '#94a3b8',
}
const COL_W = 190, NODE_W = 168, NODE_H = 44, GAP = 14

export default function EvidenceGraph({ graph, height = 340 }) {
  const [sel, setSel] = useState(null)
  const layout = useMemo(() => {
    if (!graph) return null
    const pos = {}
    LAYERS.forEach((t, li) => {
      const ns = graph.nodes.filter((n) => n.type === t)
      ns.forEach((n, i) => { pos[n.id] = { x: 12 + li * COL_W, y: 16 + i * (NODE_H + GAP), n } })
    })
    const maxY = Math.max(...Object.values(pos).map((p) => p.y + NODE_H), 120)
    return { pos, w: 12 + LAYERS.length * COL_W, h: maxY + 12 }
  }, [graph])
  if (!graph || !layout) return null
  const { pos, w, h } = layout

  return (
    <div className="flex flex-col lg:flex-row gap-3">
      <div className="overflow-auto rounded-lg border border-slate-800 bg-slate-950/60" style={{ maxHeight: height }}>
        <svg width={w} height={Math.max(h, height - 20)} className="block">
          {LAYERS.map((t, li) => (
            <text key={t} x={12 + li * COL_W} y={10} fill="#475569" fontSize={9}
              style={{ textTransform: 'uppercase', letterSpacing: 1 }}>{t}</text>
          ))}
          {graph.edges.map((e, i) => {
            const a = pos[e.from_], b = pos[e.to]
            if (!a || !b) return null
            const x1 = a.x + NODE_W, y1 = a.y + NODE_H / 2
            const x2 = b.x, y2 = b.y + NODE_H / 2
            const mx = (x1 + x2) / 2
            return (
              <g key={i}>
                <path d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} fill="none"
                  stroke={b.n.missing ? '#f8717188' : '#33415599'} strokeWidth={1.4}
                  strokeDasharray={b.n.missing ? '5 4' : undefined} />
                <text x={mx - 40} y={(y1 + y2) / 2 - 3} fill="#475569" fontSize={8}>
                  {e.label}
                </text>
              </g>
            )
          })}
          {Object.values(pos).map((p) => {
            const c = TYPE_COLOR[p.n.type] || '#94a3b8'
            const active = sel && sel.id === p.n.id
            return (
              <g key={p.n.id} onClick={() => setSel(p.n)} style={{ cursor: 'pointer' }}>
                <rect x={p.x} y={p.y} width={NODE_W} height={NODE_H} rx={8}
                  fill={p.n.missing ? '#7f1d1d22' : '#0f172a'}
                  stroke={active ? '#e2e8f0' : p.n.missing ? '#f87171' : c}
                  strokeWidth={active ? 2 : 1.4}
                  strokeDasharray={p.n.missing ? '5 4' : undefined} />
                <text x={p.x + 9} y={p.y + 17} fill={p.n.missing ? '#fca5a5' : '#e2e8f0'}
                  fontSize={10.5} fontWeight={600}>
                  {(p.n.missing ? '⚠ ' : '') + p.n.label.slice(0, 26)}
                </text>
                <text x={p.x + 9} y={p.y + 32} fill="#64748b" fontSize={9}>
                  {p.n.ts ? String(p.n.ts).replace('T', ' ').slice(0, 19) : p.n.id.slice(0, 24)}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
      <div className="w-full lg:w-72 shrink-0">
        {sel ? (
          <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase"
                style={{ background: TYPE_COLOR[sel.type] + '22', color: TYPE_COLOR[sel.type] }}>
                {sel.type}
              </span>
              <span className="font-mono text-[10px] text-slate-500">{sel.id}</span>
            </div>
            {sel.missing && (
              <div className="text-[11px] text-red-400 mb-2">
                Expected evidence record — not present in the submission. Shown as a
                supervisory indicator, never as a confirmed violation.
              </div>
            )}
            {sel.ts && <div className="text-[11px] text-slate-400 mb-2">timestamp: {String(sel.ts).replace('T', ' ')}</div>}
            <div className="space-y-1 max-h-56 overflow-auto">
              {Object.entries(sel.meta || {}).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2 text-[11px] border-b border-slate-800/60 pb-0.5">
                  <span className="text-slate-500">{k}</span>
                  <span className="text-slate-300 font-mono text-right break-all">{String(v)}</span>
                </div>
              ))}
              {Object.keys(sel.meta || {}).length === 0 &&
                <div className="text-[11px] text-slate-500">No stored record (virtual node).</div>}
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-slate-800 p-3 text-[11px] text-slate-500">
            Click any node to inspect the underlying database record. Dashed red nodes are
            <span className="text-red-400"> expected-but-absent evidence</span> — the
            negative-space view of this chain.
          </div>
        )}
      </div>
    </div>
  )
}
