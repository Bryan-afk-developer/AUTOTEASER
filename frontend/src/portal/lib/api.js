/**
 * api.js — Capa de comunicación con el backend FastAPI (portal endpoints).
 * Todos los requests usan el token JWT guardado en localStorage.
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── Helpers ───────────────────────────────────────────────────────────────────

let activeEmpresaId = null

function authHeaders() {
  if (activeEmpresaId) {
    return { Authorization: `Empresa ${activeEmpresaId}` }
  }
  return {}
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

// ── Endpoints ─────────────────────────────────────────────────────────────────

export const api = {
  // Contexto activo (para cuando el admin actúa como cliente)
  setActiveEmpresa: (id) => { activeEmpresaId = id },
  getActiveEmpresa: () => activeEmpresaId,

  crearEmpresa: (nombre, rfc = null) => 
    request('POST', '/api/portal/admin/empresas', { nombre, rfc }),

  eliminarEmpresa: (empresaId) => 
    request('DELETE', `/api/portal/admin/empresas/${empresaId}`),

  getUser: () => null,

  // Cliente - Expediente
  getExpediente: () => request('GET', '/api/portal/cliente/expediente'),

  subirDocumento: (tipoDocumento, file) => {
    const formData = new FormData()
    formData.append('tipo_documento', tipoDocumento)
    formData.append('file', file)
    return request('POST', '/api/portal/cliente/subir-documento', formData, true)
  },

  subirEstadosFinancierosAuto: (empresaId, file) => {
    const formData = new FormData()
    formData.append('empresa_id', empresaId)
    formData.append('file', file)
    return request('POST', '/api/portal/cliente/subir-estados-financieros-auto', formData, true)
  },

  subirDocumentosBanco: (cuentaId, files) => {
    const formData = new FormData()
    formData.append('cuenta_bancaria_id', cuentaId)
    // files is a FileList or Array of Files
    Array.from(files).forEach(f => formData.append('files', f))
    return request('POST', '/api/portal/cliente/subir-documentos-banco', formData, true)
  },

  justificarDocumento: (docId, justificacion) =>
    request('PATCH', `/api/portal/cliente/documentos/${docId}/justificar`, { justificacion }),

  eliminarDocumento: (tipoDocumento) =>
    request('DELETE', `/api/portal/cliente/eliminar-documento/${tipoDocumento}`),

  // Cliente - Bancos
  crearCarpetaBanco: (nombreBanco) =>
    request('POST', `/api/portal/cliente/carpetas-banco?nombre_banco=${encodeURIComponent(nombreBanco)}`),

  eliminarCarpetaBanco: (cuentaId) =>
    request('DELETE', `/api/portal/cliente/carpetas-banco/${cuentaId}`),

  procesarActaPrincipal: (clave) =>
    request('POST', `/api/portal/cliente/actas/${clave}/procesar-ia`),

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

  getBuroMops: (empresaId, tipo = 'buro_credito', refresh = false) => request('GET', `/api/portal/admin/empresas/${empresaId}/buro-mops?tipo_buro=${tipo}&refresh=${refresh}`),
  
  getBuroScore: (empresaId, tipo = 'buro_score_representante', refresh = false) => request('GET', `/api/portal/admin/empresas/${empresaId}/buro-score?tipo_buro=${tipo}&refresh=${refresh}`),

  exportToTeaser: (empresaId) => request('POST', `/api/portal/admin/empresas/${empresaId}/export-to-teaser`),
  exportToCaf: (empresaId) => request('POST', `/api/caf/empresas/${empresaId}/export`),

  // Admin - Revisión
  getDocumentoDetalle: (docId) =>
    request('GET', `/api/portal/admin/documentos/${docId}`),

  revisarDocumento: (docId, estado, comentario = '') =>
    request('PATCH', `/api/portal/admin/documentos/${docId}/revisar`, { estado, comentario }),

  verificarDomicilios: (dir1, dir2) =>
    request('POST', '/api/portal/admin/verificar-domicilios', { direccion_1: dir1, direccion_2: dir2 }),

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

  descargarDocumentoIndividual: async (empresaId, docId, isRep = false, preview = false) => {
    const headers = { ...authHeaders() }
    const res = await fetch(`${BASE_URL}/api/portal/admin/empresas/${empresaId}/documentos/${docId}/descargar?is_rep=${isRep}&preview=${preview}`, { headers })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `Error ${res.status}`)
    }
    
    const data = await res.json()
    if (!data.url) throw new Error('No URL returned')
    
    if (preview) {
      return data;
    }
    
    // Create an invisible link to trigger the download directly from Supabase CDN
    const a = document.createElement('a')
    a.href = data.url
    a.download = data.filename || 'documento.pdf'
    document.body.appendChild(a)
    a.click()
    a.remove()
  },
  
  // Admin - Google Drive
  initDrive: (empresaId) => request('POST', `/api/portal/admin/empresas/${empresaId}/drive/init`),
  syncDrive: (empresaId) => request('POST', `/api/portal/admin/empresas/${empresaId}/drive/sync`),

  // Accionistas
  getAccionistas: () => request('GET', '/api/portal/cliente/accionistas'),

  crearAccionista: (nombre = null) =>
    request('POST', '/api/portal/cliente/accionistas', { nombre }),

  actualizarAccionista: (accionistaId, nombre) =>
    request('PUT', `/api/portal/cliente/accionistas/${accionistaId}`, { nombre }),

  eliminarAccionista: (accionistaId) =>
    request('DELETE', `/api/portal/cliente/accionistas/${accionistaId}`),

  subirDocumentoAccionista: (accionistaId, tipoDocumento, file) => {
    const formData = new FormData()
    formData.append('tipo_documento', tipoDocumento)
    formData.append('accionista_id', accionistaId)
    formData.append('file', file)
    return request('POST', '/api/portal/cliente/subir-documento', formData, true)
  },

  // Sub Empresas
  getSubEmpresas: () => request('GET', '/api/portal/cliente/sub-empresas'),

  crearSubEmpresa: (nombre = null, rol = 'EMPRESA AVAL') =>
    request('POST', '/api/portal/cliente/sub-empresas', { nombre, rol }),

  actualizarSubEmpresa: (subEmpresaId, nombre, rol) =>
    request('PUT', `/api/portal/cliente/sub-empresas/${subEmpresaId}`, { nombre, rol }),

  eliminarSubEmpresa: (subEmpresaId) =>
    request('DELETE', `/api/portal/cliente/sub-empresas/${subEmpresaId}`),
    
  actualizarEmpresaRol: (rol) =>
    request('PUT', `/api/portal/cliente/expediente/rol`, { rol }),

  subirDocumentoSubEmpresa: (subEmpresaId, tipoDocumento, file) => {
    const formData = new FormData()
    formData.append('tipo_documento', tipoDocumento)
    formData.append('sub_empresa_id', subEmpresaId)
    formData.append('file', file)
    return request('POST', '/api/portal/cliente/subir-documento', formData, true)
  },
}

export default api
