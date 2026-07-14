### Desarrollo del Módulo AutoCAF (Consolidado de Análisis Financiero)

Dentro de la arquitectura del backend, uno de los submódulos más complejos implementados fue el **AutoCAF**. El Consolidado de Análisis Financiero (CAF) es una herramienta analítica obligatoria en la que los analistas de crédito deben vaciar, homologar y comparar históricamente los estados financieros de una empresa (usualmente de 2 a 4 años consecutivos) para evaluar su viabilidad crediticia.

Originalmente, este proceso requería que el analista abriera múltiples archivos PDF, extrajera manualmente las cuentas contables de cada año y las transcribiera en una plantilla maestra de Excel, cuidando de no alterar las fórmulas preestablecidas. Para automatizar este flujo, se diseñó el módulo AutoCAF, estructurado en tres fases principales dentro de la API de FastAPI: **Gestión de Estado, Extracción Multianual y Ensamblaje Dinámico de Excel**.

#### 1. Gestión de Estado y Recuperación en Memoria (`routes.py`)
A diferencia de procesos transaccionales simples, la generación de un CAF requiere que el usuario cargue múltiples documentos de diferentes periodos antes de consolidarlos. Para gestionar esto, se implementó un enrutador dedicado (`caf_router`) que mantiene un diccionario en memoria (`caf_docs`) donde se registran los metadatos y el estado de procesamiento de cada PDF cargado.

Durante las pruebas, se detectó que las recargas del servidor (reinicios por despliegue o fallos) provocaban la pérdida de este estado en memoria, dejando archivos "huérfanos" en el disco duro. Para mitigar este problema, se diseñó una función de recuperación automática (`_restore_caf_docs`). Al inicializar la aplicación, el servidor escanea el directorio de almacenamiento temporal (`uploads/caf_v2/`), lee los metadatos almacenados en archivos JSON complementarios y reconstruye dinámicamente el estado en memoria. Esto garantiza la persistencia operativa sin saturar la base de datos principal con archivos que aún se encuentran en fase de borrador.

#### 2. Pipeline de Extracción y Homologación Histórica (`llm_processor.py` y `extractor.py`)
Una vez que los documentos se encuentran en el servidor, el analista detona el proceso de análisis. El backend orquesta un flujo de extracción diferenciando si se trata de estados financieros internos o *Estados Financieros Dictaminados* (auditados), ya que estos últimos poseen estructuras mucho más complejas.

El motor extrae el texto crudo utilizando la biblioteca `PyMuPDF` y lo transfiere al módulo de procesamiento semántico. El reto principal en el CAF no es extraer un solo valor, sino **construir una serie de tiempo**. Para lograrlo, el prompt del LLM fue diseñado con reglas específicas de consolidación:
* **Extracción Multianual:** Se programó al modelo para detectar y extraer simultáneamente todos los años presentes en el documento, utilizando el año real de 4 dígitos como llave principal dentro del JSON (ej. `"2023": {...}, "2024": {...}`).
* **Agrupación Contable (NIF):** Se implementó una normalización estricta donde cuentas como "Efectivo y Equivalentes" se mapean obligatoriamente a las llaves maestras requeridas por la plantilla (ej. `caja_y_bancos`).
* **Reglas de Cuadre:** El modelo ejecuta internamente la ecuación contable, asegurando que la suma del Pasivo y el Capital coincida con el Activo Total de cada año evaluado, garantizando que el JSON devuelto al backend sea matemáticamente íntegro.

#### 3. Ensamblaje Dinámico del Excel (`excel_builder.py`)
La etapa final y de mayor valor arquitectónico del AutoCAF es la generación del documento entregable. En lugar de generar un archivo CSV plano o un Excel desde cero perdiendo el formato corporativo, se optó por un enfoque de **inyección de datos sobre plantillas**.

Utilizando la biblioteca `openpyxl`, el backend carga en memoria una plantilla preexistente del CAF (.xlsx) que ya contiene los colores institucionales, logotipos y fórmulas financieras complejas (como el cálculo de razones financieras, EBITDA y flujos de efectivo). El algoritmo de ensamblaje (`build_caf_excel`) ejecuta el siguiente flujo:

1. **Fusión de JSONs (Batch Processing):** Si el usuario seleccionó múltiples PDFs (ej. un PDF para 2022 y otro para 2023), el backend fusiona los objetos JSON extraídos en una sola estructura unificada, resolviendo posibles solapamientos mediante un sistema de "sobrescritura de años" (Year Overrides).
2. **Mapeo de Coordenadas:** El código recorre las hojas del libro de Excel ("Balance General", "Estado de Resultados") e identifica dinámicamente las columnas correspondientes a cada año.
3. **Inyección Segura:** Posteriormente, itera sobre las llaves del JSON (ej. `clientes`, `inventarios`, `proveedores`) y busca la fila correspondiente en la plantilla. Una vez localizada la intersección (Fila del Concepto + Columna del Año), inyecta el valor numérico (flotante).
4. **Preservación de Fórmulas:** El sistema está diseñado para escribir únicamente sobre celdas de entrada (Input), respetando estrictamente las celdas que contienen fórmulas calculadas.

Al finalizar, el libro de Excel se guarda temporalmente en un *buffer* de bytes (RAM) y se retorna directamente al cliente a través de una respuesta HTTP compatible (`StreamingResponse` o descarga de archivo). Esta arquitectura permite consolidar expedientes financieros complejos en segundos, eliminando errores de transcripción y entregando al área de crédito un archivo Excel completamente funcional, cuadrado y listo para el análisis de riesgo.
