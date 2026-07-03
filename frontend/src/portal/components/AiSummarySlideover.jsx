import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, Sparkles, Loader2 } from 'lucide-react';

export default function AiSummarySlideover({ isOpen, onClose, aiSummary, pdfUrl, fetchPdfUrl }) {
  const [dynamicPdfUrl, setDynamicPdfUrl] = useState(null)
  const [loadingPdf, setLoadingPdf] = useState(false)

  useEffect(() => {
    if (isOpen && fetchPdfUrl && !pdfUrl && !dynamicPdfUrl) {
      let cancelled = false;
      setLoadingPdf(true);
      fetchPdfUrl().then(res => {
        if (!cancelled && res?.url) setDynamicPdfUrl(res.url)
      }).catch(err => {
        console.error("Error fetching PDF for summary:", err);
      }).finally(() => {
        if (!cancelled) setLoadingPdf(false);
      });
      return () => { cancelled = true; }
    }
  }, [isOpen, fetchPdfUrl, pdfUrl, dynamicPdfUrl])

  if (!aiSummary) return null;

  const finalPdfUrl = pdfUrl || dynamicPdfUrl;
  const isSplitView = !!finalPdfUrl || loadingPdf;

  return (
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
            className={`fixed right-0 top-0 h-full ${isSplitView ? 'w-[95vw] max-w-screen-2xl flex flex-row' : 'w-full max-w-md flex flex-col overflow-y-auto'} bg-[#111113] border-l border-border shadow-2xl z-[910]`}
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

            {/* If PDF URL is present or loading, show PDF Viewer on the Left */}
            {isSplitView && (
              <div className="flex-1 h-full bg-white relative z-0 border-r border-border flex items-center justify-center">
                {loadingPdf ? (
                  <div className="flex flex-col items-center gap-4">
                    <Loader2 className="w-10 h-10 animate-spin text-primary-400" />
                    <p className="text-sm font-semibold text-text-muted animate-pulse">Obteniendo documento...</p>
                  </div>
                ) : finalPdfUrl ? (
                  <iframe 
                     src={finalPdfUrl} 
                     className="w-full h-full border-none"
                     title="Vista Previa PDF"
                  />
                ) : (
                  <p className="text-sm text-text-muted">No se pudo cargar el documento.</p>
                )}
              </div>
            )}

            {/* AI Summary Sidebar on the Right (or full if no PDF) */}
            <div className={`${isSplitView ? 'w-[450px] flex-shrink-0 border-l border-white/5' : 'w-full'} flex flex-col h-full overflow-y-auto custom-scrollbar relative bg-[#111113]`}>
              <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-surface relative overflow-hidden flex-shrink-0">
                <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-3xl -mr-10 -mt-10 pointer-events-none"></div>
                <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center flex-shrink-0 shadow-[0_0_15px_rgba(99,102,241,0.1)] relative z-10">
                  <Sparkles className="w-5 h-5 text-indigo-400" />
                </div>
                <div className="relative z-10">
                  <h2 className="text-lg font-bold text-white leading-tight">
                    Resumen de IA
                  </h2>
                  <p className="text-xs text-indigo-300">Acta Principal Extraída</p>
                </div>
              </div>
              
              <div className="flex-1 p-6 space-y-6 relative">
                <div className="absolute top-1/4 right-0 w-64 h-64 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none"></div>
                
                <div className="relative z-10">
                  <p className="text-xs font-black text-indigo-400 uppercase tracking-widest mb-1">Razón Social</p>
                  <p className="text-lg font-bold text-white leading-tight">{aiSummary.razon_social}</p>
                </div>

                {(aiSummary.tipo_documento || aiSummary.numero_acta || aiSummary.fecha_documento) && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 relative z-10">
                    {aiSummary.tipo_documento && (
                      <div className="bg-surface/50 p-3 rounded-lg border border-border">
                        <p className="text-[10px] font-black text-indigo-300/80 uppercase tracking-widest mb-1">Tipo de Documento</p>
                        <p className="text-sm text-text-main font-medium">{aiSummary.tipo_documento}</p>
                      </div>
                    )}
                    {aiSummary.numero_acta && (
                      <div className="bg-surface/50 p-3 rounded-lg border border-border">
                        <p className="text-[10px] font-black text-indigo-300/80 uppercase tracking-widest mb-1">Número</p>
                        <p className="text-sm text-text-main font-medium">{aiSummary.numero_acta}</p>
                      </div>
                    )}
                    {aiSummary.fecha_documento && (
                      <div className="bg-surface/50 p-3 rounded-lg border border-border md:col-span-2">
                        <p className="text-[10px] font-black text-indigo-300/80 uppercase tracking-widest mb-1">Fecha de Realización</p>
                        <p className="text-sm text-text-main font-medium">{aiSummary.fecha_documento}</p>
                      </div>
                    )}
                  </div>
                )}
                
                <div className="relative z-10">
                  <p className="text-xs font-black text-indigo-400 uppercase tracking-widest mb-2">Accionistas y Participación</p>
                  <div className="bg-surface/30 rounded-xl border border-border p-4">
                    <ul className="space-y-3">
                      {aiSummary.accionistas?.map((acc, i) => (
                        <li key={i} className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-border/50 last:border-0 last:pb-0">
                          {typeof acc === 'string' ? (
                             <span className="text-sm text-text-main">{acc}</span>
                          ) : (
                            <>
                              <span className="font-semibold text-white text-sm">{acc.nombre}</span>
                              {acc.participacion && (
                                <span className="text-xs font-medium bg-indigo-500/10 text-indigo-300 px-2 py-1 rounded-md border border-indigo-500/20 mt-1 sm:mt-0">
                                  {acc.participacion}
                                </span>
                              )}
                            </>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="relative z-10">
                  <p className="text-xs font-black text-indigo-400 uppercase tracking-widest mb-2">Poderes Legales</p>
                  <div className="bg-surface/30 rounded-xl border border-border p-4 text-sm text-text-muted leading-relaxed">
                    {aiSummary.poderes}
                  </div>
                </div>
                
                <div className="relative z-10">
                  <p className="text-xs font-black text-indigo-400 uppercase tracking-widest mb-2">Resumen del Acta</p>
                  <div className="bg-indigo-500/5 rounded-xl border border-indigo-500/20 p-4">
                    <p className="text-sm text-indigo-200/90 leading-relaxed italic border-l-4 border-indigo-500/50 pl-3 py-1">
                      "{aiSummary.resumen}"
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
