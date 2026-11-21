# Historial de cambios

El formato se inspira en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [0.7.1] — 2026-11-08

### Añadido

- Los PGN de repertorio indexan todas sus variantes de apertura, no solo la
  línea principal. Los repertorios ya creados se actualizan al abrirse.
- Al exportar una partida, tras elegir el destino se revisan sus propiedades
  PGN para que el archivo incluya las cabeceras deseadas.

### Mejorado

- El comparador identifica de forma explícita jugadas exclusivas del
  repertorio, exclusivas del rival y presentes en ambas fuentes.
- Las recomendaciones MultiPV del motor muestran números de jugada y bloques
  visualmente separados.
- El producto, instalador y ayuda se denominan Chess Games Manager.

## [0.7.0] — 2026-11-08

### Añadido

- Panel **Repertorios** con perfiles con nombre y bases independientes para
  blancas y negras.
- Importación de uno o varios PGN por repertorio, con progreso en segundo plano
  y registro individual de cada archivo para poder retirarlo después.
- Uso de un repertorio como fuente del explorador de aperturas y comparación
  directa con la preparación de un rival; las continuaciones coincidentes se
  resaltan en amarillo.

### Mejorado

- Índice compuesto para las consultas de posiciones del explorador y gestión
  transaccional de fuentes PGN, reduciendo el trabajo al actualizar repertorios
  grandes.
- Avisos de distribución: se aclara el tratamiento local de datos de usuario y
  la revisión de licencias necesaria antes de publicar binarios.

## [0.6.0] — 2026-11-08

### Añadido

- Punto de entrada gráfico `chess-games-manager`, metadatos `pyproject.toml` y receta
  reproducible de PyInstaller/Inno Setup para instaladores de escritorio.
- Icono propio de la aplicación, lanzador `.desktop` de Linux, asociación de
  archivos `.pgn` en Windows y documentación de instalación sin ejecutar
  `main.py`.
- Menú **Ayuda** con aviso de licencia GPL y documentación de terceros dentro
  de la aplicación.
- `NOTICE`, guía de contribución, política de seguridad, inventario legal más
  preciso y lista de verificación previa a publicar binarios.

### Mejorado

- Al seleccionar una variante con `→`, una segunda pulsación de `→` confirma la
  continuación elegida; `Enter` se mantiene como alternativa.
- Las anotaciones `%cal` y `%csl` se conservan por nodo PGN, incluso cuando dos
  variantes alcanzan el mismo tablero.
- Las flechas del tablero tienen mejor contraste y opacidad para conservar la
  lectura de piezas y dirección.
- La notación presenta comentarios, variantes, evaluaciones y relojes con una
  jerarquía visual más legible.
- Las rutas de documentos utilizan `QStandardPaths`, respetando carpetas
  localizadas de Windows, macOS y Linux.

## [0.5.0]

Versión de partida del repositorio antes de la preparación pública.
