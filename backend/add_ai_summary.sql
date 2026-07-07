-- Ejecuta esto en el SQL Editor de tu panel de Supabase

-- 1. Añadir la columna ai_summary a la tabla principal
ALTER TABLE documentos_expediente
ADD COLUMN IF NOT EXISTS ai_summary JSONB;

-- 2. Añadir la columna a la tabla de representantes (opcional, por si en el futuro se escanean INEs, etc.)
ALTER TABLE documentos_representante
ADD COLUMN IF NOT EXISTS ai_summary JSONB;
