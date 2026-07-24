-- Migración: Añadir columnas de Alerta de Fraude a la tabla de documentos
-- Ejecutar en Supabase SQL Editor

ALTER TABLE documentos_expediente 
ADD COLUMN IF NOT EXISTS alerta_fraude BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS motivo_fraude TEXT;
