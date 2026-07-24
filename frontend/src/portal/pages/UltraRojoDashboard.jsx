import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Building2, Plus, Search, FolderOpen, Loader2, X, AlertTriangle, Edit2, Trash2, ArrowLeft, FileText, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../lib/api'
import AdminCompanySummary from '../components/AdminCompanySummary'
import PdfDrawer from '../components/PdfDrawer'
import ClienteDashboard from './ClienteDashboard'

export default function UltraRojoDashboard() {
  const [empresas, setEmpresas] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  
  // Modal State
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newEmpresa, setNewEmpresa] = useState({ nombre: '', rfc: '' })
  const [creating, setCreating] = useState(false)
  // Detail View State
  const [selectedEmpresa, setSelectedEmpresa] = useState(null)
  const [expedienteData, setExpedienteData] = useState(null)
  const [loadingExpediente, setLoadingExpediente] = useState(false)
  const [activeTab, setActiveTab] = useState('empresa') // 'empresa' | 'representante'
  const [collapsedFolders, setCollapsedFolders] = useState({})
  const [pdfViewerDoc, setPdfViewerDoc] = useState(null)
  
  // Cliente View State (for direct URL navigation to specific company docs)
  const [clienteViewUser, setClienteViewUser] = useState(null)

  const toggleFolder = (cat) => {
    setCollapsedFolders(prev => ({ ...prev, [cat]: !prev[cat] }))
  }
  const fetchEmpresas = async () => {
    try {
      setLoading(true)
      const data = await api.getEmpresas()
      const list = data.empresas || []
      setEmpresas(list)
      setError(null)
      return list
    } catch (err) {
      setError(err.message)
      return []
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const init = async () => {
      const list = await fetchEmpresas()
      // Detectar URL ej. /ultrarojo/5cd751e8-dc30-48d0-bcef-28bdadc83a3f
      const pathParts = window.location.pathname.split('/').filter(Boolean)
      if (pathParts.length >= 2 && pathParts[0].toLowerCase() === 'ultrarojo') {
        const id = pathParts[1]
        const emp = list.find(e => e.id.includes(id) || id.includes(e.id))
        if (emp) {
          api.setActiveEmpresa(emp.id)
          setClienteViewUser({
            empresa_id: emp.id,
            nombre_empresa: emp.nombre,
            rfc: emp.rfc
          })
        }
      }
    }
    init()
  }, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!newEmpresa.nombre) return
    try {
      setCreating(true)
      await api.crearEmpresa(newEmpresa.nombre, newEmpresa.rfc)
      setShowCreateModal(false)
      setNewEmpresa({ nombre: '', rfc: '' })
      await fetchEmpresas()
    } catch (err) {
      alert(`Error: ${err.message}`)
    } finally {
      setCreating(false)
    }
  }

  const handleViewDocument = (e, docId) => {
    e.stopPropagation()
    setPdfViewerDoc({ 
      empresaId: selectedEmpresa.id, 
      docId: docId, 
      isRep: activeTab === 'representante' 
    })
  }

  const handleOpenExpediente = async (emp) => {
    setSelectedEmpresa(emp)
    setLoadingExpediente(true)
    try {
      api.setActiveEmpresa(emp.id)
      const data = await api.getExpediente()
      setExpedienteData(data)
    } catch (err) {
      alert(`Error cargando expediente: ${err.message}`)
    } finally {
      setLoadingExpediente(false)
    }
  }

  const handleBack = () => {
    setSelectedEmpresa(null)
    setExpedienteData(null)
    api.setActiveEmpresa(null)
  }
  const filteredEmpresas = empresas.filter(emp => 
    emp.nombre.toLowerCase().includes(searchTerm.toLowerCase()) || 
    (emp.rfc && emp.rfc.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  if (clienteViewUser) {
    return (
      <ClienteDashboard 
        user={clienteViewUser} 
        onLogout={() => {
          window.history.pushState({}, '', '/ultrarojo')
          setClienteViewUser(null)
        }} 
        isInternalMode={true} 
      />
    )
  }

  if (selectedEmpresa) {
    const docs = expedienteData?.documentos?.filter(d => activeTab === 'empresa' ? d.grupo !== 'representante' : d.grupo === 'representante') || []
    
    const catLabels = {
      'legal': 'DOCUMENTOS LEGALES',
      'fiscal': 'DOCUMENTOS FISCALES',
      'bancario': 'BANCARIO',
      'estados_cuenta': 'BANCARIO',
      'financiero': 'FINANCIERO',
      'financieros': 'FINANCIERO',
      'corporativo': 'CORPORATIVO',
      'vigentes': 'CORPORATIVO',
      'declaraciones': 'DOCUMENTOS FISCALES',
      'representante': 'REPRESENTANTE LEGAL',
      'Otros': 'OTROS DOCUMENTOS'
    }

    const groupedDocs = docs.reduce((acc, doc) => {
      const baseCat = doc.categoria || doc.grupo || 'Otros'
      const topCatName = catLabels[baseCat] || baseCat.toUpperCase()
      
      if (!acc[topCatName]) {
        acc[topCatName] = { isNested: false, docs: [], subFolders: {}, count: 0 }
      }
      acc[topCatName].count++
      
      if ((baseCat === 'bancario' || baseCat === 'estados_cuenta') && doc.nombre_carpeta) {
        acc[topCatName].isNested = true
        const subName = doc.nombre_carpeta.toUpperCase()
        if (!acc[topCatName].subFolders[subName]) acc[topCatName].subFolders[subName] = []
        acc[topCatName].subFolders[subName].push(doc)
      } else {
        acc[topCatName].docs.push(doc)
      }

      return acc
    }, {})

    return (
      <>
        <div className="min-h-full p-8 max-w-7xl mx-auto space-y-8 animate-fade-in">
        {/* Detail Header */}
        <div className="flex items-center justify-between bg-[#15151a] p-6 rounded-2xl border border-white/10 shadow-2xl">
          <div className="flex items-center gap-4">
            <button 
              onClick={handleBack}
              className="p-2 hover:bg-white/10 rounded-xl transition-colors text-text-muted hover:text-white"
            >
              <ArrowLeft className="w-6 h-6" />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-rose-500" />
                <h2 className="text-2xl font-bold text-white">{selectedEmpresa.nombre}</h2>
              </div>
              <p className="text-xs text-text-muted font-mono mt-1">RFC: {selectedEmpresa.rfc || 'SIN RFC'} · ID: {selectedEmpresa.id.split('-')[0]}</p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 p-1.5 bg-black/40 rounded-xl border border-white/5 w-fit">
          <button 
            onClick={() => setActiveTab('empresa')}
            className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'empresa' ? 'bg-rose-600 text-white shadow-[0_0_15px_rgba(225,29,72,0.3)]' : 'text-text-muted hover:text-white hover:bg-white/5'}`}
          >
            EMPRESA
          </button>
          <button 
            onClick={() => setActiveTab('representante')}
            className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'representante' ? 'bg-rose-600 text-white shadow-[0_0_15px_rgba(225,29,72,0.3)]' : 'text-text-muted hover:text-white hover:bg-white/5'}`}
          >
            REPRESENTANTE
          </button>
        </div>

        {/* Documents Grid */}
        {loadingExpediente ? (
          <div className="flex flex-col items-center justify-center py-32">
            <Loader2 className="w-10 h-10 animate-spin text-rose-500 mb-4" />
            <p className="text-text-muted font-medium">Cargando expediente completo...</p>
          </div>
        ) : (
          <div className="flex flex-col xl:flex-row gap-8 items-start">
            <AdminCompanySummary 
              empresa={selectedEmpresa}
              documentos={expedienteData?.documentos || []}
              actaPrincipal={null}
              alertaNombresMismatch={false}
              viewMode={activeTab}
            />
            <div className="flex-1 space-y-6 w-full min-w-0">
              {Object.keys(groupedDocs).length === 0 ? (
              <div className="py-16 text-center bg-black/20 rounded-2xl border border-white/5 border-dashed">
                <FileText className="w-8 h-8 text-text-muted opacity-30 mx-auto mb-3" />
                <p className="text-text-muted font-medium">No hay documentos requeridos para {activeTab}.</p>
              </div>
            ) : (
              Object.entries(groupedDocs).map(([cat, data]) => (
                <div key={cat} className="bg-[#15151a] border border-white/10 rounded-2xl overflow-hidden shadow-xl">
                  <button 
                    onClick={() => toggleFolder(cat)}
                    className="w-full bg-white/5 hover:bg-white/10 px-6 py-4 border-b border-white/10 flex items-center justify-between transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <FolderOpen className="w-5 h-5 text-rose-500" />
                      <h3 className="font-bold text-white uppercase tracking-wider text-sm">{cat}</h3>
                      <span className="bg-black/50 text-text-muted text-xs px-2.5 py-1 rounded-full font-mono">{data.count} docs</span>
                    </div>
                    <div className="text-text-muted">
                      {collapsedFolders[cat] ? <ChevronDown className="w-5 h-5" /> : <ChevronUp className="w-5 h-5" />}
                    </div>
                  </button>
                  
                  {!collapsedFolders[cat] && (
                    data.isNested ? (
                      <div className="p-4 space-y-4 bg-black/20 border-t border-white/5">
                        {Object.entries(data.subFolders).map(([subCat, docsInSub]) => (
                          <div key={subCat} className="border border-white/10 rounded-xl overflow-hidden bg-[#15151a]">
                            <button 
                              onClick={() => toggleFolder(`${cat}_${subCat}`)}
                              className="w-full bg-white/5 hover:bg-white/10 px-5 py-3 border-b border-white/10 flex items-center justify-between transition-colors"
                            >
                              <div className="flex items-center gap-3">
                                <FolderOpen className="w-4 h-4 text-rose-400" />
                                <h4 className="font-bold text-white/80 uppercase tracking-wider text-xs">{subCat}</h4>
                                <span className="bg-black/50 text-text-muted text-xs px-2 py-0.5 rounded-full font-mono">{docsInSub.length} docs</span>
                              </div>
                              <div className="text-text-muted">
                                {collapsedFolders[`${cat}_${subCat}`] ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
                              </div>
                            </button>
                            
                            {!collapsedFolders[`${cat}_${subCat}`] && (
                              <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse">
                                  <tbody className="divide-y divide-white/5">
                                    {docsInSub.map(doc => (
                                      <tr key={doc.clave} className="hover:bg-white/[0.02] transition-colors group">
                                        <td className="px-6 py-4 w-1/2">
                                          <div className="flex items-center gap-4">
                                            <div className={`p-2.5 rounded-xl shrink-0 ${doc.estado !== 'FALTANTE' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-white/5 text-text-muted'}`}>
                                              {doc.estado !== 'FALTANTE' ? <CheckCircle2 className="w-5 h-5" /> : <FileText className="w-5 h-5" />}
                                            </div>
                                            <p className="font-bold text-sm text-white group-hover:text-rose-300 transition-colors">{doc.nombre}</p>
                                          </div>
                                        </td>
                                        <td className="px-6 py-4">
                                          <span className={`px-3 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest ${doc.estado !== 'FALTANTE' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-500 border border-rose-500/20'}`}>
                                            {doc.estado}
                                          </span>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                          {doc.estado !== 'FALTANTE' ? (
                                            <button onClick={(e) => handleViewDocument(e, doc.documento_id)} className="bg-transparent hover:bg-emerald-500/10 text-text-muted hover:text-emerald-400 border border-white/10 hover:border-emerald-500/30 font-semibold py-1.5 px-4 rounded-lg text-xs transition-all inline-flex items-center gap-2">
                                              <FileText className="w-4 h-4" />
                                              Ver Archivo
                                            </button>
                                          ) : (
                                            <span className="text-text-muted text-xs italic font-medium pr-4">Pendiente de subida</span>
                                          )}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                          <tbody className="divide-y divide-white/5">
                            {data.docs.map(doc => (
                              <tr key={doc.clave} className="hover:bg-white/[0.02] transition-colors group">
                                <td className="px-6 py-4 w-1/2">
                                  <div className="flex items-center gap-4">
                                    <div className={`p-2.5 rounded-xl shrink-0 ${doc.estado !== 'FALTANTE' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-white/5 text-text-muted'}`}>
                                      {doc.estado !== 'FALTANTE' ? <CheckCircle2 className="w-5 h-5" /> : <FileText className="w-5 h-5" />}
                                    </div>
                                    <p className="font-bold text-sm text-white group-hover:text-rose-300 transition-colors">{doc.nombre}</p>
                                  </div>
                                </td>
                                <td className="px-6 py-4">
                                  <span className={`px-3 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest ${doc.estado !== 'FALTANTE' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-500 border border-rose-500/20'}`}>
                                    {doc.estado}
                                  </span>
                                </td>
                                <td className="px-6 py-4 text-right">
                                  {doc.estado !== 'FALTANTE' ? (
                                    <button onClick={(e) => handleViewDocument(e, doc.documento_id)} className="bg-transparent hover:bg-emerald-500/10 text-text-muted hover:text-emerald-400 border border-white/10 hover:border-emerald-500/30 font-semibold py-1.5 px-4 rounded-lg text-xs transition-all inline-flex items-center gap-2">
                                      <FileText className="w-4 h-4" />
                                      Ver Archivo
                                    </button>
                                  ) : (
                                    <span className="text-text-muted text-xs italic font-medium pr-4">Pendiente de subida</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )
                  )}
                </div>
              ))
            )}
            </div>
          </div>
        )}
      </div>
      <PdfDrawer
        isOpen={!!pdfViewerDoc}
        empresaId={pdfViewerDoc?.empresaId}
        docId={pdfViewerDoc?.docId}
        isRep={pdfViewerDoc?.isRep}
        onClose={() => setPdfViewerDoc(null)}
      />
      </>
    )
  }

  return (
    <div className="min-h-full p-8 max-w-7xl mx-auto space-y-8 animate-fade-in">
      {/* Encabezado */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <span className="text-2xl text-rose-600">🩸</span>
            <h1 className="text-3xl font-black tracking-tight text-white">Expediente UltraRojo</h1>
          </div>
          <p className="text-text-muted text-sm max-w-xl">
            Centro de control maestro para la gestión de prospectos corporativos y entidades financieras.
          </p>
        </div>
        
        <button
          onClick={() => setShowCreateModal(true)}
          className="bg-rose-600 hover:bg-rose-500 text-white font-bold py-2.5 px-6 rounded-xl shadow-[0_0_15px_rgba(225,29,72,0.3)] transition-all flex items-center gap-2 group"
        >
          <Plus className="w-5 h-5 group-hover:rotate-90 transition-transform" />
          Nueva Empresa
        </button>
      </div>

      {/* Buscador */}
      <div className="relative group">
        <div className="absolute inset-y-0 left-0 flex items-center pl-4 pointer-events-none">
          <Search className="w-5 h-5 text-text-muted group-focus-within:text-rose-500 transition-colors" />
        </div>
        <input
          type="text"
          placeholder="Buscar por nombre o RFC..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full bg-[#15151a] border border-white/10 rounded-2xl py-3.5 pl-12 pr-4 text-white placeholder-text-muted/50 focus:outline-none focus:border-rose-500/50 focus:ring-1 focus:ring-rose-500/50 transition-all shadow-inner"
        />
      </div>

      {/* Tabla */}
      <div className="bg-[#15151a] border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-rose-500 mb-4" />
            <p className="text-text-muted font-medium">Sincronizando base de datos...</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-20 text-center px-4">
            <AlertTriangle className="w-10 h-10 text-rose-500 mb-4 opacity-50" />
            <p className="text-rose-400 font-bold mb-2">Error de Conexión</p>
            <p className="text-text-muted text-sm">{error}</p>
            <button onClick={fetchEmpresas} className="mt-6 bg-white/5 hover:bg-white/10 px-4 py-2 rounded-lg text-sm transition-colors">Reintentar</button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-black/40 text-text-muted text-[10px] uppercase tracking-widest font-black border-b border-white/10">
                  <th className="px-6 py-5">Empresa</th>
                  <th className="px-6 py-5">Identificador (RFC)</th>
                  <th className="px-6 py-5 text-center">Docs</th>
                  <th className="px-6 py-5 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredEmpresas.length === 0 ? (
                  <tr>
                    <td colSpan="4" className="px-6 py-16 text-center text-text-muted">
                      No se encontraron empresas que coincidan con la búsqueda.
                    </td>
                  </tr>
                ) : (
                  filteredEmpresas.map((emp) => (
                    <tr key={emp.id} className="hover:bg-white/[0.02] transition-colors group">
                      <td className="px-6 py-5">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-rose-500/20 to-purple-500/10 border border-white/5 flex items-center justify-center shrink-0">
                            <Building2 className="w-5 h-5 text-rose-400" />
                          </div>
                          <div>
                            <p className="text-sm font-bold text-white group-hover:text-rose-300 transition-colors">{emp.nombre}</p>
                            <p className="text-[10px] text-text-muted font-mono mt-1">ID: {emp.id.split('-')[0]}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-5">
                        <span className="bg-white/5 text-text-muted px-2.5 py-1 rounded-md text-xs font-mono border border-white/5">
                          {emp.rfc || 'SIN RFC'}
                        </span>
                      </td>
                      <td className="px-6 py-5 text-center">
                        <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-white/5 text-xs font-bold text-text-muted border border-white/5">
                          {emp.documentos_count || 0}
                        </span>
                      </td>
                      <td className="px-6 py-5">
                        <div className="flex items-center justify-end gap-2">
                          <button 
                            onClick={() => handleOpenExpediente(emp)}
                            title="Abrir Expediente"
                            className="bg-transparent hover:bg-rose-500/10 text-text-muted hover:text-rose-400 border border-white/10 hover:border-rose-500/30 font-semibold py-1.5 px-4 rounded-lg text-xs transition-all flex items-center gap-2"
                          >
                            <FolderOpen className="w-4 h-4" />
                            Abrir
                          </button>
                          <a 
                            href={`/ultrarojo/${emp.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            title="Subir Documentos (Abrir en nueva pestaña)"
                            className="p-1.5 rounded-lg border border-transparent hover:border-white/10 hover:bg-white/5 text-text-muted hover:text-white transition-all inline-block"
                          >
                            <Edit2 className="w-4 h-4" />
                          </a>
                          <button 
                            onClick={() => {
                              if(window.confirm('¿Estás seguro de eliminar esta empresa?')) {
                                api.eliminarEmpresa(emp.id).then(fetchEmpresas).catch(e => alert(e.message))
                              }
                            }}
                            title="Eliminar Empresa"
                            className="p-1.5 rounded-lg border border-transparent hover:border-rose-500/30 hover:bg-rose-500/10 text-text-muted hover:text-rose-400 transition-all"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal de Creación */}
      <AnimatePresence>
        {showCreateModal && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-[999]">
            <motion.div 
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-[#15151a] border border-white/10 rounded-2xl p-6 w-full max-w-md shadow-2xl relative"
            >
              <button onClick={() => setShowCreateModal(false)} className="absolute top-4 right-4 text-text-muted hover:text-white p-1 bg-white/5 rounded-lg transition-colors">
                <X className="w-5 h-5" />
              </button>
              
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2.5 bg-rose-500/20 rounded-xl text-rose-500">
                  <Building2 className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold">Alta de Prospecto</h3>
              </div>
              
              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-text-muted uppercase tracking-widest mb-2">Nombre Comercial o Razón Social <span className="text-rose-500">*</span></label>
                  <input 
                    type="text"
                    required
                    value={newEmpresa.nombre}
                    onChange={e => setNewEmpresa({...newEmpresa, nombre: e.target.value})}
                    placeholder="Ej. Grupo Financiero Baga"
                    className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-rose-500/50"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-text-muted uppercase tracking-widest mb-2">RFC (Opcional)</label>
                  <input 
                    type="text"
                    value={newEmpresa.rfc}
                    onChange={e => setNewEmpresa({...newEmpresa, rfc: e.target.value.toUpperCase()})}
                    placeholder="XXXX000000XXX"
                    className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-sm font-mono focus:outline-none focus:border-rose-500/50 uppercase"
                  />
                </div>
                
                <div className="pt-4 flex gap-3">
                  <button type="button" onClick={() => setShowCreateModal(false)} className="flex-1 bg-white/5 hover:bg-white/10 text-white py-3 rounded-xl font-bold transition-colors">
                    Cancelar
                  </button>
                  <button type="submit" disabled={creating || !newEmpresa.nombre} className="flex-1 bg-rose-600 hover:bg-rose-500 text-white py-3 rounded-xl font-bold shadow-[0_0_15px_rgba(225,29,72,0.3)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2">
                    {creating ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Crear'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}
