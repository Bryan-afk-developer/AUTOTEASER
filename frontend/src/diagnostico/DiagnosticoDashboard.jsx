import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import * as XLSX from 'xlsx'
import {
  UploadCloud, FileSpreadsheet, Eye, X, ChevronRight,
  Loader2, Download, MessageSquarePlus, Sparkles, CheckCircle2, AlertTriangle, ImagePlus
} from 'lucide-react'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const getColLetter = (colIndex) => {
  let letter = ''
  while (colIndex >= 0) {
    letter = String.fromCharCode((colIndex % 26) + 65) + letter
    colIndex = Math.floor(colIndex / 26) - 1
  }
  return letter
}

export default function DiagnosticoDashboard() {
  const [teaserFile, setTeaserFile] = useState(null)
  const [cafFile, setCafFile] = useState(null)
  const [previewFile, setPreviewFile] = useState(null)
  const [observaciones, setObservaciones] = useState('')
  const [showObsModal, setShowObsModal] = useState(false)
  const [loading, setLoading] = useState(false)
  const [resultData, setResultData] = useState(null)
  const [error, setError] = useState(null)
  const [selectedModel, setSelectedModel] = useState('gemini-3.1-pro')
  const [excelData, setExcelData] = useState(null)
  const [chatData, setChatData] = useState(null)
  const [chatHistory, setChatHistory] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatImages, setChatImages] = useState([])

  const chatFileRef = useRef(null)

  const handleChatPaste = (e) => {
    const items = e.clipboardData?.items
    if (!items) return
    const newImages = []
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') !== -1) {
        newImages.push(items[i].getAsFile())
      }
    }
    if (newImages.length > 0) {
      setChatImages(prev => [...prev, ...newImages])
    }
  }

  const handleChatFileSelect = (e) => {
    if (e.target.files?.length) {
      setChatImages(prev => [...prev, ...Array.from(e.target.files)])
    }
    if (chatFileRef.current) chatFileRef.current.value = ''
  }

  const teaserRef = useRef(null)
  const cafRef = useRef(null)

  useEffect(() => {
    if (previewFile?.file) {
      setExcelData(null) // Reset while loading
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const data = new Uint8Array(e.target.result)
          const workbook = XLSX.read(data, { type: 'array' })
          const firstSheetName = workbook.SheetNames[0]
          const worksheet = workbook.Sheets[firstSheetName]
          const json = XLSX.utils.sheet_to_json(worksheet, { header: 1 })
          setExcelData(json.slice(0, 15)) // Show first 15 rows
        } catch (err) {
          console.error("Error parsing Excel:", err)
        }
      }
      reader.readAsArrayBuffer(previewFile.file)
    }
  }, [previewFile])

  const handleDrop = (e, type) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
      type === 'teaser' ? setTeaserFile(file) : setCafFile(file)
    }
  }

  const handleDragOver = (e) => e.preventDefault()

  const handleFileInput = (e, type) => {
    const file = e.target.files[0]
    if (file) type === 'teaser' ? setTeaserFile(file) : setCafFile(file)
  }

  const handleGenerar = async () => {
    if (!teaserFile && !cafFile) return
    setLoading(true)
    setError(null)
    setResultData(null)
    try {
      const fd = new FormData()
      if (teaserFile) fd.append('teaser_file', teaserFile)
      if (cafFile) fd.append('caf_file', cafFile)
      fd.append('observaciones', observaciones)
      fd.append('modelo_ia', selectedModel)

      const res = await axios.post(`${API_BASE}/api/diagnostico/generar`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResultData(res.data.resultados)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = (htmlStr, name) => {
    if (!htmlStr) return
    const blob = new Blob([htmlStr], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `diagnostico_${name.replace(/ /g, '_')}_${new Date().toISOString().slice(0, 10)}.html`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleDownloadPDF = (htmlStr, name) => {
    if (!htmlStr) return
    const printStyle = "<style>@media print { @page { margin: 0; } body { margin: 1.5cm; } }</style>"
    const finalHtml = htmlStr.includes('</head>') 
      ? htmlStr.replace('</head>', printStyle + '</head>')
      : printStyle + htmlStr
    const blob = new Blob([finalHtml], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const win = window.open(url, '_blank')
    win.onload = () => {
      win.print()
    }
  }

  const handleDownloadWord = (htmlStr, name) => {
    if (!htmlStr) return
    const header = "<html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'><head><meta charset='utf-8'><title>Export HTML To Doc</title></head><body>"
    const footer = "</body></html>"
    const sourceHTML = header + htmlStr + footer
    
    const source = 'data:application/vnd.ms-word;charset=utf-8,' + encodeURIComponent(sourceHTML)
    const fileDownload = document.createElement("a")
    document.body.appendChild(fileDownload)
    fileDownload.href = source
    fileDownload.download = `diagnostico_${name.replace(/ /g, '_')}_${new Date().toISOString().slice(0, 10)}.doc`
    fileDownload.click()
    document.body.removeChild(fileDownload)
  }

  const previewInTab = (htmlStr) => {
    if (!htmlStr) return
    const blob = new Blob([htmlStr], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
  }

  const handleChatSubmit = async () => {
    if (!chatInput.trim() || !chatData) return
    const userMsg = chatInput.trim()
    setChatInput('')
    setChatHistory(prev => [...prev, { role: 'user', content: userMsg }])
    setChatLoading(true)

    try {
      const fd = new FormData()
      fd.append('html_actual', chatData.html)
      fd.append('prompt_usuario', userMsg)
      fd.append('modelo_ia', chatData.modelo)
      chatImages.forEach(img => {
        fd.append('imagenes', img)
      })
      setChatImages([])

      const res = await axios.post(`${API_BASE}/api/diagnostico/chat`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      
      const newHtml = res.data.html
      
      setResultData(prev => {
        const newData = [...prev]
        newData[chatData.index] = { ...newData[chatData.index], html: newHtml }
        return newData
      })
      
      setChatData(prev => ({ ...prev, html: newHtml }))
      
      setChatHistory(prev => [...prev, { role: 'assistant', content: '¡Listo! He actualizado el reporte con los cambios solicitados. Ya puedes previsualizarlo o descargarlo.' }])
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'assistant', content: `Error al procesar la solicitud: ${err.response?.data?.detail || err.message}` }])
    } finally {
      setChatLoading(false)
    }
  }

  return (
    <div className="flex-1 flex overflow-hidden relative bg-background">
      {/* Main Content */}
      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-5xl mx-auto space-y-8">

          {/* Header */}
          <div className="flex items-center justify-between border-b border-white/5 pb-6">
            <div className="flex items-center gap-4">
              <span className="text-4xl drop-shadow-[0_0_15px_rgba(59,130,246,0.5)]">🩺</span>
              <div>
                <h2 className="text-2xl font-bold text-blue-400 tracking-tight">Diagnóstico Estratégico IA</h2>
                <p className="text-text-muted mt-1 text-sm">Sube el Teaser y/o el CAF en Excel. La IA generará un reporte ejecutivo completo.</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="text-[10px] font-black uppercase tracking-widest text-text-muted bg-white/5 px-3 py-1.5 rounded-full border border-white/10 outline-none appearance-none cursor-not-allowed text-center"
                disabled
              >
                <option value="gemini-3.1-pro" className="bg-[#15151a]">Gemini 3.1 Pro</option>
              </select>
            </div>
          </div>

          {/* Slots */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

            {/* Slot Teaser */}
            <div
              className="bg-[#0a0a0c] border border-white/5 rounded-2xl p-6 flex flex-col items-center justify-center relative overflow-hidden min-h-[280px] shadow-lg group"
              onDrop={(e) => handleDrop(e, 'teaser')}
              onDragOver={handleDragOver}
            >
              <div className="absolute top-4 left-4 bg-blue-500/10 text-blue-400 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border border-blue-500/20">
                1. Teaser Financiero
              </div>
              <input type="file" ref={teaserRef} className="hidden" accept=".xlsx,.xls" onChange={(e) => handleFileInput(e, 'teaser')} />

              {!teaserFile ? (
                <button
                  onClick={() => teaserRef.current?.click()}
                  className="w-full h-full flex flex-col items-center justify-center border-2 border-dashed border-white/10 hover:border-blue-500/50 rounded-xl mt-8 transition-colors cursor-pointer bg-white/5 hover:bg-blue-500/5"
                >
                  <UploadCloud className="w-10 h-10 text-text-muted mb-4 group-hover:text-blue-400 transition-colors" />
                  <p className="text-sm font-semibold text-text-main">Arrastra o selecciona el Excel del Teaser</p>
                  <p className="text-xs text-text-muted mt-2">.xlsx / .xls</p>
                </button>
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center mt-8 animate-fade-in">
                  <FileSpreadsheet className="w-14 h-14 text-blue-500 mb-3 drop-shadow-[0_0_15px_rgba(59,130,246,0.4)]" />
                  <p className="font-bold text-text-main text-center truncate w-full px-4">{teaserFile.name}</p>
                  <p className="text-xs text-text-muted mt-1">{(teaserFile.size / 1024).toFixed(1)} KB</p>
                  <div className="flex gap-3 mt-5">
                    <button onClick={() => setPreviewFile({ type: 'teaser', file: teaserFile })} className="flex items-center gap-2 bg-blue-600/80 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-xs font-semibold transition-colors">
                      <Eye className="w-3.5 h-3.5" /> Vista Previa
                    </button>
                    <button onClick={() => setTeaserFile(null)} className="flex items-center gap-2 bg-white/5 hover:bg-rose-500/20 border border-white/10 hover:border-rose-500/30 text-rose-400 px-4 py-2 rounded-lg text-xs font-semibold transition-colors">
                      <X className="w-3.5 h-3.5" /> Quitar
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Slot CAF */}
            <div
              className="bg-[#0a0a0c] border border-white/5 rounded-2xl p-6 flex flex-col items-center justify-center relative overflow-hidden min-h-[280px] shadow-lg group"
              onDrop={(e) => handleDrop(e, 'caf')}
              onDragOver={handleDragOver}
            >
              <div className="absolute top-4 left-4 bg-purple-500/10 text-purple-400 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border border-purple-500/20">
                2. AutoCAF
              </div>
              <input type="file" ref={cafRef} className="hidden" accept=".xlsx,.xls" onChange={(e) => handleFileInput(e, 'caf')} />

              {!cafFile ? (
                <button
                  onClick={() => cafRef.current?.click()}
                  className="w-full h-full flex flex-col items-center justify-center border-2 border-dashed border-white/10 hover:border-purple-500/50 rounded-xl mt-8 transition-colors cursor-pointer bg-white/5 hover:bg-purple-500/5"
                >
                  <UploadCloud className="w-10 h-10 text-text-muted mb-4 group-hover:text-purple-400 transition-colors" />
                  <p className="text-sm font-semibold text-text-main">Arrastra o selecciona el Excel del CAF</p>
                  <p className="text-xs text-text-muted mt-2">.xlsx / .xls</p>
                </button>
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center mt-8 animate-fade-in">
                  <FileSpreadsheet className="w-14 h-14 text-purple-500 mb-3 drop-shadow-[0_0_15px_rgba(168,85,247,0.4)]" />
                  <p className="font-bold text-text-main text-center truncate w-full px-4">{cafFile.name}</p>
                  <p className="text-xs text-text-muted mt-1">{(cafFile.size / 1024).toFixed(1)} KB</p>
                  <div className="flex gap-3 mt-5">
                    <button onClick={() => setPreviewFile({ type: 'caf', file: cafFile })} className="flex items-center gap-2 bg-purple-600/80 hover:bg-purple-500 text-white px-4 py-2 rounded-lg text-xs font-semibold transition-colors">
                      <Eye className="w-3.5 h-3.5" /> Vista Previa
                    </button>
                    <button onClick={() => setCafFile(null)} className="flex items-center gap-2 bg-white/5 hover:bg-rose-500/20 border border-white/10 hover:border-rose-500/30 text-rose-400 px-4 py-2 rounded-lg text-xs font-semibold transition-colors">
                      <X className="w-3.5 h-3.5" /> Quitar
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Observaciones badge */}
          {observaciones && (
            <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3 text-xs text-amber-300">
              <MessageSquarePlus className="w-4 h-4 shrink-0" />
              <span className="font-semibold">Observaciones añadidas:</span>
              <span className="truncate text-amber-200/70">{observaciones.slice(0, 80)}{observaciones.length > 80 ? '…' : ''}</span>
              <button onClick={() => setObservaciones('')} className="ml-auto text-amber-400 hover:text-rose-400"><X className="w-3.5 h-3.5" /></button>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="flex items-center gap-3 bg-rose-500/10 border border-rose-500/25 rounded-xl px-5 py-4 text-sm text-rose-300">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Result panel */}
          {resultData && resultData.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-emerald-500/10 border border-emerald-500/25 rounded-2xl p-6 space-y-4"
            >
              <div className="flex items-center gap-3 border-b border-emerald-500/20 pb-4">
                <CheckCircle2 className="w-8 h-8 text-emerald-400 shrink-0" />
                <div>
                  <p className="font-bold text-emerald-300">¡Diagnóstico(s) generado(s)!</p>
                  <p className="text-xs text-emerald-200 mt-0.5">Se generaron con éxito los reportes solicitados.</p>
                </div>
              </div>
              
              <div className="space-y-3">
                {resultData.map((res, idx) => (
                  <div key={idx} className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-black/20 p-4 rounded-xl border border-white/5">
                    <div className="flex items-center gap-3">
                      {res.error ? (
                        <AlertTriangle className="w-5 h-5 text-rose-400" />
                      ) : (
                        <Sparkles className="w-5 h-5 text-emerald-400" />
                      )}
                      <div>
                        <p className="font-bold text-text-main text-sm">{res.modelo}</p>
                        {res.error ? (
                          <p className="text-xs text-rose-400 mt-0.5">Fallo: {res.error}</p>
                        ) : (
                          <p className="text-xs text-text-muted mt-0.5">Completado correctamente</p>
                        )}
                      </div>
                    </div>
                    
                    {!res.error && (
                      <div className="flex flex-wrap items-center gap-2 shrink-0">
                        <button onClick={() => { setChatData({ html: res.html, index: idx, modelo: res.modelo }); setChatHistory([{ role: 'assistant', content: '¿Qué deseas modificar de este reporte?' }]); setChatInput(''); }} className="flex items-center gap-1.5 bg-amber-600/80 hover:bg-amber-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors shadow-[0_0_10px_rgba(245,158,11,0.2)]">
                          <MessageSquarePlus className="w-3.5 h-3.5" /> Corregir
                        </button>
                        <button onClick={() => previewInTab(res.html)} className="flex items-center gap-1.5 bg-emerald-600/80 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors shadow-[0_0_10px_rgba(16,185,129,0.2)]">
                          <Eye className="w-3.5 h-3.5" /> Ver
                        </button>
                        <div className="flex items-center bg-white/5 border border-white/10 rounded-lg overflow-hidden">
                          <button onClick={() => handleDownloadPDF(res.html, res.modelo)} className="flex items-center gap-1.5 hover:bg-white/10 text-text-main px-3 py-1.5 text-xs font-semibold transition-colors border-r border-white/10" title="Descargar como PDF">
                            PDF
                          </button>
                          <button onClick={() => handleDownloadWord(res.html, res.modelo)} className="flex items-center gap-1.5 hover:bg-white/10 text-text-main px-3 py-1.5 text-xs font-semibold transition-colors border-r border-white/10" title="Descargar como Word">
                            Word
                          </button>
                          <button onClick={() => handleDownload(res.html, res.modelo)} className="flex items-center gap-1.5 hover:bg-white/10 text-text-main px-3 py-1.5 text-xs font-semibold transition-colors" title="Descargar como código HTML">
                            HTML
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* Action bar */}
          <div className="flex items-center justify-between pt-4 border-t border-white/5 gap-3">
            <button
              onClick={() => setShowObsModal(true)}
              className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 text-text-muted hover:text-text-main px-5 py-3 rounded-xl text-sm font-semibold transition-colors"
            >
              <MessageSquarePlus className="w-4 h-4" />
              Observaciones del Equipo
              {observaciones && <span className="ml-1 w-2 h-2 rounded-full bg-amber-400 inline-block" />}
            </button>

            <button
              onClick={handleGenerar}
              disabled={(!teaserFile && !cafFile) || loading}
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:brightness-110 disabled:opacity-30 disabled:cursor-not-allowed text-white px-8 py-3 rounded-xl font-bold flex items-center gap-2.5 transition-all shadow-[0_0_25px_rgba(59,130,246,0.3)] disabled:shadow-none text-sm"
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Generando con IA...</>
              ) : (
                <><Sparkles className="w-4 h-4" /> Generar Diagnóstico IA <ChevronRight className="w-4 h-4" /></>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Observaciones Modal */}
      <AnimatePresence>
        {showObsModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-[900] flex items-center justify-center p-4"
            onClick={() => setShowObsModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, y: 10 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 10 }}
              className="bg-surface border border-border rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-[#15151a]">
                <div className="flex items-center gap-3">
                  <MessageSquarePlus className="w-5 h-5 text-amber-400" />
                  <h3 className="font-bold text-text-main">Observaciones Express del Equipo</h3>
                </div>
                <button onClick={() => setShowObsModal(false)} className="p-1 hover:bg-white/5 rounded-lg text-text-muted">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-6 space-y-4">
                <p className="text-xs text-text-muted leading-relaxed">
                  Agrega notas del equipo comercial sobre el cliente: dolores expresados en entrevista, planes de expansión, necesidades de capital, contexto de la relación, etc. La IA usará esto para personalizar el diagnóstico.
                </p>
                <textarea
                  value={observaciones}
                  onChange={(e) => setObservaciones(e.target.value)}
                  placeholder="Ej: El cliente mencionó que busca expandirse a 3 nuevas sucursales. Su principal dolor es que los bancos los tienen con líneas al tope. Les interesa el factoraje porque tienen contratos de gobierno a 90 días..."
                  className="w-full bg-background border border-border rounded-xl p-4 text-sm text-text-main placeholder:text-text-muted resize-none h-40 focus:outline-none focus:border-amber-500/50 transition-colors"
                />
                <div className="flex justify-end gap-3">
                  <button onClick={() => { setObservaciones(''); setShowObsModal(false) }} className="text-sm text-text-muted hover:text-rose-400 px-4 py-2 rounded-lg transition-colors">
                    Borrar
                  </button>
                  <button
                    onClick={() => setShowObsModal(false)}
                    className="bg-amber-600/80 hover:bg-amber-500 text-white px-6 py-2 rounded-xl text-sm font-semibold transition-colors"
                  >
                    Guardar Observaciones
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Slide-over Preview Panel */}
      <AnimatePresence>
        {previewFile && (
          <motion.div
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="absolute top-0 right-0 h-full w-[520px] max-w-full bg-[#0a0a0c] border-l border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.8)] z-50 flex flex-col"
          >
            <div className="flex items-center justify-between p-5 border-b border-white/5 bg-[#050505]/50">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${previewFile.type === 'teaser' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'}`}>
                  <FileSpreadsheet className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-text-main truncate max-w-[350px]">{previewFile.file.name}</h3>
                  <p className="text-[10px] text-text-muted uppercase tracking-widest font-black mt-0.5">
                    {previewFile.type === 'teaser' ? 'Teaser Financiero' : 'AutoCAF'} — {(previewFile.file.size / 1024).toFixed(1)} KB
                  </p>
                </div>
              </div>
              <button onClick={() => setPreviewFile(null)} className="p-2 hover:bg-white/5 rounded-lg text-text-muted hover:text-rose-400 transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6">
              {excelData ? (
                <div className="bg-[#0c0c0c] rounded-xl border border-white/10 overflow-hidden shadow-xl">
                  <div className="overflow-x-auto bg-white/5 p-[1px]">
                    <table className="w-full text-left text-xs whitespace-nowrap border-collapse">
                      <thead className="bg-[#1c1c22] text-[#8e8e93] select-none text-[10px]">
                        <tr>
                          <th className="px-3 py-1.5 border-r border-b border-white/10 text-center sticky left-0 z-10 w-10 font-mono bg-[#1c1c22]"></th>
                          {Array.from({ length: Math.max(8, ...excelData.map(r => r.length)) }).map((_, i) => (
                            <th key={i} className="px-4 py-1.5 border-r border-b border-white/10 font-mono font-medium text-center bg-[#1c1c22]">{getColLetter(i)}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="text-text-main font-sans">
                        {excelData.map((row, rowIndex) => (
                          <tr key={rowIndex} className="transition-colors">
                            <td className="px-2 py-1.5 border-r border-b border-white/10 bg-[#15151a] text-[#8e8e93] text-[10px] font-mono text-center sticky left-0 z-10 select-none">{rowIndex + 1}</td>
                            {Array.from({ length: Math.max(8, ...excelData.map(r => r.length)) }).map((_, colIndex) => (
                              <td key={colIndex} className="px-4 py-1.5 border-r border-b border-white/5 text-[11px] truncate max-w-[200px] text-gray-200 hover:bg-white/10 transition-colors">
                                {row[colIndex] !== undefined && row[colIndex] !== null ? String(row[colIndex]) : ''}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="p-3 bg-white/5 border-t border-white/10 text-center text-[10px] text-text-muted">
                    Mostrando las primeras {Math.min(15, excelData.length)} filas.
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full gap-6">
                  <div className={`p-6 rounded-2xl border ${previewFile.type === 'teaser' ? 'bg-blue-500/10 border-blue-500/20' : 'bg-purple-500/10 border-purple-500/20'}`}>
                    <FileSpreadsheet className={`w-20 h-20 mx-auto ${previewFile.type === 'teaser' ? 'text-blue-400' : 'text-purple-400'}`} />
                  </div>
                  <div className="text-center">
                    <p className="text-base font-bold text-text-main">{previewFile.file.name}</p>
                    <p className="text-sm text-text-muted mt-2">Procesando hoja de cálculo...</p>
                  </div>
                </div>
              )}
            </div>
            
            <div className="p-5 border-t border-white/10 bg-[#050505]/50 shrink-0">
              <div className="bg-white/5 border border-white/10 rounded-xl px-6 py-3 text-center w-full">
                <p className="text-[10px] font-mono text-text-muted">Tamaño: {(previewFile.file.size / 1024).toFixed(2)} KB · Tipo: {previewFile.file.name.split('.').pop().toUpperCase()}</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      {/* Chat Slide-over Panel */}
      <AnimatePresence>
        {chatData && (
          <motion.div
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="absolute top-0 right-0 h-full w-[450px] max-w-full bg-[#0a0a0c] border-l border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.8)] z-50 flex flex-col"
          >
            <div className="flex items-center justify-between p-5 border-b border-white/5 bg-[#050505]/50">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-amber-500/20 text-amber-400">
                  <MessageSquarePlus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-text-main">IA de Diagnóstico</h3>
                  <p className="text-[10px] text-text-muted uppercase tracking-widest font-black mt-0.5">Asistente de Correcciones</p>
                </div>
              </div>
              <button onClick={() => setChatData(null)} className="p-2 hover:bg-white/5 rounded-lg text-text-muted hover:text-rose-400 transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {chatHistory.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${msg.role === 'user' ? 'bg-amber-600 text-white rounded-br-sm' : 'bg-white/10 text-gray-200 rounded-bl-sm border border-white/5'}`}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-2xl px-4 py-3 text-sm bg-white/10 text-gray-200 rounded-bl-sm border border-white/5 flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-amber-400" /> Reescribiendo el reporte...
                  </div>
                </div>
              )}
            </div>
            
            <div className="p-4 border-t border-white/10 bg-[#050505]/50 shrink-0">
              {chatImages.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {chatImages.map((img, idx) => (
                    <div key={idx} className="relative w-14 h-14 rounded-lg overflow-hidden border border-white/20 group">
                      <img src={URL.createObjectURL(img)} alt="preview" className="w-full h-full object-cover" />
                      <button type="button" onClick={() => setChatImages(prev => prev.filter((_, i) => i !== idx))} className="absolute inset-0 bg-black/60 hidden group-hover:flex items-center justify-center text-white backdrop-blur-sm transition-all">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <form onSubmit={(e) => { e.preventDefault(); handleChatSubmit(); }} className="flex gap-2 items-center">
                <input 
                  type="file" 
                  accept="image/*" 
                  multiple 
                  ref={chatFileRef} 
                  onChange={handleChatFileSelect} 
                  className="hidden" 
                />
                <button type="button" onClick={() => chatFileRef.current?.click()} className="p-3 text-text-muted hover:text-amber-400 bg-white/5 border border-white/10 rounded-xl transition-colors shrink-0">
                  <ImagePlus className="w-5 h-5" />
                </button>
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onPaste={handleChatPaste}
                  placeholder="Ej: Cambia el título... (Ctrl+V para imagen)"
                  disabled={chatLoading}
                  className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-text-main placeholder:text-text-muted focus:outline-none focus:border-amber-500/50 transition-colors disabled:opacity-50"
                />
                <button type="submit" disabled={chatLoading || (!chatInput.trim() && chatImages.length === 0)} className="bg-amber-600 hover:bg-amber-500 text-white px-5 py-3 rounded-xl font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                  Enviar
                </button>
              </form>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
