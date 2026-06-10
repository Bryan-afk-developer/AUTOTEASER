import { useState, useCallback, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import api from '../lib/api'
import AdminCompanySummary from '../components/AdminCompanySummary'
import {
  FileText, Loader2, Search, ArrowLeft, Building2, CheckCircle2,
  XCircle, Clock, Eye, Download, RefreshCw, ChevronDown, ChevronUp,
  BarChart2, AlertTriangle, X, ChevronRight,
} from 'lucide-react'

// ── Constantes ────────────────────────────────────────────────────────────────

const ESTADO_CONFIG = {
  APROBADO: { color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/20', icon: <CheckCircle2 className="w-3.5 h-3.5" />, label: 'Aprobado' },
  PENDIENTE: { color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20', icon: <Clock className="w-3.5 h-3.5" />, label: 'Pendiente' },
  RECHAZADO: { color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/20', icon: <XCircle className="w-3.5 h-3.5" />, label: 'Rechazado' },
  FALTANTE: { color: 'text-slate-400', bg: 'bg-slate-500/10', border: 'border-slate-500/20', icon: <FileText className="w-3.5 h-3.5" />, label: 'Faltante' },
}

const MOP_NIVEL_CONFIG = [
  { nivel: 1, color: 'text-emerald-300', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', alerta: false, desc: 'Al corriente' },
  { nivel: 2, color: 'text-yellow-300', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20', alerta: false, desc: '1-29 días' },
  { nivel: 3, color: 'text-orange-300', bg: 'bg-orange-500/10', border: 'border-orange-500/20', alerta: true, desc: '30-59 días' },
  { nivel: 4, color: 'text-orange-400', bg: 'bg-orange-500/15', border: 'border-orange-500/30', alerta: true, desc: '60-89 días' },
  { nivel: 5, color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20', alerta: true, desc: '90-119 días' },
  { nivel: 6, color: 'text-red-400', bg: 'bg-red-500/15', border: 'border-red-500/30', alerta: true, desc: '120-179 días' },
  { nivel: 7, color: 'text-red-500', bg: 'bg-red-500/20', border: 'border-red-500/40', alerta: true, desc: '180+ días' },
]

// ── Componente MopsBadge (Alerta Inline) ──────────────────────────────────────
function MopsBadge({ empresaId }) {
  const [mopMax, setMopMax] = useState(null)

  useEffect(() => {
    let cancelled = false

    const process = (data) => {
      let highest = 0
      if (data.mops_alerta?.length > 0) {
        highest = Math.max(...data.mops_alerta.map(m => m.nivel))
      } else if (data.niveles) {
        const levels = Object.keys(data.niveles).map(Number)
        if (levels.length > 0) highest = Math.max(...levels)
      }
      // Solo mostrar de nivel 3 para arriba
      if (highest >= 3) setMopMax(highest)
    }

    if (mopsCache[empresaId]) {
      process(mopsCache[empresaId])
      return
    }

    api.getBuroMops(empresaId).then(res => {
      if (!cancelled) {
        mopsCache[empresaId] = res
        process(res)
      }
    }).catch(() => {})

    return () => { cancelled = true }
  }, [empresaId])

  if (!mopMax) return null

  return (
    <div className="mt-1.5 ml-2 inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-bold text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg animate-fade-in">
      ⚠️ MOP {mopMax}
    </div>
  )
}

// ── PdfDrawer ──────────────────────────────────────────────────────────────────
const pdfCache = {}

function PdfDrawer({ isOpen, empresaId, docId, onClose }) {
  const [pdfUrl, setPdfUrl] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isOpen || !docId) return
    let cancelled = false
    setLoading(true)

    const now = Date.now()
    const cached = pdfCache[docId]
    if (cached && cached.expiresAt > now) {
      setPdfUrl(cached.url)
      setLoading(false)
      return
    }

    api.descargarDocumentoIndividual(empresaId, docId, false, true)
      .then(res => {
        if (!cancelled) {
          pdfCache[docId] = {
            url: res.url,
            expiresAt: now + (55 * 60 * 1000)
          }
          setPdfUrl(res.url)
        }
      })
      .catch(err => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [isOpen, empresaId, docId])

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div 
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[900]" 
            onClick={onClose} 
          />
          <motion.div 
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 h-full w-full max-w-3xl bg-[#111113] border-l border-border shadow-2xl z-[910] flex flex-col"
          >
            {/* Floating Arrow Close Button */}
            <motion.button 
              initial={{ x: 20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 20, opacity: 0 }}
              transition={{ delay: 0.3 }}
              onClick={onClose} 
              className="absolute -left-12 top-1/2 -translate-y-1/2 w-12 h-16 bg-[#111113] border-y border-l border-border rounded-l-xl flex items-center justify-center hover:bg-surface hover:w-14 hover:-left-14 transition-all z-50 shadow-[-10px_0_20px_rgba(0,0,0,0.5)] group"
            >
              <ChevronRight className="w-6 h-6 text-text-muted group-hover:text-primary-400 transition-colors" />
            </motion.button>

            <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-surface">
              <div className="w-10 h-10 rounded-xl bg-primary-500/10 border border-primary-500/20 flex items-center justify-center flex-shrink-0 shadow-[0_0_15px_rgba(225,29,72,0.1)]">
                <FileText className="w-5 h-5 text-primary-400" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-text-main leading-tight">
                  Vista Previa del Documento
                </h2>
                <p className="text-xs text-text-muted">Previsualización segura y rápida</p>
              </div>
            </div>
            
            <div className="flex-1 bg-black/50 relative overflow-hidden">
              <AnimatePresence>
                {loading && (
                  <motion.div 
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="absolute inset-0 flex flex-col items-center justify-center bg-black/50 z-10 backdrop-blur-sm"
                  >
                    <Loader2 className="w-10 h-10 animate-spin text-primary-400 mb-4 drop-shadow-[0_0_10px_rgba(225,29,72,0.5)]" />
                    <p className="text-sm font-semibold text-text-main animate-pulse">Obteniendo vista previa segura...</p>
                  </motion.div>
                )}
                {error && (
                  <motion.div 
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="absolute inset-0 flex items-center justify-center text-red-400 px-6 text-center z-10"
                  >
                    ⚠️ {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {pdfUrl && (
                <motion.iframe 
                   initial={{ opacity: 0, scale: 0.95 }}
                   animate={{ opacity: 1, scale: 1 }}
                   transition={{ delay: 0.2 }}
                   src={pdfUrl} 
                   className="w-full h-full border-none bg-white relative z-0"
                   title="Vista Previa PDF"
                />
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  )
}

// ── MopsDrawer ────────────────────────────────────────────────────────────────
const mopsCache = {}

function MopsDrawer({ isOpen, empresaId, onClose }) {
  const [data, setData] = useState(mopsCache[empresaId] || null)
  const [loading, setLoading] = useState(!mopsCache[empresaId])
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isOpen || !empresaId) return
    if (mopsCache[empresaId]) {
      setData(mopsCache[empresaId])
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)
    setError('')
    api.getBuroMops(empresaId)
      .then(res => { 
        if (!cancelled) {
          mopsCache[empresaId] = res
          setData(res) 
        }
      })
      .catch(err => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [isOpen, empresaId])

  const anios = data?.anios || data?.años || []
  const niveles = data?.niveles || {}

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Overlay */}
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[900]"
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 h-full w-full max-w-2xl bg-[#111113] border-l border-border shadow-2xl z-[910] flex flex-col"
          >
            {/* Floating Arrow Close Button */}
            <motion.button 
              initial={{ x: 20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 20, opacity: 0 }}
              transition={{ delay: 0.3 }}
              onClick={onClose} 
              className="absolute -left-12 top-1/2 -translate-y-1/2 w-12 h-16 bg-[#111113] border-y border-l border-border rounded-l-xl flex items-center justify-center hover:bg-surface hover:w-14 hover:-left-14 transition-all z-50 shadow-[-10px_0_20px_rgba(0,0,0,0.5)] group"
            >
              <ChevronRight className="w-6 h-6 text-text-muted group-hover:text-primary-400 transition-colors" />
            </motion.button>

            {/* Header */}
            <div className="flex items-center gap-3 px-6 py-5 border-b border-border bg-surface flex-shrink-0">
              <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center flex-shrink-0 shadow-[0_0_15px_rgba(139,92,246,0.1)]">
                <BarChart2 className="w-5 h-5 text-violet-400" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-text-main leading-tight">Análisis de MOPs</h2>
                <p className="text-xs text-text-muted">Buró de Crédito — Histórico de Pagos</p>
              </div>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6 relative">
              <AnimatePresence mode="wait">
                {loading && (
                  <motion.div 
                    key="loading"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="flex flex-col items-center justify-center py-20 gap-4 text-text-muted"
                  >
                    <Loader2 className="w-10 h-10 animate-spin text-violet-400 drop-shadow-[0_0_10px_rgba(139,92,246,0.5)]" />
                    <p className="text-sm font-semibold animate-pulse text-text-main">Analizando PDF del Buró de Crédito...</p>
                    <p className="text-xs opacity-60">Extrayendo meses de pago histórico</p>
                  </motion.div>
                )}

                {error && (
                  <motion.div 
                    key="error"
                    initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                    className="bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-xl p-4 text-sm font-semibold shadow-inner"
                  >
                    ⚠️ {error}
                  </motion.div>
                )}

                {data && !loading && (
                  <motion.div 
                    key="content"
                    initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ staggerChildren: 0.1 }}
                    className="space-y-6"
                  >
                    {/* Banner alerta */}
                    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}>
                      {data.alerta ? (
                        <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/30 rounded-xl p-4 shadow-[0_0_15px_rgba(239,68,68,0.1)]">
                          <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                          <div>
                            <p className="text-sm font-bold text-red-300">⚠️ MOPs de alto riesgo detectados</p>
                            <p className="text-xs text-red-400/80 mt-0.5">
                              Se encontraron {data.mops_alerta?.length || 0} registros con nivel de atraso 3 o superior.
                              Revisa los créditos con atraso para evaluar el riesgo crediticio.
                            </p>
                          </div>
                        </div>
                      ) : !data.mops_detectados && (
                        <div className="flex items-start gap-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-4 shadow-[0_0_15px_rgba(16,185,129,0.1)]">
                          <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                          <div>
                            <p className="text-sm font-bold text-emerald-300">Sin atrasos significativos</p>
                            <p className="text-xs text-emerald-400/80 mt-0.5">No se detectaron MOPs nivel 2 o superior en el reporte.</p>
                          </div>
                        </div>
                      )}
                    </motion.div>

                    {/* Leyenda */}
                    <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
                      <h3 className="text-xs font-bold text-text-muted uppercase tracking-wider mb-3">Leyenda de MOPs</h3>
                      <div className="grid grid-cols-2 gap-1.5">
                        {MOP_NIVEL_CONFIG.map((cfg, idx) => (
                          <motion.div 
                            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.05 }}
                            key={cfg.nivel} 
                            className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${cfg.bg} ${cfg.border} hover:bg-surface/50 transition-colors`}
                          >
                            <span className={`text-xs font-black ${cfg.color}`}>{cfg.nivel}</span>
                            <span className="text-[10px] text-text-muted leading-tight font-medium">{cfg.desc}</span>
                            {cfg.alerta && <AlertTriangle className="w-3 h-3 text-red-400 ml-auto flex-shrink-0" />}
                          </motion.div>
                        ))}
                      </div>
                    </motion.div>

              {/* Tabla principal */}
              {anios.length > 0 && (
                <div>
                  <h3 className="text-xs font-bold text-text-muted uppercase tracking-wider mb-3">Tabla de Histórico de Pagos</h3>
                  <div className="bg-card border border-border rounded-xl overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-surface/70 border-b border-border">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-bold text-text-muted uppercase tracking-wider">NIVEL</th>
                          {anios.map(anio => (
                            <th key={anio} className="px-4 py-3 text-center text-xs font-bold text-text-muted uppercase tracking-wider">
                              AÑO {anio}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/50">
                        {MOP_NIVEL_CONFIG.map(cfg => {
                          const nivelData = niveles[String(cfg.nivel)] || niveles[cfg.nivel] || {}
                          const hasAnyData = Object.values(nivelData).some(v => v > 0)
                          const hasAlert = cfg.alerta && hasAnyData
                          return (
                            <tr
                              key={cfg.nivel}
                              className={`transition-colors ${hasAlert ? 'bg-red-500/5 hover:bg-red-500/10'
                                  : cfg.nivel === 2 && hasAnyData ? 'bg-yellow-500/5 hover:bg-yellow-500/10'
                                    : 'hover:bg-surface/30'
                                }`}
                            >
                              <td className="px-4 py-3">
                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border ${cfg.bg} ${cfg.color} ${cfg.border}`}>
                                  {cfg.alerta && <AlertTriangle className="w-2.5 h-2.5" />}
                                  NIVEL {cfg.nivel}
                                </span>
                              </td>
                              {anios.map(anio => {
                                const count = nivelData[anio] || 0
                                return (
                                  <td key={anio} className="px-4 py-3 text-center">
                                    <span className={`text-sm font-bold ${count === 0 ? 'text-text-muted/40'
                                        : hasAlert ? 'text-red-300'
                                          : cfg.nivel === 2 ? 'text-yellow-300'
                                            : 'text-emerald-300'
                                      }`}>
                                      {count}
                                    </span>
                                  </td>
                                )
                              })}
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Detalle alertas */}
              {data.mops_alerta?.length > 0 && (
                <div>
                  <h3 className="text-xs font-bold text-text-muted uppercase tracking-wider mb-3">Detalle de Alertas</h3>
                  <div className="space-y-2">
                    {data.mops_alerta.map((alerta, i) => (
                      <div key={i} className="flex items-center justify-between px-4 py-3 bg-red-500/5 border border-red-500/20 rounded-xl">
                        <div className="flex items-center gap-3">
                          <AlertTriangle className="w-4 h-4 text-red-400" />
                          <span className="text-sm font-semibold text-text-main">
                            NIVEL {alerta.nivel} — Año {alerta.anio || alerta.año}
                          </span>
                        </div>
                        <span className="text-sm font-bold text-red-300 bg-red-500/10 border border-red-500/20 px-3 py-1 rounded-full">
                          {alerta.conteo} ocurrencia{alerta.conteo !== 1 ? 's' : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Footer */}
              <div className="text-xs text-text-muted/60 pt-2 border-t border-border mt-6">
                📄 {data.nombre_archivo || 'Buró de Crédito'}
                {data.total_mops_nivel2_plus > 0 && (
                  <span className="ml-3">· Total MOPs nivel 2+: <strong>{data.total_mops_nivel2_plus}</strong></span>
                )}
              </div>
            </motion.div>
          )}
          </AnimatePresence>
        </div>
      </motion.div>
      </>
    )}
    </AnimatePresence>,
    document.body
  )
}

// ── ReviewModal ───────────────────────────────────────────────────────────────

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

  return createPortal(
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
              value={comentario} onChange={e => setComentario(e.target.value)} rows={3}
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
              ${estado === 'APROBADO' ? 'bg-green-600 hover:bg-green-500 shadow-[0_0_15px_rgba(22,163,74,0.3)]'
                : estado === 'RECHAZADO' ? 'bg-rose-600 hover:bg-rose-500 shadow-[0_0_15px_rgba(225,29,72,0.3)]'
                  : 'bg-amber-600 hover:bg-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.3)]'}
              ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}>
            {loading
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : estado === 'APROBADO' ? <CheckCircle2 className="w-4 h-4" />
                : estado === 'RECHAZADO' ? <XCircle className="w-4 h-4" />
                  : <Clock className="w-4 h-4" />}
            Confirmar {estado === 'APROBADO' ? 'Aprobación' : estado === 'RECHAZADO' ? 'Rechazo' : 'Revisión'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}

// ── AdminDashboard ────────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const [empresas, setEmpresas] = useState([])
  const [selectedEmpresa, setSelectedEmpresa] = useState(null)
  const [documentos, setDocumentos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [reviewDoc, setReviewDoc] = useState(null)
  const [downloading, setDownloading] = useState(false)
  const [collapsedSections, setCollapsedSections] = useState({})
  const [downloadingSection, setDownloadingSection] = useState(null)
  const [mopsEmpresaId, setMopsEmpresaId] = useState(null)
  const [pdfViewerDoc, setPdfViewerDoc] = useState(null)

  const toggleSection = title =>
    setCollapsedSections(prev => ({ ...prev, [title]: !prev[title] }))

  const handleDescargarSeccion = async (title, docs, e) => {
    e.stopPropagation()
    if (downloadingSection) return
    try {
      setDownloadingSection(title)
      const docIds = docs.map(d => d.id || d.documento_id).filter(Boolean)
      await api.descargarSeleccion(selectedEmpresa.id, docIds, `Seleccion_${title.replace(/[^a-z0-9]/gi, '_')}.zip`)
    } catch (err) {
      alert('Error al descargar: ' + err.message)
    } finally {
      setDownloadingSection(null)
    }
  }

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

  const loadDocumentos = useCallback(async empresaId => {
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
    if (!selectedEmpresa) loadEmpresas()
    else loadDocumentos(selectedEmpresa.id)
  }, [selectedEmpresa, loadEmpresas, loadDocumentos])

  const filteredEmpresas = empresas.filter(emp =>
    emp.nombre.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (emp.rfc && emp.rfc.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  // ── Vista: Lista de empresas ──────────────────────────────────────────────
  if (!selectedEmpresa) {
    return (
      <main className="max-w-6xl w-full mx-auto px-6 py-8 space-y-6 flex-1 animate-fade-in">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <h2 className="text-sm font-bold text-text-muted uppercase tracking-wider flex items-center gap-2">
            <Building2 className="w-4 h-4 text-primary-400" /> Directorio de Empresas
          </h2>
          <div className="flex items-center gap-3 w-full md:w-auto">
            <button
              onClick={loadEmpresas} disabled={loading}
              className={`p-2.5 bg-surface border border-border hover:border-primary-500/50 rounded-xl text-text-muted hover:text-primary-400 transition-colors shadow-sm flex-shrink-0 ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
              title="Actualizar directorio"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-primary-400' : ''}`} />
            </button>
            <div className="relative flex-1 md:w-64">
              <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text" placeholder="Buscar por nombre o RFC..."
                value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                className="bg-surface border border-border rounded-xl py-2 pl-9 pr-4 text-sm focus:outline-none focus:border-primary-500/50 w-full text-text-main"
              />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center p-12 text-text-muted">
            <Loader2 className="w-8 h-8 animate-spin text-primary-500 mb-3" />
            <p>Cargando empresas...</p>
          </div>
        ) : error ? (
          <div className="bg-rose-500/10 border border-rose-500/30 text-rose-400 p-4 rounded-xl font-semibold">⚠️ {error}</div>
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
                    Ver Expediente →
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    )
  }

  // ── Vista: Documentos de la empresa ──────────────────────────────────────

  const renderTable = (docs, title) => {
    if (docs.length === 0) return null
    return (
      <div className="mb-6 bg-card border border-border rounded-xl shadow-sm transition-all">
        <div
          className="flex items-center justify-between px-6 py-4 cursor-pointer hover:bg-surface/50 border-b border-border transition-colors"
          onClick={() => toggleSection(title)}
        >
          <h3 className="text-sm font-bold text-primary-400 uppercase tracking-wider mb-0 flex items-center gap-2">
            <motion.div animate={{ rotate: collapsedSections[title] ? 0 : 180 }} transition={{ duration: 0.3 }}>
              <ChevronDown className="w-4 h-4" />
            </motion.div>
            {title}
          </h3>
          <button
            onClick={e => handleDescargarSeccion(title, docs, e)}
            disabled={downloadingSection === title}
            className="inline-flex items-center gap-2 px-3 py-1.5 bg-primary-500/10 hover:bg-primary-500/20 text-primary-400 border border-primary-500/30 rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
          >
            {downloadingSection === title
              ? <><Loader2 className="w-3 h-3 animate-spin" /> Descargando...</>
              : <><Download className="w-3 h-3" /> Descargar Sección</>}
          </button>
        </div>

        <AnimatePresence initial={false}>
          {!collapsedSections[title] && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: 'easeInOut' }}
              className="overflow-hidden"
            >
              <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-surface/50 border-b border-border text-xs uppercase text-text-muted font-bold tracking-wider">
                <tr>
                  <th className="px-6 py-4">Documento</th>
                  <th className="px-6 py-4">Archivo</th>
                  <th className="px-6 py-4">Subido En</th>
                  <th className="px-6 py-4">Estado</th>
                  <th className="px-6 py-4">Descarga</th>
                  <th className="px-6 py-4 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {docs.map(doc => {
                  const cfg = ESTADO_CONFIG[doc.estado] || ESTADO_CONFIG.FALTANTE
                  const esPendiente = doc.estado === 'PENDIENTE'

                  let estadoDescarga
                  if (doc.estado === 'FALTANTE') {
                    estadoDescarga = { label: 'Falta subir', color: 'text-slate-600 italic' }
                  } else if (!doc.descargado) {
                    estadoDescarga = { label: 'Nuevo (Falta descargar)', color: 'text-emerald-400 font-bold' }
                  } else if (doc.subido_en && doc.descargado_en && new Date(doc.subido_en) > new Date(doc.descargado_en)) {
                    estadoDescarga = { label: 'Actualizado (Falta descargar)', color: 'text-amber-400 font-bold' }
                  } else {
                    estadoDescarga = { label: 'Descargado', color: 'text-slate-400' }
                  }

                  return (
                    <tr key={doc.id || doc.tipo_documento} className="hover:bg-surface/20 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-text-main text-[13px] leading-tight">
                          {doc.nombre_esperado || doc.tipo_documento}
                        </div>
                        {doc.nombre_carpeta && (
                          <div className="text-[10px] text-primary-400 font-bold mt-1 uppercase tracking-widest bg-primary-500/10 border border-primary-500/20 px-2 py-0.5 rounded inline-block">
                            📁 {doc.nombre_carpeta}
                          </div>
                        )}
                        {doc.tipo_documento === 'opinion_cumplimiento' && doc.comentario_admin?.startsWith('[SISTEMA] OPC:') && (() => {
                          const sentido = doc.comentario_admin.replace('[SISTEMA] OPC:', '').trim()
                          return (
                            <button 
                              onClick={(e) => { e.stopPropagation(); setPdfViewerDoc({ empresaId: selectedEmpresa.id, docId: doc.id }) }}
                              className={`text-[10px] font-bold mt-1 px-2 py-0.5 rounded inline-block border hover:opacity-80 transition-opacity cursor-pointer ${sentido === 'POSITIVO'
                                ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30'
                                : 'text-red-300 bg-red-500/10 border-red-500/30'
                              }`}>
                              {sentido === 'POSITIVO' ? '✅' : '❌'} {sentido}
                            </button>
                          )
                        })()}
                        {/* Botón Ver MOPs — solo para Buró de Crédito con archivo */}
                        {doc.tipo_documento === 'buro_credito' && doc.estado !== 'FALTANTE' && (
                          <div className="flex items-center">
                            <button
                              onClick={e => { e.stopPropagation(); setMopsEmpresaId(selectedEmpresa.id) }}
                              className="mt-1.5 inline-flex items-center gap-1.5 px-2.5 py-1 bg-violet-500/10 hover:bg-violet-500/20 text-violet-400 border border-violet-500/30 rounded-lg text-[10px] font-bold transition-colors"
                            >
                              <BarChart2 className="w-3 h-3" />
                              Ver MOPs
                            </button>
                            <MopsBadge empresaId={selectedEmpresa.id} />
                          </div>
                        )}
                      </td>

                      <td className="px-6 py-4 text-text-muted text-xs truncate max-w-[180px]" title={doc.nombre_archivo}>
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

                      <td className="px-6 py-4 text-[11px]">
                        <div className="flex items-center gap-2">
                          <span className={estadoDescarga.color}>{estadoDescarga.label}</span>
                          {doc.estado !== 'FALTANTE' && doc.id && (
                            <button
                              onClick={async e => {
                                e.stopPropagation()
                                const btn = e.currentTarget
                                btn.disabled = true
                                btn.style.opacity = '0.5'
                                try {
                                  await api.descargarDocumentoIndividual(selectedEmpresa.id, doc.id, doc.grupo === 'representante')
                                  loadDocumentos(selectedEmpresa.id)
                                } catch (err) {
                                  alert('Error al descargar: ' + err.message)
                                } finally {
                                  btn.disabled = false
                                  btn.style.opacity = '1'
                                }
                              }}
                              className="p-1 hover:bg-primary-500/20 text-primary-400 rounded transition-colors flex-shrink-0"
                              title="Descargar documento"
                            >
                              <Download className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
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
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    )
  }

  const docsLegales = documentos.filter(d => d.grupo === 'legal')
  const docsEdosCuenta = documentos.filter(d => d.grupo === 'estados_cuenta')
  const docsFinancieros = documentos.filter(d => d.grupo === 'financieros')
  const docsDeclaraciones = documentos.filter(d => d.grupo === 'declaraciones')
  const docsVigentes = documentos.filter(d => d.grupo === 'vigentes')
  const docsRep = documentos.filter(d => d.grupo === 'representante')
  const docsOtros = documentos.filter(d => d.grupo === 'otros')

  const banks = {}
  docsEdosCuenta.forEach(d => {
    const b = d.nombre_carpeta || 'Otros / General'
    if (!banks[b]) banks[b] = []
    banks[b].push(d)
  })

  return (
    <main className="max-w-[1600px] w-full mx-auto px-6 py-8 flex flex-col xl:flex-row gap-8 flex-1 animate-fade-in items-start">
      
      {/* Sidebar de Resumen (Izquierda) */}
      <AdminCompanySummary empresa={selectedEmpresa} documentos={documentos} />

      {/* Contenido Principal (Derecha) */}
      <div className="flex-1 space-y-6 min-w-0 w-full">

      {/* Header */}
      <div className="flex items-center justify-between">
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
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadDocumentos(selectedEmpresa.id)} disabled={loading}
            className={`p-2.5 bg-surface border border-border hover:border-primary-500/50 rounded-xl text-text-muted hover:text-primary-400 transition-colors shadow-sm flex-shrink-0 ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
            title="Actualizar expediente"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-primary-400' : ''}`} />
          </button>
          <button
            onClick={async () => {
              setDownloading(true)
              try {
                await api.descargarTodosDocumentos(selectedEmpresa.id)
                loadDocumentos(selectedEmpresa.id)
              } catch (err) {
                alert(`Error al descargar: ${err.message}`)
              } finally {
                setDownloading(false)
              }
            }}
            disabled={downloading || documentos.every(d => d.estado === 'FALTANTE')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold transition-all
              ${downloading ? 'opacity-50 cursor-not-allowed' : ''}
              bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.2)]`}
          >
            {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            <span className="hidden md:inline">{downloading ? 'Descargando...' : 'Descargar Todo (ZIP)'}</span>
            <span className="md:hidden">{downloading ? '...' : 'ZIP'}</span>
          </button>
        </div>
      </div>

      {/* Contenido */}
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
        <div className="space-y-2">
          {renderTable(docsRep, '1. Representante Legal')}
          {renderTable(docsLegales, '2.1. Actas / Legales')}
          {renderTable(docsFinancieros, '2.2. Estados Financieros')}
          {Object.entries(banks).map(([bank, items]) => (
            <div key={bank}>
              {renderTable(items, `2.3. Estados de Cuenta${bank !== 'Otros / General' ? ` — ${bank}` : ''}`)}
            </div>
          ))}
          {renderTable(docsDeclaraciones, '2.5. Declaraciones')}
          {renderTable(docsVigentes, '2.6. Generales / Vigentes')}
          {renderTable(docsOtros, '2.7. Otros Documentos')}
        </div>
      )}
      </div>

      {/* Modal Revisión */}
      {reviewDoc && (
        <ReviewModal
          doc={{ ...reviewDoc, empresa_nombre: selectedEmpresa.nombre }}
          onClose={() => setReviewDoc(null)}
          onSuccess={() => {
            setReviewDoc(null)
            loadDocumentos(selectedEmpresa.id)
          }}
        />
      )}

      {/* MOP Drawer */}
      <MopsDrawer
        isOpen={!!mopsEmpresaId}
        empresaId={mopsEmpresaId}
        onClose={() => setMopsEmpresaId(null)}
      />

      {/* PDF Drawer */}
      <PdfDrawer
        isOpen={!!pdfViewerDoc}
        empresaId={pdfViewerDoc?.empresaId}
        docId={pdfViewerDoc?.docId}
        onClose={() => setPdfViewerDoc(null)}
      />
    </main>
  )
}
