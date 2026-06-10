import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronLeft, ChevronRight, Menu, CheckCircle2, XCircle } from 'lucide-react'
import CafDashboard from './pages/CafDashboard'

export default function CafApp() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [isOnline, setIsOnline] = useState(true) // Assume online for simplicity or add health check

  return (
    <div className="min-h-screen bg-background text-text-main font-sans flex relative">
      
      {/* ── Sidebar overlay (mobile) ── */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-30 md:hidden" 
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ── */}
      <motion.aside
        initial={false}
        animate={{ width: sidebarOpen ? 260 : 72 }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className="fixed top-0 left-0 h-screen z-40 flex flex-col bg-[#0a0a0c]/95 backdrop-blur-xl border-r border-white/5 md:sticky shadow-[10px_0_30px_rgba(0,0,0,0.5)]"
      >
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="absolute -right-3.5 top-1/2 -translate-y-1/2 w-7 h-7 bg-[#1e1e24] border border-white/10 rounded-full flex items-center justify-center hover:bg-[#2a2a32] hover:scale-110 transition-all z-50 shadow-[0_0_15px_rgba(0,0,0,0.8)] group hidden md:flex"
        >
          {sidebarOpen ? (
            <ChevronLeft className="w-3.5 h-3.5 text-text-muted group-hover:text-white transition-colors" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-text-muted group-hover:text-white transition-colors" />
          )}
        </button>

        <div className={`flex items-center justify-center shrink-0 transition-all duration-300 relative overflow-hidden ${sidebarOpen ? 'py-6 h-32' : 'py-4 h-20'}`}>
          <img
            src="/Logo.webp"
            alt="Logo"
            className={`w-auto object-contain drop-shadow-[0_0_20px_rgba(230,57,70,0.5)] transition-all duration-300 ${sidebarOpen ? 'h-20' : 'h-10'}`}
          />
        </div>

        <nav className="flex-1 px-3 py-4 space-y-2 overflow-y-auto overflow-x-hidden">
          <AnimatePresence>
            {sidebarOpen && (
              <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }} className="text-[10px] font-black text-white/30 uppercase tracking-[0.2em] px-3 mb-3 mt-2">
                Herramientas
              </motion.div>
            )}
          </AnimatePresence>

          <motion.button
            whileHover={{ x: 4 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => window.location.href = '/'}
            title="AutoTeaser"
            className={`w-full flex items-center px-3 py-3 rounded-xl text-sm font-medium transition-all relative overflow-hidden group
              ${sidebarOpen ? 'justify-between' : 'justify-center'}
              text-text-muted hover:text-text-main hover:bg-white/5 border border-transparent`}
          >
            <div className={`flex items-center ${sidebarOpen ? 'gap-3 ml-1' : ''}`}>
              <span className="text-base transition-colors text-text-muted group-hover:text-primary-400">⚡</span>
              <AnimatePresence>
                {sidebarOpen && <motion.span initial={{ opacity: 0, width: 0 }} animate={{ opacity: 1, width: 'auto' }} exit={{ opacity: 0, width: 0 }} className="whitespace-nowrap">AutoTeaser</motion.span>}
              </AnimatePresence>
            </div>
          </motion.button>

          <motion.button
            whileHover={{ x: 4 }}
            whileTap={{ scale: 0.98 }}
            title="AutoCAF"
            className={`w-full flex items-center px-3 py-3 rounded-xl text-sm font-medium transition-all relative overflow-hidden group mt-2
              ${sidebarOpen ? 'justify-between' : 'justify-center'}
              bg-gradient-to-r from-primary-500/10 to-transparent border border-primary-500/20 shadow-[inset_4px_0_0_rgba(99,102,241,1)]`}
          >
            <div className={`flex items-center ${sidebarOpen ? 'gap-3 ml-1' : ''}`}>
              <span className="text-base transition-colors text-primary-400">📊</span>
              <AnimatePresence>
                {sidebarOpen && <motion.span initial={{ opacity: 0, width: 0 }} animate={{ opacity: 1, width: 'auto' }} exit={{ opacity: 0, width: 0 }} className="whitespace-nowrap text-primary-300 font-bold">AutoCAF</motion.span>}
              </AnimatePresence>
            </div>
          </motion.button>

          <div className="my-6 border-t border-white/5 mx-2" />

          <AnimatePresence>
            {sidebarOpen && (
              <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }} className="text-[10px] font-black text-white/30 uppercase tracking-[0.2em] px-3 mb-3">
                Intranet
              </motion.div>
            )}
          </AnimatePresence>

          <motion.button
            whileHover={{ x: 4 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => window.location.href = '/portal'}
            title="Expediente Rojo"
            className={`w-full flex items-center px-3 py-3 rounded-xl text-sm font-medium transition-all relative overflow-hidden group
              ${sidebarOpen ? 'justify-between' : 'justify-center'}
              text-text-muted hover:text-text-main hover:bg-white/5 border border-transparent`}
          >
            <div className={`flex items-center ${sidebarOpen ? 'gap-3 ml-1' : ''}`}>
              <span className="text-base transition-colors text-text-muted group-hover:text-rose-400">🔴</span>
              <AnimatePresence>
                {sidebarOpen && <motion.span initial={{ opacity: 0, width: 0 }} animate={{ opacity: 1, width: 'auto' }} exit={{ opacity: 0, width: 0 }} className="whitespace-nowrap">Expediente Rojo</motion.span>}
              </AnimatePresence>
            </div>
          </motion.button>
        </nav>

      </motion.aside>

      {/* ── Main Content Area ── */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen transition-all duration-300">
        
        {/* Header */}
        <header className="glass-header flex items-center justify-between px-6 py-4 sticky top-0 z-20 border-b border-border">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="md:hidden p-2 rounded-lg hover:bg-surface/60 text-text-muted"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h1 className="text-base font-bold tracking-tight">
              Auto<span className="text-primary-500">CAF</span> <span className="text-xs font-normal text-text-muted ml-2">/ Estados Financieros V2</span>
            </h1>
          </div>
        </header>

        {/* Dashboard Content */}
        <CafDashboard />

      </div>
    </div>
  )
}
