import { useState } from 'react'
import { post } from '../api.js'

export default function Login({ onLogin }) {
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const [err, setErr] = useState(null)
  async function go(ev) {
    ev.preventDefault()
    setErr(null)
    try {
      const r = await post('/login', { user, password: pass })
      localStorage.setItem('satsa_token', r.token)
      localStorage.setItem('satsa_role', r.role)
      onLogin()
    } catch (e) { setErr(String(e.message)) }
  }
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#070d1a] p-6">
      <form onSubmit={go}
        className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900/70 p-7">
        <div className="text-xl font-extrabold text-slate-100">
          SAT-<span className="text-violet-400">SA</span>
        </div>
        <div className="text-[11px] text-slate-500 mb-6">
          NCIIPC supervisor console · offline enclave · sign in
        </div>
        <label className="block text-[11px] text-slate-400 mb-1">User</label>
        <input value={user} onChange={(e) => setUser(e.target.value)} autoFocus
          className="w-full mb-3 rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-200" />
        <label className="block text-[11px] text-slate-400 mb-1">Password</label>
        <input type="password" value={pass} onChange={(e) => setPass(e.target.value)}
          className="w-full mb-4 rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-200" />
        {err && <div className="text-xs text-red-400 mb-3">{err}</div>}
        <button className="w-full rounded-lg bg-violet-600 hover:bg-violet-500 py-2 text-sm font-semibold text-white">
          Sign in
        </button>
        <div className="text-[10px] text-slate-600 mt-4">
          Demo credentials are provisioned by the enclave operator (SATSA_USERS).
        </div>
      </form>
    </div>
  )
}
