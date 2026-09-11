export function authHeaders() {
  const t = localStorage.getItem('satsa_token')
  return t ? { Authorization: 'Bearer ' + t } : {}
}

async function handle(r) {
  if (r.status === 401) {
    window.dispatchEvent(new CustomEvent('satsa:401'))
  }
  const txt = await r.text()
  let data
  try { data = JSON.parse(txt) } catch { data = { error: txt } }
  if (!r.ok) throw new Error(data.detail || txt)
  return data
}

export async function get(path) {
  return handle(await fetch('/api' + path, { headers: authHeaders() }))
}

export async function post(path, body) {
  return handle(await fetch('/api' + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  }))
}

export async function put(path, body) {
  return handle(await fetch('/api' + path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  }))
}

export async function postForm(path, form) {
  const r = await fetch('/api' + path, { method: 'POST', body: form, headers: authHeaders() })
  return handle(r)
}
