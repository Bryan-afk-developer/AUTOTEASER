-- Migración: Módulo de Accionistas
-- Ejecutar en Supabase SQL Editor

-- 1. Tabla de accionistas por empresa
CREATE TABLE IF NOT EXISTS accionistas (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id  UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    nombre      TEXT,                   -- Opcional, se puede dejar vacío
    orden       INTEGER NOT NULL,       -- Para la numeración 1.1, 1.2 en Drive
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Tabla de documentos por accionista (igual estructura que documentos_representante)
CREATE TABLE IF NOT EXISTS documentos_accionista (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    accionista_id   UUID NOT NULL REFERENCES accionistas(id) ON DELETE CASCADE,
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    tipo_documento  TEXT NOT NULL,
    nombre_archivo  TEXT,
    storage_path    TEXT,
    estado          TEXT DEFAULT 'pendiente',
    subido_en       TIMESTAMPTZ DEFAULT NOW(),
    descargado      BOOLEAN DEFAULT FALSE,
    descargado_en   TIMESTAMPTZ
);

-- 3. RLS (permisivo para desarrollo)
ALTER TABLE accionistas ENABLE ROW LEVEL SECURITY;
ALTER TABLE documentos_accionista ENABLE ROW LEVEL SECURITY;

CREATE POLICY "accionistas_all" ON accionistas FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "docs_accionista_all" ON documentos_accionista FOR ALL USING (true) WITH CHECK (true);
