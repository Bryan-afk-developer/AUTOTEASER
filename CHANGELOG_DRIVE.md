# 📋 Resumen de Cambios: Rama `DRIVE`

Este documento detalla todas las correcciones, nuevas funcionalidades y optimizaciones implementadas en la última actualización subida a la rama `DRIVE` del repositorio.

---

## ☁️ 1. Módulo de Google Drive
Se resolvió por completo la integración con Google Drive para permitir el respaldo seguro de los expedientes.

* **Integración OAuth 2.0:** Se implementó un flujo de autenticación de usuario (`authorize.py`) para utilizar un `token.json`. Esto evita la restricción de **0 MB de almacenamiento** que Google impone a las Cuentas de Servicio, permitiendo que el sistema suba archivos directamente a la cuenta del analista.
* **Sobrescritura de Archivos (Update):** Se modificó la función `upload_file_to_drive`. Ahora, si un documento modificado o corregido se sube a AutoTeaser y ya existe en Google Drive, el sistema **actualizará su contenido** en lugar de ignorarlo o crear duplicados.
* **Apuntado Directo a Carpeta Específica:** Se implementó una directiva para que el sistema apunte exactamente al ID de la carpeta raíz deseada por el usuario (`1X_i_12e01QTEslvT3NvCkW6JMKKFCMVf`), evitando que el robot busque carpetas compartidas al azar en el Drive.

## 📊 2. Módulo de Buró de Crédito (Extracción OCR)
Se mejoró significativamente la extracción de cuentas (MOPs) para abarcar formatos diferentes.

* **Soporte para Personas Físicas / Representante Legal:** Se creó la función `_parse_personal_credits` en `mop_extractor.py`. Anteriormente, el sistema solo detectaba tablas bajo la sección "FINANCIEROS ACTIVOS". Ahora, es capaz de parsear los créditos numerados (1., 2., 3.) típicos de los reportes individuales bajo la sección "CRÉDITOS BANCARIOS", logrando extraer la información del Representante Legal correctamente.

## ⚙️ 3. Backend, Dashboard y Caché
* **Re-extracción Forzada:** Se corrigió un problema donde, si la base de datos tenía un registro vacío o corrupto de extracción, el frontend se quedaba colgado con una lista vacía. Ahora `dashboard.py` verifica si existen cuentas válidas; de no ser así, vuelve a procesar el PDF en el momento.
* **Invalidación Visual Inmediata:** En el frontend (`AdminDashboard.jsx`), al dar clic en refrescar, se ejecuta un `delete mopsCache[cacheKey]` asegurando que la UI descarte la información vieja y muestre los datos del Buró recién parseados.

## 🔒 4. Seguridad y Repositorio
* **Ajuste Estricto de `.gitignore`:** Se auditaron y corrigieron las reglas de control de versiones. El repositorio ignorará estrictamente los archivos locales sensibles (`google-credentials.json`, `oauth-client.json`, `token.json` y variables de entorno `.env`) previniendo fugas de credenciales en GitHub.
* **Commit y Push:** Los archivos se encuentran empaquetados y asegurados en la rama remota `DRIVE`, lista para ser clonada o desplegada.
