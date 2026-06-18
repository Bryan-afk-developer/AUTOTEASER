import React, { useState, useRef } from 'react'
import axios from 'axios'
import { motion, AnimatePresence } from 'framer-motion'
import { UploadCloud, FileText, CheckCircle2, Download, Loader2, X, AlertTriangle, Maximize2, Columns, AlignJustify, Crop } from 'lucide-react'
import RegionSelector from '../components/RegionSelector'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function CafDashboard() {
  // documents is an array of objects: 
  // { doc_id, filename, page_count, thumbnails, selectedPages: [], status: 'uploaded' | 'processing' | 'processed' | 'error', extractedData: null }
  const [documents, setDocuments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [excelUrl, setExcelUrl] = useState(null)
  const [previewImage, setPreviewImage] = useState(null)
  const [regionSelectorState, setRegionSelectorState] = useState(null)

  const fileInputRef = useRef(null)

  const handleUpload = async (e) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return
    
    setUploading(true)
    
    try {
      const uploadPromises = files.map(async (file) => {
        const fd = new FormData()
        fd.append('file', file)
        const res = await axios.post(`${API_BASE}/api/caf/upload`, fd)
        return {
          ...res.data,
          selectedPages: [],
          status: 'uploaded',
          extractedData: null,
          pageLayouts: {}, // { 0: 'single_column', 1: 'two_column' }
          useOcr: true
        }
      })
      
      const newDocs = await Promise.all(uploadPromises)
      setDocuments(prev => [...prev, ...newDocs])
      // Reset the excel url since we have new data
      setExcelUrl(null)
    } catch (err) {
      alert("Error uploading PDFs: " + (err.response?.data?.detail || err.message))
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const togglePageSelection = (docId, pageNum) => {
    setDocuments(prev => prev.map(doc => {
      if (doc.doc_id === docId) {
        // No deseleccionar si está en processing
        if (doc.status === 'processing') {
          return doc
        }

        const isSelected = doc.selectedPages.includes(pageNum)
        
        if (!isSelected && doc.selectedPages.length >= 10) {
          alert("Has alcanzado el límite máximo de 10 páginas por documento.")
          return doc
        }
        
        const selected = isSelected
          ? doc.selectedPages.filter(p => p !== pageNum)
          : [...doc.selectedPages, pageNum].sort((a,b) => a-b)
          
        // Si se selecciona y no tiene layout asignado, poner default single_column
        const newPageLayouts = { ...doc.pageLayouts }
        if (!isSelected && !newPageLayouts[pageNum]) {
          newPageLayouts[pageNum] = 'single_column'
        }
          
        return { ...doc, selectedPages: selected, pageLayouts: newPageLayouts }
      }
      return doc
    }))
  }

  const openPreview = (e, docId, pageNum) => {
    e.stopPropagation() // Evitar que se seleccione al abrir la vista previa
    setPreviewImage(`${API_BASE}/api/caf/document/${docId}/page/${pageNum}/image`)
  }

  const updatePageLayout = (docId, pageNum, newType) => {
    setDocuments(docs => docs.map(doc => {
      if (doc.doc_id === docId) {
        // Keep existing regions if changing to a type that supports them
        const current = doc.pageLayouts[pageNum];
        const currentRegions = typeof current === 'object' ? current.regions : null;
        
        return {
          ...doc,
          pageLayouts: {
            ...doc.pageLayouts,
            [pageNum]: currentRegions ? { type: newType, regions: currentRegions } : newType
          }
        }
      }
      return doc
    }))
  }

  const openRegionSelector = (docId, pageNum, imageUrl, initialRegions, layoutType) => {
    setRegionSelectorState({ docId, pageNum, imageUrl, initialRegions, layoutType })
  }

  const handleSaveRegions = (regions) => {
    if (!regionSelectorState) return;
    const { docId, pageNum, layoutType } = regionSelectorState;
    
    setDocuments(docs => docs.map(doc => {
      if (doc.doc_id === docId) {
        return {
          ...doc,
          pageLayouts: {
            ...doc.pageLayouts,
            [pageNum]: {
              type: layoutType || 'two_column',
              regions: regions
            }
          }
        }
      }
      return doc
    }))
    setRegionSelectorState(null);
  }

  const removeDocument = (docId) => {
    setDocuments(prev => prev.filter(d => d.doc_id !== docId))
    setExcelUrl(null)
  }

  const handleProcessAll = async () => {
    const docsToProcess = documents.filter(d => d.selectedPages.length > 0 && d.status !== 'processed')
    if (docsToProcess.length === 0) {
      alert("Por favor selecciona páginas en los documentos que deseas procesar.")
      return
    }
    
    // Mark as processing
    setDocuments(prev => prev.map(d => docsToProcess.find(dp => dp.doc_id === d.doc_id) ? { ...d, status: 'processing' } : d))
    setExcelUrl(null)

    for (const doc of docsToProcess) {
      try {
        await axios.post(`${API_BASE}/api/caf/process/${doc.doc_id}`, { pages: doc.selectedPages, page_layouts: doc.pageLayouts, use_ocr: doc.useOcr !== false })
        const previewRes = await axios.get(`${API_BASE}/api/caf/preview/${doc.doc_id}`)
        
        setDocuments(prev => prev.map(d => {
          if (d.doc_id === doc.doc_id) {
            return { ...d, status: 'processed', extractedData: previewRes.data }
          }
          return d
        }))
      } catch (err) {
        console.error(`Error processing doc ${doc.doc_id}`, err)
        setDocuments(prev => prev.map(d => {
          if (d.doc_id === doc.doc_id) {
            return { ...d, status: 'error' }
          }
          return d
        }))
      }
    }
  }

  const handleGenerateExcel = async () => {
    const processedDocs = documents.filter(d => d.status === 'processed' && d.extractedData)
    if (processedDocs.length === 0) return
    
    setGenerating(true)
    try {
      const docIds = processedDocs.map(d => d.doc_id)
      const res = await axios.post(`${API_BASE}/api/caf/generate-batch-excel`, { doc_ids: docIds })
      setExcelUrl(`${API_BASE}${res.data.download_url}`)
    } catch (err) {
      alert("Error generating Excel: " + (err.response?.data?.detail || err.message))
    } finally {
      setGenerating(false)
    }
  }

  const isAnyProcessing = documents.some(d => d.status === 'processing')
  const hasProcessedDocs = documents.some(d => d.status === 'processed')

  return (
    <>
      <main className="max-w-6xl w-full mx-auto px-6 py-8 space-y-8 flex-1">
      
      {/* ── Step 1: Upload & Select ── */}
      <section className="bg-card border border-border rounded-2xl p-6 shadow-sm">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <span className="bg-primary-500 text-white w-6 h-6 rounded-full flex items-center justify-center text-xs">1</span> 
          Subir PDFs y Seleccionar Páginas
        </h2>
        
        <div 
          className="border-2 border-dashed border-border hover:border-primary-500/50 bg-surface/30 rounded-xl p-6 text-center cursor-pointer transition-all mb-6"
          onClick={() => fileInputRef.current?.click()}
        >
          {uploading ? (
            <Loader2 className="w-6 h-6 mx-auto mb-2 animate-spin text-primary-500" />
          ) : (
            <UploadCloud className="w-6 h-6 mx-auto mb-2 text-text-muted" />
          )}
          <p className="text-sm font-semibold">{uploading ? 'Subiendo archivos...' : 'Sube múltiples Estados Financieros (PDF)'}</p>
          <input type="file" ref={fileInputRef} className="hidden" accept=".pdf" multiple onChange={handleUpload} />
        </div>

        {documents.length > 0 && (
          <div className="space-y-6">
            {documents.map((doc, idx) => (
              <div key={doc.doc_id} className="border border-white/5 bg-surface/20 rounded-xl overflow-hidden shadow-sm">
                <div className="flex items-center justify-between bg-surface/50 p-3 border-b border-border">
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-primary-500" />
                    <span className="font-semibold text-sm">{doc.filename} <span className="text-text-muted font-normal">({doc.page_count} págs)</span></span>
                    
                    {doc.status === 'processed' && (
                      <span className="bg-green-500/20 text-green-400 text-[10px] px-2 py-0.5 rounded-full font-bold flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> Procesado (Año: {doc.extractedData?.year})
                      </span>
                    )}
                    {doc.status === 'error' && (
                      <span className="bg-rose-500/20 text-rose-400 text-[10px] px-2 py-0.5 rounded-full font-bold flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> Error
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2 cursor-pointer text-xs text-text-muted hover:text-white transition-colors" title="Si está activo, usa Document AI. Si se desactiva, intenta extraer el texto de forma nativa más rápido.">
                      <input 
                        type="checkbox" 
                        checked={doc.useOcr !== false} 
                        onChange={(e) => setDocuments(docs => docs.map(d => d.doc_id === doc.doc_id ? { ...d, useOcr: e.target.checked } : d))}
                        className="w-3 h-3 rounded bg-surface border-border text-primary-500 focus:ring-primary-500/50"
                      />
                      <span>Usar OCR</span>
                    </label>
                    <button onClick={() => removeDocument(doc.doc_id)} className="p-1.5 rounded-lg hover:bg-white/10 text-text-muted hover:text-rose-400 transition-colors">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                
                <div className="p-4">
                  <p className="text-xs text-text-muted mb-3">Selecciona las páginas del Balance y Estado de Resultados:</p>
                  
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 max-h-[400px] overflow-y-auto pr-2 pb-2">
                    {doc.thumbnails.map((thumb) => {
                      const isSelected = doc.selectedPages.includes(thumb.page_num)
                      const layoutConfig = doc.pageLayouts[thumb.page_num] || 'single_column'
                      const layoutType = typeof layoutConfig === 'object' ? layoutConfig.type : layoutConfig
                      const regions = typeof layoutConfig === 'object' ? layoutConfig.regions : null
                      
                      return (
                        <div 
                          key={thumb.page_num} 
                          className={`relative rounded-xl overflow-hidden border-4 transition-all group ${isSelected ? 'border-primary-500 shadow-[0_0_15px_rgba(99,102,241,0.5)]' : 'border-transparent hover:border-white/20 bg-[#11111b]'}`}
                        >
                          {/* Contenedor de la imagen */}
                          <div className="relative w-full aspect-[1/1.4] bg-white/5 cursor-pointer" onClick={() => togglePageSelection(doc.doc_id, thumb.page_num)}>
                            <img src={thumb.image} alt={`Pág ${thumb.page_num + 1}`} className={`w-full h-full object-cover transition-all duration-300 ${isSelected ? 'opacity-100' : 'opacity-70 group-hover:opacity-90'}`} />
                            
                            {/* Overlay en hover */}
                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                              <button 
                                onClick={(e) => openPreview(e, doc.doc_id, thumb.page_num)}
                                className="bg-white/10 hover:bg-primary-500/80 p-3 rounded-full backdrop-blur-md text-white transition-all transform scale-75 group-hover:scale-100"
                                title="Abrir Vista Previa"
                              >
                                <Maximize2 className="w-6 h-6" />
                              </button>
                            </div>
                            
                            {/* Removed duplicate layout selector */}
                          </div>

                          {/* Número de página */}
                          <div className={`absolute top-2 left-2 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shadow-md pointer-events-none ${isSelected ? 'bg-primary-500 text-white' : 'bg-black/70 text-white/70 backdrop-blur-md'}`}>
                            {thumb.page_num + 1}
                          </div>

                          {/* Checkmark gigante si está seleccionado */}
                          {isSelected && (
                            <div className="absolute top-2 right-2 bg-green-500 text-white rounded-full p-1 shadow-lg pointer-events-none transform scale-110">
                              <CheckCircle2 className="w-4 h-4" />
                            </div>
                          )}
                          
                          {/* Layout selector per page (solo visible si está seleccionado) */}
                          {isSelected && (
                            <div className="absolute bottom-0 left-0 right-0 p-1.5 bg-black/80 backdrop-blur-md border-t border-white/10 flex flex-col gap-1 z-30">
                              <select 
                                value={layoutType}
                                onChange={(e) => updatePageLayout(doc.doc_id, thumb.page_num, e.target.value)}
                                className="w-full bg-[#1e1e2e]/90 text-white text-[9px] border-none rounded py-1 pl-1 pr-4 appearance-none font-bold cursor-pointer outline-none focus:ring-1 focus:ring-primary-500"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <option value="single_column">LINEAL (Auto)</option>
                                <option value="split_column">CONCEPTO / MONTO</option>
                                <option value="two_column">2 COLUMNAS</option>
                              </select>
                              
                              {(layoutType === 'two_column' || layoutType === 'split_column' || layoutType === 'single_column') && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    openRegionSelector(doc.doc_id, thumb.page_num, thumb.image, regions || [], layoutType);
                                  }}
                                  className={`w-full flex items-center justify-center gap-1 py-1 rounded text-[9px] font-bold transition-colors ${regions && regions.length > 0 ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30' : 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30'}`}
                                >
                                  <Crop className="w-3 h-3" /> 
                                  {regions && regions.length > 0 ? 'Áreas Ajustadas' : 'Ajustar Áreas'}
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Step 2: Processing ── */}
      {documents.length > 0 && (
        <section className="bg-card border border-border rounded-2xl p-6 shadow-sm">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
            <span className="bg-primary-500 text-white w-6 h-6 rounded-full flex items-center justify-center text-xs">2</span> 
            Analizar e Inspeccionar
          </h2>

          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 mb-6">
            <button 
              onClick={handleProcessAll}
              disabled={isAnyProcessing || documents.every(d => d.selectedPages.length === 0)}
              className="bg-primary-600 hover:bg-primary-500 text-white px-5 py-2.5 rounded-xl font-semibold flex items-center gap-2 text-sm shadow-glow disabled:opacity-50 transition-all"
            >
              {isAnyProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
              {isAnyProcessing ? 'Procesando documentos...' : 'Analizar Páginas Seleccionadas'}
            </button>
          </div>
          
          {hasProcessedDocs && (
            <div className="space-y-4">
              <div className="bg-green-500/10 border border-green-500/30 text-green-400 p-3 rounded-lg text-sm flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" />
                Extracción completada. Los años detectados se agruparán en hojas de Excel.
              </div>
              
              <div className="overflow-x-auto border border-border rounded-lg max-h-[400px]">
                <table className="w-full text-left text-xs whitespace-nowrap">
                  <thead className="bg-surface/90 sticky top-0 backdrop-blur-md z-10 border-b border-border shadow-sm">
                    <tr>
                      <th className="p-3">Año / Archivo</th>
                      <th className="p-3">Texto Extraído</th>
                      <th className="p-3">Evidencia Visual</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.filter(d => d.status === 'processed').map((doc) => (
                      <React.Fragment key={doc.doc_id}>
                        {doc.extractedData?.pages.map(page => (
                          page.tables.map((table, tIdx) => (
                            table.map((row, rIdx) => {
                              if (!row || row.length === 0) return null;
                              const firstCell = row[0];
                              const context = row.slice(1).map(c => c.text).filter(Boolean).join(" | ");
                              return (
                                <tr key={`p${page.page_num}-t${tIdx}-r${rIdx}`} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                                  <td className="p-3">
                                    <div className="font-bold text-indigo-400">{doc.extractedData.year}</div>
                                    <div className="text-text-muted/60 text-[10px] truncate max-w-[150px]">{doc.filename}</div>
                                  </td>
                                  <td className="p-3">
                                    <div className="font-semibold text-primary-400">{firstCell.text}</div>
                                    {context && <div className="text-text-muted mt-1 truncate max-w-[300px]">{context}</div>}
                                  </td>
                                  <td className="p-3">
                                    {firstCell.evidence_b64 ? (
                                      <img src={`data:image/png;base64,${firstCell.evidence_b64}`} className="h-8 object-contain rounded border border-white/10" alt="evidencia" />
                                    ) : (
                                      <span className="text-text-muted/50 italic">Sin recorte</span>
                                    )}
                                  </td>
                                </tr>
                              )
                            })
                          ))
                        ))}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}

      {/* ── Step 3: Excel Generation ── */}
      {hasProcessedDocs && (
        <section className="bg-card border border-border rounded-2xl p-6 shadow-sm">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
            <span className="bg-primary-500 text-white w-6 h-6 rounded-full flex items-center justify-center text-xs">3</span> 
            Generar Excel Consolidado
          </h2>
          
          <div className="flex items-center gap-4">
            <button 
              onClick={handleGenerateExcel}
              disabled={generating}
              className="bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2.5 rounded-xl font-semibold flex items-center gap-2 text-sm shadow-[0_0_15px_rgba(16,185,129,0.3)] disabled:opacity-50 transition-all"
            >
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              {generating ? 'Generando...' : 'Descargar Excel (Una hoja por año)'}
            </button>
            
            {excelUrl && (
              <a 
                href={excelUrl} 
                download
                className="text-sm text-emerald-400 font-semibold hover:text-emerald-300 underline underline-offset-4 flex items-center gap-1 bg-emerald-500/10 px-4 py-2 rounded-lg"
              >
                <Download className="w-4 h-4" /> Click aquí para descargar
              </a>
            )}
          </div>
        </section>
      )}

    </main>

      {/* ── Sliding Preview Sidebar ── */}
      <AnimatePresence>
        {previewImage && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setPreviewImage(null)}
              className="fixed inset-0 bg-black/60 z-40 backdrop-blur-sm"
            />
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="fixed top-0 right-0 h-screen w-full md:w-[600px] lg:w-[800px] bg-card border-l border-border z-50 shadow-2xl flex flex-col"
            >
              <div className="p-4 border-b border-border flex justify-between items-center bg-surface">
                <h3 className="font-bold text-lg text-white">Vista Previa</h3>
                <button 
                  onClick={() => setPreviewImage(null)} 
                  className="p-2 hover:bg-white/10 rounded-lg text-text-muted hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="flex-1 overflow-auto p-6 flex items-center justify-center bg-black/50">
                <img 
                  src={previewImage} 
                  alt="Vista Previa" 
                  className="max-w-full h-auto object-contain shadow-lg rounded-md" 
                />
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── Region Selector Modal ── */}
      {regionSelectorState && (
        <RegionSelector
          imageUrl={regionSelectorState.imageUrl}
          initialRegions={regionSelectorState.initialRegions}
          layoutType={regionSelectorState.layoutType}
          onSave={handleSaveRegions}
          onCancel={() => setRegionSelectorState(null)}
        />
      )}
    </>
  )
}
