import React, { useState, useRef, useEffect } from 'react';
import { X, Save, Trash2, Info } from 'lucide-react';
import { motion } from 'framer-motion';

export default function RegionSelector({ imageUrl, initialRegions = [], onSave, onCancel }) {
  const [regions, setRegions] = useState(initialRegions);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  const [currentRegion, setCurrentRegion] = useState(null);
  const containerRef = useRef(null);

  const getRelativeCoords = (e) => {
    if (!containerRef.current) return { x: 0, y: 0 };
    const rect = containerRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    return { 
      x: Math.max(0, Math.min(1, x)), 
      y: Math.max(0, Math.min(1, y)) 
    };
  };

  const handleMouseDown = (e) => {
    if (regions.length >= 2) return; // Allow max 2 regions for two_column
    
    // Check if clicking on an existing region's delete button
    if (e.target.closest('button')) return;
    
    e.preventDefault(); // Prevent image dragging
    const coords = getRelativeCoords(e);
    setIsDrawing(true);
    setStartPos(coords);
    setCurrentRegion({
      x: coords.x,
      y: coords.y,
      w: 0,
      h: 0
    });
  };

  const handleMouseMove = (e) => {
    if (!isDrawing || !currentRegion) return;
    
    const coords = getRelativeCoords(e);
    
    const minX = Math.min(startPos.x, coords.x);
    const minY = Math.min(startPos.y, coords.y);
    const maxX = Math.max(startPos.x, coords.x);
    const maxY = Math.max(startPos.y, coords.y);
    
    setCurrentRegion({
      x: minX,
      y: minY,
      w: maxX - minX,
      h: maxY - minY
    });
  };

  const handleMouseUp = () => {
    if (!isDrawing || !currentRegion) return;
    
    setIsDrawing(false);
    
    // Solo guardar si el tamaño es suficientemente grande (ignorar clics accidentales)
    if (currentRegion.w > 0.05 && currentRegion.h > 0.05) {
      setRegions([...regions, currentRegion]);
    }
    
    setCurrentRegion(null);
  };

  const removeRegion = (index) => {
    setRegions(regions.filter((_, i) => i !== index));
  };

  const renderRegionStyle = (region, isActive = false) => {
    return {
      left: `${region.x * 100}%`,
      top: `${region.y * 100}%`,
      width: `${region.w * 100}%`,
      height: `${region.h * 100}%`,
      border: `2px solid ${isActive ? '#3b82f6' : '#10b981'}`,
      backgroundColor: isActive ? 'rgba(59, 130, 246, 0.2)' : 'rgba(16, 185, 129, 0.2)',
      position: 'absolute',
      pointerEvents: isActive ? 'none' : 'auto'
    };
  };

  return (
    <div className="fixed inset-0 bg-black/80 z-[100] flex items-center justify-center p-4 backdrop-blur-sm">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-surface border border-border rounded-xl shadow-2xl flex flex-col w-full max-w-5xl h-[90vh] overflow-hidden"
      >
        <div className="flex items-center justify-between p-4 border-b border-border bg-card">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              Definir Columnas Manualmente
            </h2>
            <p className="text-sm text-text-muted mt-1">
              Dibuja 2 rectángulos sobre la imagen: uno para la columna izquierda (Activos) y otro para la derecha (Pasivos).
            </p>
          </div>
          <button 
            onClick={onCancel}
            className="p-2 hover:bg-white/10 rounded-lg text-text-muted hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-hidden flex bg-black/50 relative p-4">
          <div 
            className="relative mx-auto h-full flex items-center justify-center select-none"
          >
            {/* Contenedor de la imagen que mantiene la relación de aspecto */}
            <div 
              ref={containerRef}
              className="relative cursor-crosshair shadow-2xl border border-white/10 h-full w-auto"
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
            >
              <img 
                src={imageUrl} 
                alt="Document Preview" 
                className="h-full w-auto object-contain pointer-events-none"
                draggable={false}
              />

              {/* Regiones dibujadas */}
              {regions.map((region, idx) => (
                <div 
                  key={idx} 
                  style={renderRegionStyle(region)}
                  className="group transition-all"
                >
                  <div className="absolute -top-3 left-0 bg-emerald-500 text-white text-[10px] font-bold px-1.5 rounded-t">
                    Columna {idx + 1}
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeRegion(idx);
                    }}
                    className="absolute -top-3 -right-3 bg-red-500 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity shadow-lg"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))}

              {/* Región actual en dibujo */}
              {isDrawing && currentRegion && (
                <div style={renderRegionStyle(currentRegion, true)} />
              )}
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-border bg-card flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-amber-400 bg-amber-400/10 px-3 py-1.5 rounded-lg">
            <Info className="w-4 h-4" />
            <span>Regiones marcadas: {regions.length} / 2</span>
          </div>
          <div className="flex gap-3">
            <button
              onClick={onCancel}
              className="px-4 py-2 rounded-lg font-medium text-text-muted hover:text-white hover:bg-white/5 transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={() => onSave(regions)}
              disabled={regions.length !== 2}
              className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-6 py-2 rounded-lg font-semibold flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(16,185,129,0.2)]"
            >
              <Save className="w-4 h-4" />
              Guardar Regiones
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
