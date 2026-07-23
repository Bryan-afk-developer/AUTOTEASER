### 3.3.3 Pruebas de Integración con Casos Reales

Para validar la eficacia operativa de la plataforma, se descartó el uso de simulaciones teóricas y se optó por ejecutar pruebas de extremo a extremo utilizando un **caso real** de originación de crédito. Se procesó un expediente documental completo perteneciente a una empresa real, evaluando cómo respondía la plataforma ante condiciones y documentos habituales.

#### Prueba 1. Normalización de Cuentas Contables en Escenarios Reales

La primera prueba consistió en cargar estados financieros reales, los cuales presentaban estructuras y conceptos atípicos propios del despacho contable del cliente. Durante la prueba, se comprobó la eficacia del módulo de normalización de la plataforma. 

Al procesar los documentos, el sistema logró homologar los conceptos sin intervención humana mediante sus reglas de negocio:
* Realizó la transformación automática de cuentas de naturaleza acreedora (como la depreciación acumulada), conservando el signo contable correcto a pesar del formato del documento físico original.
* Evitó exitosamente la duplicidad de registros financieros, asignando los montos extraídos a los conceptos exactos del modelo financiero sin crear dobles conteos.

Esta prueba arrojó un conjunto de datos estandarizados que reflejaba con absoluta precisión la situación financiera de la empresa real.

![Prueba de Normalización con Expediente Real](ruta/a/imagen_normalizacion.png)
*Figura X. Extracción y normalización exitosa de un estado financiero real.*

#### Prueba 2. Integración Exacta con la Plantilla Institucional de Excel 

Una vez que el sistema normalizó la información del caso real, se probó la fase de generación del entregable final. El objetivo era verificar si la plataforma podía insertar estos datos reales directamente en la plantilla institucional sin romper el formato ni las fórmulas establecidas por la organización.

Al ejecutar la generación, el algoritmo recorrió los datos previamente normalizados y los inyectó de forma autónoma en las celdas correspondientes del libro de trabajo. Al abrir el archivo XLSX generado, se comprobó que la prueba fue un éxito: toda la estructura se mantenía completamente intacta. Microsoft Excel logró recalcular automáticamente todos los indicadores financieros, razones y flujos de efectivo basándose en la información inyectada por el sistema.

![Inserción de Datos Reales en Plantilla de Excel](ruta/a/imagen_plantilla_excel.png)
*Figura Y. Archivo Excel generado automáticamente conservando fórmulas institucionales tras la prueba.*

#### Prueba 3. Manejo de Casos Especiales y Evidencia Visual 

Como parte del expediente real utilizado para la prueba, se incluyeron dictámenes y anexos financieros que contenían estructuras tabulares sumamente complejas (con múltiples columnas y agrupaciones anidadas) que diferían considerablemente del formato esperado.

Se verificó el comportamiento del sistema ante esta anomalía. En lugar de forzar una conversión errónea, el sistema detectó la estructura compleja y activó su mecanismo de contingencia de manera exitosa: suspendió la inserción automática de valores para ese bloque y, utilizando las coordenadas espaciales del PDF, generó automáticamente un recorte de la región correspondiente para insertarlo como imagen dentro del archivo Excel. De esta manera, se demostró que frente a documentos reales atípicos, el analista conserva acceso directo a la evidencia documental sin que el sistema afecte la consistencia del modelo.

![Evidencia Visual de Casos Especiales Reales](ruta/a/imagen_recorte_evidencia.png)
*Figura Z. Inserción automática de recortes de imagen frente a estructuras atípicas en un caso real.*

#### Pruebas de Rendimiento y Tiempos de Ejecución

Para validar la eficiencia de la solución implementada, se ejecutaron pruebas de rendimiento sobre la generación final de los documentos operativos más críticos: el Consolidado de Análisis Financiero (CAF) y el Teaser Financiero. 

Durante estas pruebas, el sistema logró completar el procesamiento y ensamblaje del Teaser Financiero en cuestión de pocos minutos. Por su parte, la extracción multianual y generación automatizada del AutoCAF registró un tiempo de ejecución de **13 minutos**. 

Como punto de referencia sobre el impacto operativo de la herramienta, el analista de crédito responsable de este flujo operativo (Esteban) indicó que, bajo el esquema manual anterior, el vaciado, revisión y cuadre del CAF tomaba un tiempo aproximado de **40 minutos** de trabajo continuo. Esto representa una optimización de aproximadamente el 67% en los tiempos de elaboración del CAF, validando la eficacia operativa del sistema.

![Comparativa de Tiempos Manual vs AutoCAF](ruta/a/imagen_tiempos_autocaf.png)
*Figura W. Gráfico comparativo de tiempos de ejecución del proceso CAF.*

### 3.3.4 Resultado de la Implementación 

