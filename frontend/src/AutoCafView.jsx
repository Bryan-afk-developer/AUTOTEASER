import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { UploadCloud, CheckCircle2, XCircle, FileText, Loader2, AlertTriangle, FileSpreadsheet } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const STEP_UPLOAD = 1;
const STEP_PROCESS = 2;
const STEP_RESULTS = 3;

export default function AutoCafView() {
  const [currentStep, setCurrentStep] = useState(STEP_UPLOAD);
  
  // State: Upload
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef(null);
  
  // State: Process
  const [isProcessing, setIsProcessing] = useState(false);
  const [processedDocs, setProcessedDocs] = useState([]);
  const [validationReport, setValidationReport] = useState(null);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [processingError, setProcessingError] = useState(null);
  
  // State: Modal details
  const [selectedDocDetails, setSelectedDocDetails] = useState(null);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);

  
  // State: Results
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [generationError, setGenerationError] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);

  // Initial load
  useEffect(() => {
    async function loadTemplates() {
      try {
        const r = await axios.get(`${API_BASE}/api/caf/templates`);
        setTemplates(r.data.templates || []);
        if (r.data.templates?.length > 0) setSelectedTemplate(r.data.templates[0].name);
      } catch (err) {
        console.error("Error cargando plantillas CAF", err);
      }
    }
    loadTemplates();
  }, []);

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e) => { e.preventDefault(); setIsDragging(false); };
  
  const handleDrop = (e) => {
    e.preventDefault(); setIsDragging(false);
    if (e.dataTransfer.files) handleFilesAdded(Array.from(e.dataTransfer.files));
  };

  // Cargar documentos recientes
  const [recentDocs, setRecentDocs] = useState([]);
  const [selectedRecent, setSelectedRecent] = useState([]);

  useEffect(() => {
    const fetchRecentDocs = async () => {
      try {
        const r = await axios.get(`${API_BASE}/api/caf/documents`);
        // Filter out those that are still 'processing' or only show the last 5
        setRecentDocs((r.data.documents || []).slice(0, 5));
      } catch (e) {
        console.error("Error fetching recent docs:", e);
      }
    };
    if (currentStep === STEP_UPLOAD) {
      fetchRecentDocs();
    }
  }, [currentStep]);

  const toggleRecentDoc = (id) => {
    setSelectedRecent(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const handleUseRecentDocs = () => {
    const docsToUse = recentDocs.filter(d => selectedRecent.includes(d.id));
    if (docsToUse.length === 0) return;
    setProcessedDocs(docsToUse);
    setCurrentStep(STEP_RESULTS); // Skip to step 3
  };

  const handleFileSelect = (e) => {
    if (e.target.files) handleFilesAdded(Array.from(e.target.files));
  };

  const handleFilesAdded = (newFiles) => {
    const pdfs = newFiles.filter(f => f.name.toLowerCase().endsWith('.pdf') || f.type === 'application/pdf');
    if (pdfs.length === 0) return alert("Solo se permiten archivos PDF.");
    setFiles(prev => [...prev, ...pdfs]);
  };

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  // ── Step 1: Upload & Move to Process ──
  const handleUploadAndProceed = async () => {
    if (files.length === 0) return;
    setIsUploading(true);
    setProcessedDocs([]); // Solo limpiamos processedDocs si estamos subiendo nuevos archivos
    
    try {
      const fd = new FormData();
      files.forEach(f => fd.append('files', f));
      
      const r = await axios.post(`${API_BASE}/api/caf/upload-batch`, fd);
      const uploadedDocs = r.data.documents || [];
      
      setProcessedDocs(uploadedDocs.map(d => ({
        id: d.id,
        fileName: d.file_name,
        status: 'pending',
      })));
      
      setCurrentStep(STEP_PROCESS);
      handleProcessBatch(uploadedDocs.map(d => d.id));
    } catch (err) {
      alert('Error al subir archivos: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsUploading(false);
    }
  };

  // ── Step 2: Process Batch ──
  const handleProcessBatch = async (docIds) => {
    setIsProcessing(true);
    setProcessingError(null);
    setProgress({ current: 0, total: docIds.length });
    
    try {
      const results = [];
      const successfulDocs = [];
      
      // Process one by one for visual progress
      for (let i = 0; i < docIds.length; i++) {
        const id = docIds[i];
        setProgress({ current: i + 1, total: docIds.length });
        
        try {
          setProcessedDocs(prev => prev.map(d => d.id === id ? { ...d, status: 'processing' } : d));
          const r = await axios.post(`${API_BASE}/api/caf/process/${id}`);
          const method = r.data.method || 'Gemini + Deterministic';
          const warnings = r.data.warnings || [];
          
          results.push({ id, status: 'success', method, warnings });
          successfulDocs.push(id);
          
          setProcessedDocs(prev => prev.map(d => d.id === id ? { ...d, status: 'success', method, warnings } : d));
        } catch (err) {
          results.push({ id, status: 'error', error: err.response?.data?.detail || err.message });
          setProcessedDocs(prev => prev.map(d => d.id === id ? { ...d, status: 'error', error: err.response?.data?.detail || err.message } : d));
        }
      }
      
      // Fetch validation summary
      if (successfulDocs.length > 0) {
        try {
          const r = await axios.post(`${API_BASE}/api/caf/validation-summary`, { doc_ids: docIds });
          if (r.data.validation) setValidationReport(r.data.validation);
        } catch (err) {
          console.error("Error obteniendo validación", err);
        }
      }
    } catch (err) {
      setProcessingError(err.message);
    } finally {
      setIsProcessing(false);
    }
  };

  // ── Step 3: Generate Consolidated Excel ──
  const handleGenerate = async () => {
    if (!selectedTemplate) return;
    
    const successfulDocIds = processedDocs.filter(d => d.status === 'success').map(d => d.id);
    if (successfulDocIds.length === 0) return setGenerationError("No hay documentos válidos para consolidar.");
    
    setIsGenerating(true);
    setGenerationError(null);
    setDownloadUrl(null);
    
    try {
      const r = await axios.post(`${API_BASE}/api/caf/generate-consolidated`, { 
        doc_ids: successfulDocIds, 
        template_name: selectedTemplate 
      });
      setDownloadUrl(`${API_BASE}${r.data.download_url}`);
    } catch (err) {
      setGenerationError(err.response?.data?.detail || err.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = async () => {
    if (isDownloading) return;
    setIsDownloading(true);
    try {
      const response = await axios.get(downloadUrl, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      
      let filename = 'Consolidado_CAF.xlsx';
      const disposition = response.headers['content-disposition'];
      if (disposition && disposition.indexOf('attachment') !== -1) {
          const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
          const matches = filenameRegex.exec(disposition);
          if (matches != null && matches[1]) { 
            filename = matches[1].replace(/['"]/g, '');
          }
      }
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error("Error downloading file:", err);
      alert('Error descargando el archivo. Intenta de nuevo.');
    } finally {
      setIsDownloading(false);
    }
  };

  const resetAll = () => {
    setFiles([]);
    setProcessedDocs([]);
    setValidationReport(null);
    setDownloadUrl(null);
    setCurrentStep(STEP_UPLOAD);
  };

  const handleViewCafDocDetails = async (docId) => {
    try {
      const r = await axios.get(`${API_BASE}/api/caf/documents/${docId}`);
      setSelectedDocDetails(r.data);
      setIsDetailsModalOpen(true);
    } catch (err) {
      alert('Error al obtener detalles del documento: ' + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#1e1e2d] text-white">
      {/* Header */}
      <div className="p-6 border-b border-[#2b2b40] flex justify-between items-center bg-[#151521]">
        <div>
          <h2 className="text-2xl font-bold text-[#b0a4ff] flex items-center gap-2">
            <Database className="w-6 h-6" /> AutoCAF Pro
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            Validación y consolidación de Estados Financieros multi-año
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8 max-w-5xl mx-auto w-full">
        
        {/* STEPPER */}
        <div className="flex items-center justify-center mb-10">
          <StepIndicator num={1} label="Subir PDFs" active={currentStep >= 1} completed={currentStep > 1} onClick={() => setCurrentStep(1)} />
          <div className={`w-16 h-1 mx-4 rounded ${currentStep > 1 ? 'bg-[#7c6df0]' : 'bg-gray-700'}`} />
          <StepIndicator num={2} label="Análisis Contable" active={currentStep >= 2} completed={currentStep > 2} onClick={() => { if (currentStep > 1) setCurrentStep(2) }} />
          <div className={`w-16 h-1 mx-4 rounded ${currentStep > 2 ? 'bg-[#7c6df0]' : 'bg-gray-700'}`} />
          <StepIndicator num={3} label="Consolidado" active={currentStep >= 3} completed={currentStep > 3} onClick={() => { if (currentStep > 2) setCurrentStep(3) }} />
        </div>

        {/* --- STEP 1 --- */}
        {currentStep === STEP_UPLOAD && (
          <div className="animate-fade-in">
            <div 
              className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${isDragging ? 'border-[#7c6df0] bg-[#7c6df0]/10' : 'border-gray-600 hover:border-gray-500 bg-[#151521]'}`}
              onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <UploadCloud className="w-16 h-16 mx-auto mb-4 text-gray-400" />
              <h3 className="text-lg font-medium text-gray-200">Arrastra múltiples PDFs de EEFF aquí</h3>
              <p className="text-gray-500 mt-2 text-sm">O haz clic para explorar tus archivos</p>
              <input type="file" className="hidden" ref={fileInputRef} onChange={handleFileSelect} accept="application/pdf" multiple />
            </div>

            {files.length > 0 && (
              <div className="mt-6 space-y-2">
                <h4 className="text-sm font-medium text-gray-400">Archivos seleccionados ({files.length}):</h4>
                {files.map((f, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-[#151521] rounded-lg border border-gray-700">
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-blue-400" />
                      <span className="text-sm">{f.name}</span>
                    </div>
                    <button onClick={() => removeFile(i)} className="text-gray-500 hover:text-red-400">
                      <XCircle className="w-5 h-5" />
                    </button>
                  </div>
                ))}
                
                <div className="mt-8 flex justify-end">
                  <button 
                    onClick={handleUploadAndProceed} disabled={isUploading}
                    className="flex items-center gap-2 bg-[#7c6df0] hover:bg-[#6a5bdf] text-white px-6 py-3 rounded-lg font-medium transition-colors"
                  >
                    {isUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : null}
                    {isUploading ? 'Subiendo...' : `Analizar ${files.length} Documentos ➔`}
                  </button>
                </div>
              </div>
            )}

            {/* CACHE / RECIENTES */}
            {recentDocs.length > 0 && files.length === 0 && (
              <div className="mt-12">
                <h4 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
                  <Database className="w-4 h-4" /> Últimos documentos procesados (Caché)
                </h4>
                <div className="space-y-2">
                  {recentDocs.map((doc) => (
                    <div key={doc.id} className="flex items-center justify-between p-3 bg-[#151521] rounded-lg border border-gray-700 hover:border-gray-600 transition-colors cursor-pointer" onClick={() => toggleRecentDoc(doc.id)}>
                      <div className="flex items-center gap-3">
                        <div className={`w-5 h-5 rounded border flex items-center justify-center ${selectedRecent.includes(doc.id) ? 'bg-[#7c6df0] border-[#7c6df0]' : 'border-gray-500'}`}>
                          {selectedRecent.includes(doc.id) && <CheckCircle2 className="w-4 h-4 text-white" />}
                        </div>
                        <span className="text-sm">{doc.file_name}</span>
                        <span className="text-xs px-2 py-0.5 bg-gray-800 rounded text-gray-400">{doc.uploaded_at?.split('T')[0]}</span>
                      </div>
                      <div className="flex gap-2">
                         {doc.status === 'processed' ? <span className="text-xs text-green-400">Procesado</span> : <span className="text-xs text-yellow-400">Error</span>}
                      </div>
                    </div>
                  ))}
                </div>
                {selectedRecent.length > 0 && (
                  <div className="mt-4 flex justify-end">
                    <button 
                      onClick={handleUseRecentDocs}
                      className="flex items-center gap-2 bg-[#1e1e2d] border border-[#7c6df0] text-[#b0a4ff] hover:bg-[#7c6df0]/10 px-6 py-2 rounded-lg font-medium transition-colors"
                    >
                      Continuar con {selectedRecent.length} seleccionados ➔
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* --- STEP 2 --- */}
        {currentStep === STEP_PROCESS && (
          <div className="animate-fade-in space-y-6">
            <h3 className="text-xl font-semibold">Procesando y Validando...</h3>
            
            {isProcessing && (
              <div className="bg-[#151521] p-5 rounded-xl border border-gray-700">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-400">Extrayendo datos y validando ecuaciones...</span>
                  <span className="font-medium">{progress.current} / {progress.total}</span>
                </div>
                <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-blue-500 to-[#7c6df0] transition-all duration-300" 
                       style={{ width: `${(progress.current / Math.max(progress.total, 1)) * 100}%` }} />
                </div>
              </div>
            )}

            {validationReport && (
              <div className={`p-5 rounded-xl border flex items-start gap-4 ${validationReport.overall_valid ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
                {validationReport.overall_valid ? 
                  <CheckCircle2 className="w-8 h-8 text-green-400 flex-shrink-0" /> : 
                  <AlertTriangle className="w-8 h-8 text-red-400 flex-shrink-0" />
                }
                <div>
                  <h4 className={`text-lg font-semibold ${validationReport.overall_valid ? 'text-green-400' : 'text-red-400'}`}>
                    {validationReport.overall_valid ? 'Validación Contable Exitosa' : 'Discrepancias Contables Detectadas'}
                  </h4>
                  <p className="text-sm text-gray-300 mt-1">
                    Años procesados: {validationReport.years_processed?.join(', ')}. Balances OK: {validationReport.summary?.balance_ok}.
                  </p>
                  
                  <div className="flex gap-3 mt-4 flex-wrap">
                    {Object.entries(validationReport.balance || {}).map(([year, val]) => (
                      <div key={year} className="bg-[#1e1e2d] px-4 py-2 rounded-lg border border-gray-700">
                        <div className="text-xs text-gray-400 font-medium">Balance {year}</div>
                        <div className={`font-semibold ${val.valid ? 'text-green-400' : 'text-red-400'}`}>
                          {val.valid ? 'Cuadra' : `Δ ${val.diferencia.toLocaleString()}`}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-3">
              {processedDocs.map(doc => (
                <div key={doc.id} className="flex items-center justify-between p-4 bg-[#151521] rounded-xl border border-gray-700">
                  <div className="flex items-center gap-3">
                    {doc.status === 'success' && <CheckCircle2 className="w-5 h-5 text-green-400" />}
                    {doc.status === 'error' && <XCircle className="w-5 h-5 text-red-400" />}
                    {doc.status === 'processing' && <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />}
                    {doc.status === 'pending' && <FileText className="w-5 h-5 text-gray-500" />}
                    <div>
                      <div className="font-medium text-sm">{doc.fileName}</div>
                      {doc.error && <div className="text-xs text-red-400 mt-1">{doc.error}</div>}
                      {doc.warnings && doc.warnings.length > 0 && (
                        <div className="text-xs text-yellow-400 mt-1 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          <span>Balance ajustado matemáticamente — revisar datos</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {(doc.status === 'success' || doc.status === 'error') && (
                      <button 
                        onClick={() => handleViewCafDocDetails(doc.id)}
                        className="bg-[#2b2b40] hover:bg-[#3b3b55] text-xs px-3 py-1.5 rounded transition-colors"
                      >
                        👁️ Ver Info
                      </button>
                    )}
                    {doc.method && (
                      <span className="text-xs px-2 py-1.5 bg-gray-800 rounded font-medium text-gray-300">
                        🤖 {doc.method}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {!isProcessing && (
              <div className="flex justify-end gap-3 mt-8">
                <button onClick={resetAll} className="px-5 py-2 rounded-lg text-gray-300 hover:bg-gray-800">
                  Cancelar
                </button>
                <button 
                  onClick={() => setCurrentStep(STEP_RESULTS)}
                  disabled={processedDocs.filter(d => d.status === 'success').length === 0}
                  className="bg-[#7c6df0] hover:bg-[#6a5bdf] disabled:opacity-50 text-white px-6 py-2 rounded-lg font-medium"
                >
                  Siguiente: Consolidación ➔
                </button>
              </div>
            )}
          </div>
        )}

        {/* --- STEP 3 --- */}
        {currentStep === STEP_RESULTS && (
          <div className="animate-fade-in grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div>
              <h3 className="text-xl font-semibold mb-2">Generar Excel Consolidado</h3>
              <p className="text-sm text-gray-400 mb-6">Selecciona la plantilla Excel. Los años extraídos se mapearán automáticamente a las columnas correspondientes.</p>
              
              <div className="space-y-3">
                {templates.length === 0 ? (
                  <div className="text-sm text-gray-500">No hay plantillas cargadas en el servidor.</div>
                ) : (
                  templates.map(t => (
                    <div 
                      key={t.name}
                      onClick={() => setSelectedTemplate(t.name)}
                      className={`p-4 rounded-xl border cursor-pointer transition-colors flex items-center gap-3 ${selectedTemplate === t.name ? 'border-[#7c6df0] bg-[#7c6df0]/10' : 'border-gray-700 bg-[#151521] hover:border-gray-500'}`}
                    >
                      <FileSpreadsheet className={`w-6 h-6 ${selectedTemplate === t.name ? 'text-[#7c6df0]' : 'text-gray-500'}`} />
                      <div>
                        <div className="font-medium text-sm">{t.name}</div>
                        <div className="text-xs text-gray-500">{t.size}</div>
                      </div>
                    </div>
                  ))
                )}
              </div>
              
              {generationError && <div className="mt-4 text-sm text-red-400">{generationError}</div>}
            </div>

            <div className="bg-[#151521] p-6 rounded-xl border border-gray-700 h-fit">
              <h4 className="font-medium text-gray-300 mb-4">Años Listos para Exportar</h4>
              <div className="flex flex-wrap gap-2 mb-8">
                {validationReport?.years_processed?.map(year => (
                  <span key={year} className="bg-[#1e1e2d] border border-gray-700 px-3 py-1 rounded text-sm font-medium">
                    {year}
                  </span>
                )) || <span className="text-gray-500 text-sm">Sin datos de años disponibles</span>}
              </div>

              {!downloadUrl ? (
                <button 
                  onClick={handleGenerate} disabled={!selectedTemplate || isGenerating}
                  className="w-full flex items-center justify-center gap-2 bg-[#7c6df0] hover:bg-[#6a5bdf] disabled:opacity-50 text-white px-6 py-3 rounded-xl font-medium transition-colors"
                >
                  {isGenerating ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                  {isGenerating ? 'Generando...' : 'Generar Archivo Consolidado'}
                </button>
              ) : (
                <div className="space-y-3">
                  <button 
                    onClick={handleDownload}
                    disabled={isDownloading}
                    className="w-full flex items-center justify-center gap-2 bg-green-600 hover:bg-green-500 disabled:bg-green-800 disabled:opacity-70 text-white px-6 py-3 rounded-xl font-medium transition-colors"
                  >
                    {isDownloading ? <Loader2 className="w-5 h-5 animate-spin" /> : '⬇️'} 
                    {isDownloading ? 'Descargando...' : 'Descargar Excel Consolidado'}
                  </button>
                  <button onClick={resetAll} className="w-full py-2 text-sm text-gray-400 hover:text-white">
                    Empezar de nuevo
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Details Modal */}
      {isDetailsModalOpen && selectedDocDetails && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center z-[100] p-4" onClick={() => setIsDetailsModalOpen(false)}>
          <div className="bg-[#151521] border border-gray-700 rounded-xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="p-5 border-b border-gray-700 flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-200 flex items-center gap-2">
                <FileText className="w-5 h-5 text-[#7c6df0]" />
                Detalles: {selectedDocDetails.file_name}
              </h2>
              <div className="flex items-center gap-3">
                {selectedDocDetails.searchable_pdf_path && (
                  <a
                    href={`http://127.0.0.1:8000/api/caf/download-pdf/${selectedDocDetails.id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 bg-[#7c6df0]/20 text-[#7c6df0] hover:bg-[#7c6df0]/30 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
                  >
                    <FileText className="w-4 h-4" />
                    PDF con OCR
                  </a>
                )}
                <button className="text-gray-400 hover:text-white" onClick={() => setIsDetailsModalOpen(false)}>
                  <XCircle className="w-6 h-6" />
                </button>
              </div>
            </div>
            <div className="p-5 overflow-y-auto custom-scrollbar flex-1 space-y-6">
              
              <div>
                <h3 className="text-sm font-semibold text-[#7c6df0] mb-3 uppercase tracking-wider">Datos Extraídos (JSON)</h3>
                <pre className="bg-[#1e1e2d] border border-gray-700 p-4 rounded-lg text-sm text-gray-300 overflow-x-auto">
                  {JSON.stringify(selectedDocDetails.llm_result?.data || {}, null, 2)}
                </pre>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-[#7c6df0] mb-3 uppercase tracking-wider">Texto Crudo (OCR/PyMuPDF)</h3>
                <pre className="bg-[#1e1e2d] border border-gray-700 p-4 rounded-lg text-sm text-gray-300 overflow-y-auto max-h-[400px] whitespace-pre-wrap">
                  {selectedDocDetails.extracted_text || selectedDocDetails.extraction?.full_text || "No hay texto disponible."}
                </pre>
              </div>

            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StepIndicator({ num, label, active, completed, onClick }) {
  return (
    <div 
      className={`flex flex-col items-center ${onClick ? 'cursor-pointer hover:opacity-80 transition-opacity' : ''}`}
      onClick={onClick}
    >
      <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-colors
        ${completed ? 'bg-green-500/20 text-green-400 border-2 border-green-500/50' : 
          active ? 'bg-[#7c6df0]/20 text-[#7c6df0] border-2 border-[#7c6df0]' : 
          'bg-gray-800 text-gray-500 border-2 border-gray-700'}`}
      >
        {completed ? <CheckCircle2 className="w-5 h-5" /> : num}
      </div>
      <span className={`text-xs mt-2 font-medium ${active || completed ? 'text-gray-200' : 'text-gray-500'}`}>
        {label}
      </span>
    </div>
  );
}

// Stub for missing icons if lucide-react doesn't have Sparkles or Database in this version
function Sparkles(props) { return <span {...props}>✨</span>; }
function Database(props) { return <span {...props}>🗄️</span>; }
