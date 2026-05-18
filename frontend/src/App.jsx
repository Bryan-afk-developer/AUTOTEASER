import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { UploadCloud, CheckCircle2, XCircle, FileText, Loader2, Trash2, AlertTriangle, Download, RefreshCw, FileSpreadsheet } from 'lucide-react'

// Use environment variable if available (e.g. Render), otherwise default to localhost:8000 where backend is running
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [isOnline, setIsOnline] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [toast, setToast] = useState({ show: false, msg: '', isError: false })
  
  const [documents, setDocuments] = useState([])
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [batchOutput, setBatchOutput] = useState(null)
  
  const fileInputRef = useRef(null)

  // Health check & fetch templates
  useEffect(() => {
    const checkHealth = async () => {
      try {
        await axios.get(`${API_BASE}/api/health`)
        setIsOnline(true)
      } catch {
        setIsOnline(false)
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 10000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/templates`)
        setTemplates(res.data.templates || [])
        if (res.data.templates?.length > 0) {
          setSelectedTemplate(res.data.templates[0].name)
        }
      } catch (e) {
        console.error('Error fetching templates:', e)
      }
    }
    fetchTemplates()
  }, [])

  const showToast = (msg, isError = false) => {
    setToast({ show: true, msg, isError })
    setTimeout(() => setToast(prev => ({ ...prev, show: false })), 3000)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) handleUploadBatch(files)
  }

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files)
    if (files.length > 0) handleUploadBatch(files)
  }

  const handleUploadBatch = async (files) => {
    const validFiles = files.filter(f => f.name.toLowerCase().endsWith('.pdf'))
    if (validFiles.length === 0) {
      showToast('Solo se aceptan archivos PDF', true)
      return
    }

    showToast(`Subiendo ${validFiles.length} documento(s)...`)

    for (const file of validFiles) {
      const formData = new FormData()
      formData.append('file', file)

      try {
        const res = await axios.post(`${API_BASE}/api/upload-pdf`, formData)
        const newDoc = res.data
        setDocuments(prev => [...prev, newDoc])
        
        const bank = newDoc.detected_bank?.toLowerCase()
        if (bank === 'hsbc') {
          alert(`El archivo "${file.name}" contiene documentos HSBC, necesita revisión humana.`)
        } else if (!bank || bank === 'desconocido' || bank === 'ninguno') {
          alert(`Banco no registrado o desconocido en el archivo "${file.name}". Por favor verifica el formato.`)
        }
      } catch (err) {
        showToast(`Error al subir ${file.name}: ${err.response?.data?.detail || err.message}`, true)
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
    showToast('Subida completada')
  }

  const handleProcessAll = async () => {
    const unprocessed = documents.filter(d => d.status === 'uploaded' && d.detected_bank && d.detected_bank.toLowerCase() !== 'desconocido')
    if (unprocessed.length === 0) {
      showToast('No hay documentos pendientes de procesar con banco válido', true)
      return
    }

    setIsLoading(true)
    showToast(`Procesando ${unprocessed.length} documento(s)...`)

    for (const doc of unprocessed) {
      try {
        const res = await axios.post(`${API_BASE}/api/process/${doc.id}`)
        setDocuments(prev => prev.map(item => item.id === doc.id ? {
          ...item,
          status: res.data.status,
          parsed_data: res.data.data
        } : item))
      } catch (err) {
        setDocuments(prev => prev.map(item => item.id === doc.id ? { ...item, status: 'error' } : item))
        showToast(`Error al procesar ${doc.file_name}`, true)
      }
    }
    setIsLoading(false)
    showToast('Procesamiento completado')
  }

  const handleGenerateBatchExcel = async () => {
    const processedDocs = documents.filter(d => d.parsed_data)
    if (processedDocs.length === 0) {
      showToast('No hay documentos procesados para generar el Excel', true)
      return
    }
    if (!selectedTemplate) {
      showToast('Selecciona una plantilla primero', true)
      return
    }

    setIsLoading(true)
    showToast('Generando Excel consolidado...')

    try {
      const docIds = processedDocs.map(d => d.id)
      const res = await axios.post(`${API_BASE}/api/fill-template-batch`, {
        doc_ids: docIds,
        template_name: selectedTemplate
      })
      setBatchOutput(res.data)
      showToast('¡Excel consolidado generado con éxito!')
    } catch (err) {
      showToast(err.response?.data?.detail || 'Error al generar Excel en lote', true)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeleteDoc = async (id) => {
    try {
      await axios.delete(`${API_BASE}/api/documents/${id}`)
    } catch (e) {
      console.error(e)
    }
    setDocuments(prev => prev.filter(d => d.id !== id))
    showToast('Documento eliminado')
  }

  const handleClearAll = () => {
    documents.forEach(d => {
      axios.delete(`${API_BASE}/api/documents/${d.id}`).catch(() => {})
    })
    setDocuments([])
    setBatchOutput(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
    showToast('Todos los documentos limpiados')
  }

  const hasHsbc = documents.some(d => d.detected_bank?.toLowerCase() === 'hsbc')
  const hasUnrecognized = documents.some(d => !d.detected_bank || d.detected_bank?.toLowerCase() === 'desconocido')

  return (
    <div className="min-h-screen bg-background text-text-main font-sans pb-20 selection:bg-primary-500/30">
      
      {/* Header */}
      <header className="glass-header flex items-center justify-between px-8 py-4 mb-10">
        <div className="flex items-center gap-3">
          <div className="h-20 w-auto flex items-center justify-center">
            <img src="/Logo.webp" alt="Logo" className="h-full w-auto object-contain drop-shadow-[0_0_15px_rgba(230,57,70,0.3)]" />
          </div>
          <h1 className="text-[22px] font-bold tracking-tight">
            Auto<span className="text-primary-500">Teaser</span>
          </h1>
        </div>
        <div className="flex items-center gap-2 bg-surface px-3 py-1.5 rounded-full border border-border">
          <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]' : 'bg-primary-500'}`}></span>
          <span className="text-xs text-text-muted font-medium">{isOnline ? 'Conectado' : 'Desconectado'}</span>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-6 space-y-8">
        
        {/* Upload Zone (Supports Multiple Files) */}
        <div 
          className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-300
            ${isDragging ? 'border-primary-500 bg-primary-500/5 shadow-glow' : 'border-border hover:border-border-hover bg-surface hover:bg-surface/80'}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <UploadCloud className={`w-14 h-14 mx-auto mb-4 transition-colors ${isDragging ? 'text-primary-500' : 'text-text-muted'}`} />
          <h3 className="text-xl font-semibold text-text-main mb-2">Sube uno o múltiples estados de cuenta</h3>
          <p className="text-sm text-text-muted max-w-md mx-auto">Arrastra tus archivos PDF aquí o haz clic para explorar. Puedes seleccionar varios archivos a la vez.</p>
          <input 
            type="file" 
            ref={fileInputRef} 
            className="hidden" 
            accept=".pdf" 
            multiple
            onChange={handleFileSelect} 
          />
        </div>

        {/* Global Warning Banners */}
        {hasHsbc && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-5 flex items-start gap-4 text-amber-200 shadow-glow animate-fade-in">
            <AlertTriangle className="w-6 h-6 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <h3 className="text-base font-semibold text-amber-300">Atención: Documento(s) HSBC detectado(s)</h3>
              <p className="text-sm text-amber-200/80 mt-1">
                Los estados de cuenta de HSBC cuentan con protección avanzada y utilizan IA (OCR) para su lectura. Por favor, realiza una revisión humana de los datos extraídos para confirmar su exactitud.
              </p>
            </div>
          </div>
        )}

        {hasUnrecognized && (
          <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-5 flex items-start gap-4 text-rose-200 shadow-glow animate-fade-in">
            <AlertTriangle className="w-6 h-6 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <h3 className="text-base font-semibold text-rose-300">Aviso: Banco(s) no registrado(s) detectado(s)</h3>
              <p className="text-sm text-rose-200/80 mt-1">
                Algunos documentos subidos pertenecen a bancos no registrados en el sistema o tienen un formato desconocido. Estos archivos no podrán ser procesados automáticamente.
              </p>
            </div>
          </div>
        )}

        {/* Document List & Batch Actions */}
        {documents.length > 0 && (
          <div className="space-y-6 animate-fade-in">
            
            {/* Action Bar */}
            <div className="glass-panel p-6 rounded-2xl flex flex-wrap items-center justify-between gap-4 border border-border bg-surface/40 backdrop-blur-md">
              <div className="flex items-center gap-4 flex-wrap">
                <button 
                  onClick={handleProcessAll}
                  disabled={isLoading}
                  className="bg-gradient-to-r from-primary-500 to-primary-600 hover:to-primary-500 text-white font-semibold py-3 px-6 rounded-xl shadow-glow hover:shadow-glow-strong disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2 text-sm"
                >
                  {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  Procesar Todos los Datos
                </button>

                <div className="flex items-center gap-2 bg-background/50 px-4 py-2 rounded-xl border border-border">
                  <FileSpreadsheet className="w-4 h-4 text-primary-500" />
                  <span className="text-xs font-medium text-text-muted">Plantilla:</span>
                  <select 
                    value={selectedTemplate} 
                    onChange={e => setSelectedTemplate(e.target.value)}
                    className="bg-transparent text-sm font-semibold text-text-main focus:outline-none cursor-pointer pr-2"
                  >
                    {templates.map(t => (
                      <option key={t.name} value={t.name} className="bg-surface text-text-main">{t.name}</option>
                    ))}
                  </select>
                </div>

                <button 
                  onClick={handleGenerateBatchExcel}
                  disabled={isLoading || documents.filter(d => d.parsed_data).length === 0}
                  className="bg-green-600 hover:bg-green-500 text-white font-semibold py-3 px-6 rounded-xl shadow-[0_0_15px_rgba(22,163,74,0.4)] hover:shadow-[0_0_20px_rgba(22,163,74,0.6)] disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2 text-sm"
                >
                  {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4" />}
                  Generar Excel Consolidado
                </button>
              </div>

              <button 
                onClick={handleClearAll}
                className="text-text-muted hover:text-rose-400 font-medium py-2 px-4 rounded-xl hover:bg-rose-500/10 transition-colors flex items-center gap-2 text-sm"
              >
                <Trash2 className="w-4 h-4" />
                Limpiar Todos
              </button>
            </div>

            {/* Batch Download Card */}
            {batchOutput && (
              <div className="bg-gradient-to-r from-green-500/10 to-emerald-500/10 border-2 border-green-500/30 rounded-2xl p-6 flex items-center justify-between shadow-glow animate-fade-in">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-green-500/20 rounded-xl border border-green-500/30 text-green-400">
                    <Download className="w-8 h-8" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-green-300">¡Archivo Excel Consolidado Listo!</h3>
                    <p className="text-sm text-green-200/80 mt-0.5">Se han vaciado todos los datos procesados en la plantilla seleccionada.</p>
                  </div>
                </div>
                <a 
                  href={`${API_BASE}${batchOutput.download_url}`}
                  download
                  className="bg-green-500 hover:bg-green-400 text-white font-bold py-3 px-8 rounded-xl shadow-[0_0_20px_rgba(34,197,94,0.5)] transition-all flex items-center gap-2"
                >
                  <Download className="w-5 h-5" />
                  Descargar Excel
                </a>
              </div>
            )}

            {/* Documents Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {documents.map((doc) => (
                <div key={doc.id} className="bg-card border border-border rounded-2xl overflow-hidden hover:border-gray-700 transition-all flex flex-col justify-between shadow-sm hover:shadow-md">
                  <div>
                    <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-surface/50">
                      <div className="flex items-center gap-2.5 overflow-hidden pr-2">
                        <FileText className="w-4 h-4 text-primary-500 shrink-0" />
                        <h2 className="text-sm font-semibold text-text-main truncate">{doc.file_name}</h2>
                      </div>
                      <button 
                        onClick={() => handleDeleteDoc(doc.id)}
                        className="p-1.5 text-text-muted hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors shrink-0"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    
                    <div className="p-5 space-y-3.5">
                      <div className="flex justify-between items-center pb-3 border-b border-white/5">
                        <span className="text-sm text-text-muted">Banco detectado</span>
                        <span className={`text-xs font-bold uppercase tracking-wider px-3 py-1 rounded-full shadow-sm
                          ${doc.detected_bank?.toLowerCase() === 'hsbc' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' :
                            !doc.detected_bank || doc.detected_bank?.toLowerCase() === 'desconocido' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' :
                            'bg-gradient-to-r from-primary-500 to-primary-600 text-white shadow-glow'}`}
                        >
                          {doc.detected_bank || 'Desconocido'}
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-text-muted">Estado</span>
                        <span className={`text-xs font-bold px-3 py-1 rounded-full border 
                          ${doc.status === 'uploaded' ? 'border-blue-500/30 text-blue-400 bg-blue-500/10' : 
                            doc.status === 'processed' ? 'border-green-500/30 text-green-400 bg-green-500/10' : 
                            'border-rose-500/30 text-rose-400 bg-rose-500/10'}`}>
                          {doc.status === 'uploaded' ? 'Extraído' : 
                           doc.status === 'processed' ? 'Procesado' : 'Error'}
                        </span>
                      </div>

                      {/* Parsed Data Preview */}
                      {doc.parsed_data && (
                        <div className="mt-4 pt-4 border-t border-white/5 bg-surface/30 p-3 rounded-xl">
                          <div className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Datos extraídos:</div>
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div><span className="text-text-muted">Cuenta:</span> <span className="font-medium text-primary-400">{doc.parsed_data.account_name}</span></div>
                            <div><span className="text-text-muted">Periodo:</span> <span className="font-medium text-primary-400">{doc.parsed_data.month} {doc.parsed_data.year}</span></div>
                            <div><span className="text-text-muted">Depósitos:</span> <span className="font-medium text-text-main">${doc.parsed_data.deposits?.toLocaleString('en-US', {minimumFractionDigits: 2})}</span></div>
                            <div><span className="text-text-muted">Promedio:</span> <span className="font-medium text-text-main">${doc.parsed_data.average_balance?.toLocaleString('en-US', {minimumFractionDigits: 2})}</span></div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

          </div>
        )}
      </main>

      {/* Toast */}
      <div className={`fixed bottom-8 left-1/2 -translate-x-1/2 px-6 py-3 rounded-xl border shadow-2xl transition-all duration-300 z-50 flex items-center gap-2.5 backdrop-blur-md
        ${toast.show ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10 pointer-events-none'}
        ${toast.isError ? 'bg-rose-500/90 border-rose-500 text-white shadow-[0_0_20px_rgba(244,63,94,0.4)]' : 'bg-surface/90 border-border text-text-main shadow-lg'}`}
      >
        {toast.isError ? <XCircle className="w-4 h-4 text-white" /> : <CheckCircle2 className="w-4 h-4 text-green-400" />}
        <span className="text-sm font-semibold">{toast.msg}</span>
      </div>

    </div>
  )
}

export default App
