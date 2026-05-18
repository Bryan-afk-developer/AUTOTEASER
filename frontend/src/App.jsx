import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { UploadCloud, CheckCircle2, XCircle, FileText, Loader2, Trash2 } from 'lucide-react'

// Use environment variable if available (e.g. Render), otherwise default to localhost:8000 where backend is running
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [isOnline, setIsOnline] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [toast, setToast] = useState({ show: false, msg: '', isError: false })
  
  const [document, setDocument] = useState(null)
  
  const fileInputRef = useRef(null)

  // Health check
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
    const file = e.dataTransfer.files[0]
    if (file) handleUpload(file)
  }

  const handleFileSelect = (e) => {
    const file = e.target.files[0]
    if (file) handleUpload(file)
  }

  const handleUpload = async (file) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showToast('Solo se aceptan archivos PDF', true)
      return
    }

    showToast('Subiendo PDF...')
    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await axios.post(`${API_BASE}/api/upload-pdf`, formData)
      setDocument(res.data)
      showToast(`Banco detectado: ${res.data.detected_bank || 'ninguno'}`)
    } catch (err) {
      showToast(err.response?.data?.detail || 'Error al subir', true)
    }
  }

  const handleProcess = async () => {
    if (!document?.id) return

    setIsLoading(true)
    showToast('Procesando documento...')

    try {
      const res = await axios.post(`${API_BASE}/api/process/${document.id}`)
      setDocument(prev => ({
        ...prev,
        status: res.data.status,
        parsed_data: res.data.data
      }))
      showToast('Documento procesado correctamente')
    } catch (err) {
      setDocument(prev => ({ ...prev, status: 'error' }))
      showToast(err.response?.data?.detail || 'Error al procesar', true)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!document?.id) return
    try {
      await axios.delete(`${API_BASE}/api/documents/${document.id}`)
    } catch (e) {
      console.error(e)
    }
    setDocument(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
    showToast('Documento eliminado')
  }

  return (
    <div className="min-h-screen bg-background text-text-main font-sans pb-20 selection:bg-primary-500/30">
      
      {/* Header */}
      <header className="glass-header flex items-center justify-between px-8 py-4">
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
      <main className="max-w-2xl mx-auto mt-10 px-6">
        
        {/* Upload Zone */}
        {!document && (
          <div 
            className={`border-2 border-dashed rounded-xl p-14 text-center cursor-pointer transition-all duration-300
              ${isDragging ? 'border-primary-500 bg-primary-500/5 shadow-glow' : 'border-border hover:border-border-hover bg-surface hover:bg-surface/80'}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <UploadCloud className={`w-12 h-12 mx-auto mb-4 transition-colors ${isDragging ? 'text-primary-500' : 'text-text-muted'}`} />
            <h3 className="text-lg font-medium text-text-main mb-1">Sube un estado de cuenta</h3>
            <p className="text-sm text-text-muted">Arrastra tu PDF aquí o haz clic para buscar</p>
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              accept=".pdf" 
              onChange={handleFileSelect} 
            />
          </div>
        )}

        {/* Results */}
        {document && (
          <div className="animate-fade-in space-y-6">
            
            {/* File Info Card */}
            <div className="bg-card border border-border rounded-xl overflow-hidden hover:border-gray-800 transition-colors">
              <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-surface/50">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-text-muted" />
                  <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wide">Documento</h2>
                </div>
                <button 
                  onClick={handleDelete}
                  className="p-1.5 text-text-muted hover:text-primary-500 hover:bg-primary-500/10 rounded-md transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              
              <div className="p-5 space-y-3">
                <div className="flex justify-between items-center pb-3 border-b border-white/5">
                  <span className="text-sm text-text-muted">Archivo</span>
                  <span className="text-sm font-medium">{document.file_name}</span>
                </div>
                <div className="flex justify-between items-center pb-3 border-b border-white/5">
                  <span className="text-sm text-text-muted">Banco detectado</span>
                  <span className="text-xs font-bold uppercase tracking-wider bg-gradient-to-r from-primary-500 to-primary-600 text-white px-3 py-1 rounded-full shadow-glow">
                    {document.detected_bank || 'Desconocido'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-text-muted">Estado</span>
                  <span className={`text-xs font-bold px-3 py-1 rounded-full border 
                    ${document.status === 'uploaded' ? 'border-blue-500/30 text-blue-400 bg-blue-500/10' : 
                      document.status === 'processed' ? 'border-green-500/30 text-green-400 bg-green-500/10' : 
                      'border-primary-500/30 text-primary-400 bg-primary-500/10'}`}>
                    {document.status === 'uploaded' ? 'Extraído' : 
                     document.status === 'processed' ? 'Procesado' : 'Error'}
                  </span>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-4">
              <button 
                onClick={handleProcess}
                disabled={isLoading || !document.detected_bank}
                className="flex-1 bg-gradient-to-r from-primary-500 to-primary-600 hover:to-primary-500 text-white font-medium py-3 px-6 rounded-lg shadow-glow hover:shadow-glow-strong disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
              >
                {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <CheckCircle2 className="w-5 h-5" />}
                {isLoading ? 'Procesando...' : 'Procesar Datos'}
              </button>
            </div>

            {/* Parsed Data (if exists) */}
            {document.parsed_data && (
              <div className="bg-card border border-border rounded-xl overflow-hidden animate-fade-in">
                <div className="px-5 py-4 border-b border-border bg-surface/50">
                  <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wide">Datos Estructurados</h2>
                </div>
                <div className="p-4">
                  <pre className="text-xs text-primary-400 font-mono whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(document.parsed_data, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            {/* Raw Text Preview */}
            <div className="bg-card border border-border rounded-xl overflow-hidden">
              <div className="px-5 py-4 border-b border-border bg-surface/50">
                <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wide">Texto Crudo (Preview)</h2>
              </div>
              <div className="p-4">
                <pre className="text-xs text-text-muted font-mono whitespace-pre-wrap max-h-48 overflow-y-auto">
                  {document.text_preview}
                </pre>
              </div>
            </div>

          </div>
        )}
      </main>

      {/* Toast */}
      <div className={`fixed bottom-8 left-1/2 -translate-x-1/2 px-6 py-3 rounded-lg border shadow-xl transition-all duration-300 z-50 flex items-center gap-2
        ${toast.show ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10 pointer-events-none'}
        ${toast.isError ? 'bg-card border-primary-500 text-white' : 'bg-surface border-border text-text-main'}`}
      >
        {toast.isError ? <XCircle className="w-4 h-4 text-primary-500" /> : <CheckCircle2 className="w-4 h-4 text-green-500" />}
        <span className="text-sm font-medium">{toast.msg}</span>
      </div>

    </div>
  )
}

export default App
