import { useEffect, useState } from 'react'
import { get } from '../api.js'
import { Card, Loading, ScoreBar, Spark, SevChip, Chip } from '../ui.jsx'

export default function Entities({ openEntity }) {
  const [rows, setRows] = useState(null)
  useEffect(() => { get('/entities').then(setRows) }, [])
  if (!rows) return <Loading />

  return (
    <Card title="Critical Sector Entities under supervision"
      sub="ranked by composite supervisory risk score · click a row for full drill-down">
      <div className="overflow-x-auto -mx-4 px-4">
        <table className="w-full text-sm min-w-[980px]">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
              <th className="text-left py-2 pr-2">#</th>
              <th className="text-left py-2 pr-3">Entity</th>
              <th className="text-left py-2 pr-3">Sector</th>
              <th className="text-left py-2 pr-3">Risk</th>
              <th className="text-right py-2 pr-3">Alerts 30d</th>
              <th className="text-right py-2 pr-3">Open crit</th>
              <th className="text-right py-2 pr-3">MTTR</th>
              <th className="text-right py-2 pr-3">SLA ok</th>
              <th className="text-right py-2 pr-3">Esc rate</th>
              <th className="text-left py-2 pr-3">10-wk trend</th>
              <th className="text-left py-2 pr-3">Risk trajectory (4×30d)</th>
              <th className="text-left py-2">Signals</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id} onClick={() => openEntity(e.id)}
                className="border-b border-slate-800/60 hover:bg-slate-800/40 cursor-pointer">
                <td className="py-2.5 pr-2 text-slate-500 text-xs">{e.rank}</td>
                <td className="py-2.5 pr-3">
                  <div className="font-semibold text-slate-200">{e.name}</div>
                  <div className="text-[11px] text-slate-500">{e.id} · {e.criticality}</div>
                </td>
                <td className="py-2.5 pr-3 text-slate-400 text-xs">{e.sector}</td>
                <td className="py-2.5 pr-3"><ScoreBar score={e.score} /></td>
                <td className="py-2.5 pr-3 text-right text-slate-300">{e.alerts30.toLocaleString('en-IN')}</td>
                <td className="py-2.5 pr-3 text-right font-semibold" style={{ color: e.open_now > 10 ? '#f87171' : '#e2e8f0' }}>
                  {e.open_now}
                </td>
                <td className="py-2.5 pr-3 text-right text-slate-300">{e.mttr}h</td>
                <td className="py-2.5 pr-3 text-right text-slate-300">{e.sla_ok_pct}%</td>
                <td className="py-2.5 pr-3 text-right text-slate-300">{Math.round(e.esc_rate * 100)}%</td>
                <td className="py-2.5 pr-3"><Spark data={e.spark} /></td>
                <td className="py-2.5 pr-3">
                  <span className="flex items-center gap-2">
                    <Spark data={e.traj} color="#a78bfa" w={64} h={22} />
                    <span className="text-[11px] font-bold"
                      style={{ color: e.delta > 0 ? '#f87171' : e.delta < 0 ? '#34d399' : '#64748b' }}>
                      {e.delta > 0 ? `▲ +${e.delta}` : e.delta < 0 ? `▼ ${e.delta}` : '• 0'}
                    </span>
                  </span>
                </td>
                <td className="py-2.5">
                  {e.signals === 0
                    ? <span className="text-[11px] text-emerald-400">clean</span>
                    : <span className="flex items-center gap-1.5">
                        <span className="text-xs font-bold text-slate-200">{e.signals}</span>
                        {e.worst && <SevChip sev={e.worst} />}
                      </span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
