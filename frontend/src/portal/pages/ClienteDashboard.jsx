import { useState, useCallback } from 'react'
import api from '../lib/api'

const ESTADO_CONFIG = {
  APROBADO:  { color: '#22c55e', bg: 'rgba(34,197,94,0.12)',  border: 'rgba(34,197,94,0.3)',  icon: '✅', label: 'Aprobado' },
  PENDIENTE: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.3)', icon: '⏳', label: 'En Revisión' },
  RECHAZADO: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.3)',  icon: '❌', label: 'Rechazado' },
  FALTANTE:  { color: '#64748b', bg: 'rgba(100,116,139,0.1)', border: 'rgba(100,116,139,0.25)', icon: '📭', label: 'Faltante' },
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
    if (f && f.type === 'application/pdf') setFile(f)
    else setError('Solo se aceptan archivos PDF')
  }, [])

  const handleFileChange = (e) => {
    const f = e.target.files[0]
    if (f && f.type === 'application/pdf') { setFile(f); setError('') }
    else setError('Solo se aceptan archivos PDF')
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError('')
    try {
      await api.subirDocumento(doc.clave, file)
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
          <input id="file-input-hidden" type="file" accept=".pdf" onChange={handleFileChange} style={{ display: 'none' }} />
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
              <p style={{ color: '#cbd5e1', fontWeight: 600, margin: 0 }}>Arrastra tu PDF aquí</p>
              <p style={{ color: '#64748b', fontSize: '13px', margin: '6px 0 0' }}>o haz clic para seleccionar</p>
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
            {uploading ? '⏳ Subiendo...' : '⬆️ Subir Documento'}
          </button>
        </div>
      </div>
    </div>
  )
}

function DocumentCard({ doc, onUpload }) {
  const cfg = ESTADO_CONFIG[doc.estado] || ESTADO_CONFIG.FALTANTE
  const canUpload = doc.estado === 'FALTANTE' || doc.estado === 'RECHAZADO'

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

      {canUpload && (
        <button
          id={`btn-subir-${doc.clave}`}
          onClick={() => onUpload(doc)}
          style={{
            ...cardStyles.uploadBtn,
            background: doc.estado === 'RECHAZADO'
              ? 'linear-gradient(135deg, #ef4444, #dc2626)'
              : 'linear-gradient(135deg, #e11d48, #be123c)',
          }}
        >
          {doc.estado === 'RECHAZADO' ? '🔄 Volver a Subir' : '⬆️ Subir Documento'}
        </button>
      )}
    </div>
  )
}

