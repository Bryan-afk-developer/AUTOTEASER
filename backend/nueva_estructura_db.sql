-- ==========================================
-- SCRIPT DE MIGRACIÓN: NUEVA ESTRUCTURA DB
-- ==========================================

-- 1. Crear ENUMs para organizar los tipos y categorías
CREATE TYPE tipo_entidad_enum AS ENUM ('prospecto', 'aval', 'empresa_grupo', 'aval_fisico');
CREATE TYPE categoria_documento_enum AS ENUM ('legal', 'financiero', 'bancario', 'identificacion', 'buro', 'otro');

-- 2. Tabla Principal: EMPRESAS (Maneja prospectos, avales y grupo de forma unificada)
CREATE TABLE IF NOT EXISTS empresas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre TEXT NOT NULL,
    rfc TEXT,
    tipo_entidad tipo_entidad_enum NOT NULL DEFAULT 'prospecto',
    
    -- Si es aval o grupo, apunta al id del prospecto principal. Si es el prospecto, va null.
    prospecto_padre_id UUID REFERENCES empresas(id) ON DELETE CASCADE,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Tabla: CUENTAS BANCARIAS (Para organizar estados de cuenta por banco)
CREATE TABLE IF NOT EXISTS cuentas_bancarias (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    banco TEXT NOT NULL,
    numero_cuenta TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Tabla Unificada: DOCUMENTOS (Bóveda central para archivos infinitos)
CREATE TABLE IF NOT EXISTS documentos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    
    categoria categoria_documento_enum NOT NULL DEFAULT 'otro',
    tipo_documento TEXT NOT NULL, -- ej. "Acta Constitutiva", "INE", "Balance General"
    
    nombre_archivo TEXT NOT NULL,
    storage_url TEXT, -- Ruta donde se guarda en el bucket de Supabase
    
    -- Solo se usa si es un estado de cuenta vinculado a un banco específico
    cuenta_bancaria_id UUID REFERENCES cuentas_bancarias(id) ON DELETE SET NULL,
    
    descargado BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- ==========================================
-- POLÍTICAS DE SEGURIDAD (RLS - Supabase)
-- ==========================================

-- Habilitar seguridad a nivel de fila (obligatorio en Supabase)
ALTER TABLE empresas ENABLE ROW LEVEL SECURITY;
ALTER TABLE cuentas_bancarias ENABLE ROW LEVEL SECURITY;
ALTER TABLE documentos ENABLE ROW LEVEL SECURITY;

-- Políticas básicas (Permitir lectura y escritura solo a usuarios logueados en tu app)
CREATE POLICY "Activar TODO para usuarios autenticados en empresas" 
ON empresas FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Activar TODO para usuarios autenticados en cuentas" 
ON cuentas_bancarias FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Activar TODO para usuarios autenticados en documentos" 
ON documentos FOR ALL USING (auth.role() = 'authenticated');
