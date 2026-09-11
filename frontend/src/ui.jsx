import { useState } from 'react'

export const SEV = { critical: '#f87171', high: '#fb923c', medium: '#facc15', low: '#94a3b8' }

export function ExplainBtn({ sid }) {
  const [txt, setTxt] = useState(null)
  const [busy, setBusy] = useState(false)
  async function go() {
    if (txt) { setTxt(null); return }
    setBusy(true)
    try { setTxt(await fetch('/api/explain/' + sid).then((r) => r.json())) } finally { setBusy(false) }
  }
  return (
    <div className="mt-2 no-print">
      <button onClick={go} className="text-[11px] text-sky-300 hover:underline">
        {txt ? 'hide explanation' : busy ? 'explaining…' : '✦ structured explanation'}
      </button>
      {txt && (
        <div className="mt-1.5 rounded border border-sky-800/50 bg-sky-900/10 p-2.5 text-[11px] text-sky-100 leading-relaxed space-y-2">
          <div><span className="font-bold text-sky-300 uppercase tracking-wider text-[9px]">What</span>
            <div>{txt.what}</div></div>
          <div><span className="font-bold text-sky-300 uppercase tracking-wider text-[9px]">Why it was raised</span>
            <div className="text-sky-200/90">{txt.why}</div></div>
          <div><span className="font-bold text-sky-300 uppercase tracking-wider text-[9px]">Evidence</span>
            <div className="text-sky-200/90">Source: {txt.evidence?.[0]?.source}</div>
            <div className="text-sky-400/80">
              {txt.evidence?.[0]?.references?.map((r) => `${r.table} → ${r.ref}`).join(' · ')}
            </div>
            <details className="mt-1">
              <summary className="text-[10px] text-sky-400 cursor-pointer">raw evidence values</summary>
              <pre className="mt-1 text-[10px] text-sky-200/80 bg-slate-950/60 rounded p-1.5 overflow-x-auto">
                {JSON.stringify({ observed: txt.evidence?.[0]?.observed,
                  benchmark: txt.evidence?.[0]?.benchmark, ...txt.evidence?.[0]?.raw }, null, 1)}
              </pre>
            </details>
          </div>
          <div><span className="font-bold text-sky-300 uppercase tracking-wider text-[9px]">How unusual</span>
            <div className="text-sky-200/90">Observed {txt.how_unusual?.observed} vs {txt.how_unusual?.benchmark}
              {' '}· peer group “{txt.how_unusual?.peer_group}” · attention {txt.how_unusual?.attention?.score}/100
              ({txt.how_unusual?.attention?.label})</div></div>
          <div><span className="font-bold text-sky-300 uppercase tracking-wider text-[9px]">Confidence</span>
            <div className="flex items-center gap-2">
              <div className="w-24 h-1.5 rounded bg-slate-800 overflow-hidden">
                <div className="h-full bg-sky-400" style={{ width: `${(txt.confidence?.score || 0) * 100}%` }} />
              </div>
              <span className="text-sky-200">{Math.round((txt.confidence?.score || 0) * 100)}% · {txt.confidence?.interpretation}</span>
            </div>
            <div className="text-[10px] text-sky-400/70 mt-0.5">{txt.confidence?.basis}</div></div>
          <div><span className="font-bold text-sky-300 uppercase tracking-wider text-[9px]">What to review</span>
            <ul className="list-disc list-inside text-sky-200/90">
              {(txt.what_to_review || []).map((r, i) => <li key={i}>{r}</li>)}
            </ul></div>
          <div className="text-[10px] text-sky-500/80 border-t border-sky-800/40 pt-1.5">
            {txt.disclaimer}<br />engine: {txt.engine}{txt.narrative_engine ? ` · narrative: ${txt.narrative_engine}` : ''}
          </div>
        </div>
      )}
    </div>
  )
}

export function SevChip({ sev }) {
  const c = SEV[sev] || '#94a3b8'
  return (
    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider whitespace-nowrap"
      style={{ background: c + '1f', color: c, border: `1px solid ${c}66` }}>
      {sev}
    </span>
  )
}

export function Chip({ color = '#38bdf8', children }) {
  return (
    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider whitespace-nowrap"
      style={{ background: color + '1a', color, border: `1px solid ${color}55` }}>
      {children}
    </span>
  )
}

export function Stat({ label, value, sub, color = '#e2e8f0' }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
      <div className="text-[11px] uppercase tracking-wider text-slate-400">{label}</div>
      <div className="text-2xl font-bold mt-1" style={{ color }}>{value}</div>
      {sub && <div className="text-[11px] text-slate-500 mt-0.5">{sub}</div>}
    </div>
  )
}

export function Card({ title, sub, right, children, className = '' }) {
  return (
    <div className={`rounded-xl border border-slate-800 bg-slate-900/60 p-4 ${className}`}>
      {(title || right) && (
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="text-sm font-semibold text-slate-200">{title}</div>
            {sub && <div className="text-[11px] text-slate-500 mt-0.5">{sub}</div>}
          </div>
          {right}
        </div>
      )}
      {children}
    </div>
  )
}

export function ScoreBadge({ score }) {
  const c = score >= 60 ? '#f87171' : score >= 30 ? '#fbbf24' : '#34d399'
  return (
    <span className="inline-flex items-center gap-1.5 font-bold text-sm" style={{ color: c }}>
      <span className="w-2 h-2 rounded-full" style={{ background: c }} />
      {score}
    </span>
  )
}

export function ScoreBar({ score }) {
  const c = score >= 60 ? '#f87171' : score >= 30 ? '#fbbf24' : '#34d399'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded bg-slate-800 overflow-hidden">
        <div className="h-full rounded" style={{ width: `${score}%`, background: c }} />
      </div>
      <span className="text-xs font-bold" style={{ color: c }}>{score}</span>
    </div>
  )
}

export function Spark({ data = [], color = '#38bdf8', w = 88, h = 26 }) {
  if (!data.length) return null
  const max = Math.max(...data, 1), min = Math.min(...data)
  const pts = data.map((v, i) =>
    `${(i / (data.length - 1)) * (w - 2) + 1},${h - 2 - ((v - min) / Math.max(max - min, 1)) * (h - 4)}`
  ).join(' ')
  return (
    <svg width={w} height={h} className="shrink-0">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  )
}

export function Loading() {
  return <div className="p-10 text-slate-500 text-sm animate-pulse">Loading SAT-SA analytics…</div>
}

export const AXIS = { stroke: '#475569', fontSize: 10, tickLine: false, axisLine: false }
export const TT_STYLE = {
  background: '#0f172a', border: '1px solid #334155', borderRadius: 8,
  fontSize: 12, color: '#e2e8f0',
}