function EstadosCuentaModal({ docs, onClose, onUpload }) {
  return (
    <div style={modalStyles.overlay} onClick={onClose}>
      <div style={{ ...modalStyles.modal, maxWidth: '600px' }} onClick={(e) => e.stopPropagation()}>
        <div style={modalStyles.header}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '28px' }}>🏦</span>
            <div>
              <h3 style={modalStyles.title}>Estados de Cuenta</h3>
              <p style={modalStyles.desc}>Últimos 7 meses de estados bancarios</p>
            </div>
          </div>
          <button onClick={onClose} style={modalStyles.closeBtn}>✕</button>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '60vh', overflowY: 'auto', paddingRight: '4px' }}>
          {docs.map(doc => {
            const cfg = ESTADO_CONFIG[doc.estado] || ESTADO_CONFIG.FALTANTE
            const canUpload = doc.estado === 'FALTANTE' || doc.estado === 'RECHAZADO'
            return (
              <div key={doc.clave} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '16px', borderRadius: '12px',
                background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)'
              }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ color: '#e2e8f0', fontSize: '14px', fontWeight: 600 }}>{doc.nombre}</span>
                  {doc.nombre_archivo && <span style={{ color: '#64748b', fontSize: '12px', fontStyle: 'italic' }}>📎 {doc.nombre_archivo}</span>}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ 
                    padding: '4px 10px', borderRadius: '16px', fontSize: '12px', fontWeight: 700, 
                    background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` 
                  }}>
                    {cfg.icon} {cfg.label}
                  </span>
                  {canUpload && (
                    <button
                      onClick={() => onUpload(doc)}
                      style={{
                        padding: '6px 14px', borderRadius: '8px', border: 'none',
                        background: 'linear-gradient(135deg, #e11d48, #be123c)',
                        color: '#fff', fontSize: '12px', fontWeight: 700, cursor: 'pointer'
                      }}
                    >
                      ⬆️ Subir
                    </button>
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

function EstadosCuentaCard({ docs, onOpenModal }) {
  const totalEdos = docs.length
  const aprobados = docs.filter(d => d.estado === 'APROBADO').length
  const pendientes = docs.filter(d => d.estado === 'PENDIENTE').length
  const faltantes = docs.filter(d => d.estado === 'FALTANTE').length

  let statusKey = 'FALTANTE'
  if (aprobados === totalEdos) statusKey = 'APROBADO'
  else if (pendientes > 0) statusKey = 'PENDIENTE'

  const cfg = ESTADO_CONFIG[statusKey]

  return (
    <div style={{
      ...cardStyles.card,
      borderColor: cfg.border,
      background: `linear-gradient(135deg, rgba(24,24,27,0.9) 0%, ${cfg.bg} 100%)`,
    }}>
      <div style={cardStyles.topRow}>
        <div style={cardStyles.iconWrap}>
          <span style={{ fontSize: '22px' }}>🏦</span>
        </div>
        <span style={{ ...cardStyles.badge, background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
          {aprobados} / {totalEdos} Aprobados
        </span>
      </div>

      <h4 style={cardStyles.docName}>Estados de Cuenta</h4>
      <p style={cardStyles.docDesc}>Últimos 7 meses de estados bancarios</p>

      {faltantes > 0 && (
        <p style={{ margin: '4px 0 0', color: '#fca5a5', fontSize: '12px', fontWeight: 600 }}>
          ⚠️ Faltan {faltantes} meses por subir
        </p>
      )}

      <button
        onClick={onOpenModal}
        style={{
          ...cardStyles.uploadBtn,
          background: 'rgba(255,255,255,0.1)',
          border: '1px solid rgba(255,255,255,0.2)',
          marginTop: 'auto'
        }}
      >
        👁️ Ver meses
      </button>
    </div>
  )
}

export default function ClienteDashboard({ user, onLogout }) {
  const [expediente, setExpediente] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [uploadDoc, setUploadDoc] = useState(null)
  const [showEdosModal, setShowEdosModal] = useState(false)

  const fetchExpediente = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.getExpediente()
      setExpediente(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useState(() => { fetchExpediente() }, [])

  // Separate documents into groups
  const docsEmpresa = expediente
    ? expediente.documentos.filter(d => d.grupo === 'empresa')
    : []
  const docsRepresentante = expediente
    ? expediente.documentos.filter(d => d.grupo === 'representante')
    : []
  const docsEstados = expediente
    ? expediente.documentos.filter(d => d.grupo === 'estados_cuenta')
    : []

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
        <button id="btn-logout" onClick={onLogout} style={dashStyles.logoutBtn}>
          Cerrar Sesión
        </button>
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

        {/* State */}
        {loading && (
          <div style={dashStyles.centerMsg}>
            <div style={dashStyles.spinner} />
            <p style={{ color: '#94a3b8' }}>Cargando expediente...</p>
          </div>
        )}
        {error && <div style={dashStyles.errorBox}>⚠️ {error}</div>}

        {/* EMPRESA Section */}
        {!loading && !error && (docsEmpresa.length > 0 || docsEstados.length > 0) && (
          <div style={dashStyles.section}>
            <h2 style={dashStyles.sectionTitle}>🏢 Documentos de la Empresa</h2>
            <div style={dashStyles.grid}>
              {docsEmpresa.map(doc => (
                <DocumentCard key={doc.clave} doc={doc} onUpload={setUploadDoc} />
              ))}
              {docsEstados.length > 0 && (
                <EstadosCuentaCard 
                  docs={docsEstados} 
                  onOpenModal={() => setShowEdosModal(true)} 
                />
              )}
            </div>
          </div>
        )}

        {/* REPRESENTANTE Section */}
        {!loading && !error && docsRepresentante.length > 0 && (
          <div style={dashStyles.section}>
            <h2 style={dashStyles.sectionTitle}>🧑‍💼 Documentos del Representante Legal</h2>
            <div style={dashStyles.grid}>
              {docsRepresentante.map(doc => (
                <DocumentCard key={doc.clave} doc={doc} onUpload={setUploadDoc} />
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Modals */}
      {showEdosModal && (
        <EstadosCuentaModal
          docs={docsEstados}
          onClose={() => setShowEdosModal(false)}
          onUpload={(doc) => {
            setShowEdosModal(false);
            setUploadDoc(doc);
          }}
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

// ── Styles ────────────────────────────────────────────────────────────────────

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

const edoStyles = {
  wrapper: {
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '16px',
    background: 'rgba(24,24,27,0.7)',
    overflow: 'hidden',
  },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '18px 24px',
    cursor: 'pointer',
    transition: 'background 0.2s',
    background: 'rgba(255,255,255,0.03)',
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: '14px' },
  iconWrap: {
    width: '48px', height: '48px', borderRadius: '14px',
    background: 'rgba(225,29,72,0.12)',
    border: '1px solid rgba(225,29,72,0.25)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  title: { margin: 0, color: '#f1f5f9', fontSize: '16px', fontWeight: 700 },
  sub: { margin: '2px 0 0', color: '#64748b', fontSize: '12px' },
  headerRight: { display: 'flex', alignItems: 'center', gap: '14px' },
  statusBadge: { fontSize: '12px', fontWeight: 600 },
  chevron: { color: '#64748b', fontSize: '12px', transition: 'transform 0.3s ease' },
  body: {
    borderTop: '1px solid rgba(255,255,255,0.06)',
    padding: '8px 0',
  },
  row: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '12px 24px',
    borderBottom: '1px solid rgba(255,255,255,0.04)',
    transition: 'background 0.15s',
  },
  rowInfo: { display: 'flex', flexDirection: 'column', gap: '2px' },
  rowName: { color: '#e2e8f0', fontSize: '13px', fontWeight: 600 },
  rowFile: { color: '#64748b', fontSize: '11px', fontStyle: 'italic' },
  rowActions: { display: 'flex', alignItems: 'center', gap: '10px' },
  rowBadge: {
    padding: '3px 10px', borderRadius: '16px',
    fontSize: '11px', fontWeight: 700, border: '1px solid',
  },
  rowBtn: {
    padding: '6px 14px', borderRadius: '8px', border: 'none',
    background: 'linear-gradient(135deg, #e11d48, #be123c)',
    color: '#fff', fontSize: '12px', fontWeight: 700, cursor: 'pointer',
    transition: 'opacity 0.2s',
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
