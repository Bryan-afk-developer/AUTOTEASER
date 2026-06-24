# 📕 Documentación de Módulo: Expediente Rojo (Gestión y Automatización Documental)

El **Expediente Rojo** es el núcleo crítico de recopilación de información legal, fiscal y financiera dentro de la plataforma AutoTeaser. Representa el conjunto de documentos obligatorios que una empresa o individuo debe presentar para que la **empresa de gestión financiera** pueda realizar un análisis de crédito, inversión o auditoría corporativa.

Este módulo está diseñado para eliminar la fricción típica del "ida y vuelta" de correos electrónicos, estandarizando la recepción de documentos y aplicando una capa inicial de **automatización ligera** para agilizar la validación.

A continuación, se detalla el Expediente Rojo dividido estrictamente por módulos tecnológicos y operativos.

---

## 💻 Módulo 1: Frontend (Interfaz Web y Experiencia de Usuario)

El Frontend del Expediente Rojo se divide en dos perspectivas fundamentales, diseñadas para brindar máxima claridad y usabilidad.

### 1.1 Portal del Cliente (Flujo de Carga y Progreso)
Para el cliente, el Expediente Rojo es un **checklist interactivo y guiado**, diseñado para reducir la ansiedad del proceso de integración (onboarding).

- **Dashboard de Progreso:** Al entrar, el cliente visualiza un medidor general (ej. "75% Completado"). Esto se calcula en base a los documentos obligatorios vs. los documentos en estado `APROBADO`.
- **Estructura por Categorías (Acordeones):** Los requerimientos no se presentan como una lista plana, sino categorizados lógicamente:
  - **📁 Legal:** Acta Constitutiva, Poderes Notariales, Identificaciones (INE).
  - **📁 Fiscal:** Constancia de Situación Fiscal (CSF), Opinión de Cumplimiento (32-D), Declaraciones Anuales.
  - **📁 Bancario:** Sección dinámica que agrupa los estados de cuenta por banco y terminación de cuenta.
- **Sistema de Semáforos (Estados Visuales):** Cada documento tiene un indicador en tiempo real:
  - ⚪ **Faltante:** El sistema lo requiere, pero no se ha subido.
  - 🟡 **Pendiente de Revisión:** El archivo fue cargado y está a la espera de la validación del Admin.
  - 🟢 **Aprobado:** El analista financiero ha dado el visto bueno.
  - 🔴 **Rechazado:** El documento es inválido (ej. borroso, incompleto). El UI muestra un globo de alerta interactivo con el comentario del Admin para que el cliente lo corrija inmediatamente.

### 1.2 Portal del Administrador (Consola de Validación)
Para el analista de la empresa de gestión financiera, el portal es un **panel de control de riesgos**.

- **Tabla Maestra de Clientes:** Muestra una lista de todos los clientes activos y el porcentaje de completitud de su Expediente Rojo.
- **Visor de Documentos Integrado:** Cuando el Admin hace clic en un documento "Pendiente de Revisión", el PDF se renderiza directamente en el navegador (vía iframe o visor PDF). No hay necesidad de descargar los archivos localmente, manteniendo la seguridad de los datos.
- **Acciones Rápidas (Aprobar/Rechazar):** Junto al visor, el Admin tiene botones de acción. Si rechaza, se despliega obligatoriamente un campo de texto para detallar el motivo (feedback para el cliente).

---

## ⚙️ Módulo 2: Backend (Lógica de Negocios y API)

El Backend (FastAPI) es el cerebro que orquesta qué documentos se necesitan y cómo se procesan las reglas de negocio.

### 2.1 Generador Dinámico de Requerimientos
No todas las empresas necesitan el mismo Expediente Rojo. El Backend calcula los "slots" faltantes en tiempo real:
- **Cálculo de Periodos Bancarios:** Si la política dicta "Últimos 6 meses", el backend lee la fecha actual e inyecta dinámicamente en el perfil del cliente los 6 meses exactos requeridos.
- **Cálculo Fiscal:** Determina si se requiere la Declaración Anual del año anterior (dependiendo del mes en curso y la fecha límite del SAT).

### 2.2 Endpoints de Subida y Gestión de Estados
- **Endpoint `POST /upload/documento`:** Recibe el archivo, valida el tipo MIME (solo PDFs o imágenes permitidas) y lo enruta al Storage de Supabase. Automáticamente actualiza el registro en PostgreSQL a estado `PENDIENTE`.
- **Endpoint `PUT /review/documento`:** Utilizado por el Admin. Modifica el estado en PostgreSQL a `APROBADO` o `RECHAZADO`. Si es rechazado, dispara una notificación lógica para el cliente.

