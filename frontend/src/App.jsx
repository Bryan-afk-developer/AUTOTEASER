import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { UploadCloud, CheckCircle2, XCircle, FileText, Loader2, Trash2, AlertTriangle, Download, Eye, EyeOff, FileSpreadsheet, X } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const MONTH_LABELS = { nov: 'Nov', dic: 'Dic', ene: 'Ene', feb: 'Feb', mar: 'Mar', abr: 'Abr', may: 'May' }

function fmt(n) {
  if (n == null) return '—'
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function App() {
  const [isOnline, setIsOnline] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [toast, setToast] = useState({ show: false, msg: '', isError: false })
  const [documents, setDocuments] = useState([])
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [batchOutput, setBatchOutput] = useState(null)
  const [preview, setPreview] = useState(null)
  const [showPreview, setShowPreview] = useState(false)
  const fileInputRef = useRef(null)

  // Health check
  useEffect(() => {
    const check = async () => {
      try { await axios.get(`${API_BASE}/api/health`); setIsOnline(true) }
      catch { setIsOnline(false) }
    }
    check()
    const i = setInterval(check, 10000)
    return () => clearInterval(i)
  }, [])

  // Fetch templates
  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/api/templates`)
        setTemplates(r.data.templates || [])
        if (r.data.templates?.length > 0) setSelectedTemplate(r.data.templates[0].name)
      } catch {}
    })()
  }, [])

  const showToast = (msg, isError = false) => {
    setToast({ show: true, msg, isError })
    setTimeout(() => setToast(p => ({ ...p, show: false })), 3500)
  }

  // ─── Upload ───
  const handleDrop = (e) => { e.preventDefault(); setIsDragging(false); handleUploadBatch(Array.from(e.dataTransfer.files)) }
  const handleFileSelect = (e) => { handleUploadBatch(Array.from(e.target.files)) }

  const handleUploadBatch = async (files) => {
    const pdfs = files.filter(f => f.name.toLowerCase().endsWith('.pdf'))
    if (!pdfs.length) return showToast('Solo se aceptan archivos PDF', true)
    showToast(`Subiendo ${pdfs.length} PDF(s)...`)
    for (const file of pdfs) {
      const fd = new FormData(); fd.append('file', file)
      try {
        const r = await axios.post(`${API_BASE}/api/upload-pdf`, fd)
        setDocuments(prev => [...prev, r.data])
        const bank = r.data.detected_bank?.toLowerCase()
        if (bank === 'hsbc') alert(`"${file.name}" es de HSBC — necesita revisión humana.`)
        else if (!bank || bank === 'desconocido') alert(`Banco no reconocido en "${file.name}".`)
      } catch (err) { showToast(`Error: ${err.response?.data?.detail || err.message}`, true) }
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
    showToast(`${pdfs.length} archivo(s) subidos`)
  }

  // ─── Process ───
  const handleProcessAll = async () => {
    const pending = documents.filter(d => d.status === 'uploaded' && d.detected_bank)
    if (!pending.length) return showToast('Nada que procesar', true)
    setIsLoading(true); showToast(`Procesando ${pending.length} doc(s)...`)
    for (const doc of pending) {
      try {
        const r = await axios.post(`${API_BASE}/api/process/${doc.id}`)
        setDocuments(prev => prev.map(d => d.id === doc.id ? { ...d, status: r.data.status, parsed_data: r.data.data } : d))
      } catch { setDocuments(prev => prev.map(d => d.id === doc.id ? { ...d, status: 'error' } : d)) }
    }
    setIsLoading(false); showToast('Procesamiento completado')
  }

  // ─── Preview ───
  const handlePreview = async () => {
    const processed = documents.filter(d => d.parsed_data)
    if (!processed.length) return showToast('No hay datos procesados para previsualizar', true)
    setIsLoading(true)
    try {
      const r = await axios.post(`${API_BASE}/api/preview-batch`, { doc_ids: processed.map(d => d.id), template_name: selectedTemplate })
      setPreview(r.data); setShowPreview(true)
    } catch (err) { showToast(err.response?.data?.detail || 'Error en preview', true) }
    finally { setIsLoading(false) }
  }

  // ─── Generate Excel ───
  const handleGenerate = async () => {
    const processed = documents.filter(d => d.parsed_data)
    if (!processed.length) return showToast('No hay datos procesados', true)
    setIsLoading(true); showToast('Generando Excel...')
    try {
      const r = await axios.post(`${API_BASE}/api/fill-template-batch`, { doc_ids: processed.map(d => d.id), template_name: selectedTemplate })
      setBatchOutput(r.data); showToast('¡Excel generado!')
    } catch (err) { showToast(err.response?.data?.detail || 'Error', true) }
    finally { setIsLoading(false) }
  }

  const handleDeleteDoc = (id) => { axios.delete(`${API_BASE}/api/documents/${id}`).catch(() => {}); setDocuments(p => p.filter(d => d.id !== id)) }
  const handleClearAll = () => { documents.forEach(d => axios.delete(`${API_BASE}/api/documents/${d.id}`).catch(() => {})); setDocuments([]); setBatchOutput(null); setPreview(null); setShowPreview(false) }

  const uploaded = documents.filter(d => d.status === 'uploaded').length
  const processed = documents.filter(d => d.parsed_data).length
  const errors = documents.filter(d => d.status === 'error').length
  const hasHsbc = documents.some(d => d.detected_bank?.toLowerCase() === 'hsbc')

  return (
    <div className="min-h-screen bg-background text-text-main font-sans selection:bg-primary-500/30">

      {/* ── Header ── */}
      <header className="glass-header flex items-center justify-between px-6 py-3 sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <img src="/Logo.webp" alt="Logo" className="h-14 w-auto object-contain drop-shadow-[0_0_12px_rgba(230,57,70,0.3)]" />
          <h1 className="text-lg font-bold tracking-tight">Auto<span className="text-primary-500">Teaser</span></h1>
        </div>
        <div className="flex items-center gap-4">
          {documents.length > 0 && (
            <div className="flex items-center gap-3 text-xs font-medium">
              <span className="text-blue-400">{uploaded} pendiente{uploaded !== 1 && 's'}</span>
              <span className="text-green-400">{processed} procesado{processed !== 1 && 's'}</span>
              {errors > 0 && <span className="text-rose-400">{errors} error{errors !== 1 && 'es'}</span>}
            </div>
          )}
          <div className="flex items-center gap-1.5 bg-surface px-2.5 py-1 rounded-full border border-border">
            <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.5)]' : 'bg-rose-500'}`}></span>
            <span className="text-[11px] text-text-muted font-medium">{isOnline ? 'Online' : 'Offline'}</span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">

        {/* ── Drop Zone ── */}
        <div
          className={`relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-300
            ${isDragging ? 'border-primary-500 bg-primary-500/5 shadow-glow scale-[1.01]' : 'border-border hover:border-primary-500/40 bg-surface/40'}`}
          onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <UploadCloud className={`w-8 h-8 mx-auto mb-2 ${isDragging ? 'text-primary-500' : 'text-text-muted'}`} />
          <p className="text-sm font-semibold">Arrastra PDFs de estados de cuenta aquí</p>
          <p className="text-xs text-text-muted mt-0.5">o haz clic para seleccionar · múltiples archivos permitidos</p>
          <input type="file" ref={fileInputRef} className="hidden" accept=".pdf" multiple onChange={handleFileSelect} />
        </div>

        {/* ── HSBC Warning ── */}
        {hasHsbc && (
          <div className="bg-amber-500/10 border border-amber-500/25 rounded-xl p-4 flex items-start gap-3 animate-fade-in">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-amber-300">Documentos HSBC detectados</p>
              <p className="text-xs text-amber-200/70 mt-0.5">HSBC usa protección de copia. Los datos se extraen con IA y requieren verificación humana.</p>
            </div>
          </div>
        )}

        {/* ── Document Cards ── */}
        {documents.length > 0 && (
          <>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-text-muted uppercase tracking-wider">Documentos ({documents.length})</h2>
              <button onClick={handleClearAll} className="text-xs text-text-muted hover:text-rose-400 transition-colors flex items-center gap-1">
                <Trash2 className="w-3 h-3" /> Limpiar todos
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {documents.map(doc => (
                <div key={doc.id} className="bg-card border border-border rounded-xl p-4 flex flex-col gap-2 hover:border-gray-700 transition-all group">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="w-4 h-4 text-primary-500 shrink-0" />
                      <span className="text-sm font-medium truncate">{doc.file_name}</span>
                    </div>
                    <button onClick={() => handleDeleteDoc(doc.id)} className="opacity-0 group-hover:opacity-100 p-1 text-text-muted hover:text-rose-400 transition-all">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="flex items-center justify-between mt-auto">
                    <span className={`text-[11px] font-bold uppercase px-2 py-0.5 rounded-full
                      ${doc.detected_bank?.toLowerCase() === 'hsbc' ? 'bg-amber-500/15 text-amber-300' :
                        !doc.detected_bank ? 'bg-rose-500/15 text-rose-300' :
                        'bg-primary-500/15 text-primary-400'}`}>
                      {doc.detected_bank || '???'}
                    </span>
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full
                      ${doc.status === 'uploaded' ? 'bg-blue-500/10 text-blue-400' :
                        doc.status === 'processed' ? 'bg-green-500/10 text-green-400' :
                        'bg-rose-500/10 text-rose-400'}`}>
                      {doc.status === 'uploaded' ? '● Subido' : doc.status === 'processed' ? '✓ Procesado' : '✗ Error'}
                    </span>
                  </div>
                  {doc.parsed_data && (
                    <div className="text-[11px] text-text-muted bg-surface/50 rounded-lg p-2 mt-1 grid grid-cols-2 gap-x-3 gap-y-1">
                      <span>Cuenta: <b className="text-primary-400">{doc.parsed_data.account_name}</b></span>
                      <span>Periodo: <b className="text-text-main">{doc.parsed_data.month}/{doc.parsed_data.year}</b></span>
                      <span>Depósitos: <b className="text-text-main">{fmt(doc.parsed_data.deposits)}</b></span>
                      <span>Promedio: <b className="text-text-main">{fmt(doc.parsed_data.average_balance)}</b></span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        {/* ── Action Bar ── */}
        {documents.length > 0 && (
          <div className="bg-surface/60 backdrop-blur-lg border border-border rounded-2xl p-5 flex flex-wrap items-center gap-3 sticky bottom-4 z-30 shadow-2xl">
            {/* Process */}
            <button onClick={handleProcessAll} disabled={isLoading || uploaded === 0}
              className="bg-gradient-to-r from-primary-500 to-primary-600 hover:brightness-110 text-white font-semibold py-2.5 px-5 rounded-xl shadow-glow disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-2 text-sm">
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              Procesar ({uploaded})
            </button>

            <div className="w-px h-8 bg-border" />

            {/* Template selector */}
            <div className="flex items-center gap-2 bg-background/50 px-3 py-2 rounded-xl border border-border">
              <FileSpreadsheet className="w-4 h-4 text-green-500" />
              <select value={selectedTemplate} onChange={e => setSelectedTemplate(e.target.value)}
                className="bg-transparent text-sm font-medium text-text-main focus:outline-none cursor-pointer">
                {templates.map(t => <option key={t.name} value={t.name} className="bg-surface">{t.name}</option>)}
              </select>
            </div>

            {/* Preview */}
            <button onClick={handlePreview} disabled={isLoading || processed === 0}
              className="bg-indigo-600/80 hover:bg-indigo-500 text-white font-semibold py-2.5 px-5 rounded-xl shadow-[0_0_12px_rgba(99,102,241,0.3)] disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-2 text-sm">
              <Eye className="w-4 h-4" />
              Preview
            </button>

            {/* Generate */}
            <button onClick={handleGenerate} disabled={isLoading || processed === 0}
              className="bg-green-600/80 hover:bg-green-500 text-white font-semibold py-2.5 px-5 rounded-xl shadow-[0_0_12px_rgba(34,197,94,0.3)] disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-2 text-sm">
              <Download className="w-4 h-4" />
              Generar Excel
            </button>

            {/* Download link */}
            {batchOutput && (
              <a href={`${API_BASE}${batchOutput.download_url}`} download
                className="ml-auto bg-emerald-500 hover:bg-emerald-400 text-white font-bold py-2.5 px-6 rounded-xl shadow-[0_0_20px_rgba(16,185,129,0.4)] transition-all flex items-center gap-2 text-sm animate-fade-in">
                <Download className="w-4 h-4" />
                Descargar .xlsx
              </a>
            )}
          </div>
        )}

        {/* ── Preview Modal ── */}
        {showPreview && preview && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-6 animate-fade-in" onClick={() => setShowPreview(false)}>
            <div className="bg-card border border-border rounded-2xl w-full max-w-6xl max-h-[85vh] overflow-hidden shadow-2xl flex flex-col" onClick={e => e.stopPropagation()}>
              {/* Modal Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface/50">
                <div className="flex items-center gap-3">
                  <Eye className="w-5 h-5 text-indigo-400" />
                  <h2 className="text-base font-bold">Preview del Excel — {preview.total_accounts} cuenta(s)</h2>
                </div>
                <button onClick={() => setShowPreview(false)} className="p-2 hover:bg-white/5 rounded-lg transition-colors">
                  <X className="w-5 h-5 text-text-muted" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="overflow-auto flex-1 p-6">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr>
                      <th className="text-left py-3 px-4 text-text-muted font-semibold text-xs uppercase tracking-wider sticky left-0 bg-card z-10 border-b border-border">Cuenta</th>
                      {preview.months_order.map(m => (
                        <th key={m} colSpan={2} className="text-center py-3 px-2 text-text-muted font-semibold text-xs uppercase tracking-wider border-b border-border">
                          {MONTH_LABELS[m] || m}
                        </th>
                      ))}
                    </tr>
                    <tr>
                      <th className="sticky left-0 bg-card z-10 border-b border-border"></th>
                      {preview.months_order.map(m => (
                        <>
                          <th key={m+'d'} className="text-right py-1.5 px-2 text-[10px] text-text-muted font-medium border-b border-border">Depósitos</th>
                          <th key={m+'b'} className="text-right py-1.5 px-2 text-[10px] text-text-muted font-medium border-b border-border border-r border-r-white/5">Saldo Prom.</th>
                        </>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.accounts.map((acct, i) => (
                      <tr key={acct.account_name} className={`${i % 2 === 0 ? 'bg-surface/20' : ''} hover:bg-primary-500/5 transition-colors`}>
                        <td className="py-2.5 px-4 font-bold text-primary-400 whitespace-nowrap sticky left-0 bg-card z-10 border-b border-white/5">{acct.account_name}</td>
                        {preview.months_order.map(m => {
                          const d = acct.months[m]
                          return (
                            <>
                              <td key={m+'d'} className={`py-2.5 px-2 text-right font-mono text-xs border-b border-white/5 ${d ? 'text-text-main' : 'text-text-muted/30'}`}>
                                {d ? fmt(d.deposits) : '—'}
                              </td>
                              <td key={m+'b'} className={`py-2.5 px-2 text-right font-mono text-xs border-b border-white/5 border-r border-r-white/5 ${d ? 'text-text-main' : 'text-text-muted/30'}`}>
                                {d ? fmt(d.average_balance) : '—'}
                              </td>
                            </>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>

                {preview.accounts.length === 0 && (
                  <div className="text-center py-12 text-text-muted">
                    <EyeOff className="w-8 h-8 mx-auto mb-3 opacity-30" />
                    <p>No hay datos para previsualizar</p>
                  </div>
                )}
              </div>

              {/* Modal Footer */}
              <div className="flex items-center justify-between px-6 py-3 border-t border-border bg-surface/30">
                <p className="text-xs text-text-muted">{preview.total_accounts} cuenta(s) · {preview.months_order.length} meses · Plantilla: {selectedTemplate}</p>
                <div className="flex gap-3">
                  <button onClick={() => setShowPreview(false)} className="text-sm text-text-muted hover:text-text-main px-4 py-2 rounded-lg transition-colors">Cerrar</button>
                  <button onClick={() => { setShowPreview(false); handleGenerate() }}
                    className="bg-green-600 hover:bg-green-500 text-white font-semibold text-sm py-2 px-5 rounded-xl flex items-center gap-2 transition-colors">
                    <Download className="w-4 h-4" />
                    Generar Excel
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── Toast ── */}
      <div className={`fixed bottom-6 left-1/2 -translate-x-1/2 px-5 py-2.5 rounded-xl border shadow-2xl transition-all duration-300 z-[60] flex items-center gap-2 backdrop-blur-md
        ${toast.show ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8 pointer-events-none'}
        ${toast.isError ? 'bg-rose-500/90 border-rose-400 text-white' : 'bg-surface/90 border-border text-text-main'}`}>
        {toast.isError ? <XCircle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4 text-green-400" />}
        <span className="text-sm font-medium">{toast.msg}</span>
      </div>
    </div>
  )
}

export default App
