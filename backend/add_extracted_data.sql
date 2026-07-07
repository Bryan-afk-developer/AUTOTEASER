-- Ejecuta esto en el SQL Editor de tu panel de Supabase

-- 1. Añadir la columna extracted_data a la tabla principal
ALTER TABLE documentos_expediente
ADD COLUMN IF NOT EXISTS extracted_data JSONB;

-- 2. Añadir la columna a la tabla de representantes
ALTER TABLE documentos_representante
ADD COLUMN IF NOT EXISTS extracted_data JSONB;
