/**
 * api.js — Capa de comunicación con el backend FastAPI (portal endpoints).
 * Todos los requests usan el token JWT guardado en localStorage.
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── Helpers ───────────────────────────────────────────────────────────────────

function getToken() {
  return localStorage.getItem('portal_token')
}

function authHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(method, path, body = null, isFormData = false) {
  const headers = { ...authHeaders() }
  if (!isFormData) headers['Content-Type'] = 'application/json'

  const options = { method, headers }
  if (body) options.body = isFormData ? body : JSON.stringify(body)

  const res = await fetch(`${BASE_URL}${path}`, options)
  const data = await res.json().catch(() => ({}))

  if (!res.ok) {
    throw new Error(data.detail || data.message || `Error ${res.status}`)
  }
  return data
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const api = {
  // Cliente - Auth
  registro: (email, password, nombre_empresa, rfc = null) =>
    request('POST', '/api/portal/cliente/registro', { email, password, nombre_empresa, rfc }),

  login: async (email, password) => {
    const data = await request('POST', '/api/portal/cliente/login', { email, password })
    if (data.access_token) {
      localStorage.setItem('portal_token', data.access_token)
      localStorage.setItem('portal_user', JSON.stringify(data.user))
    }
    return data
  },

  logout: () => {
    localStorage.removeItem('portal_token')
    localStorage.removeItem('portal_user')
  },

  perfil: () => request('GET', '/api/portal/cliente/perfil'),

  getUser: () => {
    try {
      return JSON.parse(localStorage.getItem('portal_user'))
    } catch {
      return null
    }
  },

  isAuthenticated: () => !!getToken(),

  // Cliente - Expediente
  getExpediente: () => request('GET', '/api/portal/cliente/expediente'),

  subirDocumento: (tipoDocumento, file) => {
    const formData = new FormData()
    formData.append('tipo_documento', tipoDocumento)
    formData.append('file', file)
    return request('POST', '/api/portal/cliente/subir-documento', formData, true)
  },

  subirDocumentosBanco: (cuentaId, files) => {
    const formData = new FormData()
    formData.append('cuenta_bancaria_id', cuentaId)
    // files is a FileList or Array of Files
    Array.from(files).forEach(f => formData.append('files', f))
    return request('POST', '/api/portal/cliente/subir-documentos-banco', formData, true)
  },

  eliminarDocumento: (tipoDocumento) =>
    request('DELETE', `/api/portal/cliente/eliminar-documento/${tipoDocumento}`),

  // Cliente - Bancos
  crearCarpetaBanco: (nombreBanco) =>
    request('POST', `/api/portal/cliente/carpetas-banco?nombre_banco=${encodeURIComponent(nombreBanco)}`),

  eliminarCarpetaBanco: (cuentaId) =>
    request('DELETE', `/api/portal/cliente/carpetas-banco/${cuentaId}`),

  subirEstadosCuentaAuto: (files) => {
    const formData = new FormData()
    Array.from(files).forEach(f => formData.append('files', f))
    return request('POST', '/api/portal/cliente/subir-estados-cuenta-auto', formData, true)
  },

  subirDeclaracionesAuto: (files) => {
    const formData = new FormData()
    Array.from(files).forEach(f => formData.append('files', f))
    return request('POST', '/api/portal/cliente/subir-declaraciones-auto', formData, true)
  },

  subirDeclaracionManual: (file, tipo, year) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('tipo', tipo)
    formData.append('year', year)
    return request('POST', '/api/portal/cliente/subir-declaracion-manual', formData, true)
  },

  moverDocumentoBanco: (documentoId, cuentaBancariaDestinoId) =>
    request('PATCH', '/api/portal/cliente/mover-documento-banco', {
      documento_id: documentoId,
      cuenta_bancaria_destino_id: cuentaBancariaDestinoId,
    }),

  // Admin - Dashboard
  getPendientes: (estado = 'PENDIENTE') =>
    request('GET', `/api/portal/admin/pendientes?estado=${estado}`),

  getEmpresas: () => request('GET', '/api/portal/admin/empresas'),

  getEmpresaDocumentos: (empresaId) => request('GET', `/api/portal/admin/empresas/${empresaId}/documentos`),

  // Admin - Revisión
  getDocumentoDetalle: (docId) =>
    request('GET', `/api/portal/admin/documentos/${docId}`),

  revisarDocumento: (docId, estado, comentario = '') =>
    request('PATCH', `/api/portal/admin/documentos/${docId}/revisar`, { estado, comentario }),

  descargarTodosDocumentos: async (empresaId) => {
    const headers = { ...authHeaders() }
    const res = await fetch(`${BASE_URL}/api/portal/admin/empresas/${empresaId}/descargar-todo`, { headers })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `Error ${res.status}`)
    }
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="?(.+?)"?$/)
    const filename = match ? match[1] : `Expediente_${empresaId}.zip`
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  },

  descargarSeleccion: async (empresaId, docIds, filename) => {
    const headers = { ...authHeaders(), 'Content-Type': 'application/json' }
    const res = await fetch(`${BASE_URL}/api/portal/admin/empresas/${empresaId}/descargar-seleccion`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ doc_ids: docIds })
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `Error ${res.status}`)
    }
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || `Seleccion_${empresaId}.zip`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  },

  descargarDocumentoIndividual: async (empresaId, docId, isRep = false) => {
    const headers = { ...authHeaders() }
    const res = await fetch(`${BASE_URL}/api/portal/admin/empresas/${empresaId}/documentos/${docId}/descargar?is_rep=${isRep}`, { headers })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `Error ${res.status}`)
    }
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') || ''
    // Try RFC 5987 filename* first, then plain filename
    const matchUtf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i)
    const matchPlain = disposition.match(/filename="?([^"]+)"?/i)
    const filename = matchUtf8
      ? decodeURIComponent(matchUtf8[1])
      : matchPlain
        ? matchPlain[1]
        : `documento_${docId}.pdf`
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  },
}

export default api
