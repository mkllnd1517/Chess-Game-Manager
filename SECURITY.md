# Política de seguridad

## Versiones compatibles

La rama principal y la última versión publicada reciben correcciones de
seguridad de buena fe. Las versiones antiguas pueden requerir una actualización
completa.

## Informar una vulnerabilidad

No publiques de inmediato una vulnerabilidad que pueda exponer tokens, PGN
privados, archivos locales o ejecución de código. Abre una incidencia privada
si GitHub la ofrece para el repositorio o contacta con el mantenedor a través
del perfil de GitHub, incluyendo:

- una descripción breve y el impacto esperado;
- pasos reproducibles o una prueba de concepto mínima;
- versión de ChessStudio, sistema operativo y versión de Python;
- posibles mitigaciones, si las conoces.

Evita adjuntar tokens reales, bases privadas, partidas no públicas o datos
personales. Se intentará confirmar la recepción, evaluar el informe y acordar
una divulgación coordinada antes de hacerlo público.

## Alcance habitual

Son especialmente relevantes: manejo de PGN no confiables, validación de URLs
y tokens de Lichess, almacenamiento local de credenciales, consultas SQLite,
empaquetado de escritorio y dependencias. Los problemas de seguridad de un
motor UCI externo deben notificarse también al proyecto que distribuye dicho
motor; ChessStudio no incluye ni ejecuta motores por su cuenta hasta que la
persona usuaria los selecciona.