La culminación del desarrollo e integración de los módulos implementados durante el proyecto permitió transformar el proceso tradicional de análisis documental y financiero en un flujo automatizado, centralizado y apoyado por herramientas de Inteligencia Artificial. La arquitectura desarrollada logró integrar los diferentes componentes del sistema dentro de una única plataforma web, permitiendo que la información fluya desde la recepción de los documentos hasta la generación del reporte financiero sin intervención manual durante las etapas críticas del procesamiento. 

Como resultado de la implementación, AutoTeaser dejó de funcionar únicamente como un repositorio documental para convertirse en una plataforma de Procesamiento Inteligente de Documentos (Intelligent Document Processing, IDP), capaz de administrar expedientes, interpretar información financiera y generar automáticamente los entregables requeridos por el área de análisis de crédito. 

Los principales resultados obtenidos durante la implementación pueden agruparse en tres componentes principales:

#### Expediente Rojo 
El primer resultado obtenido correspondió a la implementación del módulo Expediente Rojo, el cual sustituyó el intercambio tradicional de documentos mediante correo electrónico por un portal web centralizado para la recepción y administración de expedientes. 

A través de este módulo, los clientes pueden cargar directamente la documentación requerida desde la plataforma, mientras que los analistas financieros realizan el proceso de revisión utilizando una única interfaz administrativa. Cada documento permanece asociado a la empresa correspondiente y su estado es actualizado conforme avanza el proceso de validación. 

La incorporación de indicadores visuales permitió que tanto clientes como analistas conozcan en tiempo real el estado de cada documento, identificando si éste se encuentra pendiente, en revisión, aprobado o rechazado. Esta funcionalidad redujo significativamente las actividades de seguimiento manual y permitió mantener un mayor control sobre el avance de cada expediente. 

Adicionalmente, la integración con Supabase Storage permitió automatizar el almacenamiento y organización de los archivos cargados por los usuarios, eliminando la necesidad de administrar manualmente carpetas locales o repositorios compartidos. 

#### AutoCAF 
Uno de los componentes con mayor impacto dentro del proyecto fue el desarrollo del módulo AutoCAF, encargado de automatizar la elaboración del Consolidado de Análisis Financiero utilizado por los analistas de crédito. 

Antes de la implementación del sistema, este proceso requería revisar manualmente varios estados financieros, homologar conceptos contables provenientes de diferentes fuentes y capturar la información dentro de una plantilla institucional de Microsoft Excel. 

Con la incorporación del módulo AutoCAF, el backend procesa automáticamente los documentos cargados por el usuario, extrae la información financiera mediante técnicas de procesamiento documental e Inteligencia Artificial y genera una estructura normalizada que posteriormente es utilizada para construir el consolidado financiero. 

Durante la generación del archivo final, el sistema identifica automáticamente las hojas y columnas correspondientes a cada ejercicio fiscal e inserta los valores obtenidos en las celdas apropiadas de la plantilla institucional utilizando la biblioteca `openpyxl`. Este procedimiento conserva intactas las fórmulas, formatos y cálculos previamente definidos por la empresa, permitiendo obtener un documento completamente funcional sin requerir modificaciones posteriores. 

La automatización de este proceso disminuyó considerablemente el tiempo invertido en la captura de información y redujo la posibilidad de errores asociados a la transcripción manual de datos financieros. 

#### AutoTeaser 
El resultado final del proyecto se materializó mediante la implementación del módulo AutoTeaser, componente que da nombre a la plataforma y cuya finalidad consiste en automatizar la generación del Teaser Financiero utilizado durante la evaluación de solicitudes de crédito. 

El funcionamiento del módulo inicia con la carga de los estados financieros por parte del analista. Posteriormente, el sistema ejecuta el proceso de extracción documental, interpreta la información mediante los modelos de Inteligencia Artificial integrados y transforma los datos obtenidos en una estructura estandarizada. 

Finalmente, el backend utiliza esta información para completar automáticamente la plantilla institucional de Microsoft Excel, generando un documento estructurado que conserva el formato corporativo, las fórmulas financieras y la distribución establecida por la organización. 

Gracias a esta implementación, actividades que anteriormente requerían varias horas de trabajo manual fueron sustituidas por un proceso automatizado que se ejecuta en pocos minutos, permitiendo que el personal especializado concentre sus esfuerzos en el análisis financiero y la toma de decisiones, en lugar de invertir tiempo en tareas repetitivas de captura y consolidación de información. 

En conjunto, la implementación de estos módulos permitió desarrollar una plataforma integral capaz de centralizar la gestión documental, automatizar la interpretación de información financiera y generar los reportes requeridos durante el proceso de análisis de crédito. De esta manera, AutoTeaser cumplió con los objetivos establecidos durante la etapa de análisis, proporcionando una solución tecnológica que mejora la eficiencia operativa, disminuye el riesgo asociado al procesamiento manual de documentos y establece una base sólida para futuras ampliaciones del sistema.
