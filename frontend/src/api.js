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
  async post(path, body, headers = {}) { return request(path, { method: 'POST', headers: { ...headers }, body: JSON.stringify(body) }) },
  async admin(path, method, key, body) {
    const headers = { 'X-Admin-Key': key }
    let payload
    if (body instanceof FormData) payload = body
    else if (body !== undefined) {
      headers['Content-Type'] = 'application/json'
      payload = JSON.stringify(body)
    }
    return request(path, { method, headers, body: payload })
  }
}
