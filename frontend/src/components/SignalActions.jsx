import { useState } from 'react'
import { post } from '../api.js'

const ACT = [
  ['reviewed', '✓ Reviewed', '#34d399'],
  ['request_info', '? Request info', '#fbbf24'],
  ['escalate', '↑ Escalate', '#f87171'],
  ['dismiss', '× Dismiss', '#94a3b8'],
]

export default function SignalActions({ sid, current, onChanged }) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  async function act(a) {
    setBusy(true)
    try {
      await post(`/signals/${sid}/action`, { action: a, note })
      setNote('')
      onChanged()
    } finally { setBusy(false) }
  }
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5 no-print">
      {current && (
        <span className="text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider"
          style={{ color: (ACT.find(([k]) => k === current.action) || [,, '#94a3b8'])[2],
                   border: `1px solid ${((ACT.find(([k]) => k === current.action) || [,, '#94a3b8'])[2])}66`,
                   background: '#0f172a' }}>
          {current.action.replace('_', ' ')} · {current.user}
        </span>
      )}
      {ACT.map(([k, label, colr]) => (
        <button key={k} disabled={busy} onClick={() => act(k)}
          className="text-[10px] px-2 py-1 rounded border border-slate-700 hover:border-slate-500 text-slate-300 disabled:opacity-40"
          style={current?.action === k ? { borderColor: colr, color: colr } : {}}>
          {label}
        </button>
      ))}
      <input value={note} onChange={(e) => setNote(e.target.value)}
        placeholder="examiner note (optional)"
        className="text-[10px] bg-slate-900 border border-slate-700 rounded px-2 py-1 w-44 text-slate-300" />
    </div>
  )
}
