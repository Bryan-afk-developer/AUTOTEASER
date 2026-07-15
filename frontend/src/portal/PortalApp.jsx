/**
 * PortalApp.jsx — Punto de entrada del Portal de Expedientes.
 * Maneja la autenticación y el enrutado entre:
 *   - LoginPage      → /portal/login (o cuando no hay sesión)
 *   - ClienteDashboard → /portal/cliente
 *   - AdminDashboard   → /portal/admin
 */
import { useState, useEffect } from 'react'
import ClienteDashboard from './pages/ClienteDashboard'
import AdminDashboard from './pages/AdminDashboard'
import api from './lib/api'

export default function PortalApp() {
  const path = window.location.pathname
  const parts = path.split('/').filter(Boolean)
  const isCompanyView = parts.length > 1
  const companyId = isCompanyView ? parts[1] : null

  const [company, setCompany] = useState(null)
  const [loading, setLoading] = useState(isCompanyView)

  useEffect(() => {
    if (isCompanyView && companyId) {
      api.setActiveEmpresa(companyId)
      api.getEmpresas().then(data => {
        const found = data.empresas?.find(e => String(e.id) === String(companyId))
        if (found) setCompany(found)
        setLoading(false)
      }).catch(() => setLoading(false))
    }
  }, [isCompanyView, companyId])

  if (isCompanyView) {
    if (loading) {
      return (
        <div style={styles.loadingPage}>
          <div style={styles.spinner} />
        </div>
      )
    }
    
    if (!company) {
      return (
        <div style={styles.loadingPage}>
          <div className="text-white text-center">
            <h2 className="text-2xl font-bold text-rose-500 mb-2">Empresa no encontrada</h2>
            <button onClick={() => window.location.href = '/portal'} className="mt-4 px-4 py-2 bg-surface border border-border rounded-lg text-text-main hover:bg-surface/50">Volver al Directorio</button>
          </div>
        </div>
      )
    }

    const dummyUser = {
      empresa_id: company.id,
      nombre_empresa: company.nombre,
      rfc: company.rfc
    }

    return (
      <ClienteDashboard 
        user={dummyUser} 
        onLogout={() => window.location.href = '/portal'} 
        isInternalMode={true} 
      />
    )
  }

  return (
    <AdminDashboard />
  )
}

const styles = {
  loadingPage: {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  spinner: {
    width: '48px', height: '48px', borderRadius: '50%',
    border: '4px solid rgba(99,102,241,0.2)', borderTopColor: '#6366f1',
    animation: 'spin 0.8s linear infinite',
  },
}
