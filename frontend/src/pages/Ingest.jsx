import { useEffect, useRef, useState } from 'react'
import { get, post, postForm } from '../api.js'
import { Card, Loading, Chip } from '../ui.jsx'

export default function Ingest() {
  const [schema, setSchema] = useState(null)
  const [msg, setMsg] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [resetMsg, setResetMsg] = useState(null)
  const fileRef = useRef(null)
  useEffect(() => { get('/schema').then(setSchema) }, [])
  if (!schema) return <Loading />

  async function upload(ev) {
    ev.preventDefault()
    setMsg(null); setErr(null)
    const f = fileRef.current?.files?.[0]
    if (!f) { setErr('Choose a CSV file first.'); return }
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', f)
      const r = await postForm('/ingest', fd)
      setMsg(r)
    } catch (e) {
      setErr(String(e.message || e))
    } finally { setBusy(false) }
  }

  return (
    <div className="grid lg:grid-cols-2 gap-4 items-start">
      <Card title="Structured data submission" sub="CSE SOC → NCIIPC periodic submission channel">
        <p className="text-xs text-slate-400 leading-relaxed">
          SAT-SA ingests periodic structured submissions of SOC operational records
          (alert metadata, case management, investigation workflow, escalations,
          disposition & closure, asset inventory). In production this arrives as
          CSV / JSON / DB export over the secure offline transfer; the same pipeline
          is exposed here as an upload.
        </p>
        <div className="flex gap-2 mt-3 flex-wrap">
          <Chip color="#34d399">CSV</Chip><Chip color="#34d399">JSON</Chip>
          <Chip color="#34d399">DB export</Chip><Chip color="#34d399">API</Chip>
          {schema.signing_enabled
            ? <Chip color="#f87171">HMAC signing enforced</Chip>
            : <Chip color="#64748b">HMAC signing: optional (set SATSA_SIGNING_KEY)</Chip>}
        </div>
        <div className="mt-4 text-[11px] uppercase tracking-wider text-slate-400 mb-2">
          Expected daily-record schema
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[11px] text-slate-300">
          {schema.columns.map((c) => (
            <div key={c} className="flex items-center gap-1.5">
              <span className="w-1 h-1 rounded-full bg-violet-400" />{c}
            </div>
          ))}
        </div>
        <div className="mt-4 text-[11px] text-slate-500">
          Known entity IDs: <span className="text-slate-300">{schema.known_entities.join(', ')}</span>
        </div>
      </Card>

      <Card title="Submit a batch" sub="upload triggers validation + full analytics recompute">
        <form onSubmit={upload} className="space-y-3">
          <input ref={fileRef} type="file" accept=".csv,text/csv"
            className="block w-full text-xs text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-violet-600 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-white hover:file:bg-violet-500" />
          <button disabled={busy}
            className="rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 px-4 py-2 text-xs font-semibold text-white">
            {busy ? 'Ingesting…' : 'Ingest & re-run analytics'}
          </button>
        </form>
        {msg && (
          <div className="mt-4 rounded-lg border border-emerald-700/50 bg-emerald-900/20 p-3 text-xs text-emerald-300">
            ✔ {msg.rows} rows ingested for {msg.entities.join(', ')} — {msg.status}.
            Dashboard, rankings and signals have been recomputed.
          </div>
        )}
        {err && (
          <div className="mt-4 rounded-lg border border-red-700/50 bg-red-900/20 p-3 text-xs text-red-300">
            ✖ {err}
          </div>
        )}
        <div className="mt-4 text-[11px] text-slate-500 leading-relaxed">
          Validation rejects files with missing schema columns or unknown entity IDs.
          After ingestion the rule engine, anomaly detection and risk scoring re-run
          end-to-end, so supervisory signals immediately reflect the new data.
          When the enclave operator sets <code className="text-slate-300">SATSA_SIGNING_KEY</code>,
          submissions must carry an <code className="text-slate-300">X-SATSA-Signature</code>
          HMAC-SHA256 header over the file bytes (see <code className="text-slate-300">backend/scripts/sign_submission.py</code>).
        </div>
      </Card>

      <Card title="Demo maintenance" sub="restore the pristine seeded dataset" className="lg:col-start-2">
        <button onClick={async () => { const r = await post('/reset', {}); setResetMsg(r.status) }}
          className="rounded-lg border border-red-700/60 text-red-300 hover:bg-red-900/20 px-4 py-2 text-xs font-semibold">
          ♻ Reseed demo database
        </button>
        {resetMsg && <div className="text-[11px] text-emerald-400 mt-3">{resetMsg} — rankings, signals and eval restored.</div>}
      </Card>
    </div>
  )
}