---

## 🗄️ Módulo 3: Base de Datos y Almacenamiento (Supabase)

La persistencia del Expediente Rojo requiere seguridad estricta y trazabilidad para auditorías.

### 3.1 Modelo Relacional (PostgreSQL)
Las tablas principales que soportan este módulo son:
- `empresas` / `usuarios`: Dueños del expediente.
- `documentos_expediente`: Tabla transaccional. Registra: `id_empresa`, `categoria`, `tipo_documento` (ej. 'Acta Constitutiva'), `estado` (enum), `comentario_rechazo`, `url_archivo`, y timestamps (`created_at`, `updated_at`).

### 3.2 Almacenamiento Seguro (Supabase Storage)
- **Bucket Privado:** Los archivos físicos (PDFs) se guardan en un bucket llamado `expedientes_bucket`.
- **Row Level Security (RLS):** Existen políticas de seguridad estrictas:
  - El **Cliente** solo puede hacer *SELECT*, *INSERT* y *UPDATE* (para re-subir) sobre las filas de su propia `id_empresa`.
  - El **Admin** puede acceder a todas las filas, pero se audita quién realizó la acción de aprobación/rechazo.

---

## 🤖 Módulo 4: Automatización Ligera y Extracción IA (AutoCAF)

El valor disruptivo del Expediente Rojo es que no es un simple "DropBox". En el momento de la subida, interviene una capa de **automatización ligera** (mediante OCR y llamadas iniciales a la API de Google Gemini) que pre-procesa el documento antes de que el Admin lo vea.

### 4.1 Extracción de Identidad (INE y KYC)
Cuando un cliente sube una Identificación Oficial en la sección de "Representante Legal":
- **Lectura Automática:** El sistema extrae el **Nombre Completo**, la **Clave de Elector** y la **Vigencia**.
- **Beneficio Operativo:** El analista no tiene que transcribir datos. La interfaz le presenta el documento original a la izquierda y los datos extraídos a la derecha, requiriendo solo un clic de confirmación.

### 4.2 Validación de Comprobantes de Domicilio y Situación Fiscal
Al subir un recibo de luz (CFDI) o la Constancia de Situación Fiscal (CSF):
- **Extracción de Domicilio Estructurado:** El sistema ubica y separa la dirección en: Calle, Número, Colonia, Municipio, Estado y Código Postal.
- **Beneficio Operativo:** Permite hacer un cruce automatizado (Match) para alertar al analista si el domicilio en el recibo no coincide con el domicilio fiscal registrado.

### 4.3 Análisis de Opinión de Cumplimiento (32-D)
Este es un documento crítico que caduca rápidamente. La automatización extrae:
- **Sentido de la Resolución:** (Positiva / Negativa).
- **Fecha de Emisión:** El backend calcula si el documento tiene más de 30 días de antigüedad. Si es así, se puede auto-rechazar indicando al cliente que está vencido, sin intervención humana.
- **MOPS:** Extracción del Módulo de Opinión del Cumplimiento para detectar rápidamente créditos fiscales pendientes o problemas con el IMSS/INFONAVIT.

### 4.4 Organización Dinámica Bancaria (El cuello de botella principal)
La gestión de estados de cuenta suele ser caótica. La automatización ligera resuelve esto de la siguiente manera:
- **Detección del Banco y Número de Cuenta:** Cuando el cliente arrastra un PDF de estado de cuenta, el sistema "lee" la primera página y detecta automáticamente a qué banco pertenece (Banorte, BBVA, etc.) y los últimos 4 dígitos de la cuenta.
- **Creación de Carpetas por Cuenta:** El sistema crea virtualmente "Carpetas por Cuenta de Banco" (ej. "Banorte Terminación 5678").
- **Acomodo por Meses:** El sistema lee el periodo (ej. "Del 01 al 31 de Marzo 2023") y aloja el documento exactamente en el "slot" de Marzo 2023 de la cuenta correspondiente.
- **Beneficio Operativo:** Evita que el analista reciba un archivo llamado `scan_final_banco.pdf` y tenga que abrirlo para saber qué mes y qué cuenta es. Esta pre-organización deja la data perfecta y lista para el análisis pesado (extracción de depósitos y retiros en Excel).
