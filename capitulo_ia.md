### 3.1.5 Integración del Motor de Extracción Semántica

**Extracción del texto**
Durante las pruebas realizadas con balances generales y reportes financieros reales, se observó que los documentos provenientes de diferentes instituciones y despachos contables utilizaban nombres distintos para representar un mismo concepto. Los algoritmos tradicionales basados en Expresiones Regulares (Regex) resultaron frágiles e inescalables ante esta inconsistencia. Un algoritmo programado para buscar "Cuentas por Cobrar" fallaba si el documento indicaba "Deudores". Además, conceptos clave como los impuestos solían aparecer agrupados en una sola fila o desglosados en múltiples subcuentas, rompiendo las reglas estáticas de extracción.

**Interpretación mediante Gemini**
Para resolver este problema, se decidió sustituir los analizadores léxicos tradicionales por la API de Google Gemini. El objetivo fue aprovechar la capacidad del modelo para comprender el contexto de la información y clasificar los datos financieros independientemente de la nomenclatura visual utilizada en cada documento.

**Diseño del Prompt**
La integración en el backend (`llm_processor.py`) requirió contener el comportamiento natural del modelo para evitar que devolviera respuestas descriptivas. Se diseñó un prompt donde se definieron reglas de extracción estructuradas:

1. **Igualación de conceptos:** Se indicó explícitamente al modelo las equivalencias entre diferentes conceptos contables. Por ejemplo, se estableció que "Gastos Generales" y "Gastos de Operación" debían tratarse como sinónimos de "Gastos de Administración".
2. **Reglas de consolidación:** Se inyectaron directivas matemáticas para procesar rubros complejos. Por ejemplo, se instruyó al modelo para que el Costo de Ventas devuelto fuera el resultado neto tras restar las devoluciones y rebajas al costo base encontrado en el texto.
3. **Verificación de consistencia:** El modelo fue instruido para validar que las sumas parciales extraídas coincidieran con los totales reportados en el documento antes de generar la respuesta final, asegurando el cuadre de la información.

**Validación con Pydantic**
Para que el sistema pudiera consumir la información de manera automatizada, se configuró el modelo para devolver los resultados exclusivamente en formato JSON. Una vez que Gemini entrega la respuesta, el backend en FastAPI la procesa a través de esquemas de validación construidos con la biblioteca Pydantic. Esta herramienta verifica que todos los campos requeridos existan y que los valores financieros sean estrictamente numéricos. Si se detecta un formato incorrecto (como recibir texto en lugar de un flotante), el sistema rechaza la solicitud y evita que datos inconsistentes ingresen a la base de datos.

**Resultado**
Mediante este flujo de trabajo, AutoTeaser logró estandarizar la ingesta de datos financieros provenientes de fuentes irregulares. La información extraída y validada fluye directamente hacia los módulos de generación de Excel y almacenamiento en Supabase, automatizando un proceso operativo que originalmente requería horas de transcripción y análisis manual por parte de los analistas de crédito.

*(Aquí puedes insertar tu Figura 18)*
**Figura 18.** Respuesta estructurada en formato JSON generada por la API tras aplicar las reglas de extracción. Elaboración Propia (2026).
