const BASE = ''
async function request(path, options = {}) {
  const res = await fetch(BASE + path, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || 'Request failed')
  }
  return res.json()
}
export default {
  async get(path) { return request(path) },
  async post(path, body) { return request(path, { method: 'POST', body: JSON.stringify(body) }) }
}