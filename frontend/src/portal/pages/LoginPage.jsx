import { useState } from 'react'
import api from '../lib/api'

export default function LoginPage({ onLogin }) {
  const [mode, setMode] = useState('login') // 'login' | 'registro'
  const [form, setForm] = useState({ email: '', password: '', nombre_empresa: '', rfc: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
        if (mode === 'login') {
          const data = await api.login(form.email, form.password)
          onLogin(data.user)
        } else {
          await api.registro(form.email, form.password, form.nombre_empresa, form.rfc || null, form.representante_legal || null)
          const data = await api.login(form.email, form.password)
          onLogin(data.user)
        }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.page}>
      {/* Background blobs */}
      <div style={styles.blob1} />
      <div style={styles.blob2} />

      <div style={styles.card}>
        {/* Logo / Header */}
        <div style={styles.logoWrap}>
          <img src="/Logo.webp" alt="Gestión Financiera Logo" style={styles.logoIcon} />
          <h1 style={styles.title}>Expediente Rojo</h1>
          <p style={styles.subtitle}>Gestión de documentos de clientes</p>
        </div>

        {/* Tabs */}
        <div style={styles.tabs}>
          <button
            id="tab-login"
            style={{ ...styles.tab, ...(mode === 'login' ? styles.tabActive : {}) }}
            onClick={() => { setMode('login'); setError('') }}
          >
            Iniciar Sesión
          </button>
          <button
            id="tab-registro"
            style={{ ...styles.tab, ...(mode === 'registro' ? styles.tabActive : {}) }}
            onClick={() => { setMode('registro'); setError('') }}
          >
            Registrarse
          </button>
        </div>

        <form onSubmit={handleSubmit} style={styles.form}>
          {mode === 'registro' && (
            <>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Nombre de la Empresa *</label>
                <input
                  id="input-nombre-empresa"
                  name="nombre_empresa"
                  type="text"
                  required
                  placeholder="Ej: Distribuidora XYZ S.A. de C.V."
                  value={form.nombre_empresa}
                  onChange={handleChange}
                  style={styles.input}
                />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Representante Legal *</label>
                <input
                  id="input-representante-legal"
                  name="representante_legal"
                  type="text"
                  required
                  placeholder="Nombre completo"
                  value={form.representante_legal || ''}
                  onChange={handleChange}
                  style={styles.input}
                />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>RFC (opcional)</label>
                <input
                  id="input-rfc"
                  name="rfc"
                  type="text"
                  placeholder="Ej: DXY991231ABC"
                  value={form.rfc}
                  onChange={handleChange}
                  style={styles.input}
                />
              </div>
            </>
          )}

          <div style={styles.inputGroup}>
            <label style={styles.label}>Correo Electrónico *</label>
            <input
              id="input-email"
              name="email"
              type="email"
              required
              placeholder="correo@empresa.com"
              value={form.email}
              onChange={handleChange}
              style={styles.input}
            />
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Contraseña *</label>
            <input
              id="input-password"
              name="password"
              type="password"
              required
              minLength={6}
              placeholder="Mínimo 6 caracteres"
              value={form.password}
              onChange={handleChange}
              style={styles.input}
            />
          </div>

          {error && (
            <div id="login-error" style={styles.errorBox}>
              ⚠️ {error}
            </div>
          )}

          <button
            id="btn-submit-auth"
            type="submit"
            disabled={loading}
            style={{ ...styles.btnPrimary, ...(loading ? styles.btnDisabled : {}) }}
          >
            {loading ? '⏳ Procesando...' : mode === 'login' ? '→ Iniciar Sesión' : '✓ Crear Cuenta'}
          </button>
        </form>

        <p style={styles.footer}>
          {mode === 'login' ? '¿Aún no tienes cuenta? ' : '¿Ya tienes cuenta? '}
          <span
            style={styles.link}
            onClick={() => { setMode(mode === 'login' ? 'registro' : 'login'); setError('') }}
          >
            {mode === 'login' ? 'Regístrate aquí' : 'Inicia sesión'}
          </span>
        </p>
      </div>
    </div>
  )
}

const styles = {
  page: {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    position: 'relative',
    overflow: 'hidden',
  },
  blob1: {
    position: 'absolute', top: '-120px', right: '-80px',
    width: '400px', height: '400px', borderRadius: '50%',
    background: 'radial-gradient(circle, rgba(225,29,72,0.3) 0%, transparent 70%)',
    pointerEvents: 'none',
  },
  blob2: {
    position: 'absolute', bottom: '-100px', left: '-60px',
    width: '350px', height: '350px', borderRadius: '50%',
    background: 'radial-gradient(circle, rgba(244,63,94,0.25) 0%, transparent 70%)',
    pointerEvents: 'none',
  },
  card: {
    background: 'rgba(255,255,255,0.05)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '24px',
    padding: '40px',
    width: '100%',
    maxWidth: '440px',
    position: 'relative',
    zIndex: 10,
    boxShadow: '0 25px 50px rgba(0,0,0,0.4)',
  },
  logoWrap: { textAlign: 'center', marginBottom: '28px' },
  logoIcon: { height: '80px', width: 'auto', margin: '0 auto 16px auto', display: 'block', dropShadow: '0 0 12px rgba(225,29,72,0.4)' },
  title: { margin: 0, fontSize: '24px', fontWeight: 700, color: '#f8fafc' },
  subtitle: { margin: '6px 0 0', fontSize: '14px', color: '#94a3b8' },
  tabs: {
    display: 'flex', gap: '4px',
    background: 'rgba(255,255,255,0.05)',
    borderRadius: '12px', padding: '4px',
    marginBottom: '28px',
  },
  tab: {
    flex: 1, padding: '10px', border: 'none',
    borderRadius: '8px', cursor: 'pointer',
    fontSize: '14px', fontWeight: 500,
    background: 'transparent', color: '#94a3b8',
    transition: 'all 0.2s',
  },
  tabActive: {
    background: 'linear-gradient(135deg, #e11d48, #be123c)',
    color: '#fff',
    boxShadow: '0 4px 12px rgba(225,29,72,0.4)',
  },
  form: { display: 'flex', flexDirection: 'column', gap: '16px' },
  inputGroup: { display: 'flex', flexDirection: 'column', gap: '6px' },
  label: { fontSize: '13px', fontWeight: 600, color: '#cbd5e1' },
  input: {
    padding: '12px 16px',
    borderRadius: '10px',
    border: '1px solid rgba(255,255,255,0.1)',
    background: 'rgba(255,255,255,0.07)',
    color: '#f1f5f9',
    fontSize: '14px',
    outline: 'none',
    transition: 'border-color 0.2s',
  },
  errorBox: {
    padding: '12px 16px',
    borderRadius: '10px',
    background: 'rgba(239,68,68,0.15)',
    border: '1px solid rgba(239,68,68,0.4)',
    color: '#fca5a5',
    fontSize: '13px',
  },
  btnPrimary: {
    padding: '14px',
    borderRadius: '12px',
    border: 'none',
    background: 'linear-gradient(135deg, #e11d48, #be123c)',
    color: '#fff',
    fontSize: '15px',
    fontWeight: 700,
    cursor: 'pointer',
    marginTop: '4px',
    transition: 'all 0.2s',
    boxShadow: '0 4px 15px rgba(225,29,72,0.4)',
  },
  btnDisabled: { opacity: 0.6, cursor: 'not-allowed' },
  footer: { textAlign: 'center', marginTop: '20px', fontSize: '13px', color: '#64748b' },
  link: { color: '#fb7185', cursor: 'pointer', fontWeight: 600 },
}
