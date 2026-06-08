import React, { useState, useEffect } from 'react'
import { CheckCircle2, XCircle, AlertTriangle, FileText, MapPin, Building2, Landmark, Loader2 } from 'lucide-react'
import api from '../lib/api'

// We will use the same cache object from AdminDashboard if possible, 
// but since it's defined in AdminDashboard, we can just maintain a local one here or rely on the fast network cache.
// For simplicity, we just fetch it, it's fast anyway.

const mopsCache = {}

export default function AdminCompanySummary({ empresa, documentos }) {
  const [mopData, setMopData] = useState(null)
  const [loadingMop, setLoadingMop] = useState(true)

  useEffect(() => {
    if (!empresa?.id) return
    
    let cancelled = false
    setLoadingMop(true)

    if (mopsCache[empresa.id]) {
      setMopData(mopsCache[empresa.id])
      setLoadingMop(false)
      return
    }

    api.getBuroMops(empresa.id)
      .then(res => {
        if (!cancelled) {
          mopsCache[empresa.id] = res
          setMopData(res)
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoadingMop(false) })

    return () => { cancelled = true }
  }, [empresa?.id])

  // Extract MOP Max
  let maxMop = 0
  if (mopData) {
    if (mopData.mops_alerta?.length > 0) {
      maxMop = Math.max(...mopData.mops_alerta.map(m => m.nivel))
    } else if (mopData.niveles) {
      const levels = Object.keys(mopData.niveles).map(Number)
      if (levels.length > 0) maxMop = Math.max(...levels)
    }
  }

  // Extract Opinion de Cumplimiento
  const opcDoc = documentos?.find(d => d.tipo_documento === 'opinion_cumplimiento')
  let opinion = 'Pendiente'
  let opinionColor = 'text-slate-400'
  let opinionBg = 'bg-slate-500/10 border-slate-500/20'
  let OpinionIcon = FileText

  if (opcDoc && opcDoc.comentario_admin?.startsWith('[SISTEMA] OPC:')) {
    const sentido = opcDoc.comentario_admin.replace('[SISTEMA] OPC:', '').trim()
    opinion = sentido
    if (sentido === 'POSITIVO') {
      opinionColor = 'text-emerald-400'
      opinionBg = 'bg-emerald-500/10 border-emerald-500/30'
      OpinionIcon = CheckCircle2
    } else {
      opinionColor = 'text-red-400'
      opinionBg = 'bg-red-500/10 border-red-500/30'
      OpinionIcon = XCircle
    }
  }

  // Calculate Bank Folders
  const docsEdos = documentos?.filter(d => d.grupo === 'estados_cuenta' && d.estado !== 'FALTANTE') || []
  const banks = new Set(docsEdos.map(d => d.nombre_carpeta).filter(Boolean))
  const totalBancos = banks.size

  // Check representative documents
  const isUploaded = (clave) => {
    const doc = documentos?.find(d => d.tipo_documento === clave)
    return doc && doc.estado !== 'FALTANTE'
  }

  const hasINE = isUploaded('ine_representante')
  const hasCSF = isUploaded('csf_representante')
  const hasMatrimonio = isUploaded('acta_matrimonio')
  const hasCD = isUploaded('comprobante_domicilio_representante')

  return (
    <div className="w-full xl:w-80 flex-shrink-0 flex flex-col gap-6 animate-fade-in">
      
      {/* ── CARD: Resumen de Empresa ────────────────────────────── */}
      <div className="bg-[#111113] border border-border rounded-2xl overflow-hidden shadow-xl">
        <div className="px-5 py-4 border-b border-border bg-surface/50 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary-500/10 border border-primary-500/20 flex items-center justify-center text-primary-400">
            <Building2 className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-text-main">Resumen de Empresa</h3>
            <p className="text-[11px] text-text-muted">Datos extraídos del expediente</p>
          </div>
        </div>

        <div className="p-5 space-y-5">
          {/* MOP de Buró */}
          <div className="group">
            <div className="flex items-center gap-2 mb-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-text-muted" />
              <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">MOP de Buró</span>
            </div>
            <div className="flex items-center gap-3">
              {loadingMop ? (
                <div className="flex items-center gap-2 text-text-muted text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-xs">Analizando...</span>
                </div>
              ) : (
                <div className={`px-3 py-1.5 rounded-lg border flex items-center gap-2 transition-all ${
                  maxMop >= 3 ? 'bg-red-500/10 border-red-500/30 text-red-400' :
                  maxMop > 0 ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                  'bg-slate-500/10 border-slate-500/20 text-slate-400'
                }`}>
                  <span className="text-lg font-black leading-none">{maxMop > 0 ? maxMop : '-'}</span>
                  <span className="text-[10px] font-bold uppercase tracking-widest opacity-80">
                    {maxMop >= 3 ? 'Alerta' : maxMop > 0 ? 'Normal' : 'Sin Datos'}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Opinión de Cumplimiento */}
          <div className="group">
            <div className="flex items-center gap-2 mb-1.5">
              <FileText className="w-3.5 h-3.5 text-text-muted" />
              <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Opinión SAT</span>
            </div>
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all ${opinionBg} ${opinionColor}`}>
              <OpinionIcon className="w-4 h-4" />
              <span className="text-sm font-bold">{opinion}</span>
            </div>
          </div>

          {/* Estados de Cuenta */}
          <div className="group">
            <div className="flex items-center gap-2 mb-1.5">
              <Landmark className="w-3.5 h-3.5 text-text-muted" />
              <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Bancos / Carpetas</span>
            </div>
            <div className="flex items-baseline gap-1.5 text-text-main">
              <span className="text-xl font-black">{totalBancos}</span>
              <span className="text-xs text-text-muted font-medium">cuentas detectadas</span>
            </div>
          </div>

          <hr className="border-border" />

          {/* Ubicaciones (Placeholders) */}
          <div className="space-y-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <MapPin className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Ubicación CD</span>
              </div>
              <p className="text-sm text-text-muted italic bg-surface/50 border border-border/50 rounded-lg px-3 py-2">
                No disponible
              </p>
            </div>
            
            <div>
              <div className="flex items-center gap-2 mb-1">
                <MapPin className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Ubicación CSF</span>
              </div>
              <p className="text-sm text-text-muted italic bg-surface/50 border border-border/50 rounded-lg px-3 py-2">
                No disponible
              </p>
            </div>
          </div>

        </div>
      </div>

      {/* ── CARD: Representante Legal ────────────────────────────── */}
      <div className="bg-[#111113] border border-border rounded-2xl overflow-hidden shadow-xl">
        <div className="px-5 py-4 border-b border-border bg-surface/50 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-bold text-text-main">Representante Legal</h3>
            <p className="text-[11px] text-text-muted">Estado de los documentos</p>
          </div>
        </div>

        <div className="p-5 space-y-5">
          
          {/* INE: Nombre */}
          <div className="group">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <FileText className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">INE (Nombre)</span>
              </div>
              {hasINE ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400 opacity-50" />}
            </div>
            <p className="text-sm text-text-muted italic bg-surface/50 border border-border/50 rounded-lg px-3 py-2">
              No disponible
            </p>
          </div>

          {/* CSF y Matrimonio */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="flex flex-col gap-1.5">
                <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Constancia (CSF)</span>
                <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all ${
                  hasCSF 
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
                    : 'bg-rose-500/5 border-rose-500/20 text-rose-400/50'
                }`}>
                  {hasCSF ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  <span className="text-xs font-bold">{hasCSF ? 'Subida' : 'Faltante'}</span>
                </div>
              </div>
            </div>
            
            <div>
              <div className="flex flex-col gap-1.5">
                <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Acta Matrimonio</span>
                <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all ${
                  hasMatrimonio 
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
                    : 'bg-rose-500/5 border-rose-500/20 text-rose-400/50'
                }`}>
                  {hasMatrimonio ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  <span className="text-xs font-bold">{hasMatrimonio ? 'Subida' : 'Faltante'}</span>
                </div>
              </div>
            </div>
          </div>

          <hr className="border-border" />

          {/* CD Ubicacion */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <MapPin className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Ubicación CD (Rep)</span>
              </div>
              {hasCD ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400 opacity-50" />}
            </div>
            <p className="text-sm text-text-muted italic bg-surface/50 border border-border/50 rounded-lg px-3 py-2">
              No disponible
            </p>
          </div>

        </div>
      </div>

    </div>
  )
}
