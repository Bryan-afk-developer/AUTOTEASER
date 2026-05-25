/**
 * PortalApp.jsx — Punto de entrada del Portal de Expedientes.
 * Maneja la autenticación y el enrutado entre:
 *   - LoginPage      → /portal/login (o cuando no hay sesión)
 *   - ClienteDashboard → /portal/cliente
 *   - AdminDashboard   → /portal/admin
 */
import { useState, useEffect } from 'react'
import LoginPage from './pages/LoginPage'
import ClienteDashboard from './pages/ClienteDashboard'
import AdminDashboard from './pages/AdminDashboard'
import api from './lib/api'

export default function PortalApp() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // Al montar, intenta restaurar sesión desde localStorage
  useEffect(() => {
    const savedUser = api.getUser()
    if (savedUser && api.isAuthenticated()) {
      setUser(savedUser)
    }
    setLoading(false)
  }, [])

  const handleLogin = (userData) => {
    setUser(userData)
  }

  const handleLogout = () => {
    api.logout()
    setUser(null)
  }

  if (loading) {
    return (
      <div style={styles.loadingPage}>
        <div style={styles.spinner} />
      </div>
    )
  }

  if (!user) {
    return <LoginPage onLogin={handleLogin} />
  }

  // Determinar si es admin
  const esAdmin = user.es_admin || false

  if (esAdmin) {
    return <AdminDashboard user={user} onLogout={handleLogout} />
  }

  return <ClienteDashboard user={user} onLogout={handleLogout} />
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
