import React, { useState, useRef } from 'react';
import { X, Save, Trash2, Plus, ZoomIn, ZoomOut, Maximize } from 'lucide-react';
import { motion } from 'framer-motion';

const CONCEPT_SLOT = { label: 'Conceptos', emoji: '🟣', border: '#a855f7', bg: 'rgba(168,85,247,0.2)' };
const VALUE_COLORS = [
  { emoji: '🟢', border: '#22c55e', bg: 'rgba(34,197,94,0.2)' },
  { emoji: '🔵', border: '#3b82f6', bg: 'rgba(59,130,246,0.2)' },
  { emoji: '🟠', border: '#f97316', bg: 'rgba(249,115,22,0.2)' },
  { emoji: '🔴', border: '#ef4444', bg: 'rgba(239,68,68,0.2)' },
  { emoji: '🟡', border: '#eab308', bg: 'rgba(234,179,8,0.2)' },
  { emoji: '🟤', border: '#8b5cf6', bg: 'rgba(139,92,246,0.2)' },
];

const emptyGroup = () => ({ notaNum: '', conceptRegion: null, valueRegions: [null, null] });

export default function CustomNotaRegionSelector({ imageUrl, initialSubTables = [], onSave, onCancel }) {
  const mapInitialToState = (initial) => {
      if (!initial || initial.length === 0) return [emptyGroup()];
      return initial.map(t => ({
          notaNum: t.nota_num || '',
          conceptRegion: t.concept_region || null,
          // Support old format or new array format
          valueRegions: t.value_regions 
              ? t.value_regions 
              : [t.val1_region || null, t.val2_region || null]
      }));
  }

  const [subTables, setSubTables] = useState(mapInitialToState(initialSubTables));
  const [drawingTarget, setDrawingTarget] = useState(null); // { groupIdx, type: 'concept' | 'value', valIdx?: number }
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  const [currentRegion, setCurrentRegion] = useState(null);
  const [zoom, setZoom] = useState(1);
  const containerRef = useRef(null);

  const getRelativeCoords = (e) => {
    if (!containerRef.current) return { x: 0, y: 0 };
    const rect = containerRef.current.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)),
    };
  };

  const handleMouseDown = (e) => {
    if (!drawingTarget || e.target.closest('button') || e.target.closest('input')) return;
    e.preventDefault();
    const coords = getRelativeCoords(e);
    setIsDrawing(true);
    setStartPos(coords);
    setCurrentRegion({ x: coords.x, y: coords.y, w: 0, h: 0 });
  };

  const handleMouseMove = (e) => {
    if (!isDrawing) return;
    const coords = getRelativeCoords(e);
    setCurrentRegion({
      x: Math.min(startPos.x, coords.x),
      y: Math.min(startPos.y, coords.y),
      w: Math.abs(coords.x - startPos.x),
      h: Math.abs(coords.y - startPos.y),
    });
  };

  const handleMouseUp = () => {
    if (!isDrawing || !currentRegion || !drawingTarget) return;
    setIsDrawing(false);
    if (currentRegion.w > 0.02 && currentRegion.h > 0.02) {
      const { groupIdx, type, valIdx } = drawingTarget;
      setSubTables(prev => prev.map((t, i) => {
        if (i !== groupIdx) return t;
        if (type === 'concept') return { ...t, conceptRegion: { ...currentRegion } };
        
        const newVals = [...t.valueRegions];
        newVals[valIdx] = { ...currentRegion };
        return { ...t, valueRegions: newVals };
      }));
    }
    setCurrentRegion(null);
    setDrawingTarget(null);
  };

  const addGroup = () => setSubTables(prev => [...prev, emptyGroup()]);
  const removeGroup = (idx) => setSubTables(prev => prev.filter((_, i) => i !== idx));
  const updateNotaNum = (idx, val) => setSubTables(prev => prev.map((t, i) => i === idx ? { ...t, notaNum: val } : t));

  const addValueRegion = (idx) => setSubTables(prev => prev.map((t, i) => i === idx ? { ...t, valueRegions: [...t.valueRegions, null] } : t));
  
  const clearConcept = (groupIdx) => setSubTables(prev => prev.map((t, i) => i === groupIdx ? { ...t, conceptRegion: null } : t));
  const clearValue = (groupIdx, valIdx) => setSubTables(prev => prev.map((t, i) => {
      if (i !== groupIdx) return t;
      const newVals = [...t.valueRegions];
      newVals[valIdx] = null;
      return { ...t, valueRegions: newVals };
  }));
  const removeValueColumn = (groupIdx, valIdx) => setSubTables(prev => prev.map((t, i) => {
      if (i !== groupIdx) return t;
      const newVals = t.valueRegions.filter((_, j) => j !== valIdx);
      return { ...t, valueRegions: newVals };
  }));

  const isGroupComplete = (g) => g.notaNum.trim() && g.conceptRegion && g.valueRegions.some(v => v !== null);
  const isValid = subTables.length > 0 && subTables.every(isGroupComplete);
  const completedCount = subTables.filter(isGroupComplete).length;

  const handleSave = () => {
    onSave({
      type: 'notas_custom',
      sub_tables: subTables.map(t => ({
        nota_num: t.notaNum.trim(),
        concept_region: t.conceptRegion,
        value_regions: t.valueRegions.filter(v => v !== null),
      })),
    });
  };

  const getActiveColorInfo = () => {
      if (!drawingTarget) return null;
      if (drawingTarget.type === 'concept') return CONCEPT_SLOT;
      return VALUE_COLORS[drawingTarget.valIdx % VALUE_COLORS.length];
  }
  const activeSlotColor = getActiveColorInfo();

  return (
    <div className="fixed inset-0 bg-black/80 z-[100] flex items-center justify-center p-4 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-surface border border-border rounded-xl shadow-2xl flex flex-col w-full max-w-6xl h-[95vh] overflow-hidden"
      >
        <div className="flex items-center justify-between p-4 border-b border-border bg-card shrink-0">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              📊 Notas Personalizadas Multi-columna
              {drawingTarget && (
                <span
                  style={{ backgroundColor: activeSlotColor?.border }}
                  className="text-xs font-semibold px-2 py-0.5 rounded-full text-white animate-pulse"
                >
                  Dibujando {drawingTarget.type === 'concept' ? 'Conceptos' : `Valor ${drawingTarget.valIdx + 1}`} → Tabla {drawingTarget.groupIdx + 1}
                </span>
              )}
            </h2>
            <p className="text-sm text-text-muted mt-0.5">
              Dibuja los Conceptos y N columnas de valores separadas. Cada valor se emparejará en una fila independiente.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 bg-black/20 rounded-lg p-1 mr-2">
              <button onClick={() => setZoom(z => Math.max(0.5, z - 0.25))} className="p-1.5 hover:bg-white/10 rounded-md text-text-muted hover:text-white transition-colors"><ZoomOut className="w-4 h-4" /></button>
              <span className="text-xs font-mono w-12 text-center text-white/80">{Math.round(zoom * 100)}%</span>
              <button onClick={() => setZoom(z => Math.min(3, z + 0.25))} className="p-1.5 hover:bg-white/10 rounded-md text-text-muted hover:text-white transition-colors"><ZoomIn className="w-4 h-4" /></button>
              <button onClick={() => setZoom(1)} className="p-1.5 hover:bg-white/10 rounded-md text-text-muted hover:text-white transition-colors ml-1 border-l border-white/10 pl-2"><Maximize className="w-4 h-4" /></button>
            </div>
            <button onClick={onCancel} className="p-2 hover:bg-white/10 rounded-lg text-text-muted hover:text-white transition-colors"><X className="w-5 h-5" /></button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden min-h-0">
          {/* Left Panel */}
          <div className="w-80 flex-shrink-0 border-r border-border bg-card overflow-y-auto custom-scrollbar p-3 flex flex-col gap-3">
            <div className="text-[10px] text-text-muted font-semibold uppercase tracking-widest px-1">Tablas de Nota</div>

            {subTables.map((group, gIdx) => {
              const complete = isGroupComplete(group);
              return (
                <div
                  key={gIdx}
                  className={`bg-surface border rounded-lg p-3 space-y-2.5 transition-colors ${complete ? 'border-emerald-500/40' : 'border-border'}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white flex items-center gap-1.5">
                      Tabla {gIdx + 1}
                      {complete && <span className="text-emerald-400 text-[10px]">✓</span>}
                    </span>
                    {subTables.length > 1 && (
                      <button onClick={() => removeGroup(gIdx)} className="text-red-400 hover:text-red-300 p-1 rounded hover:bg-red-500/10 transition-colors">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  <div>
                    <label className="text-[10px] text-text-muted uppercase tracking-wider">Número de Nota</label>
                    <input
                      type="text"
                      value={group.notaNum}
                      onChange={e => updateNotaNum(gIdx, e.target.value)}
                      placeholder="ej: 9"
                      className="mt-1 w-full bg-black/30 border border-border rounded px-2 py-1.5 text-white text-sm placeholder:text-text-muted/40 focus:outline-none focus:ring-1 focus:ring-primary-500"
                      onClick={e => e.stopPropagation()}
                    />
                  </div>

                  <div className="space-y-1.5 mt-2">
                    {/* Concept Slot */}
                    <div className="flex items-center gap-1.5">
                        <button
                        onClick={() => setDrawingTarget(drawingTarget?.groupIdx === gIdx && drawingTarget?.type === 'concept' ? null : { groupIdx: gIdx, type: 'concept' })}
                        style={{
                            borderColor: (drawingTarget?.groupIdx === gIdx && drawingTarget?.type === 'concept') ? CONCEPT_SLOT.border : group.conceptRegion ? CONCEPT_SLOT.border + '80' : 'transparent',
                            backgroundColor: (drawingTarget?.groupIdx === gIdx && drawingTarget?.type === 'concept') ? CONCEPT_SLOT.bg : group.conceptRegion ? CONCEPT_SLOT.bg.replace('0.2', '0.08') : 'rgba(255,255,255,0.04)',
                        }}
                        className="flex-1 flex items-center gap-1.5 px-2 py-1.5 rounded border text-xs font-medium text-white transition-all hover:opacity-90"
                        >
                        <span>{CONCEPT_SLOT.emoji}</span>
                        <span>Conceptos</span>
                        <span className="ml-auto">
                            {(drawingTarget?.groupIdx === gIdx && drawingTarget?.type === 'concept')
                            ? <span className="text-yellow-300 animate-pulse text-[9px]">Dibujando...</span>
                            : group.conceptRegion
                                ? <span className="text-emerald-400 text-[9px] font-bold">✓ OK</span>
                                : <span className="text-text-muted/40 text-[9px]">Vacío</span>
                            }
                        </span>
                        </button>
                        {group.conceptRegion && (
                        <button onClick={() => clearConcept(gIdx)} className="p-1 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded transition-colors"><X className="w-3 h-3" /></button>
                        )}
                    </div>

                    <div className="border-t border-white/5 my-2"></div>
                    <div className="text-[10px] text-text-muted mb-1 font-semibold">COLUMNAS DE VALORES</div>

                    {/* Value Slots */}
                    {group.valueRegions.map((valRegion, vIdx) => {
                        const isActive = drawingTarget?.groupIdx === gIdx && drawingTarget?.type === 'value' && drawingTarget?.valIdx === vIdx;
                        const hasRegion = !!valRegion;
                        const slotColor = VALUE_COLORS[vIdx % VALUE_COLORS.length];
                        
                        return (
                            <div key={vIdx} className="flex items-center gap-1.5">
                                <button
                                    onClick={() => setDrawingTarget(isActive ? null : { groupIdx: gIdx, type: 'value', valIdx: vIdx })}
                                    style={{
                                        borderColor: isActive ? slotColor.border : hasRegion ? slotColor.border + '80' : 'transparent',
                                        backgroundColor: isActive ? slotColor.bg : hasRegion ? slotColor.bg.replace('0.2', '0.08') : 'rgba(255,255,255,0.04)',
                                    }}
                                    className="flex-1 flex items-center gap-1.5 px-2 py-1.5 rounded border text-xs font-medium text-white transition-all hover:opacity-90"
                                >
                                    <span>{slotColor.emoji}</span>
                                    <span>Valor {vIdx + 1}</span>
                                    <span className="ml-auto">
                                    {isActive
                                        ? <span className="text-yellow-300 animate-pulse text-[9px]">Dibujando...</span>
                                        : hasRegion
                                        ? <span className="text-emerald-400 text-[9px] font-bold">✓ OK</span>
                                        : <span className="text-text-muted/40 text-[9px]">Vacío</span>
                                    }
                                    </span>
                                </button>
                                {hasRegion ? (
                                    <button onClick={() => clearValue(gIdx, vIdx)} className="p-1 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded transition-colors"><X className="w-3 h-3" /></button>
                                ) : (
                                    <button onClick={() => removeValueColumn(gIdx, vIdx)} className="p-1 text-text-muted hover:text-white hover:bg-white/10 rounded transition-colors" title="Eliminar columna"><Trash2 className="w-3 h-3" /></button>
                                )}
                            </div>
                        )
                    })}
                    
                    <button 
                        onClick={() => addValueRegion(gIdx)}
                        className="w-full flex items-center justify-center gap-1 mt-2 py-1.5 rounded bg-white/5 hover:bg-white/10 text-white/70 hover:text-white text-[10px] font-semibold transition-colors"
                    >
                        <Plus className="w-3 h-3" /> Añadir Columna de Valor
                    </button>
                  </div>
                </div>
              );
            })}

            <button
              onClick={addGroup}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg border border-dashed border-border text-text-muted hover:text-white hover:border-primary-500 hover:bg-primary-500/5 transition-all text-xs font-semibold"
            >
              <Plus className="w-3.5 h-3.5" /> Agregar otra tabla
            </button>
          </div>

          {/* Right: Image canvas */}
          <div className="flex-1 overflow-auto bg-black/50 p-4 custom-scrollbar">
            <div className="min-h-full min-w-full flex items-center justify-center select-none">
              <div
                ref={containerRef}
                className={`relative shadow-2xl border border-white/10 flex-shrink-0 ${drawingTarget ? 'cursor-crosshair' : 'cursor-default'}`}
                style={{ height: `${zoom * 78}vh` }}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
              >
                <img src={imageUrl} alt="Document Preview" className="h-full w-auto block pointer-events-none" draggable={false} />

                {/* Drawn regions */}
                {subTables.map((group, gIdx) => {
                    const renderRegion = (region, colorInfo, title) => {
                        if (!region) return null;
                        return (
                            <div
                                key={`${gIdx}-${title}`}
                                style={{
                                    left: `${region.x * 100}%`, top: `${region.y * 100}%`,
                                    width: `${region.w * 100}%`, height: `${region.h * 100}%`,
                                    border: `2px solid ${colorInfo.border}`,
                                    backgroundColor: colorInfo.bg,
                                    position: 'absolute', pointerEvents: 'none',
                                }}
                            >
                                <div style={{ backgroundColor: colorInfo.border }} className="absolute -top-5 left-0 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-t whitespace-nowrap shadow-sm">
                                    T{gIdx + 1} {colorInfo.emoji} {title}{group.notaNum ? ` (NOTA ${group.notaNum})` : ''}
                                </div>
                            </div>
                        );
                    }

                    return (
                        <React.Fragment key={`regions-${gIdx}`}>
                            {renderRegion(group.conceptRegion, CONCEPT_SLOT, 'Conceptos')}
                            {group.valueRegions.map((vReg, vIdx) => 
                                renderRegion(vReg, VALUE_COLORS[vIdx % VALUE_COLORS.length], `Valor ${vIdx + 1}`)
                            )}
                        </React.Fragment>
                    )
                })}

                {/* Live preview while drawing */}
                {isDrawing && currentRegion && drawingTarget && activeSlotColor && (
                  <div style={{
                    left: `${currentRegion.x * 100}%`, top: `${currentRegion.y * 100}%`,
                    width: `${currentRegion.w * 100}%`, height: `${currentRegion.h * 100}%`,
                    border: `2px dashed ${activeSlotColor.border}`,
                    backgroundColor: activeSlotColor.bg,
                    position: 'absolute', pointerEvents: 'none',
                  }} />
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border bg-card flex items-center justify-between shrink-0">
          <div className="text-sm text-text-muted">
            <span className={completedCount === subTables.length ? 'text-emerald-400 font-semibold' : ''}>
              {completedCount} / {subTables.length} tablas completas
            </span>
            {!isValid && <span className="ml-2 text-amber-400/70 text-xs">— Todas necesitan número de nota + región de conceptos + al menos 1 valor</span>}
          </div>
          <div className="flex gap-3">
            <button onClick={onCancel} className="px-4 py-2 rounded-lg font-medium text-text-muted hover:text-white hover:bg-white/5 transition-colors">Cancelar</button>
            <button
              onClick={handleSave}
              disabled={!isValid}
              className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg font-semibold flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(16,185,129,0.2)]"
            >
              <Save className="w-4 h-4" /> Guardar Tablas
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
