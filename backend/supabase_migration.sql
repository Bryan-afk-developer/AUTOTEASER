-- Migración para soportar Carpetas de Bancos (Múltiples cuentas bancarias)

-- 1. Crear la tabla de cuentas bancarias
CREATE TABLE IF NOT EXISTS cuentas_bancarias (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    nombre_banco TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(empresa_id, nombre_banco)
);

-- Habilitar RLS en la nueva tabla (opcional, dependiendo de tus políticas)
ALTER TABLE cuentas_bancarias ENABLE ROW LEVEL SECURITY;

-- Crear políticas para cuentas_bancarias (ajusta según tus roles)
CREATE POLICY "Enable read for authenticated users" ON cuentas_bancarias FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Enable insert for authenticated users" ON cuentas_bancarias FOR INSERT WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Enable update for authenticated users" ON cuentas_bancarias FOR UPDATE USING (auth.role() = 'authenticated');
CREATE POLICY "Enable delete for authenticated users" ON cuentas_bancarias FOR DELETE USING (auth.role() = 'authenticated');

-- 2. Modificar la tabla documentos_expediente para relacionar el documento con el banco (opcionalmente)
ALTER TABLE documentos_expediente
ADD COLUMN IF NOT EXISTS cuenta_bancaria_id UUID REFERENCES cuentas_bancarias(id) ON DELETE CASCADE;

-- 3. Modificar la tabla documentos_expediente para guardar el nombre de la carpeta de manera denormalizada (más fácil para consultas)
ALTER TABLE documentos_expediente
ADD COLUMN IF NOT EXISTS nombre_carpeta TEXT;

-- 4. Añadir columnas de control de descarga
ALTER TABLE documentos_expediente
ADD COLUMN IF NOT EXISTS descargado BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS descargado_en TIMESTAMPTZ;

ALTER TABLE documentos_representante
ADD COLUMN IF NOT EXISTS descargado BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS descargado_en TIMESTAMPTZ;
