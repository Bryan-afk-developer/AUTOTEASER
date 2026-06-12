# Registro de Cambios - Módulo CAF (AutoTeaser)
**Fecha**: 11 de Junio de 2026
**Rama**: `NEW_CAF`

Este documento detalla exhaustivamente todos los cambios arquitectónicos y lógicos implementados en el módulo CAF (Consolidado de Análisis Financiero) para resolver los problemas de memoria volátil y la desestructuración del OCR en el armado de Excel.

---

## 1. Persistencia de Sesión y Manejo de Errores 404 (`backend/app/CAF/routes.py`)

**Problema Original**: 
Cada vez que el backend se recargaba (por cambios de código o reinicio del servidor), el diccionario en memoria `caf_docs` se borraba. Esto causaba que la interfaz de usuario perdiera el rastro de los documentos en proceso y arrojara errores `404 Not Found` en la consola al intentar procesar o descargar los Excel.

**Solución Implementada**:
*   **Recuperación Automática (`_restore_caf_docs`)**: Se implementó una función que se ejecuta al inicio de la aplicación. Esta escanea la carpeta `uploads/caf_v2/` en busca de archivos PDF huérfanos y los vuelve a cargar en la memoria RAM automáticamente.
*   **Generación de Miniaturas en Frío**: Al restaurar los PDFs, el sistema utiliza `fitz` (PyMuPDF) para volver a generar sobre la marcha las miniaturas de las páginas en base64, restaurando completamente el estado de la UI como si el archivo se acabara de subir.
*   **Metadatos de Archivo Original (Sidecar JSON)**: Se añadió lógica en el endpoint de subida (`/upload`) para que, al guardar el PDF con su identificador UUID, guarde paralelamente un archivo `[uuid].json` que contiene el nombre original del archivo (ej. `EEFF - Empresa - 2026.pdf`). Durante la restauración, este JSON se lee para devolverle su nombre real y evitar que el documento quede nombrado como un hash.

---

## 2. Reingeniería Completa del Ensamblador de Excel (`backend/app/CAF/excel_builder.py`)

**Problema Original**: 
La herramienta intentaba hacer un "vaciado crudo" concatenando las celdas directamente o inyectando fragmentos completos de texto por fila. Documentos con doble columna (como un Balance General donde el Activo está a la izquierda y el Pasivo a la derecha) eran leídos por Google Document AI como una sola cadena de texto gigante (ej. `BANCOS $ 6,098,985 PROVEEDORES $ 3,232,186`), lo que hacía que el Excel fuera ilegible y desordenado.

**Solución Implementada**:
El archivo fue completamente reescrito desde cero para usar una estructura semántica e inteligente de partición de filas.

### A. Tokenizador de Conceptos (Manejo de Doble Columna)
*   En lugar de escribir la celda tal y como viene, el sistema ahora toma el texto extraído y lo rompe usando saltos de línea (`\n`).
*   Se desarrolló un analizador semántico que itera sobre los tokens de izquierda a derecha. Acumula las palabras de texto y, cuando detecta una cifra numérica (validado por la función `_is_numeric()`), empareja todo el texto anterior como el "Concepto" y el número como el "Monto".
*   Esto permite que una sola fila defectuosa del PDF que trae información de 4 columnas, se descomponga internamente y emita **múltiples filas perfectas** en el archivo Excel (una para cada cuenta encontrada).
*   Se agregó manejo especial para celdas vacías representadas con guiones (`-`), permitiendo que el analizador no las ignore y las trate como un valor de 0 válido.
*   Filtro de "ruido" OCR integrado para descartar capturas basura (como "$", "EA", "SSS", "69").

### B. Rediseño del Layout del Excel Generado
Se rediseñó por completo el acomodo de las columnas para tener una experiencia de usuario amigable y orientada a la revisión:

**Sección Izquierda (Datos Crudos):**
*   **Columna A (Cuenta Extraída)**: El nombre del concepto limpio.
*   **Columna B (Monto Extraído)**: El número asociado.
*   **Columna C (Página)**: Referencia exacta a la página del PDF.
*   **Columna D (Evidencia Visual)**: Imagen recortada en alta resolución (`300 DPI` escalados mediante PyMuPDF y optimizados con PIL) del renglón original donde se encontró ese dato específico.
*   **Columna E (Input / Ajuste)**: Celda amarilla (estilo `FFF2CC`) totalmente en blanco, proporcionando espacio para notas o correcciones manuales del usuario.

**Sección Derecha (Plantilla Mapeada):**
*   **Columnas G y H**: Se mantuvieron separadas visualmente del volcado crudo.
*   Aquí se imprimen exclusivamente los conceptos que están definidos en el archivo estructurado `mapa.json`.
*   **Inyección de Secciones**: Se agregaron bloques con estilos dinámicos de colores (`_get_section()`) para separar visualmente "ACTIVO CIRCULANTE" (Verde Oscuro), "PASIVO" (Rojo), "CAPITAL CONTABLE" (Morado), etc., mejorando drásticamente la lectura.
*   **Enlace de Fórmulas Dinámico**: Las celdas de importe en la columna H se vinculan con fórmulas (ej. `='2026'!H10`) directamente hacia las hojas maestras del modelo (`Balance` y `Edo de resultados`), permitiendo que cualquier valor ingresado fluya a la plantilla de Brightec de manera instantánea.

---

## 3. Pruebas y Validación

*   Se creó un script de validación masiva (`process_all_pdfs.py`) que simuló de manera asíncrona la API del frontend en el backend.
*   Se validó la generación con éxito de 5 PDFs distintos (mezcla de PDF Nativos y PDF Escaneados interpretados por Document AI).
*   Se validó el soporte para archivos gigantescos, soportando hojas de Excel resultantes de hasta 72MB debido a las evidencias visuales de alta densidad, las cuales son renderizadas y optimizadas automáticamente con compresión LANCZOS antes de empaquetarse en el xlsx.
