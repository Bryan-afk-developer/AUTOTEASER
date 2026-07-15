import { useState, useCallback, useEffect } from 'react'
import api from '../lib/api'
import BancosView from './BancosView'
import ActasView from './ActasView'

const ESTADO_CONFIG = {
  APROBADO: { color: '#22c55e', bg: 'rgba(34,197,94,0.12)', border: 'rgba(34,197,94,0.3)', icon: '✅', label: 'Aprobado' },
  PENDIENTE: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.3)', icon: '⏳', label: 'En Revisión' },
  RECHAZADO: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)', icon: '❌', label: 'Rechazado' },
  FALTANTE: { color: '#64748b', bg: 'rgba(100,116,139,0.1)', border: 'rgba(100,116,139,0.25)', icon: '', label: 'Faltante' },
}

// ══════════════════════════════════════════════════════════════════════════════
// UPLOAD MODAL — acepta cualquier tipo de archivo
// ══════════════════════════════════════════════════════════════════════════════

// ── EEFF AI Upload Modal ────────────────────────────────────────────────────────

function EEFFAIAUploadModal({ empresaId, onClose, onSuccess }) {
  const [files, setFiles] = useState([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const droppedFiles = Array.from(e.dataTransfer.files)
    if (droppedFiles.length > 0) { 
      setFiles(prev => [...prev, ...droppedFiles])
      setError('') 
    }
  }, [])

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files)
    if (selectedFiles.length > 0) { 
      setFiles(prev => [...prev, ...selectedFiles])
      setError('') 
    }
  }

  const handleRemoveFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (files.length === 0) return
    setUploading(true)
    setError('')
    
    const remainingFiles = []
    let successCount = 0
    let lastError = ""

    for (const file of files) {
      try {
        await api.subirEstadosFinancierosAuto(empresaId, file)
        successCount++
      } catch (err) {
        remainingFiles.push(file)
        lastError = err.message || 'Error al subir un documento'
      }
    }

    setFiles(remainingFiles)
    setUploading(false)

    if (successCount > 0 && remainingFiles.length === 0) {
      alert(`¡Éxito! ${successCount} archivo(s) procesados con IA.`)
      onSuccess()
      onClose()
    } else if (successCount > 0 && remainingFiles.length > 0) {
      setError(`Se subieron ${successCount} archivo(s), pero fallaron otros. Error: ${lastError}`)
      onSuccess() // update UI for the ones that succeeded
    } else {
      setError(lastError || 'No se pudo subir ningún archivo.')
    }
  }

  return (
    <div style={modalStyles.overlay} onClick={onClose}>
      <div style={{ ...modalStyles.modal, maxWidth: '500px' }} onClick={(e) => e.stopPropagation()}>
        <div style={modalStyles.header}>
          <h3 style={{ margin: 0, fontSize: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            📊 Subir Estados Financieros
          </h3>
          <button style={modalStyles.closeButton} onClick={onClose}>✕</button>
        </div>
        <div style={modalStyles.body}>
          <p className="text-sm text-text-muted mb-4 text-center">
            Arrastra aquí tus archivos PDF de los Estados Financieros. Nuestra IA leerá las primeras páginas para detectar el año de cada uno automáticamente.
          </p>

          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-10 text-center transition-all ${
              dragging ? 'border-primary-500 bg-primary-500/10' : 'border-border bg-surface'
            }`}
          >
            {files.length > 0 ? (
              <div className="space-y-4">
                <div className="flex flex-col gap-2 max-h-48 overflow-y-auto pr-2">
                  {files.map((file, idx) => (
                    <div key={idx} className="p-3 bg-background rounded-lg border border-border flex items-center justify-between">
                      <div className="flex flex-col text-left">
                        <p className="text-sm font-semibold text-text-main flex items-center gap-2">
                          📄 <span className="truncate max-w-[200px]">{file.name}</span>
                        </p>
                        <p className="text-xs text-text-muted mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                      </div>
                      <button
                        onClick={() => handleRemoveFile(idx)}
                        className="text-xs text-rose-400 hover:text-rose-300 font-semibold px-2 py-1"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
                <label className="cursor-pointer text-sm font-semibold text-primary-400 hover:text-primary-300 transition-colors inline-block mt-2">
                  <span>+ Agregar más archivos</span>
                  <input type="file" accept=".pdf" multiple className="hidden" onChange={handleFileChange} />
                </label>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="w-12 h-12 bg-primary-500/10 rounded-full flex items-center justify-center mx-auto text-primary-400 text-2xl">
                  📄
                </div>
                <p className="text-sm text-text-main font-semibold">
                  Arrastra tus PDFs aquí o
                </p>
                <label className="cursor-pointer text-sm font-semibold text-primary-400 hover:text-primary-300 transition-colors inline-block">
                  <span>Selecciona archivos</span>
                  <input type="file" accept=".pdf" multiple className="hidden" onChange={handleFileChange} />
                </label>
              </div>
            )}
          </div>

          {error && (
            <div className="mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm flex items-start gap-2">
              <span className="mt-0.5 flex-shrink-0">⚠️</span>
              <p>{error}</p>
            </div>
          )}

          <div style={modalStyles.footer} className="mt-6">
            <button style={modalStyles.buttonSecondary} onClick={onClose} disabled={uploading}>
              Cancelar
            </button>
            <button 
              style={{...modalStyles.buttonPrimary, opacity: (files.length === 0 || uploading) ? 0.5 : 1}} 
              onClick={handleUpload} 
              disabled={files.length === 0 || uploading}
              className="flex items-center gap-2"
            >
              {uploading ? (
                <>
                  <span className="animate-spin">⏳</span>
                  Analizando con IA...
                </>
              ) : 'Subir y Analizar'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function UploadModal({ doc, onClose, onSuccess }) {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) { setFile(f); setError('') }
  }, [])

  const handleFileChange = (e) => {
    const f = e.target.files[0]
    if (f) { setFile(f); setError('') }
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError('')
    try {
      const res = await api.subirDocumento(doc.clave, file)
      
      if (res.requires_justification) {
        const justification = window.prompt("Hemos detectado que tu Opinión de Cumplimiento es NEGATIVA.\n\nSi lo deseas, puedes proveer una justificación breve para el equipo de crédito (opcional):")
        if (justification && justification.trim().length > 0) {
          await api.justificarDocumento(res.documento_id, justification.trim())
        }
      }
      
      onSuccess()
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div style={modalStyles.overlay} onClick={onClose}>
      <div style={modalStyles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={modalStyles.header}>
          <h3 style={modalStyles.title}>{doc.icono} {doc.nombre}</h3>
          <button id="modal-close-btn" onClick={onClose} style={modalStyles.closeBtn}>✕</button>
        </div>
        <p style={modalStyles.desc}>{doc.descripcion}</p>

        <div
          id="upload-dropzone"
          style={{ ...modalStyles.dropzone, ...(dragging ? modalStyles.dropzoneDrag : {}) }}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => document.getElementById('file-input-hidden').click()}
        >
          <input id="file-input-hidden" type="file" onChange={handleFileChange} style={{ display: 'none' }} />
          {file ? (
            <div>
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>📄</div>
              <p style={{ color: '#e2e8f0', fontWeight: 600, margin: 0 }}>{file.name}</p>
              <p style={{ color: '#94a3b8', fontSize: '12px', margin: '4px 0 0' }}>
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: '40px', marginBottom: '12px' }}>☁️</div>
              <p style={{ color: '#cbd5e1', fontWeight: 600, margin: 0 }}>Arrastra tu archivo aquí</p>
              <p style={{ color: '#64748b', fontSize: '13px', margin: '6px 0 0' }}>o haz clic para seleccionar</p>
              <p style={{ color: '#94a3b8', fontSize: '11px', margin: '8px 0 0', fontStyle: 'italic' }}>
                De preferencia en formato PDF
              </p>
            </div>
          )}
        </div>

        {error && <p style={modalStyles.error}>⚠️ {error}</p>}

        {doc.estado === 'RECHAZADO' && doc.comentario_admin && (
          <div style={modalStyles.comentarioBox}>
            <strong>💬 Motivo de rechazo:</strong> {doc.comentario_admin}
          </div>
        )}

        <div style={modalStyles.actions}>
          <button id="btn-cancelar-upload" onClick={onClose} style={modalStyles.btnSecondary}>
            Cancelar
          </button>
          <button
            id="btn-confirmar-upload"
            onClick={handleUpload}
            disabled={!file || uploading}
            style={{ ...modalStyles.btnPrimary, ...(!file || uploading ? modalStyles.btnDisabled : {}) }}
          >
            {uploading ? '⏳ Subiendo...' : 'Subir Documento'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// DOCUMENT CARD — tarjeta individual para docs simples
// ══════════════════════════════════════════════════════════════════════════════

function DocumentCard({ doc, onUpload, onSuccess }) {
  const cfg = ESTADO_CONFIG[doc.estado] || ESTADO_CONFIG.FALTANTE

  return (
    <div
      id={`doc-card-${doc.clave}`}
      style={{
        ...cardStyles.card,
        borderColor: cfg.border,
        background: `linear-gradient(135deg, rgba(24,24,27,0.9) 0%, ${cfg.bg} 100%)`,
      }}
    >
      <div style={cardStyles.topRow}>
        <div style={cardStyles.iconWrap}>
          <span style={{ fontSize: '22px' }}>{doc.icono}</span>
        </div>
        <span style={{ ...cardStyles.badge, background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
          {cfg.icon} {cfg.label}
        </span>
      </div>

      <h4 style={cardStyles.docName}>{doc.nombre}</h4>
      <p style={cardStyles.docDesc}>{doc.descripcion}</p>

      {doc.comentario_admin && doc.estado === 'RECHAZADO' && (
        <div style={cardStyles.comentario}>
          💬 <em>{doc.comentario_admin}</em>
        </div>
      )}

      {doc.nombre_archivo && (
        <p style={cardStyles.fileName}>📎 {doc.nombre_archivo}</p>
      )}

      {doc.subido_en && (
        <p style={cardStyles.fecha}>
          {doc.estado === 'APROBADO' ? '✅ Aprobado' : '📤 Subido'}{' '}
          {new Date(doc.subido_en).toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' })}
        </p>
      )}

      {doc.estado !== 'FALTANTE' && (
        <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
          {doc.url_documento && (
            <button
              onClick={() => window.open(doc.url_documento, '_blank')}
              style={{ flex: 1, padding: '8px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', cursor: 'pointer', fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
            >
              👁️ Ver PDF
            </button>
          )}
          <button
            onClick={async () => {
              if (window.confirm(`¿Seguro que deseas eliminar el archivo de ${doc.nombre}?`)) {
                try {
                  await api.eliminarDocumento(doc.clave);
                  if (onSuccess) onSuccess();
                } catch (err) {
                  alert('Error al eliminar: ' + err.message);
                }
              }
            }}
            style={{ padding: '8px 14px', borderRadius: '8px', background: 'rgba(239,68,68,0.1)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.2)', cursor: 'pointer', fontSize: '14px', flexShrink: 0 }}
            title="Eliminar"
          >
            🗑️
          </button>
        </div>
      )}

      <button
        id={`btn-subir-${doc.clave}`}
        onClick={() => onUpload(doc)}
        style={{
          ...cardStyles.uploadBtn,
          marginTop: doc.estado !== 'FALTANTE' ? '8px' : 'auto',
          background: doc.estado === 'RECHAZADO'
            ? 'linear-gradient(135deg, #ef4444, #dc2626)'
            : doc.estado === 'FALTANTE'
              ? 'linear-gradient(135deg, #e11d48, #be123c)'
              : 'rgba(255,255,255,0.1)',
          border: (doc.estado !== 'FALTANTE' && doc.estado !== 'RECHAZADO') ? '1px solid rgba(255,255,255,0.2)' : 'none',
        }}
      >
        {doc.estado === 'RECHAZADO' ? 'Volver a Subir'
          : doc.estado === 'FALTANTE' ? 'Subir Documento'
            : 'Reemplazar Archivo'}
      </button>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// GROUPED CARD — tarjeta resumen para grupos con modal desplegable
// ══════════════════════════════════════════════════════════════════════════════

function GroupedCard({ title, icon, description, docs, onOpenModal }) {
  const total = docs.length
  const aprobados = docs.filter(d => d.estado === 'APROBADO').length
  const faltantes = docs.filter(d => d.estado === 'FALTANTE').length
  const rechazados = docs.filter(d => d.estado === 'RECHAZADO').length

  let statusKey = 'FALTANTE'
  if (aprobados === total) statusKey = 'APROBADO'
  else if (aprobados > 0) statusKey = 'PENDIENTE'
  if (rechazados > 0) statusKey = 'RECHAZADO'

  const cfg = ESTADO_CONFIG[statusKey]

  return (
    <div style={{
      ...cardStyles.card,
      borderColor: cfg.border,
      background: `linear-gradient(135deg, rgba(24,24,27,0.9) 0%, ${cfg.bg} 100%)`,
    }}>
      <div style={cardStyles.topRow}>
        <div style={cardStyles.iconWrap}>
          <span style={{ fontSize: '22px' }}>{icon}</span>
        </div>
        <span style={{ ...cardStyles.badge, background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
          {aprobados} / {total} Aprobados
        </span>
      </div>

      <h4 style={cardStyles.docName}>{title}</h4>
      <p style={cardStyles.docDesc}>{description}</p>

      {faltantes > 0 && (
        <p style={{ margin: '4px 0 0', color: '#fca5a5', fontSize: '12px', fontWeight: 600 }}>
          ⚠️ Faltan {faltantes} por subir
        </p>
      )}
      {rechazados > 0 && (
        <p style={{ margin: '2px 0 0', color: '#fca5a5', fontSize: '12px', fontWeight: 600 }}>
          ❌ {rechazados} rechazados
        </p>
      )}

      <button
        onClick={onOpenModal}
        style={{
          ...cardStyles.uploadBtn,
          background: 'rgba(255,255,255,0.1)',
          border: '1px solid rgba(255,255,255,0.2)',
          marginTop: 'auto',
        }}
      >
        👁️ Ver documentos
      </button>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// GROUPED MODAL — modal con lista de documentos (sin sub-secciones)
// ══════════════════════════════════════════════════════════════════════════════

function GroupedModal({ title, icon, description, docs, onClose, onUpload, onSuccess }) {
  return (
    <div style={modalStyles.overlay} onClick={onClose}>
      <div style={{ ...modalStyles.modal, maxWidth: '640px' }} onClick={(e) => e.stopPropagation()}>
        <div style={modalStyles.header}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '28px' }}>{icon}</span>
            <div>
              <h3 style={modalStyles.title}>{title}</h3>
              <p style={modalStyles.desc}>{description}</p>
            </div>
          </div>
          <button onClick={onClose} style={modalStyles.closeBtn}>✕</button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '65vh', overflowY: 'auto', paddingRight: '4px' }}>
          {docs.map(doc => {
            const cfg = ESTADO_CONFIG[doc.estado] || ESTADO_CONFIG.FALTANTE
            return (
              <div key={doc.clave} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '14px 16px', borderRadius: '12px',
                background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', flex: 1, minWidth: 0 }}>
                  <span style={{ color: '#e2e8f0', fontSize: '13px', fontWeight: 600 }}>
                    {doc.icono} {doc.nombre}
                  </span>
                  {doc.nombre_archivo && (
                    <span style={{ color: '#64748b', fontSize: '11px', fontStyle: 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      📎 {doc.nombre_archivo}
                    </span>
                  )}
                  {doc.comentario_admin && doc.estado === 'RECHAZADO' && (
                    <span style={{ color: '#fca5a5', fontSize: '11px' }}>
                      💬 {doc.comentario_admin}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
                  <span style={{
                    padding: '4px 10px', borderRadius: '16px', fontSize: '11px', fontWeight: 700,
                    background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}`,
                  }}>
                    {cfg.icon} {cfg.label}
                  </span>
                  <button
                    onClick={() => onUpload(doc)}
                    style={{
                      padding: '6px 14px', borderRadius: '8px', border: (doc.estado !== 'FALTANTE' && doc.estado !== 'RECHAZADO') ? '1px solid rgba(255,255,255,0.2)' : 'none',
                      background: doc.estado === 'RECHAZADO'
                        ? 'linear-gradient(135deg, #ef4444, #dc2626)'
                        : doc.estado === 'FALTANTE'
                          ? 'linear-gradient(135deg, #e11d48, #be123c)'
                          : 'rgba(255,255,255,0.1)',
                      color: '#fff', fontSize: '12px', fontWeight: 700, cursor: 'pointer',
                    }}
                  >
                    {doc.estado === 'RECHAZADO' ? 'Resubir'
                      : doc.estado === 'FALTANTE' ? 'Subir'
                        : 'Reemplazar'}
                  </button>
                  {doc.estado !== 'FALTANTE' && (
                    <div style={{ display: 'flex', gap: '6px' }}>
                      {doc.url_documento && (
                        <button
                          onClick={() => window.open(doc.url_documento, '_blank')}
                          style={{
                            padding: '6px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center'
                          }}
                          title="Ver PDF"
                        >
                          👁️
                        </button>
                      )}
                      <button
                        onClick={async () => {
                          if (window.confirm(`¿Seguro que deseas eliminar el archivo de ${doc.nombre}?`)) {
                            try {
                              await api.eliminarDocumento(doc.clave);
                              if (onSuccess) onSuccess();
                            } catch (err) {
                              alert('Error al eliminar: ' + err.message);
                            }
                          }
                        }}
                        style={{
                          padding: '6px', borderRadius: '8px', background: 'rgba(239,68,68,0.1)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.2)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}
                        title="Eliminar"
                      >
                        🗑️
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}


// ══════════════════════════════════════════════════════════════════════════════
// DECLARACIONES VIEW — arrastrar y soltar PDFs del SAT para clasificación automática
// ══════════════════════════════════════════════════════════════════════════════

function DeclaracionesView({ declaraciones, declaracionesCompleto, onSuccess, onBack }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [selectedDocs, setSelectedDocs] = useState(new Set())
  const [eliminandoMultiples, setEliminandoMultiples] = useState(false)

  const toggleSelection = (clave) => {
    const newSel = new Set(selectedDocs)
    if (newSel.has(clave)) newSel.delete(clave)
    else newSel.add(clave)
    setSelectedDocs(newSel)
  }

  const selectAll = () => {
    if (declaraciones && selectedDocs.size === declaraciones.length) {
      setSelectedDocs(new Set())
    } else {
      setSelectedDocs(new Set(declaraciones.map(d => d.clave)))
    }
  }

  const handleEliminarMultiples = async () => {
    if (!window.confirm(`¿Eliminar los ${selectedDocs.size} archivos seleccionados?`)) return
    setEliminandoMultiples(true)
    try {
      await Promise.all(Array.from(selectedDocs).map(clave => api.eliminarDocumento(clave)))
      setSelectedDocs(new Set())
      onSuccess()
    } catch (err) {
      alert('Error al eliminar algunos archivos: ' + err.message)
    } finally {
      setEliminandoMultiples(false)
    }
  }

  const handleDrop = useCallback(async (e) => {
    e.preventDefault()
    setDragging(false)
    const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf')
    if (!droppedFiles.length) return
    await handleAutoUpload(droppedFiles)
  }, [])

  const handleFileChange = async (e) => {
    const selectedFiles = Array.from(e.target.files).filter(f => f.type === 'application/pdf')
    if (!selectedFiles.length) return
    await handleAutoUpload(selectedFiles)
    e.target.value = ''
  }

  const handleAutoUpload = async (selectedFiles) => {
    setUploading(true)
    setUploadResult(null)
    try {
      const result = await api.subirDeclaracionesAuto(selectedFiles)
      setUploadResult(result)
      onSuccess()
    } catch (err) {
      setUploadResult({ error: err.message })
    } finally {
      setUploading(false)
    }
  }

  const handleEliminar = async (doc) => {
    if (!window.confirm(`¿Eliminar "${doc.nombre_archivo || doc.nombre}"?`)) return
    try {
      await api.eliminarDocumento(doc.clave)
      onSuccess()
    } catch (err) {
      alert('Error: ' + err.message)
    }
  }

  const tieneArchivos = declaraciones && declaraciones.length > 0

  return (
    <div style={{ animation: 'fadeIn 0.3s ease-in-out' }}>
      <button onClick={onBack} style={{ background: 'none', border: '1px solid rgba(255,255,255,0.15)', color: '#94a3b8', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', fontSize: '14px', marginBottom: '8px' }}>
        ← Volver al Dashboard
      </button>

      <div style={{ marginTop: '24px', marginBottom: '28px' }}>
        <h2 style={{ fontSize: '32px', fontWeight: 800, margin: 0, color: '#f8fafc', letterSpacing: '-0.5px' }}>
          🏨 Declaraciones Fiscales (SAT)
        </h2>
        <p style={{ color: '#94a3b8', fontSize: '15px', marginTop: '8px', maxWidth: '600px', lineHeight: 1.5 }}>
          Sube tus PDFs del SAT. El sistema los clasificará automáticamente si es posible.
        </p>
      </div>

      {/* Banner de mínimo requerido */}
      {!declaracionesCompleto && (
        <div style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: '12px', padding: '14px 18px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '20px' }}>⚠️</span>
          <div>
            <p style={{ color: '#fbbf24', fontWeight: 700, margin: 0, fontSize: '14px' }}>Mínimo 2 archivos requeridos</p>
            <p style={{ color: '#94a3b8', fontSize: '13px', margin: '2px 0 0' }}>Necesitamos las Declaraciones y Acuses de los últimos 3 años o los ultimos años que disponga.</p>
          </div>
        </div>
      )}
      {declaracionesCompleto && (
        <div style={{ background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: '12px', padding: '14px 18px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '20px' }}>✅</span>
          <p style={{ color: '#4ade80', fontWeight: 700, margin: 0, fontSize: '14px' }}>Mínimo requerido cubierto</p>
        </div>
      )}

      {/* Zona de Drop */}
      <div
        style={{
          border: `2px dashed ${dragging ? '#7c3aed' : 'rgba(124,58,237,0.3)'}`,
          borderRadius: '16px', padding: '36px', textAlign: 'center', cursor: 'pointer',
          background: dragging ? 'rgba(124,58,237,0.08)' : 'rgba(124,58,237,0.03)',
          transition: 'all 0.2s', marginBottom: '28px',
        }}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById('sat-file-input').click()}
      >
        <input id="sat-file-input" type="file" multiple accept=".pdf" onChange={handleFileChange} style={{ display: 'none' }} />
        <div style={{ fontSize: '40px', marginBottom: '12px' }}>{uploading ? '⏳' : '📤'}</div>
        <p style={{ color: '#f1f5f9', fontSize: '16px', fontWeight: 700, margin: 0 }}>
          {uploading ? 'Procesando archivos SAT...' : 'Arrastra tus PDFs del SAT aquí'}
        </p>
        <p style={{ color: '#64748b', fontSize: '13px', margin: '6px 0 0' }}>
          Acuses de Recibo y Declaraciones del Ejercicio de 2023 en adelante
        </p>
      </div>

      {/* Resultado del upload */}
      {uploadResult && (
        <div style={{ marginBottom: '20px' }}>
          {uploadResult.error && (
            <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '10px', padding: '14px', color: '#fca5a5', fontSize: '14px' }}>
              ⚠️ {uploadResult.error}
            </div>
          )}
          {uploadResult.detectados?.length > 0 && (
            <div style={{ background: 'rgba(34,197,94,0.07)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: '10px', padding: '14px', marginBottom: '8px' }}>
              <p style={{ color: '#4ade80', fontWeight: 700, margin: '0 0 6px', fontSize: '14px' }}>
                ✅ {uploadResult.detectados.length} archivo(s) clasificados automáticamente
              </p>
              {uploadResult.detectados.map((d, i) => (
                <p key={i} style={{ color: '#86efac', fontSize: '13px', margin: '2px 0' }}>
                  • {d.tipo} {d.year} → {d.nombre}
                </p>
              ))}
            </div>
          )}
          {uploadResult.no_detectados?.length > 0 && (
            <div style={{ background: 'rgba(148,163,184,0.06)', border: '1px solid rgba(148,163,184,0.15)', borderRadius: '10px', padding: '14px' }}>
              <p style={{ color: '#94a3b8', fontWeight: 700, margin: '0 0 6px', fontSize: '14px' }}>
                📁 {uploadResult.no_detectados.filter(d => d.guardado).length} guardado(s) sin clasificar — el equipo los revisará
              </p>
              {uploadResult.no_detectados.filter(d => !d.guardado).map((d, i) => (
                <p key={i} style={{ color: '#f87171', fontSize: '13px', margin: '2px 0' }}>
                  • {d.nombre}: {d.razon}
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Lista de archivos subidos */}
      {tieneArchivos ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {/* Controles de Selección Múltiple */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', padding: '0 8px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: '#94a3b8', fontSize: '14px' }}>
              <input 
                type="checkbox" 
                checked={selectedDocs.size === declaraciones.length && declaraciones.length > 0} 
                onChange={selectAll} 
                style={{ cursor: 'pointer' }}
              />
              Seleccionar Todos
            </label>
            {selectedDocs.size > 0 && (
              <button
                onClick={handleEliminarMultiples}
                disabled={eliminandoMultiples}
                style={{
                  background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                  color: '#fca5a5', padding: '6px 14px', borderRadius: '8px', cursor: 'pointer',
                  fontSize: '13px', fontWeight: 600
                }}
              >
                {eliminandoMultiples ? 'Eliminando...' : `🗑️ Borrar Seleccionados (${selectedDocs.size})`}
              </button>
            )}
          </div>
          {declaraciones.map((doc) => {
            const cfg = ESTADO_CONFIG[doc.estado] || ESTADO_CONFIG.PENDIENTE
            return (
              <div
                key={doc.clave}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '14px 18px', borderRadius: '12px',
                  background: 'rgba(255,255,255,0.03)',
                  border: `1px solid ${doc.clasificado ? cfg.border : 'rgba(148,163,184,0.15)'}`,
                }}
              >
                <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                  <input 
                    type="checkbox" 
                    checked={selectedDocs.has(doc.clave)} 
                    onChange={() => toggleSelection(doc.clave)}
                    style={{ marginTop: '4px', cursor: 'pointer' }}
                  />
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '16px' }}>{doc.icono}</span>
                    <span style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '14px' }}>{doc.nombre}</span>
                    {!doc.clasificado && (
                      <span style={{ fontSize: '11px', color: '#64748b', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.08)' }}>
                        Pendiente de Revisión
                      </span>
                    )}
                  </div>
                  {doc.nombre_archivo && doc.clasificado && (
                    <p style={{ color: '#64748b', fontSize: '12px', margin: '3px 0 0 24px', fontStyle: 'italic' }}>
                      📎 {doc.nombre_archivo}
                    </p>
                  )}
                    {!doc.clasificado && doc.nombre_archivo && (
                      <p style={{ color: '#64748b', fontSize: '12px', margin: '3px 0 0 24px', fontStyle: 'italic' }}>
                        📎 {doc.nombre_archivo}
                      </p>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                  <span style={{ padding: '4px 10px', borderRadius: '14px', fontSize: '12px', fontWeight: 700, background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
                    {cfg.icon} {cfg.label}
                  </span>
                  {doc.url_documento && (
                    <button
                      onClick={() => window.open(doc.url_documento, '_blank')}
                      style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', padding: '6px', borderRadius: '8px', cursor: 'pointer' }}
                      title="Ver PDF"
                    >
                      👁️
                    </button>
                  )}
                  <button
                    onClick={() => handleEliminar(doc)}
                    style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#fca5a5', padding: '6px', borderRadius: '8px', cursor: 'pointer' }}
                    title="Eliminar"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '48px 24px', color: '#64748b' }}>
          <div style={{ fontSize: '48px', marginBottom: '12px', opacity: 0.4 }}>📋</div>
          <p style={{ fontSize: '15px', margin: 0 }}>Aún no has subido ningún documento del SAT</p>
          <p style={{ fontSize: '13px', margin: '6px 0 0' }}>Usa la zona de arriba para subir tus declaraciones</p>
        </div>
      )}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// MAIN DASHBOARD — 2 secciones: Empresa + Representante Legal
// ══════════════════════════════════════════════════════════════════════════════

export default function ClienteDashboard({ user, onLogout, isInternalMode }) {
  const [expediente, setExpediente] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [uploadDoc, setUploadDoc] = useState(null)
  const [showFinancierosModal, setShowFinancierosModal] = useState(false)
  
  const [activeView, setActiveView] = useState(() => {
    const isActas = window.location.pathname.endsWith('/actas')
    const isBancos = window.location.pathname.endsWith('/bancos')
    if (isActas) return 'actas'
    if (isBancos) return 'bancos'
    return 'main'
  })

  useEffect(() => {
    const basePath = isInternalMode ? `/portal/${user.empresa_id}` : '/portal'
    const newPath = activeView === 'main' ? basePath : `${basePath}/${activeView}`
    if (window.location.pathname !== newPath) {
      window.history.replaceState(null, '', newPath)
    }
  }, [activeView, isInternalMode, user.empresa_id])

  const fetchExpediente = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.getExpediente()
      setExpediente(data)
    } catch (err) {
      if (err.message.includes('401') || err.message.toLowerCase().includes('unauthorized')) {
        onLogout()
        return
      }
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchExpediente() }, [fetchExpediente])

  // ── Filter docs by group ──
  const byGroup = (grupo) =>
    expediente ? expediente.documentos.filter(d => d.grupo === grupo) : []

  // Documentos de la empresa (todos excepto representante)
  const docsLegal = byGroup('legal').filter(d => !d.clave.startsWith('acta_constitutiva'))
  const docsEdos = byGroup('estados_cuenta')
  const docsFinancieros = byGroup('financieros')
  const docsDeclaraciones = byGroup('declaraciones')
  const docsVigentes = byGroup('vigentes')
  const docsRepresentante = byGroup('representante')
  const docsOtros = byGroup('otros')

  const hasEmpresaDocs = docsLegal.length > 0 || docsEdos.length > 0 ||
    docsFinancieros.length > 0 || docsDeclaraciones.length > 0 || docsVigentes.length > 0

  const handleUploadFromModal = (doc) => {
    setShowFinancierosModal(false)
    setUploadDoc(doc)
  }

  if (activeView === 'actas') {
    return (
      <div style={dashStyles.page}>
        <header style={dashStyles.header}>
          <div style={dashStyles.headerLeft}>
            <img src="/Logo.webp" alt="Logo" style={dashStyles.headerIcon} />
            <div>
              <h1 style={dashStyles.headerTitle}>Expediente Rojo</h1>
              <p style={dashStyles.headerSub}>{user?.nombre_empresa || user?.email}</p>
            </div>
          </div>
          <button onClick={onLogout} style={dashStyles.logoutBtn}>{isInternalMode ? 'Volver al Directorio' : 'Cerrar Sesión'}</button>
        </header>
        <main style={dashStyles.main}>
          <ActasView
            expediente={expediente}
            docs_subidos={[]}
            onBack={() => setActiveView('main')}
            fetchExpediente={fetchExpediente}
            onUpload={setUploadDoc}
          />
        </main>
        {uploadDoc && (
          <UploadModal
            doc={uploadDoc}
            onClose={() => setUploadDoc(null)}
            onSuccess={fetchExpediente}
          />
        )}
      </div>
    )
  }

  if (activeView === 'bancos') {
    return (
      <div style={dashStyles.page}>
        <header style={dashStyles.header}>
          <div style={dashStyles.headerLeft}>
            <img src="/Logo.webp" alt="Logo" style={dashStyles.headerIcon} />
            <div>
              <h1 style={dashStyles.headerTitle}>Expediente Rojo</h1>
              <p style={dashStyles.headerSub}>{user?.nombre_empresa || user?.email}</p>
            </div>
          </div>
          <button onClick={onLogout} style={dashStyles.logoutBtn}>{isInternalMode ? 'Volver al Directorio' : 'Cerrar Sesión'}</button>
        </header>
        <main style={dashStyles.main}>
          <BancosView
            bancos={expediente?.bancos || []}
            allDocs={expediente?.documentos || []}
            onSuccess={fetchExpediente}
            onBack={() => setActiveView('dashboard')}
            onUpload={setUploadDoc}
          />
        </main>
        {uploadDoc && (
          <UploadModal
            doc={uploadDoc}
            onClose={() => setUploadDoc(null)}
            onSuccess={fetchExpediente}
          />
        )}
      </div>
    )
  }

  if (activeView === 'declaraciones') {
    return (
      <div style={dashStyles.page}>
        <header style={dashStyles.header}>
          <div style={dashStyles.headerLeft}>
            <img src="/Logo.webp" alt="Logo" style={dashStyles.headerIcon} />
            <div>
              <h1 style={dashStyles.headerTitle}>Expediente Rojo</h1>
              <p style={dashStyles.headerSub}>{user?.nombre_empresa || user?.email}</p>
            </div>
          </div>
          <button onClick={onLogout} style={dashStyles.logoutBtn}>{isInternalMode ? 'Volver al Directorio' : 'Cerrar Sesión'}</button>
        </header>
        <main style={dashStyles.main}>
          <DeclaracionesView
            declaraciones={expediente?.declaraciones_sat || []}
            declaracionesCompleto={expediente?.declaraciones_completo || false}
            onSuccess={fetchExpediente}
            onBack={() => setActiveView('dashboard')}
          />
        </main>
        {uploadDoc && (
          <UploadModal
            doc={uploadDoc}
            onClose={() => setUploadDoc(null)}
            onSuccess={fetchExpediente}
          />
        )}
      </div>
    )
  }

  return (
    <div style={dashStyles.page}>
      {/* Header */}
      <header style={dashStyles.header}>
        <div style={dashStyles.headerLeft}>
          <img src="/Logo.webp" alt="Logo" style={dashStyles.headerIcon} />
          <div>
            <h1 style={dashStyles.headerTitle}>Expediente Rojo</h1>
            <p style={dashStyles.headerSub}>{user?.nombre_empresa || user?.email}</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button onClick={fetchExpediente} style={dashStyles.refreshBtn}>
            🔄 Actualizar
          </button>
          <button id="btn-logout" onClick={onLogout} style={dashStyles.logoutBtn}>
            Cerrar Sesión
          </button>
        </div>
      </header>

      <main style={dashStyles.main}>
        {/* Progress bar */}
        {expediente && (
          <div style={dashStyles.progressCard}>
            <div style={dashStyles.progressInfo}>
              <span style={{ color: '#f8fafc', fontWeight: 700 }}>Progreso del Expediente</span>
              <span style={{ color: '#94a3b8', fontSize: '14px' }}>
                {expediente.resumen.aprobados} / {expediente.resumen.total} documentos aprobados
              </span>
            </div>
            <div style={dashStyles.progressBar}>
              <div
                style={{
                  ...dashStyles.progressFill,
                  width: `${expediente.resumen.progreso_porcentaje}%`,
                }}
              />
            </div>
            <div style={dashStyles.statsRow}>
              {[
                { label: 'Aprobados', value: expediente.resumen.aprobados, color: '#22c55e' },
                { label: 'En Revisión', value: expediente.resumen.pendientes, color: '#f59e0b' },
                { label: 'Rechazados', value: expediente.resumen.rechazados, color: '#ef4444' },
                { label: 'Faltantes', value: expediente.resumen.faltantes, color: '#64748b' },
              ].map(s => (
                <div key={s.label} style={dashStyles.statChip}>
                  <span style={{ color: s.color, fontWeight: 700, fontSize: '20px' }}>{s.value}</span>
                  <span style={{ color: '#94a3b8', fontSize: '12px' }}>{s.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Loading / Error */}
        {loading && (
          <div style={dashStyles.centerMsg}>
            <div style={dashStyles.spinner} />
            <p style={{ color: '#94a3b8' }}>Cargando expediente...</p>
          </div>
        )}
        {error && <div style={dashStyles.errorBox}>⚠️ {error}</div>}

        {/* ══════════════════════════════════════════════════════════════════ */}
        {/* SECCIÓN 1: DOCUMENTOS DE LA EMPRESA                             */}
        {/* ══════════════════════════════════════════════════════════════════ */}
        {!loading && !error && hasEmpresaDocs && (
          <div style={dashStyles.section}>
            <h2 style={dashStyles.sectionTitle}>🏢 Documentos de la Empresa</h2>
            <div style={dashStyles.grid}>
              {/* Documentos legales — tarjetas individuales */}
              {docsLegal.map(doc => (
                <DocumentCard key={doc.clave} doc={doc} onUpload={setUploadDoc} onSuccess={fetchExpediente} />
              ))}

              {/* Carpetas de Banco (Estados de cuenta dinámicos) */}
              <div style={{
                ...cardStyles.card,
                background: 'linear-gradient(135deg, rgba(30,30,36,0.9) 0%, rgba(15,23,42,0.9) 100%)',
                borderColor: 'rgba(255,255,255,0.1)'
              }}>
                <div style={cardStyles.topRow}>
                  <div style={cardStyles.iconWrap}><span style={{ fontSize: '22px' }}>🏦</span></div>
                  <span style={{ ...cardStyles.badge, background: 'rgba(59,130,246,0.1)', color: '#60a5fa', border: '1px solid rgba(59,130,246,0.2)' }}>
                    {expediente.bancos?.length || 0} cuentas
                  </span>
                </div>
                <h4 style={cardStyles.docName}>Estados de Cuenta Bancarios</h4>
                <p style={cardStyles.docDesc}>Administra tus cuentas bancarias y sube los últimos 7 meses de estados de cuenta.</p>

                <button
                  onClick={() => setActiveView('bancos')}
                  style={{
                    ...cardStyles.uploadBtn,
                    background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                    marginTop: 'auto',
                  }}
                >
                  Ir a Cuentas Bancarias ➔
                </button>
              </div>

              {/* Actas Constitutivas y Asambleas (Card dinámico) */}
              <div style={{
                ...cardStyles.card,
                background: 'linear-gradient(135deg, rgba(30,30,36,0.9) 0%, rgba(15,23,42,0.9) 100%)',
                borderColor: 'rgba(255,255,255,0.1)'
              }}>
                <div style={cardStyles.topRow}>
                  <div style={cardStyles.iconWrap}><span style={{ fontSize: '22px' }}>📜</span></div>
                  <span style={{ ...cardStyles.badge, background: 'rgba(99,102,241,0.1)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.2)' }}>
                    {expediente?.requeridos?.filter(d => d.clave.startsWith('acta_constitutiva') && d.estado !== 'FALTANTE').length || 0} actas
                  </span>
                </div>
                <h4 style={cardStyles.docName}>Actas Constitutivas y Asambleas</h4>
                <p style={cardStyles.docDesc}>Sube múltiples actas constitutivas, asambleas y poderes notariales.</p>

                <button
                  onClick={() => setActiveView('actas')}
                  style={{
                    ...cardStyles.uploadBtn,
                    background: 'linear-gradient(135deg, #6366f1, #4f46e5)',
                    marginTop: 'auto',
                  }}
                >
                  Administrar Actas ➔
                </button>
              </div>

              {/* Estados financieros — tarjeta agrupada */}
              {docsFinancieros.length > 0 && (
                <GroupedCard
                  title="Estados Financieros"
                  icon="📊"
                  description="Balance General, Estado de Resultados, Analíticas y Firmado (un archivo por periodo)"
                  docs={docsFinancieros}
                  onOpenModal={() => setShowFinancierosModal(true)}
                />
              )}

              {/* Declaraciones SAT — tarjeta tipo bancos */}
              <div style={{
                ...cardStyles.card,
                background: 'linear-gradient(135deg, rgba(30,30,36,0.9) 0%, rgba(15,23,42,0.9) 100%)',
                borderColor: 'rgba(255,255,255,0.1)'
              }}>
                <div style={cardStyles.topRow}>
                  <div style={cardStyles.iconWrap}><span style={{ fontSize: '22px' }}>🏨</span></div>
                  <span style={{ ...cardStyles.badge, background: 'rgba(168,85,247,0.1)', color: '#c084fc', border: '1px solid rgba(168,85,247,0.2)' }}>
                    {expediente?.declaraciones_sat?.length || 0} archivo(s) subidos
                  </span>
                </div>
                <h4 style={cardStyles.docName}>Declaraciones Anuales (SAT)</h4>
                <p style={cardStyles.docDesc}>Sube tu Acuse de Recibo y Declaración del Ejercicio de 2023 en adelante. El sistema los clasifica automáticamente.</p>
                {!expediente?.declaraciones_completo && (
                  <p style={{ margin: '4px 0 0', color: '#fca5a5', fontSize: '12px', fontWeight: 600 }}>
                    ⚠️ Mínimo 2 archivos de 2023 en adelante requeridos
                  </p>
                )}
                {expediente?.declaraciones_completo && (
                  <p style={{ margin: '4px 0 0', color: '#4ade80', fontSize: '12px', fontWeight: 600 }}>
                    ✅ Mínimo requerido cubierto
                  </p>
                )}
                <button
                  onClick={() => setActiveView('declaraciones')}
                  style={{
                    ...cardStyles.uploadBtn,
                    background: 'linear-gradient(135deg, #7c3aed, #5b21b6)',
                    marginTop: 'auto',
                  }}
                >
                  Ir a Declaraciones SAT →
                </button>
              </div>

              {/* Documentos vigentes — tarjetas individuales */}
              {docsVigentes.map(doc => (
                <DocumentCard key={doc.clave} doc={doc} onUpload={setUploadDoc} onSuccess={fetchExpediente} />
              ))}
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════ */}
        {/* SECCIÓN 3: OTROS DOCUMENTOS                                     */}
        {/* ══════════════════════════════════════════════════════════════════ */}
        {!loading && !error && (
          <div style={dashStyles.section}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', paddingBottom: '10px', borderBottom: '1px solid rgba(225,29,72,0.2)' }}>
              <h2 style={{ ...dashStyles.sectionTitle, marginBottom: 0, paddingBottom: 0, borderBottom: 'none' }}>
                📁 Otros Documentos
              </h2>
              <button
                onClick={() => setUploadDoc({ clave: `otros_${Date.now()}`, nombre: 'Documento Adicional', descripcion: 'Sube cualquier archivo extra aquí.', grupo: 'otros', estado: 'FALTANTE', icono: '📁' })}
                style={{ ...cardStyles.uploadBtn, background: 'linear-gradient(135deg, #3b82f6, #2563eb)', padding: '6px 16px', fontSize: '13px' }}
              >
                + Subir Archivo Extra
              </button>
            </div>

            <div style={dashStyles.grid}>
              {docsOtros.map(doc => (
                <DocumentCard key={doc.clave} doc={doc} onUpload={setUploadDoc} onSuccess={fetchExpediente} />
              ))}
              {docsOtros.length === 0 && (
                <div style={{ gridColumn: '1 / -1', background: 'rgba(255,255,255,0.02)', padding: '24px', borderRadius: '16px', textAlign: 'center', border: '1px dashed rgba(255,255,255,0.1)' }}>
                  <p style={{ color: '#64748b', fontSize: '14px', margin: 0 }}>No has subido documentos adicionales.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════ */}
        {/* SECCIÓN 2: DOCUMENTOS DEL REPRESENTANTE LEGAL                   */}
        {/* ══════════════════════════════════════════════════════════════════ */}
        {!loading && !error && docsRepresentante.length > 0 && (
          <div style={dashStyles.section}>
            <h2 style={dashStyles.sectionTitle}>🧑‍💼 Documentos del Representante Legal</h2>
            <div style={dashStyles.grid}>
              {docsRepresentante.map(doc => (
                <DocumentCard key={doc.clave} doc={doc} onUpload={setUploadDoc} onSuccess={fetchExpediente} />
              ))}
            </div>
          </div>
        )}
      </main>

      {/* ── MODALS ── */}

      {showFinancierosModal && (
        <EEFFAIAUploadModal
          empresaId={user?.empresa_id}
          onClose={() => setShowFinancierosModal(false)}
          onSuccess={fetchExpediente}
        />
      )}

      {uploadDoc && (
        <UploadModal
          doc={uploadDoc}
          onClose={() => setUploadDoc(null)}
          onSuccess={fetchExpediente}
        />
      )}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// STYLES
// ══════════════════════════════════════════════════════════════════════════════

const cardStyles = {
  card: {
    border: '1px solid',
    borderRadius: '16px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    transition: 'transform 0.2s, box-shadow 0.2s',
    cursor: 'default',
  },
  topRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  iconWrap: {
    width: '44px', height: '44px', borderRadius: '12px',
    background: 'rgba(255,255,255,0.06)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  badge: {
    padding: '4px 10px', borderRadius: '20px',
    fontSize: '12px', fontWeight: 700,
  },
  docName: { margin: 0, color: '#f1f5f9', fontSize: '15px', fontWeight: 700 },
  docDesc: { margin: 0, color: '#94a3b8', fontSize: '13px', lineHeight: 1.4 },
  comentario: {
    padding: '10px 12px',
    borderRadius: '8px',
    background: 'rgba(239,68,68,0.1)',
    border: '1px solid rgba(239,68,68,0.3)',
    color: '#fca5a5',
    fontSize: '12px',
  },
  fileName: { margin: 0, color: '#64748b', fontSize: '11px', fontStyle: 'italic' },
  fecha: { margin: 0, color: '#475569', fontSize: '11px' },
  uploadBtn: {
    padding: '10px', borderRadius: '10px', border: 'none',
    color: '#fff', fontWeight: 700, fontSize: '13px', cursor: 'pointer',
    marginTop: 'auto', transition: 'opacity 0.2s',
  },
}

const modalStyles = {
  overlay: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,0.75)',
    backdropFilter: 'blur(8px)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000, padding: '24px',
  },
  modal: {
    background: '#1c1c1e',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '20px',
    padding: '32px',
    width: '100%',
    maxWidth: '480px',
    display: 'flex', flexDirection: 'column', gap: '16px',
  },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  title: { margin: 0, color: '#f1f5f9', fontSize: '17px', fontWeight: 700 },
  closeBtn: {
    background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '8px',
    color: '#94a3b8', cursor: 'pointer', width: '32px', height: '32px',
    fontSize: '14px',
  },
  desc: { margin: 0, color: '#94a3b8', fontSize: '13px' },
  dropzone: {
    border: '2px dashed rgba(225,29,72,0.35)',
    borderRadius: '14px',
    padding: '32px',
    textAlign: 'center',
    cursor: 'pointer',
    transition: 'all 0.2s',
    background: 'rgba(225,29,72,0.04)',
  },
  dropzoneDrag: {
    border: '2px dashed #e11d48',
    background: 'rgba(225,29,72,0.12)',
  },
  error: { color: '#fca5a5', fontSize: '13px', margin: 0 },
  comentarioBox: {
    padding: '12px',
    borderRadius: '10px',
    background: 'rgba(239,68,68,0.1)',
    border: '1px solid rgba(239,68,68,0.3)',
    color: '#fca5a5', fontSize: '13px',
  },
  actions: { display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '4px' },
  btnSecondary: {
    padding: '10px 20px', borderRadius: '10px',
    background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.1)',
    color: '#94a3b8', cursor: 'pointer', fontWeight: 600, fontSize: '14px',
  },
  btnPrimary: {
    padding: '10px 24px', borderRadius: '10px', border: 'none',
    background: 'linear-gradient(135deg, #e11d48, #be123c)',
    color: '#fff', cursor: 'pointer', fontWeight: 700, fontSize: '14px',
  },
  btnDisabled: { opacity: 0.5, cursor: 'not-allowed' },
}

const dashStyles = {
  page: {
    minHeight: '100vh',
    background: '#141416',
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    color: '#f8fafc',
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '20px 32px',
    background: 'rgba(28,28,30,0.95)',
    backdropFilter: 'blur(12px)',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
    position: 'sticky', top: 0, zIndex: 100,
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: '16px' },
  headerIcon: { height: '36px', width: 'auto' },
  headerTitle: { margin: 0, fontSize: '20px', fontWeight: 800 },
  headerSub: { margin: 0, fontSize: '13px', color: '#64748b' },
  logoutBtn: {
    padding: '8px 18px', borderRadius: '10px',
    background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)',
    color: '#fca5a5', cursor: 'pointer', fontWeight: 600, fontSize: '13px',
  },
  refreshBtn: {
    padding: '8px 18px', borderRadius: '10px',
    background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)',
    color: '#60a5fa', cursor: 'pointer', fontWeight: 600, fontSize: '13px',
    display: 'flex', alignItems: 'center', gap: '6px'
  },
  main: { padding: '32px', maxWidth: '1200px', margin: '0 auto' },
  progressCard: {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: '20px',
    padding: '24px 28px',
    marginBottom: '32px',
    display: 'flex', flexDirection: 'column', gap: '14px',
  },
  progressInfo: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  progressBar: {
    height: '8px', borderRadius: '8px',
    background: 'rgba(255,255,255,0.06)',
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    background: 'linear-gradient(90deg, #f43f5e, #be123c)',
    borderRadius: '8px',
    transition: 'width 0.6s ease',
  },
  statsRow: { display: 'flex', gap: '24px' },
  statChip: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' },
  section: { marginBottom: '32px' },
  sectionTitle: {
    fontSize: '15px', fontWeight: 700, color: '#e11d48',
    textTransform: 'uppercase', letterSpacing: '1.5px',
    marginBottom: '16px', marginTop: 0,
    paddingBottom: '10px',
    borderBottom: '1px solid rgba(225,29,72,0.2)',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '16px',
  },
  centerMsg: { display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '60px', gap: '16px' },
  spinner: {
    width: '40px', height: '40px', borderRadius: '50%',
    border: '3px solid rgba(225,29,72,0.2)',
    borderTopColor: '#e11d48',
    animation: 'spin 0.8s linear infinite',
  },
  errorBox: {
    padding: '16px', borderRadius: '12px',
    background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)',
    color: '#fca5a5',
  },
}
