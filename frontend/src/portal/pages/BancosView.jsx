import React, { useState, useCallback } from 'react'
import api from '../lib/api'
const ESTADO_CONFIG = {
  APROBADO: { color: '#22c55e', bg: 'rgba(34,197,94,0.12)', border: 'rgba(34,197,94,0.3)', icon: '✅', label: 'Aprobado' },
  PENDIENTE: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.3)', icon: '⏳', label: 'En Revisión' },
  RECHAZADO: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)', icon: '❌', label: 'Rechazado' },
  FALTANTE: { color: '#64748b', bg: 'rgba(100,116,139,0.1)', border: 'rgba(100,116,139,0.25)', icon: '📭', label: 'Faltante' },
}
function AccountDetails({ banco, docs, onBack, onSuccess, onUpload }) {
  const [files, setFiles] = useState([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf')
    if (droppedFiles.length) { setFiles(prev => [...prev, ...droppedFiles]); setError('') }
  }, [])
  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files).filter(f => f.type === 'application/pdf')
    if (selectedFiles.length) { setFiles(prev => [...prev, ...selectedFiles]); setError('') }
  }
  const handleUpload = async () => {
    if (!files.length) return
    setUploading(true)
    setError('')
    try {
      await api.subirDocumentosBanco(banco.id, files)
      setFiles([])
      onSuccess()
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }
  const handleEliminar = async () => {
    if (window.confirm(`¿Seguro que deseas eliminar la cuenta ${banco.nombre_banco}?`)) {
      try {
        await api.eliminarCarpetaBanco(banco.id)
        onSuccess()
        onBack()
      } catch (err) {
        setError(err.message)
      }
    }
  }
  const faltantes = docs.filter(d => d.estado === 'FALTANTE' || d.estado === 'RECHAZADO').length
  return (
    <div style={{ animation: 'fadeIn 0.3s ease-in-out' }}>
      <button onClick={onBack} style={styles.btnVolver}>
        ← Volver a mis cuentas
      </button>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginTop: '24px', marginBottom: '32px' }}>
        <div>
          <h2 style={{ fontSize: '32px', fontWeight: 800, margin: 0, color: '#f8fafc', letterSpacing: '-0.5px' }}>
            🏦 {banco.nombre_banco}
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '15px', marginTop: '8px', maxWidth: '600px', lineHeight: 1.5 }}>
            Sube los estados de cuenta de esta institución. Arrastra los PDFs de todos los archivos que tengas; el sistema los acomodará automáticamente.
          </p>
        </div>
        <button onClick={handleEliminar} style={styles.btnEliminar}>
          🗑️ Eliminar Cuenta
        </button>
      </div>
      <div style={styles.contentGrid}>
        {/* Zona de Drop para Bulk Upload */}
        <div style={{ flex: '1 1 400px' }}>
          <div
            style={{ ...styles.dropzone, ...(dragging ? styles.dropzoneDrag : {}) }}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => document.getElementById('bulk-file-input').click()}
          >
            <input id="bulk-file-input" type="file" multiple accept=".pdf" onChange={handleFileChange} style={{ display: 'none' }} />
            <div style={{ fontSize: '48px', marginBottom: '16px', filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.3))' }}>☁️</div>
            <p style={{ color: '#f1f5f9', fontSize: '18px', fontWeight: 700, margin: 0 }}>Arrastra tus PDFs aquí</p>
            <p style={{ color: '#94a3b8', fontSize: '14px', margin: '8px 0 0' }}>Puedes subir varios a la vez para llenar los {faltantes} documentos faltantes</p>
          </div>
          {files.length > 0 && (
            <div style={styles.filesCard}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <p style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: '#e2e8f0' }}>
                  {files.length} {files.length === 1 ? 'archivo listo' : 'archivos listos'} para subir:
                </p>
                <button onClick={() => setFiles([])} style={styles.btnOutline}>Limpiar</button>
              </div>

              <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '200px', overflowY: 'auto' }}>
                {files.map((f, i) => (
                  <li key={i} style={{ padding: '10px 12px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', fontSize: '13px', color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    📄 <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                  </li>
                ))}
              </ul>
              <button onClick={handleUpload} disabled={uploading} style={{ ...styles.btnPrimary, width: '100%', marginTop: '16px', padding: '14px' }}>
                {uploading ? '⏳ Subiendo documentos...' : `⬆️ Subir ${files.length} archivos`}
              </button>
            </div>
          )}
          {error && <div style={styles.errorBox}>⚠️ {error}</div>}
        </div>
        {/* Lista de Slots */}
        <div style={{ flex: '1 1 400px' }}>
          <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#e2e8f0', marginBottom: '16px', marginTop: 0 }}>
            Documentos Requeridos
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {docs.map(doc => {
              const cfg = ESTADO_CONFIG[doc.estado] || ESTADO_CONFIG.FALTANTE
              return (
                <div key={doc.clave} style={styles.slotRow}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, minWidth: 0 }}>
                    <span style={{ color: '#f1f5f9', fontSize: '14px', fontWeight: 600 }}>{doc.icono} {doc.nombre}</span>
                    {doc.nombre_archivo && <span style={{ color: '#94a3b8', fontSize: '12px', fontStyle: 'italic' }}>📎 {doc.nombre_archivo}</span>}
                    {doc.estado === 'RECHAZADO' && doc.comentario_admin && (
                      <span style={{ color: '#fca5a5', fontSize: '12px', background: 'rgba(239,68,68,0.1)', padding: '6px 10px', borderRadius: '6px', marginTop: '4px' }}>
                        💬 {doc.comentario_admin}
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                    <span style={{ padding: '6px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: 700, background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
                      {cfg.icon} {cfg.label}
                    </span>
                    <button
                      onClick={() => onUpload && onUpload(doc)}
                      style={{
                        padding: '6px 12px', borderRadius: '8px',
                        background: doc.estado === 'RECHAZADO'
                          ? 'linear-gradient(135deg, #ef4444, #dc2626)'
                          : doc.estado === 'FALTANTE'
                            ? 'linear-gradient(135deg, #e11d48, #be123c)'
                            : 'rgba(255,255,255,0.1)',
                        border: (doc.estado !== 'FALTANTE' && doc.estado !== 'RECHAZADO') ? '1px solid rgba(255,255,255,0.2)' : 'none',
                        color: '#fff', fontSize: '12px', fontWeight: 700, cursor: 'pointer', transition: 'transform 0.2s'
                      }}
                      title={doc.estado === 'RECHAZADO' ? 'Volver a Subir' : doc.estado === 'FALTANTE' ? 'Subir Documento' : 'Reemplazar Archivo'}
                      onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.05)'}
                      onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
                    >
                      {doc.estado === 'RECHAZADO' ? '🔄 Resubir'
                        : doc.estado === 'FALTANTE' ? '⬆️ Subir'
                          : '🔄 Reemplazar'}
                    </button>
                    {doc.estado !== 'FALTANTE' && (
                      <>
                        {doc.url_documento && (
                          <button
                            onClick={() => window.open(doc.url_documento, '_blank')}
                            style={{
                              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
                              color: '#fff', padding: '6px', borderRadius: '50%', cursor: 'pointer',
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              width: '28px', height: '28px', fontSize: '14px', transition: 'transform 0.2s'
                            }}
                            title="Ver PDF"
                            onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.1)'}
                            onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
                          >
                            👁️
                          </button>
                        )}
                        <button
                        onClick={async () => {
                          if (window.confirm(`¿Seguro que deseas eliminar el archivo de ${doc.nombre}?`)) {
                            try {
                              await api.eliminarDocumento(doc.clave);
                              onSuccess();
                            } catch (err) {
                              alert('Error al eliminar: ' + err.message);
                            }
                          }
                        }}
                        style={{
                          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                          color: '#fca5a5', padding: '6px', borderRadius: '50%', cursor: 'pointer',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          width: '28px', height: '28px', fontSize: '14px', transition: 'transform 0.2s'
                        }}
                        title="Eliminar archivo"
                        onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.1)'}
                        onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
                      >
                        🗑️
                      </button>
                      </>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
export default function BancosView({ bancos, allDocs, onSuccess, onBack, onUpload }) {
  const [draggingBulk, setDraggingBulk] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState(null) // { detectados, no_detectados }
  const [activeBanco, setActiveBanco] = useState(null)
  const [movingDoc, setMovingDoc] = useState(null) // doc to move
  const [movingTo, setMovingTo] = useState('') // target banco id
  const [moveLoading, setMoveLoading] = useState(false)
  const [selectedBanks, setSelectedBanks] = useState([])
  const [deletingBulk, setDeletingBulk] = useState(false)

  const handleToggleBankSelection = (e, id) => {
    e.stopPropagation()
    setSelectedBanks(prev => prev.includes(id) ? prev.filter(b => b !== id) : [...prev, id])
  }

  const handleBulkDelete = async () => {
    if (window.confirm(`¿Seguro que deseas eliminar ${selectedBanks.length} cuenta(s) seleccionada(s)?`)) {
      setDeletingBulk(true)
      try {
        for (const id of selectedBanks) {
          await api.eliminarCarpetaBanco(id)
        }
        setSelectedBanks([])
        onSuccess()
      } catch (err) {
        alert('Error al eliminar: ' + err.message)
      } finally {
        setDeletingBulk(false)
      }
    }
  }

  const handleBulkDrop = useCallback(async (e) => {
    e.preventDefault()
    setDraggingBulk(false)
    const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf')
    if (!droppedFiles.length) return
    await handleAutoUpload(droppedFiles)
  }, [bancos])

  const handleAutoUpload = async (files) => {
    setUploading(true)
    setUploadResult(null)
    try {
      const result = await api.subirEstadosCuentaAuto(files)
      setUploadResult(result)
      onSuccess()
    } catch (err) {
      setUploadResult({ error: err.message })
    } finally {
      setUploading(false)
    }
  }

  const handleMover = async () => {
    if (!movingDoc || !movingTo) return
    setMoveLoading(true)
    try {
      await api.moverDocumentoBanco(movingDoc.documento_id, movingTo)
      setMovingDoc(null)
      setMovingTo('')
      onSuccess()
    } catch (err) {
      alert('Error al mover: ' + err.message)
    } finally {
      setMoveLoading(false)
    }
  }

  // Separate "No Reconocidos" from real banks
  const bancosReales = bancos.filter(b => b.nombre_banco !== 'No Reconocidos')
  const bancoNoRec = bancos.find(b => b.nombre_banco === 'No Reconocidos')
  const docsNoRec = bancoNoRec ? allDocs.filter(d => d.cuenta_bancaria_id === bancoNoRec.id && d.estado !== 'FALTANTE') : []

  if (activeBanco) {
    return (
      <AccountDetails
        banco={activeBanco}
        docs={allDocs.filter(d => d.cuenta_bancaria_id === activeBanco.id)}
        onBack={() => setActiveBanco(null)}
        onSuccess={onSuccess}
        onUpload={onUpload}
      />
    )
  }

  return (
    <div style={{ animation: 'fadeIn 0.3s ease-in-out' }}>
      <button onClick={onBack} style={styles.btnVolver}>
        ← Volver al Dashboard Principal
      </button>

      <div style={{ ...styles.headerArea, marginBottom: '24px' }}>
        <div>
          <h1 style={styles.pageTitle}>Cuentas Bancarias</h1>
          <p style={styles.pageSubtitle}>Arrastra todos tus estados de cuenta aquí — el sistema detectará el banco automáticamente.</p>
        </div>
      </div>

      {/* ═ ZONA DE DROP MASIVA ═ */}
      <div
        style={{
          ...styles.bulkDropzone,
          ...(draggingBulk ? styles.bulkDropzoneDrag : {}),
          ...(uploading ? { opacity: 0.7, pointerEvents: 'none' } : {})
        }}
        onDragOver={(e) => { e.preventDefault(); setDraggingBulk(true) }}
        onDragLeave={() => setDraggingBulk(false)}
        onDrop={handleBulkDrop}
        onClick={() => !uploading && document.getElementById('bulk-auto-input').click()}
      >
        <input
          id="bulk-auto-input"
          type="file"
          multiple
          accept=".pdf"
          style={{ display: 'none' }}
          onChange={e => handleAutoUpload(Array.from(e.target.files))}
        />
        {uploading ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
            <div style={styles.spinner} />
            <p style={{ color: '#f1f5f9', fontSize: '18px', fontWeight: 700, margin: 0 }}>Analizando y clasificando archivos...</p>
            <p style={{ color: '#94a3b8', fontSize: '14px', margin: 0 }}>Esto puede tomar unos segundos por archivo</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
            <div style={{ fontSize: '48px' }}>☁️</div>
            <p style={{ color: '#f1f5f9', fontSize: '20px', fontWeight: 800, margin: 0 }}>Arrastra aquí todos tus PDFs</p>
            <p style={{ color: '#94a3b8', fontSize: '15px', margin: 0 }}>Estados de cuenta de cualquier banco, achocados</p>
            <p style={{ color: '#64748b', fontSize: '13px', margin: 0, fontStyle: 'italic' }}>o haz clic para seleccionar archivos</p>
          </div>
        )}
      </div>

      {/* ═ RESULTADO DEL UPLOAD ═ */}
      {uploadResult && !uploadResult.error && (
        <div style={styles.resultBox}>
          <p style={{ margin: '0 0 8px', fontWeight: 700, color: '#f1f5f9' }}>
            ✅ Procesados {(uploadResult.detectados || []).length + (uploadResult.no_detectados || []).length} archivos
          </p>
          {(uploadResult.detectados || []).map((d, i) => (
            <p key={i} style={{ margin: '2px 0', fontSize: '13px', color: '#86efac' }}>
              🏦 <strong>{d.banco}</strong>: {d.nombre}
            </p>
          ))}
          {(uploadResult.no_detectados || []).map((d, i) => (
            <p key={i} style={{ margin: '2px 0', fontSize: '13px', color: '#fca5a5' }}>
              ⚠️ <strong>No reconocido</strong>: {d.nombre} — {d.razon}
            </p>
          ))}
        </div>
      )}
      {uploadResult?.error && (
        <div style={styles.errorBox}>⚠️ {uploadResult.error}</div>
      )}

      {/* ═ TARJETA NO RECONOCIDOS (si hay) ═ */}
      {docsNoRec.length > 0 && (
        <div style={{ margin: '32px 0 8px' }}>
          <h3 style={{ color: '#fca5a5', fontSize: '14px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', margin: '0 0 16px' }}>
            ⚠️ Archivos No Reconocidos
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {docsNoRec.map(doc => (
              <div key={doc.documento_id || doc.clave} style={styles.noRecRow}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ color: '#f1f5f9', fontSize: '14px', fontWeight: 600 }}>📄 {doc.nombre_archivo}</span>
                  <span style={{ color: '#64748b', fontSize: '12px', marginLeft: '12px' }}>No se pudo identificar el banco</span>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexShrink: 0 }}>
                  {doc.url_documento && (
                    <a
                      href={doc.url_documento}
                      target="_blank"
                      rel="noreferrer"
                      style={{ ...styles.btnOutline, padding: '7px 12px', textDecoration: 'none', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '4px' }}
                    >
                      👁️ Ver PDF
                    </a>
                  )}
                  {bancosReales.length > 0 && (
                    movingDoc?.documento_id === doc.documento_id ? (
                      <>
                        <select
                          value={movingTo}
                          onChange={e => setMovingTo(e.target.value)}
                          style={styles.select}
                        >
                          <option value="">Seleccionar banco...</option>
                          {bancosReales.map(b => (
                            <option key={b.id} value={b.id}>{b.nombre_banco}</option>
                          ))}
                        </select>
                        <button
                          onClick={handleMover}
                          disabled={!movingTo || moveLoading}
                          style={{ ...styles.btnMover, opacity: (!movingTo || moveLoading) ? 0.5 : 1 }}
                        >
                          {moveLoading ? 'Moviendo...' : 'Confirmar'}
                        </button>
                        <button onClick={() => { setMovingDoc(null); setMovingTo('') }} style={styles.btnCancelarMover}>
                          Cancelar
                        </button>
                      </>
                    ) : (
                      <button onClick={() => setMovingDoc(doc)} style={styles.btnMover}>
                        Mover a…
                      </button>
                    )
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═ GRID DE BANCOS DETECTADOS ═ */}
      {bancosReales.length > 0 && (
        <div style={{ marginTop: '32px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ color: '#94a3b8', fontSize: '14px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', margin: 0 }}>
              🏦 Bancos Detectados
            </h3>
            {selectedBanks.length > 0 && (
              <button 
                onClick={handleBulkDelete}
                disabled={deletingBulk}
                style={{
                  background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                  color: '#fca5a5', padding: '6px 12px', borderRadius: '8px', cursor: 'pointer',
                  fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px'
                }}
              >
                {deletingBulk ? '⏳ Eliminando...' : `🗑️ Eliminar ${selectedBanks.length} seleccionados`}
              </button>
            )}
          </div>
          <div style={styles.grid}>
            {bancosReales.map(banco => {
              const bankDocs = allDocs.filter(d => d.cuenta_bancaria_id === banco.id)
              const total = bankDocs.length
              const aprobados = bankDocs.filter(d => d.estado === 'APROBADO').length
              const faltantes = bankDocs.filter(d => d.estado === 'FALTANTE' || d.estado === 'RECHAZADO').length
              const progress = total > 0 ? (aprobados / total) * 100 : 0
              return (
                <div key={banco.id} style={{ ...styles.bankCard, position: 'relative' }} onClick={() => setActiveBanco(banco)}>
                  <div style={{ position: 'absolute', top: '16px', right: '16px', zIndex: 10 }}>
                    <input 
                      type="checkbox"
                      checked={selectedBanks.includes(banco.id)}
                      onChange={(e) => handleToggleBankSelection(e, banco.id)}
                      onClick={(e) => e.stopPropagation()}
                      style={{ transform: 'scale(1.3)', cursor: 'pointer', accentColor: '#ef4444' }}
                    />
                  </div>
                  <div style={{...styles.bankCardHeader, paddingRight: '24px'}}>
                    <div style={styles.bankIcon}>🏦</div>
                    <div style={styles.bankBadge}>{aprobados} de {total} aprobados</div>
                  </div>
                  <h3 style={styles.bankName}>{banco.nombre_banco}</h3>
                  <div style={styles.progressBarBg}>
                    <div style={{ ...styles.progressBarFill, width: `${progress}%` }} />
                  </div>
                  {faltantes > 0 ? (
                    <p style={{ color: '#fca5a5', fontSize: '13px', margin: '16px 0 0', fontWeight: 600 }}>
                      ⚠️ Faltan {faltantes} documentos por subir
                    </p>
                  ) : (
                    <p style={{ color: '#4ade80', fontSize: '13px', margin: '16px 0 0', fontWeight: 600 }}>
                      ✅ Todos los documentos cargados

                    </p>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {bancos.length === 0 && (
        <div style={styles.emptyState}>
          <div style={{ fontSize: '48px', marginBottom: '16px', opacity: 0.8 }}>🏗️</div>
          <h3 style={{ fontSize: '20px', color: '#f1f5f9', margin: '0 0 8px 0' }}>Aún no hay estados de cuenta</h3>
          <p style={{ color: '#94a3b8', fontSize: '15px', maxWidth: '400px', margin: '0 auto' }}>
            Arrastra tus PDFs a la zona de arriba y el sistema los clasificará automáticamente.
          </p>
        </div>
      )}
    </div>
  )
}
const styles = {
  headerArea: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '20px',
    marginBottom: '40px', marginTop: '24px'
  },
  pageTitle: { fontSize: '36px', fontWeight: 800, margin: 0, color: '#f8fafc', letterSpacing: '-1px' },
  pageSubtitle: { fontSize: '16px', color: '#94a3b8', margin: '8px 0 0', maxWidth: '600px', lineHeight: 1.5 },
  btnVolver: {
    background: 'none', border: 'none', color: '#ffffffff', fontSize: '28px', fontWeight: 600,
    cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', gap: '8px', transition: 'color 0.2s',
  },
  btnPrimary: {
    background: 'linear-gradient(135deg, #e11d48 0%, #be123c 100%)',
    color: 'white', border: 'none', padding: '12px 24px', borderRadius: '12px',
    fontSize: '15px', fontWeight: 700, cursor: 'pointer',
    boxShadow: '0 8px 20px rgba(225,29,72,0.3)', transition: 'transform 0.2s, box-shadow 0.2s',
  },
  btnOutline: {
    background: 'rgba(255,255,255,0.05)', color: '#f1f5f9',
    border: '1px solid rgba(255,255,255,0.1)', padding: '12px 20px', borderRadius: '12px',
    fontSize: '15px', fontWeight: 600, cursor: 'pointer', transition: 'background 0.2s',
  },
  btnEliminar: {
    background: 'rgba(239,68,68,0.1)', color: '#fca5a5',
    border: '1px solid rgba(239,68,68,0.3)', padding: '10px 16px', borderRadius: '10px',
    fontSize: '14px', fontWeight: 600, cursor: 'pointer', transition: 'background 0.2s',
  },
  addCard: {
    background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '16px', padding: '24px', marginBottom: '32px',
    backdropFilter: 'blur(10px)',
  },
  input: {
    flex: 1, padding: '12px 16px', borderRadius: '12px',
    background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.15)',
    color: 'white', fontSize: '16px', outline: 'none',
    boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.2)',
  },
  emptyState: {
    textAlign: 'center', padding: '64px 20px',
    background: 'rgba(255,255,255,0.02)', border: '1px dashed rgba(255,255,255,0.1)',
    borderRadius: '24px', margin: '40px 0',
  },
  grid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '24px',
  },
  bankCard: {
    background: 'linear-gradient(145deg, rgba(30,30,34,0.9) 0%, rgba(20,20,24,0.9) 100%)',
    border: '1px solid rgba(255,255,255,0.08)', borderRadius: '20px', padding: '24px',
    cursor: 'pointer', transition: 'transform 0.2s, box-shadow 0.2s, border-color 0.2s',
    boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
  },
  bankCardHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' },
  bankIcon: {
    width: '48px', height: '48px', borderRadius: '14px',
    background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '24px',
  },
  bankBadge: {
    background: 'rgba(255,255,255,0.06)', padding: '6px 12px', borderRadius: '20px',
    fontSize: '12px', fontWeight: 700, color: '#cbd5e1',
  },
  bankName: { margin: '0 0 20px 0', fontSize: '22px', fontWeight: 800, color: '#f8fafc' },
  progressBarBg: { height: '8px', background: 'rgba(255,255,255,0.06)', borderRadius: '8px', overflow: 'hidden' },
  progressBarFill: { height: '100%', background: 'linear-gradient(90deg, #3b82f6, #60a5fa)', borderRadius: '8px', transition: 'width 0.6s ease' },

  contentGrid: { display: 'flex', flexWrap: 'wrap', gap: '32px' },
  dropzone: {
    border: '2px dashed rgba(225,29,72,0.4)', borderRadius: '24px', padding: '64px 32px',
    textAlign: 'center', cursor: 'pointer', transition: 'all 0.2s',
    background: 'rgba(225,29,72,0.04)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    minHeight: '300px',
  },
  dropzoneDrag: {
    border: '2px dashed #e11d48', background: 'rgba(225,29,72,0.12)', transform: 'scale(1.02)'
  },
  filesCard: {
    background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '16px', padding: '20px', marginTop: '24px',
  },
  slotRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '16px', borderRadius: '16px',
    background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
    transition: 'background 0.2s',
  },
  errorBox: {
    padding: '16px', borderRadius: '12px', marginTop: '24px',
    background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', color: '#fca5a5',
  },
  bulkDropzone: {
    border: '2px dashed rgba(59,130,246,0.4)', borderRadius: '24px', padding: '56px 32px',
    textAlign: 'center', cursor: 'pointer', transition: 'all 0.2s',
    background: 'rgba(59,130,246,0.04)', display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', minHeight: '200px',
    marginBottom: '0',
  },
  bulkDropzoneDrag: {
    border: '2px dashed #3b82f6', background: 'rgba(59,130,246,0.1)', transform: 'scale(1.01)',
  },
  spinner: {
    width: '44px', height: '44px', borderRadius: '50%',
    border: '4px solid rgba(59,130,246,0.2)', borderTopColor: '#3b82f6',
    animation: 'spin 0.8s linear infinite',
  },
  resultBox: {
    background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '14px', padding: '16px 20px', marginTop: '16px',
  },
  noRecRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)',
    borderRadius: '14px', padding: '14px 18px', flexWrap: 'wrap', gap: '10px',
  },
  btnMover: {
    background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)',
    color: '#60a5fa', padding: '7px 16px', borderRadius: '10px',
    fontSize: '13px', fontWeight: 700, cursor: 'pointer', transition: 'background 0.2s',
  },
  btnCancelarMover: {
    background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
    color: '#94a3b8', padding: '7px 14px', borderRadius: '10px',
    fontSize: '13px', fontWeight: 600, cursor: 'pointer',
  },
  select: {
    background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)',
    color: '#f1f5f9', padding: '7px 12px', borderRadius: '10px', fontSize: '13px',
    outline: 'none', cursor: 'pointer',
  },
}