### 4.2.2 Módulo de Buró de Crédito

Uno de los componentes más críticos dentro de la evaluación de riesgo corporativo, y que forma parte integral de las herramientas del Expediente Rojo, es el análisis del Buró de Crédito. Previo a la implementación de la plataforma, el flujo de trabajo del analista consistía en recibir reportes en formato PDF que, dependiendo de la antigüedad de la empresa o de los avales, podían superar las 20 páginas de texto continuo. El analista debía realizar una lectura manual exhaustiva para localizar el *Score* crediticio y, posteriormente, contar e ingresar en una hoja de cálculo cada una de las cuentas activas (MOPs), clasificándolas según su comportamiento de pago.

Como resultado de la implementación, el Portal Administrativo ofrece ahora una interfaz de trabajo basada en el patrón de "Pantalla Dividida" (*Split View*). Cuando el analista selecciona un reporte de Buró, el sistema no descarga el archivo al equipo local; en su lugar, renderiza el documento original en el panel izquierdo utilizando un visor PDF nativo del navegador. Simultáneamente, en el panel derecho se despliega un componente lateral interactivo (*Slideover*) que expone la información procesada por la Inteligencia Artificial.

En esta vista de resultados, el sistema entrega al analista un dictamen estructurado que incluye:
* **Score Crediticio:** Extraído y posicionado en la parte superior del panel para una evaluación visual inmediata.
* **Clasificación de Cuentas (MOPs):** Una tabla dinámica que agrupa todos los créditos activos encontrados en el documento. En lugar de una lista plana, el frontend presenta las cuentas categorizadas, mostrando el saldo actual de cada una y su estatus de pago (por ejemplo, MOP 01 para cuentas al corriente, MOP 02 para atrasos leves).
Esta reingeniería de la interfaz eliminó por completo el error humano en la transcripción de saldos y redujo el tiempo de procesamiento de un reporte de Buró de Crédito de aproximadamente 15 minutos a menos de 10 segundos. Una vez que el analista audita visualmente que los datos del panel derecho coinciden con el documento de la izquierda, presiona el botón de validación para integrar esta información al AutoTeaser.

*(Sugerencia: Aquí puedes insertar tu Figura 31 mostrando la pantalla dividida del Buró de Crédito con el PDF a la izquierda y la tabla de MOPs extraída a la derecha).*
**Figura 31.** Interfaz de validación del Buró de Crédito en el Portal Administrativo. Elaboración Propia (2026).


### 4.2.3 Módulo de Situación Fiscal (SAT)

El cumplimiento fiscal es un requisito restrictivo (no negociable) para el otorgamiento de cualquier línea de crédito. Dentro de los documentos recabados en el Expediente Rojo, la Constancia de Situación Fiscal (CSF) y la Opinión de Cumplimiento representan el primer filtro de viabilidad.

El resultado entregado por la plataforma en este módulo fue la automatización de la lectura y validación de documentos oficiales emitidos por el Servicio de Administración Tributaria (SAT). Al igual que en el módulo de Buró, la interfaz administrativa despliega el PDF original y arroja el dictamen de validación en tiempo real. 

Para el caso de la Opinión de Cumplimiento, la extracción resulta binaria pero vital: el sistema identifica de inmediato si el estatus del contribuyente es "Positivo" o "Negativo". En el caso de la CSF, el módulo extrae automáticamente el Régimen Fiscal, el Código Postal del domicilio fiscal y la fecha de inicio de operaciones. Una validación adicional implementada en el sistema contrasta el Registro Federal de Contribuyentes (RFC) extraído del documento contra el RFC registrado en el perfil de la empresa en la base de datos. Si existe una discrepancia, la interfaz alerta visualmente al analista, previniendo el riesgo operativo de aprobar una solicitud basada en documentos pertenecientes a una entidad legal distinta.


### 4.2.4 Módulo Legal (Actas Constitutivas y Poderes)

El procesamiento de documentos legales representó un reto particular debido a su volumen y falta de estructura tabular. Un Acta Constitutiva o una escritura de Otorgamiento de Poderes notariada puede superar fácilmente las 100 páginas de texto continuo, lo que exigía horas de lectura por parte del área jurídica o de crédito.

