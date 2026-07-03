import React, { useState, useEffect } from 'react'
import { CheckCircle2, XCircle, AlertTriangle, FileText, MapPin, Building2, Landmark, Loader2, Copy, ShieldCheck, FolderPlus, UploadCloud, ExternalLink } from 'lucide-react'
import api from '../lib/api'
import { formatMopText } from '../lib/utils'

// We will use the same cache object from AdminDashboard if possible, 
// but since it's defined in AdminDashboard, we can just maintain a local one here or rely on the fast network cache.
// For simplicity, we just fetch it, it's fast anyway.

const mopsCache = {}

export default function AdminCompanySummary({ empresa, documentos }) {
  const [mopData, setMopData] = useState(null)
  const [loadingMop, setLoadingMop] = useState(true)

  const [mopRepData, setMopRepData] = useState(null)
  const [loadingMopRep, setLoadingMopRep] = useState(true)

  const [scoreRepData, setScoreRepData] = useState(null)
  const [loadingScoreRep, setLoadingScoreRep] = useState(true)

  const [verificandoEmpresa, setVerificandoEmpresa] = useState(false)
  const [matchEmpresa, setMatchEmpresa] = useState(null)
  
  const [verificandoRep, setVerificandoRep] = useState(false)
  const [matchRep, setMatchRep] = useState(null)

  const [driveLoading, setDriveLoading] = useState(false)
  const [driveLink, setDriveLink] = useState(null)

  const handleInitDrive = async () => {
    setDriveLoading(true)
    try {
      const res = await api.initDrive(empresa.id)
      if (res.link) setDriveLink(res.link)
      alert(res.message)
    } catch (e) {
      alert("Error: " + e.message)
    }
    setDriveLoading(false)
  }

  const handleSyncDrive = async () => {
    setDriveLoading(true)
    try {
      const res = await api.syncDrive(empresa.id)
      if (res.link) setDriveLink(res.link)
      alert(res.message)
    } catch (e) {
      alert("Error: " + e.message)
    }
    setDriveLoading(false)
  }

  const handleCopy = (text) => {
    if (text && text !== 'No disponible') {
      navigator.clipboard.writeText(text)
    }
  }

  const verificarUbicacionEmpresa = async () => {
    setVerificandoEmpresa(true)
    try {
      const res = await api.verificarDomicilios(cdEmpresaName, csfEmpresaName)
      setMatchEmpresa(res)
    } catch (e) {
      console.error(e)
    }
    setVerificandoEmpresa(false)
  }

  const verificarUbicacionRep = async () => {
    setVerificandoRep(true)
    try {
      const res = await api.verificarDomicilios(cdRepName, csfRepName)
      setMatchRep(res)
    } catch (e) {
      console.error(e)
    }
    setVerificandoRep(false)
  }

  useEffect(() => {
    if (!empresa?.id) return
    
    let cancelled = false
    setLoadingMop(true)

    if (mopsCache[empresa.id]) {
      setMopData(mopsCache[empresa.id])
      setLoadingMop(false)
    } else {
      api.getBuroMops(empresa.id, 'buro_credito')
        .then(res => {
          if (!cancelled) {
            mopsCache[empresa.id] = res
            setMopData(res)
          }
        })
        .catch(() => {})
        .finally(() => { if (!cancelled) setLoadingMop(false) })
    }

    const cacheRepKey = `${empresa.id}_rep`
    if (mopsCache[cacheRepKey]) {
      setMopRepData(mopsCache[cacheRepKey])
      setLoadingMopRep(false)
    } else {
      api.getBuroMops(empresa.id, 'buro_representante')
        .then(res => {
          if (!cancelled) {
            mopsCache[cacheRepKey] = res
            setMopRepData(res)
          }
        })
        .catch(() => {})
        .finally(() => { if (!cancelled) setLoadingMopRep(false) })
    }

    const scoreRepKey = `${empresa.id}_score_rep`
    if (mopsCache[scoreRepKey]) {
      setScoreRepData(mopsCache[scoreRepKey])
      setLoadingScoreRep(false)
    } else {
      api.getBuroScore(empresa.id, 'buro_score_representante')
        .then(res => {
          if (!cancelled) {
            mopsCache[scoreRepKey] = res
            setScoreRepData(res)
          }
        })
        .catch(() => {})
        .finally(() => { if (!cancelled) setLoadingScoreRep(false) })
    }

    return () => { cancelled = true }
  }, [empresa?.id])

  // Format MOPs
  const mopInfo = formatMopText(mopData)
  const mopRepInfo = formatMopText(mopRepData)

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
  const ineDoc = documentos?.find(d => d.tipo_documento === 'ine_representante')
  const hasINE = ineDoc && ineDoc.estado !== 'FALTANTE'
  
  let ineName = 'No disponible'
  if (hasINE && ineDoc?.nombre_archivo) {
    const match = ineDoc.nombre_archivo.match(/1\. INE - (.*?)(?:\.[a-zA-Z0-9]+)?$/i)
    if (match && match[1]) {
      ineName = match[1]
    } else {
      // Fallback
      ineName = ineDoc.nombre_archivo
    }
  }

  const cdEmpresaDoc = documentos?.find(d => d.tipo_documento === 'comprobante_domicilio_empresa')
  const hasCDEmpresa = cdEmpresaDoc && cdEmpresaDoc.estado !== 'FALTANTE'
  let cdEmpresaName = 'No disponible'
  if (hasCDEmpresa && cdEmpresaDoc?.nombre_archivo) {
    const match = cdEmpresaDoc.nombre_archivo.match(/3\. CD - (.*?)(?:\.[a-zA-Z0-9]+)?$/i)
    if (match && match[1]) {
      cdEmpresaName = match[1].replace(' - ', ' | ')
    } else {
      cdEmpresaName = cdEmpresaDoc.nombre_archivo
    }
  }

  const cdRepDoc = documentos?.find(d => d.tipo_documento === 'comprobante_domicilio_representante')
  const hasCDRep = cdRepDoc && cdRepDoc.estado !== 'FALTANTE'
  let cdRepName = 'No disponible'
  if (hasCDRep && cdRepDoc?.nombre_archivo) {
    const match = cdRepDoc.nombre_archivo.match(/2\. CD - (.*?)(?:\.[a-zA-Z0-9]+)?$/i)
    if (match && match[1]) {
      cdRepName = match[1].replace(' - ', ' | ')
    } else {
      cdRepName = cdRepDoc.nombre_archivo
    }
  }

  const csfEmpresaDoc = documentos?.find(d => d.tipo_documento === 'csf_empresa')
  const hasCSFEmpresa = csfEmpresaDoc && csfEmpresaDoc.estado !== 'FALTANTE'
  let csfEmpresaName = 'No disponible'
  if (hasCSFEmpresa && csfEmpresaDoc?.nombre_archivo) {
    const match = csfEmpresaDoc.nombre_archivo.match(/1\. CSF - (.*?)(?:\.[a-zA-Z0-9]+)?$/i)
    if (match && match[1]) {
      csfEmpresaName = match[1]
    } else {
      csfEmpresaName = csfEmpresaDoc.nombre_archivo
    }
  }

  const csfRepDoc = documentos?.find(d => d.tipo_documento === 'csf_representante')
  const hasCSF = csfRepDoc && csfRepDoc.estado !== 'FALTANTE'
  let csfRepName = 'No disponible'
  if (hasCSF && csfRepDoc?.nombre_archivo) {
    const match = csfRepDoc.nombre_archivo.match(/3\. CSF - (.*?)(?:\.[a-zA-Z0-9]+)?$/i)
    if (match && match[1]) {
      csfRepName = match[1]
    } else {
      csfRepName = csfRepDoc.nombre_archivo
    }
  }

  const isUploaded = (clave) => {
    const doc = documentos?.find(d => d.tipo_documento === clave)
    return doc && doc.estado !== 'FALTANTE'
  }

  const hasMatrimonio = isUploaded('acta_matrimonio')

  return (
    <div className="w-full xl:w-[26rem] flex-shrink-0 flex flex-col gap-6 animate-fade-in">
      
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
                <div className={`px-3 py-1.5 rounded-lg border flex flex-col justify-center transition-all ${
                  mopInfo.alert ? 'bg-red-500/10 border-red-500/30 text-red-400' :
                  mopInfo.maxLevel > 0 ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                  'bg-slate-500/10 border-slate-500/20 text-slate-400'
                }`}>
                  <span className="text-base font-black leading-none whitespace-nowrap">{mopInfo.text}</span>
                  {mopInfo.subtext ? (
                    <span className="text-[9px] font-bold uppercase tracking-widest opacity-80 mt-0.5">
                      {mopInfo.subtext}
                    </span>
                  ) : (
                    <span className="text-[9px] font-bold uppercase tracking-widest opacity-80 mt-0.5">
                      {mopInfo.alert ? 'Alerta' : mopInfo.maxLevel > 0 ? 'Normal' : 'Sin Datos'}
                    </span>
                  )}
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

          {/* Ubicaciones */}
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <MapPin className="w-3.5 h-3.5 text-text-muted" />
                  <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Ubicación CD</span>
                </div>
                {hasCDEmpresa && (
                  <button onClick={() => handleCopy(cdEmpresaName)} className="text-text-muted hover:text-emerald-400 transition-colors" title="Copiar">
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
              <p className={`text-sm ${hasCDEmpresa ? 'text-emerald-400 font-medium bg-emerald-500/10 border border-emerald-500/20 not-italic' : 'text-text-muted italic bg-surface/50 border border-border/50'} rounded-lg px-3 py-2 truncate`} title={cdEmpresaName}>
                {cdEmpresaName}
              </p>
            </div>
            
            <div>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <MapPin className="w-3.5 h-3.5 text-text-muted" />
                  <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Ubicación CSF</span>
                </div>
                {hasCSFEmpresa && (
                  <button onClick={() => handleCopy(csfEmpresaName)} className="text-text-muted hover:text-emerald-400 transition-colors" title="Copiar">
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
              <p className={`text-sm ${hasCSFEmpresa ? 'text-emerald-400 font-medium bg-emerald-500/10 border border-emerald-500/20 not-italic' : 'text-text-muted italic bg-surface/50 border border-border/50'} rounded-lg px-3 py-2 truncate`} title={csfEmpresaName}>
                {csfEmpresaName}
              </p>
            </div>

            {/* Verificación Gemini */}
            {(hasCDEmpresa && hasCSFEmpresa) && (
              <div className="pt-2">
                <button 
                  onClick={verificarUbicacionEmpresa}
                  disabled={verificandoEmpresa}
                  className="w-full py-2 px-3 rounded-lg border border-indigo-500/30 bg-indigo-500/10 text-indigo-400 text-xs font-semibold flex items-center justify-center gap-2 hover:bg-indigo-500/20 transition-all disabled:opacity-50"
                >
                  {verificandoEmpresa ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                  {verificandoEmpresa ? 'Verificando con Gemini...' : 'Verificar Coincidencia de Domicilios'}
                </button>
                {matchEmpresa && (
                  <div className={`mt-2 p-3 rounded-lg text-xs border ${matchEmpresa.match ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-amber-500/10 border-amber-500/30 text-amber-400'}`}>
                    <div className="font-bold mb-1 flex items-center gap-1">
                      {matchEmpresa.match ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                      {matchEmpresa.match ? 'Domicilios Coincidentes' : 'Posible Discrepancia'}
                    </div>
                    <p className="opacity-90">{matchEmpresa.razon}</p>
                  </div>
                )}
              </div>
            )}
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
          
          {/* MOP de Buró (Representante) */}
          <div className="group">
            <div className="flex items-center gap-2 mb-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-text-muted" />
              <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Buró de Crédito</span>
            </div>
            <div className="flex items-center gap-3">
              {/* MOP Block */}
              {loadingMopRep ? (
                <div className="flex items-center gap-2 text-text-muted text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-xs">Analizando MOPs...</span>
                </div>
              ) : (
                <div className={`px-3 py-1.5 rounded-lg border flex flex-col justify-center transition-all ${
                  mopRepInfo.alert ? 'bg-red-500/10 border-red-500/30 text-red-400' :
                  mopRepInfo.maxLevel > 0 ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                  'bg-slate-500/10 border-slate-500/20 text-slate-400'
                }`}>
                  <span className="text-base font-black leading-none whitespace-nowrap">{mopRepInfo.text}</span>
                  {mopRepInfo.subtext ? (
                    <span className="text-[9px] font-bold uppercase tracking-widest opacity-80 mt-0.5">
                      {mopRepInfo.subtext}
                    </span>
                  ) : (
                    <span className="text-[9px] font-bold uppercase tracking-widest opacity-80 mt-0.5">
                      {mopRepInfo.alert ? 'Alerta' : mopRepInfo.maxLevel > 0 ? 'Normal' : 'Sin Datos'}
                    </span>
                  )}
                </div>
              )}

              {/* Score Block */}
              {loadingScoreRep ? (
                <div className="flex items-center gap-2 text-text-muted text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-xs">Score...</span>
                </div>
              ) : (
                <div className={`px-3 py-1.5 rounded-lg border flex flex-col justify-center transition-all ${
                  !scoreRepData?.score ? 'bg-slate-500/10 border-slate-500/20 text-slate-400' :
                  scoreRepData.score >= 650 ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                  scoreRepData.score >= 550 ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400' :
                  'bg-red-500/10 border-red-500/30 text-red-400'
                }`}>
                  <span className="text-base font-black leading-none whitespace-nowrap">{scoreRepData?.score || '-'}</span>
                  <span className="text-[9px] font-bold uppercase tracking-widest opacity-80 mt-0.5">
                    {scoreRepData?.score ? 'BC Score' : 'Sin Score'}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* INE: Nombre */}
          <div className="group">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <FileText className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">INE (Nombre)</span>
              </div>
              <div className="flex items-center gap-2">
                {hasINE && (
                  <button onClick={() => handleCopy(ineName)} className="text-text-muted hover:text-emerald-400 transition-colors" title="Copiar">
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                )}
                {hasINE ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400 opacity-50" />}
              </div>
            </div>
            <p className={`text-sm ${hasINE ? 'text-emerald-400 font-medium bg-emerald-500/10 border border-emerald-500/20 not-italic' : 'text-text-muted italic bg-surface/50 border border-border/50'} rounded-lg px-3 py-2 truncate`} title={ineName}>
              {ineName}
            </p>
          </div>

          {/* Ubicación CSF (Rep) */}
          <div className="group">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <MapPin className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Ubicación CSF (Rep)</span>
              </div>
              <div className="flex items-center gap-2">
                {hasCSF && (
                  <button onClick={() => handleCopy(csfRepName)} className="text-text-muted hover:text-emerald-400 transition-colors" title="Copiar">
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                )}
                {hasCSF ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400 opacity-50" />}
              </div>
            </div>
            <p className={`text-sm ${hasCSF ? 'text-emerald-400 font-medium bg-emerald-500/10 border border-emerald-500/20 not-italic' : 'text-text-muted italic bg-surface/50 border border-border/50'} rounded-lg px-3 py-2 truncate`} title={csfRepName}>
              {hasCSF ? csfRepName : 'No disponible'}
            </p>
          </div>

          {/* Acta Matrimonio */}
          <div className="group">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <FileText className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Acta Matrimonio</span>
              </div>
              {hasMatrimonio ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400 opacity-50" />}
            </div>
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all ${
              hasMatrimonio 
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
                : 'bg-rose-500/5 border-rose-500/20 text-rose-400/50'
            }`}>
              <span className="text-xs font-bold">{hasMatrimonio ? 'Subida' : 'Faltante'}</span>
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
              <div className="flex items-center gap-2">
                {hasCDRep && (
                  <button onClick={() => handleCopy(cdRepName)} className="text-text-muted hover:text-emerald-400 transition-colors" title="Copiar">
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                )}
                {hasCDRep ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400 opacity-50" />}
              </div>
            </div>
            <p className={`text-sm ${hasCDRep ? 'text-emerald-400 font-medium bg-emerald-500/10 border border-emerald-500/20 not-italic' : 'text-text-muted italic bg-surface/50 border border-border/50'} rounded-lg px-3 py-2 truncate`} title={cdRepName}>
              {cdRepName}
            </p>
          </div>

          {/* Verificación Gemini (Rep) */}
          {(hasCDRep && hasCSF) && (
            <div className="pt-2">
              <button 
                onClick={verificarUbicacionRep}
                disabled={verificandoRep}
                className="w-full py-2 px-3 rounded-lg border border-indigo-500/30 bg-indigo-500/10 text-indigo-400 text-xs font-semibold flex items-center justify-center gap-2 hover:bg-indigo-500/20 transition-all disabled:opacity-50"
              >
                {verificandoRep ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                {verificandoRep ? 'Verificando con Gemini...' : 'Verificar Coincidencia de Domicilios'}
              </button>
              {matchRep && (
                <div className={`mt-2 p-3 rounded-lg text-xs border ${matchRep.match ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-amber-500/10 border-amber-500/30 text-amber-400'}`}>
                  <div className="font-bold mb-1 flex items-center gap-1">
                    {matchRep.match ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                    {matchRep.match ? 'Domicilios Coincidentes' : 'Posible Discrepancia'}
                  </div>
                  <p className="opacity-90">{matchRep.razon}</p>
                </div>
              )}
            </div>
          )}

        </div>
      </div>

      {/* Acciones de Google Drive */}
      <div className="bg-surface border border-border rounded-xl p-5 w-[320px] shadow-sm flex flex-col gap-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded bg-blue-500/10 flex items-center justify-center border border-blue-500/20">
            <svg className="w-4 h-4 text-blue-400" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L3 18h18L12 2zm0 4.2L16.2 14H7.8L12 6.2zM8.5 22l-4-7h5.8l4 7H8.5zm11 0l-4-7h-5.8l4 7h5.8z" />
            </svg>
          </div>
          <h3 className="text-sm font-bold text-text-primary tracking-wide">Google Drive</h3>
        </div>

        <button 
          onClick={handleSyncDrive}
          disabled={driveLoading}
          className="w-full py-2.5 px-3 rounded-lg border border-indigo-500/30 bg-indigo-500/10 text-indigo-400 text-xs font-semibold flex items-center justify-center gap-2 hover:bg-indigo-500/20 transition-all disabled:opacity-50"
        >
          {driveLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
          Sincronizar Documentos a Drive
        </button>

        {driveLink && (
          <a
            href={driveLink}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full py-2 px-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-xs font-semibold flex items-center justify-center gap-2 hover:bg-emerald-500/20 transition-all"
          >
            <ExternalLink className="w-3 h-3" />
            Abrir Carpeta en Drive
          </a>
        )}
      </div>

    </div>
  )
}
