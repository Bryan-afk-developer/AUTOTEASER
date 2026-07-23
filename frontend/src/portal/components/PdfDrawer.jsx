import React, { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronRight, FileText, Loader2 } from 'lucide-react'
import { api } from '../lib/api'

const pdfCache = {}

export default function PdfDrawer({ isOpen, empresaId, docId, isRep, onClose }) {
  const [pdfUrl, setPdfUrl] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isOpen || !docId) return
    let cancelled = false
    setLoading(true)

    const now = Date.now()
    const cached = pdfCache[docId]
    if (cached && cached.expiresAt > now) {
      setPdfUrl(cached.url)
      setLoading(false)
      return
    }

    api.descargarDocumentoIndividual(empresaId, docId, isRep, true)
      .then(res => {
        if (!cancelled) {
          pdfCache[docId] = {
            url: res.url,
            expiresAt: now + (55 * 60 * 1000)
          }
          setPdfUrl(res.url)
        }
      })
      .catch(err => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [isOpen, empresaId, docId, isRep])

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div 
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[900]" 
            onClick={onClose} 
          />
          <motion.div 
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 h-full w-full max-w-3xl bg-[#111113] border-l border-border shadow-2xl z-[910] flex flex-col"
          >
            {/* Floating Arrow Close Button */}
            <motion.button 
              initial={{ x: 20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 20, opacity: 0 }}
              transition={{ delay: 0.3 }}
              onClick={onClose} 
              className="absolute -left-12 top-1/2 -translate-y-1/2 w-12 h-16 bg-[#111113] border-y border-l border-border rounded-l-xl flex items-center justify-center hover:bg-surface hover:w-14 hover:-left-14 transition-all z-50 shadow-[-10px_0_20px_rgba(0,0,0,0.5)] group"
            >
              <ChevronRight className="w-6 h-6 text-text-muted group-hover:text-primary-400 transition-colors" />
            </motion.button>

            <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-surface">
              <div className="w-10 h-10 rounded-xl bg-primary-500/10 border border-primary-500/20 flex items-center justify-center flex-shrink-0 shadow-[0_0_15px_rgba(225,29,72,0.1)]">
                <FileText className="w-5 h-5 text-primary-400" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-text-main leading-tight">
                  Vista Previa del Documento
                </h2>
                <p className="text-xs text-text-muted">Previsualización segura y rápida</p>
              </div>
            </div>
            
            <div className="flex-1 bg-black/50 relative overflow-hidden">
              <AnimatePresence>
                {loading && (
                  <motion.div 
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="absolute inset-0 flex flex-col items-center justify-center bg-black/50 z-10 backdrop-blur-sm"
                  >
                    <Loader2 className="w-10 h-10 animate-spin text-primary-400 mb-4 drop-shadow-[0_0_10px_rgba(225,29,72,0.5)]" />
                    <p className="text-sm font-semibold text-text-main animate-pulse">Obteniendo vista previa segura...</p>
                  </motion.div>
                )}
                {error && (
                  <motion.div 
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="absolute inset-0 flex items-center justify-center text-red-400 px-6 text-center z-10"
                  >
                    ⚠️ {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {pdfUrl && (
                <motion.iframe 
                   initial={{ opacity: 0, scale: 0.95 }}
                   animate={{ opacity: 1, scale: 1 }}
                   transition={{ delay: 0.2 }}
                   src={pdfUrl} 
                   className="w-full h-full border-none bg-white relative z-0"
                   title="Vista Previa PDF"
                />
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  )
}