El resultado final obtenido en este módulo es un asistente de lectura focalizada. El sistema procesa el documento notarial completo y presenta al analista un resumen estructurado con los datos esenciales de la constitución de la empresa (fecha de constitución, nombre del notario, número de instrumento y folio mercantil). De manera crítica, la interfaz identifica y enlista al **Representante Legal** vigente y clasifica las facultades que le fueron otorgadas (Pleitos y Cobranzas, Actos de Administración, Actos de Dominio, Otorgamiento de Títulos de Crédito). 

Este resultado transforma la experiencia del usuario, permitiendo que el analista pueda emitir un dictamen sobre la capacidad legal del cliente para firmar un contrato de crédito mediante una validación de pantalla que toma segundos, en lugar de realizar una lectura profunda de decenas de páginas.

---

### 4.3 Resultados del Módulo AutoCAF (Consolidado de Análisis Financiero)

A la par de la automatización del AutoTeaser, el desarrollo de mayor impacto operativo para la institución fue el módulo AutoCAF. Esta herramienta se materializó como un entorno de trabajo interactivo dentro del Portal Administrativo, diseñado para resolver el problema de la consolidación histórica de estados financieros de múltiples ejercicios fiscales.

**Fase 1: Interfaz de Carga y Selección de Regiones (Herramienta de Recortes)**
El flujo operativo inicia en un panel especializado (`CafDashboard`) donde el analista cuenta con una zona interactiva para arrastrar y soltar (Drag & Drop) los archivos PDF correspondientes a los estados financieros de diferentes años (por ejemplo, 2022, 2023 y 2024). 

Dado que los estados financieros auditados suelen incluir dictámenes externos y extensas páginas de notas metodológicas que no aportan valores numéricos al análisis, se implementó una interfaz de selección visual. El sistema despliega miniaturas de todas las páginas cargadas, permitiendo al analista hacer clic exclusivamente sobre las hojas que contienen el Balance General y el Estado de Resultados.

La innovación principal en esta fase fue la incorporación de un Selector de Regiones (*Region Selector*). Esta herramienta de "Recortes" permite al usuario trazar cajas delimitadoras (*Bounding Boxes*) directamente sobre la imagen del documento en el navegador. Al dibujar estos recuadros sobre las tablas financieras, el usuario le indica al motor de extracción que debe ignorar por completo el resto de la página (como firmas de auditores, encabezados decorativos o pies de página). Esto garantizó que el motor de Inteligencia Artificial recibiera texto limpio, eliminando el "ruido" que previamente causaba errores en la extracción.

**Fase 2: Procesamiento Semántico Multianual**
Al confirmar la selección de regiones y presionar el botón de "Analizar", el sistema ejecuta el procesamiento en segundo plano. La interfaz bloquea nuevas interacciones y despliega indicadores visuales de progreso. El resultado operativo de esta fase es que el sistema lee el contenido de los recortes, lo interpreta semánticamente y homologa cuentas contables dispares bajo el estándar de las Normas de Información Financiera (NIF). Toda la información de los diferentes ejercicios fiscales es consolidada por el backend en una única estructura de datos, aplicando reglas internas de cuadre matemático para asegurar que, en cada año extraído, la suma del Pasivo y el Capital sea exactamente igual al Activo Total.

**Fase 3: Exportación a la Plantilla Institucional (Excel)**
El producto final del flujo de AutoCAF es la exportación del consolidado. Una vez que el sistema finaliza la extracción, el analista puede auditar las cifras clave proyectadas en la pantalla. Al validar la información, el usuario acciona la descarga del documento. 

El resultado entregado por el navegador es un archivo en formato `.xlsx` que conserva intactos los logotipos, la tipografía corporativa y, sobre todo, las fórmulas financieras complejas de la institución (cálculo de liquidez, apalancamiento, EBITDA, flujos de efectivo). El sistema inyecta las cantidades extraídas exactamente en las celdas de captura correspondientes a cada año fiscal. 
Una actividad técnica que originalmente obligaba al analista a transcribir datos celda por celda durante horas, cuidando de no romper las fórmulas de Excel, fue sustituida por un flujo visual de carga documental, recorte de regiones y generación automatizada que se completa en pocos minutos.

*(Sugerencia: Aquí puedes insertar tu Figura 32 mostrando el "Region Selector" dibujando un recorte sobre el PDF y, a un lado, el Excel final generado).*
**Figura 32.** Herramienta interactiva de selección de regiones (recortes) y generación del entregable en el módulo AutoCAF. Elaboración Propia (2026).
