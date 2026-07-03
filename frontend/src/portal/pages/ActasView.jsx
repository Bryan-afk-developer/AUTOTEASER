import React, { useRef, useState } from 'react'
import { ArrowLeft, Plus, FileText, XCircle, RefreshCw, Trash2, CheckCircle2, Loader2, Sparkles, ChevronRight } from 'lucide-react'
import api from '../lib/api'
import AiSummarySlideover from '../components/AiSummarySlideover'

export default function ActasView({ expediente, docs_subidos, onBack, fetchExpediente, onUpload }) {
  const actasRequeridas = expediente?.documentos?.filter(d => d.clave.startsWith('acta_constitutiva')) || []
  const fileInputRef = useRef(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [processingClave, setProcessingClave] = useState(null)
  const [selectedAiSummary, setSelectedAiSummary] = useState(null)

  const uploadFiles = async (files) => {
    if (!files || files.length === 0) return

    setIsUploading(true)
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const clave = `acta_constitutiva_${Date.now()}_${i}`
        await api.subirDocumento(clave, file)
      }
      await fetchExpediente()
    } catch (error) {
      alert(error.message || 'Error al subir actas')
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleMassiveUpload = (e) => uploadFiles(e.target.files)

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    uploadFiles(e.dataTransfer.files)
  }

  const handleEliminarActa = async (clave) => {
    if (!confirm('¿Estás seguro de eliminar esta acta? Esta acción no se puede deshacer.')) return

    try {
      await api.eliminarDocumento(clave)
      await fetchExpediente()
    } catch (error) {
      alert(error.response?.data?.detail || 'Error al eliminar el acta')
    }
  }

  const handleProcesarIA = async (clave) => {
    setProcessingClave(clave)
    try {
      await api.procesarActaPrincipal(clave)
      await fetchExpediente()
    } catch (error) {
      alert(error.message || 'Error al procesar acta con IA')
    } finally {
      setProcessingClave(null)
    }
  }

  return (
    <div
      className="animate-fade-in relative"
      style={{ padding: '32px', minHeight: '400px' }}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Drag overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-50 bg-primary-500/10 backdrop-blur-sm border-2 border-dashed border-primary-500 rounded-3xl flex items-center justify-center pointer-events-none">
          <div className="bg-surface p-6 rounded-2xl shadow-xl flex flex-col items-center gap-3">
            <div className="w-16 h-16 bg-primary-500/20 rounded-full flex items-center justify-center">
              <Plus className="w-8 h-8 text-primary-400" />
            </div>
            <p className="text-xl font-bold text-white">Suelta tus actas aquí</p>
            <p className="text-sm text-text-muted">Se subirán automáticamente</p>
          </div>
        </div>
      )}

      <button
        onClick={onBack}
        className="flex items-center gap-2 text-text-muted hover:text-white transition-colors mb-6 text-sm font-semibold"
      >
        <ArrowLeft className="w-4 h-4" />
        Volver al Expediente
      </button>

      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-black tracking-tight text-white flex items-center gap-3">
            <span className="text-3xl">📜</span> Actas Constitutivas y Asambleas
          </h2>
          <p className="text-text-muted mt-2 text-sm max-w-2xl">
            Sube tu acta constitutiva original y cualquier acta de asamblea extraordinaria, modificaciones de estatutos, o poderes notariales relevantes. Puedes seleccionar múltiples archivos a la vez.
          </p>
        </div>

        {/* Input oculto para subida masiva */}
        <input
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png"
          ref={fileInputRef}
          style={{ display: 'none' }}
          onChange={handleMassiveUpload}
        />

        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className={`bg-primary-500 hover:bg-primary-400 text-white font-bold py-2.5 px-5 rounded-xl shadow-[0_0_15px_rgba(99,102,241,0.4)] flex items-center gap-2 transition-all ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          {isUploading ? 'Subiendo Actas...' : 'Agregar Actas'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {actasRequeridas.length === 0 && (
          <div className="col-span-full py-12 text-center text-text-muted bg-surface/30 border border-border rounded-2xl">
            No hay actas registradas, Arrastra para agregar actas o presiona el boton "Agregar Actas".
          </div>
        )}

        {actasRequeridas.map((docReq) => {
          const isUploaded = docReq.estado !== 'FALTANTE'
          const isPrincipal = expediente?.acta_principal?.clave_principal === docReq.clave

          return (
            <div
              key={docReq.clave}
              className={`bg-surface border rounded-2xl p-5 flex flex-col gap-3 transition-all ${docReq.estado === 'RECHAZADO' ? 'border-rose-500/50 bg-rose-500/5' :
                  docReq.estado === 'APROBADO' ? 'border-emerald-500/30' : 
                  isPrincipal ? 'border-indigo-500/50 shadow-[0_0_20px_rgba(99,102,241,0.2)]' : 'border-border hover:border-primary-500/50'
                }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2 text-lg font-bold">
                  <FileText className={`w-5 h-5 ${isPrincipal ? 'text-indigo-400' : 'text-primary-400'}`} />
                  {docReq.nombre}
                </div>
                {/* Status Badge */}
                {isPrincipal && <span className="bg-indigo-500/20 text-indigo-400 text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-widest flex items-center gap-1"><Sparkles className="w-3 h-3" /> Principal</span>}
                {docReq.estado === 'APROBADO' && <span className="bg-emerald-500/20 text-emerald-400 text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-widest flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Aprobado</span>}
                {docReq.estado === 'PENDIENTE' && <span className="bg-amber-500/20 text-amber-400 text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-widest">En Revisión</span>}
                {docReq.estado === 'RECHAZADO' && <span className="bg-rose-500/20 text-rose-400 text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-widest flex items-center gap-1"><XCircle className="w-3 h-3" /> Rechazado</span>}
                {docReq.estado === 'FALTANTE' && <span className="bg-slate-500/20 text-slate-400 text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-widest">Faltante</span>}
              </div>

              <p className="text-xs text-text-muted mt-1">{docReq.descripcion}</p>

              {docReq.estado === 'RECHAZADO' && docReq.comentario_admin && (
                <div className="mt-2 bg-rose-500/10 border border-rose-500/20 rounded-lg p-2.5 text-xs text-rose-400 font-medium">
                  {docReq.comentario_admin}
                </div>
              )}

              {/* Botón Ver Resumen IA */}
              {isPrincipal && expediente?.acta_principal?.ai_summary && (
                <button
                  onClick={() => setSelectedAiSummary({ aiSummary: expediente.acta_principal.ai_summary, pdfUrl: docReq.url_documento })}
                  className="mt-3 w-full bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 hover:text-white font-bold py-2.5 px-3 rounded-xl text-xs transition-colors flex items-center justify-between shadow-glow"
                >
                  <span className="flex items-center gap-1.5"><Sparkles className="w-4 h-4" /> Ver Resumen de IA</span>
                  <ChevronRight className="w-4 h-4 opacity-50" />
                </button>
              )}

              <div className="mt-auto pt-4 flex flex-wrap gap-2">
                {isUploaded ? (
                  <>
                    {!isPrincipal && (
                      <button 
                        onClick={() => handleProcesarIA(docReq.clave)}
                        disabled={processingClave === docReq.clave}
                        className="w-full bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-500/50 text-indigo-300 hover:text-white font-bold py-2 px-3 rounded-lg text-xs transition-colors flex items-center justify-center gap-1.5 mb-1"
                      >
                        {processingClave === docReq.clave ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                        {processingClave === docReq.clave ? 'Leyendo con IA (puede tardar ~30s)...' : '✨ Procesar con IA'}
                      </button>
                    )}
                    <button
                      onClick={() => onUpload(docReq)}
                      className="flex-1 bg-surface/50 hover:bg-primary-500/20 border border-border hover:border-primary-500/50 text-text-muted hover:text-primary-400 font-bold py-2 px-3 rounded-lg text-xs transition-colors flex items-center justify-center gap-1.5"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      Reemplazar
                    </button>
                    {/* Solo permitir borrar si NO está aprobado (por seguridad) */}
                    {docReq.estado !== 'APROBADO' && (
                      <button
                        onClick={() => handleEliminarActa(docReq.clave)}
                        className="bg-surface/50 hover:bg-rose-500/20 border border-border hover:border-rose-500/50 text-text-muted hover:text-rose-400 font-bold p-2 rounded-lg transition-colors flex items-center justify-center"
                        title="Borrar Acta"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </>
                ) : (
                  <button
                    onClick={() => onUpload(docReq)}
                    className="w-full bg-primary-500 hover:bg-primary-400 text-white font-bold py-2 px-3 rounded-lg text-xs transition-colors flex items-center justify-center gap-1.5 shadow-glow"
                  >
                    <Plus className="w-4 h-4" />
                    Subir Documento
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <AiSummarySlideover 
        isOpen={!!selectedAiSummary} 
        onClose={() => setSelectedAiSummary(null)} 
        aiSummary={selectedAiSummary?.aiSummary} 
        pdfUrl={selectedAiSummary?.pdfUrl}
      />
    </div>
  )
}
