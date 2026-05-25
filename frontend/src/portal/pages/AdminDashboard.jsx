import { useState, useCallback, useEffect } from 'react'
import api from '../lib/api'
import {
  FileText, Loader2, Search, ArrowLeft, Building2, CheckCircle2,
  XCircle, Clock, Eye, Download, ShieldCheck
} from 'lucide-react'

const ESTADO_CONFIG = {
  APROBADO:  { color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/20', icon: <CheckCircle2 className="w-3.5 h-3.5"/>, label: 'Aprobado' },
  PENDIENTE: { color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20', icon: <Clock className="w-3.5 h-3.5"/>, label: 'Pendiente' },
  RECHAZADO: { color: 'text-rose-400',  bg: 'bg-rose-500/10',  border: 'border-rose-500/20',  icon: <XCircle className="w-3.5 h-3.5"/>, label: 'Rechazado' },
  FALTANTE:  { color: 'text-slate-400', bg: 'bg-slate-500/10', border: 'border-slate-500/20', icon: <FileText className="w-3.5 h-3.5"/>, label: 'Faltante' },
}

function ReviewModal({ doc, onClose, onSuccess }) {
  const [estado, setEstado] = useState('APROBADO')
  const [comentario, setComentario] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [pdfUrl, setPdfUrl] = useState(null)
  const [loadingPdf, setLoadingPdf] = useState(false)

  const fetchUrl = useCallback(async () => {
    setLoadingPdf(true)
    try {
      const detail = await api.getDocumentoDetalle(doc.id)
      if (detail.url_documento) setPdfUrl(detail.url_documento)
    } catch (e) {
      console.warn('No se pudo obtener URL del PDF:', e)
    } finally {
      setLoadingPdf(false)
    }
  }, [doc.id])

  useEffect(() => { fetchUrl() }, [fetchUrl])

  const handleSubmit = async () => {
    if (estado === 'RECHAZADO' && !comentario.trim()) {
      setError('Debes escribir un comentario al rechazar el documento.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await api.revisarDocumento(doc.id, estado, comentario)
      onSuccess()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-[1000] flex items-center justify-center p-4 animate-fade-in" onClick={onClose}>
      <div className="bg-card border border-border rounded-2xl w-full max-w-lg shadow-2xl flex flex-col overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface/50">
          <div>
            <h3 className="text-base font-bold text-text-main">Revisar Documento</h3>
            <p className="text-xs text-text-muted mt-0.5">{doc.empresa_nombre} · {doc.nombre_esperado || doc.tipo_documento}</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-lg transition-colors text-text-muted hover:text-text-main">
            ✕
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium text-text-muted">📎 {doc.nombre_archivo || 'Sin nombre de archivo'}</span>
            {loadingPdf && <span className="text-xs text-primary-400 flex items-center gap-2"><Loader2 className="w-3 h-3 animate-spin" /> Obteniendo vista previa...</span>}
            {pdfUrl && (
              <a href={pdfUrl} target="_blank" rel="noopener noreferrer" 
                 className="inline-flex items-center gap-2 px-4 py-2 bg-primary-500/10 hover:bg-primary-500/20 text-primary-400 border border-primary-500/30 rounded-xl text-sm font-semibold transition-colors self-start">
                <Eye className="w-4 h-4" /> Ver PDF en nueva pestaña
              </a>
            )}
          </div>

          <div className="flex gap-3">
            {['APROBADO', 'RECHAZADO', 'PENDIENTE'].map(e => {
              const cfg = ESTADO_CONFIG[e]
              const isActive = estado === e
              return (
                <button key={e} onClick={() => setEstado(e)}
                  className={`flex-1 py-3 rounded-xl border flex items-center justify-center gap-2 text-[11px] md:text-sm font-bold transition-all
                    ${isActive ? `${cfg.bg} ${cfg.border} ${cfg.color}` : 'bg-surface border-border text-text-muted hover:border-gray-600'}`}>
                  {cfg.icon} {e === 'APROBADO' ? 'Aprobar' : e === 'RECHAZADO' ? 'Rechazar' : 'A Revisión'}
                </button>
              )
            })}
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-text-muted uppercase tracking-wider">
              Comentario {estado === 'RECHAZADO' ? <span className="text-rose-500">*</span> : '(opcional)'}
            </label>
            <textarea
              value={comentario} onChange={(e) => setComentario(e.target.value)} rows={3}
              className="w-full bg-surface border border-border rounded-xl p-3 text-sm text-text-main focus:outline-none focus:border-primary-500/50 transition-colors"
              placeholder={estado === 'RECHAZADO' ? 'Ej: El documento está borroso o no corresponde al mes.' : 'Ej: Todo correcto.'}
            />
            {error && <p className="text-xs font-semibold text-rose-400 flex items-center gap-1">⚠️ {error}</p>}
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border bg-surface/30">
          <button onClick={onClose} className="px-4 py-2 text-sm font-semibold text-text-muted hover:text-text-main transition-colors">
            Cancelar
          </button>
          <button onClick={handleSubmit} disabled={loading}
            className={`px-5 py-2 rounded-xl text-sm font-bold text-white flex items-center gap-2 transition-all
              ${estado === 'APROBADO' ? 'bg-green-600 hover:bg-green-500 shadow-[0_0_15px_rgba(22,163,74,0.3)]' : estado === 'RECHAZADO' ? 'bg-rose-600 hover:bg-rose-500 shadow-[0_0_15px_rgba(225,29,72,0.3)]' : 'bg-amber-600 hover:bg-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.3)]'}
              ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : (estado === 'APROBADO' ? <CheckCircle2 className="w-4 h-4" /> : estado === 'RECHAZADO' ? <XCircle className="w-4 h-4" /> : <Clock className="w-4 h-4" />)}
            Confirmar {estado === 'APROBADO' ? 'Aprobación' : estado === 'RECHAZADO' ? 'Rechazo' : 'Revisión'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function AdminDashboard() {
  const [empresas, setEmpresas] = useState([])
  const [selectedEmpresa, setSelectedEmpresa] = useState(null)
  const [documentos, setDocumentos] = useState([])
  
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [reviewDoc, setReviewDoc] = useState(null)

  const loadEmpresas = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getEmpresas()
      setEmpresas(data.empresas || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDocumentos = useCallback(async (empresaId) => {
    setLoading(true)
    try {
      const data = await api.getEmpresaDocumentos(empresaId)
      setDocumentos(data.documentos || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!selectedEmpresa) {
      loadEmpresas()
    } else {
      loadDocumentos(selectedEmpresa.id)
    }
  }, [selectedEmpresa, loadEmpresas, loadDocumentos])

  const filteredEmpresas = empresas.filter(emp => 
    emp.nombre.toLowerCase().includes(searchQuery.toLowerCase()) || 
    (emp.rfc && emp.rfc.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  // ── Render View: Lista de Empresas ──
  if (!selectedEmpresa) {
    return (
      <main className="max-w-6xl w-full mx-auto px-6 py-8 space-y-6 flex-1 animate-fade-in">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <h2 className="text-sm font-bold text-text-muted uppercase tracking-wider flex items-center gap-2">
            <Building2 className="w-4 h-4 text-primary-400" /> Directorio de Empresas
          </h2>
          
          <div className="relative">
            <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input 
              type="text" 
              placeholder="Buscar por nombre o RFC..." 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="bg-surface border border-border rounded-xl py-2 pl-9 pr-4 text-sm focus:outline-none focus:border-primary-500/50 w-full md:w-64 text-text-main"
            />
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center p-12 text-text-muted">
            <Loader2 className="w-8 h-8 animate-spin text-primary-500 mb-3" />
            <p>Cargando empresas...</p>
          </div>
        ) : error ? (
          <div className="bg-rose-500/10 border border-rose-500/30 text-rose-400 p-4 rounded-xl font-semibold">
            ⚠️ {error}
          </div>
        ) : filteredEmpresas.length === 0 ? (
          <div className="border border-border bg-surface/20 rounded-xl p-12 text-center text-text-muted">
            <Building2 className="w-12 h-12 mx-auto mb-3 opacity-20" />
            <p className="font-semibold text-sm">No se encontraron empresas.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredEmpresas.map(emp => (
              <div 
                key={emp.id} 
                onClick={() => setSelectedEmpresa(emp)}
                className="bg-card border border-border hover:border-primary-500/50 rounded-xl p-5 cursor-pointer transition-all hover:shadow-[0_0_15px_rgba(225,29,72,0.05)] group flex flex-col h-full"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="min-w-0">
                    <h3 className="font-bold text-text-main truncate text-base group-hover:text-primary-400 transition-colors">{emp.nombre}</h3>
                    <p className="text-xs text-text-muted mt-0.5">{emp.rfc || 'Sin RFC'}</p>
                  </div>
                </div>

                <div className="mt-auto pt-4 border-t border-border flex items-center justify-between">
                  <div className="flex gap-2">
                    {emp.conteo_estados?.PENDIENTE > 0 && (
                      <span className="flex items-center gap-1 text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full">
                        <Clock className="w-3 h-3" /> {emp.conteo_estados.PENDIENTE}
                      </span>
                    )}
                    {emp.conteo_estados?.RECHAZADO > 0 && (
                      <span className="flex items-center gap-1 text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20 px-2 py-0.5 rounded-full">
                        <XCircle className="w-3 h-3" /> {emp.conteo_estados.RECHAZADO}
                      </span>
                    )}
                  </div>
                  <span className="text-xs font-semibold text-primary-400 opacity-0 group-hover:opacity-100 transition-opacity">
                    Ver doc. →
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    )
  }

  // ── Render View: Documentos de la Empresa ──
  return (
    <main className="max-w-6xl w-full mx-auto px-6 py-8 space-y-6 flex-1 animate-fade-in">
      {/* Header back & title */}
      <div className="flex items-center gap-4">
        <button 
          onClick={() => setSelectedEmpresa(null)}
          className="p-2 bg-surface hover:bg-surface/80 border border-border rounded-xl text-text-muted hover:text-text-main transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h2 className="text-lg font-bold text-text-main leading-tight">{selectedEmpresa.nombre}</h2>
          <p className="text-xs text-text-muted">{selectedEmpresa.rfc || 'Sin RFC'}</p>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center p-12 text-text-muted">
          <Loader2 className="w-8 h-8 animate-spin text-primary-500 mb-3" />
          <p>Cargando documentos...</p>
        </div>
      ) : error ? (
        <div className="bg-rose-500/10 border border-rose-500/30 text-rose-400 p-4 rounded-xl font-semibold">⚠️ {error}</div>
      ) : documentos.length === 0 ? (
        <div className="border border-border bg-surface/20 rounded-xl p-12 text-center text-text-muted">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-20" />
          <p className="font-semibold text-sm">Esta empresa aún no ha subido documentos.</p>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
          <table className="w-full text-sm text-left">
            <thead className="bg-surface/50 border-b border-border text-xs uppercase text-text-muted font-bold tracking-wider">
              <tr>
                <th className="px-6 py-4">Documento</th>
                <th className="px-6 py-4">Archivo</th>
                <th className="px-6 py-4">Subido En</th>
                <th className="px-6 py-4">Estado</th>
                <th className="px-6 py-4 text-right">Acción</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {documentos.map(doc => {
                const cfg = ESTADO_CONFIG[doc.estado] || ESTADO_CONFIG.FALTANTE
                const esPendiente = doc.estado === 'PENDIENTE'
                return (
                  <tr key={doc.id || doc.tipo_documento} className="hover:bg-surface/20 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-text-main text-[13px] leading-tight">
                        {doc.nombre_esperado || doc.tipo_documento}
                      </div>
                      <div className="text-[10px] text-text-muted mt-1 uppercase tracking-widest">{doc.grupo === 'representante' ? 'Rep. Legal' : 'Empresa'}</div>
                    </td>
                    <td className="px-6 py-4 text-text-muted text-xs truncate max-w-[200px]" title={doc.nombre_archivo}>
                      {doc.nombre_archivo || '—'}
                    </td>
                    <td className="px-6 py-4 text-text-muted text-xs">
                      {doc.subido_en ? new Date(doc.subido_en).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border ${cfg.bg} ${cfg.color} ${cfg.border}`}>
                        {cfg.icon} {cfg.label}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      {esPendiente ? (
                        <button
                          onClick={() => setReviewDoc(doc)}
                          className="bg-primary-600 hover:bg-primary-500 text-white font-semibold text-xs py-1.5 px-4 rounded-lg transition-colors shadow-[0_0_10px_rgba(225,29,72,0.2)]"
                        >
                          Revisar
                        </button>
                      ) : (
                        doc.estado !== 'FALTANTE' && (
                          <div className="flex items-center justify-end gap-2">
                            {doc.comentario_admin && (
                              <span className="text-[11px] text-text-muted bg-surface px-2 py-1 rounded border border-border max-w-[150px] truncate" title={doc.comentario_admin}>
                                💬 {doc.comentario_admin}
                              </span>
                            )}
                            <button
                              onClick={() => setReviewDoc(doc)}
                              className="text-primary-400 hover:text-primary-300 bg-primary-500/10 hover:bg-primary-500/20 px-2 py-1.5 rounded-lg text-xs font-semibold transition-colors"
                            >
                              Cambiar estado
                            </button>
                          </div>
                        )
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal Review */}
      {reviewDoc && (
        <ReviewModal
          doc={{...reviewDoc, empresa_nombre: selectedEmpresa.nombre}}
          onClose={() => setReviewDoc(null)}
          onSuccess={() => {
            setReviewDoc(null)
            loadDocumentos(selectedEmpresa.id)
          }}
        />
      )}
    </main>
  )
}
