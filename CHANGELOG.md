# Historial de cambios

El formato se inspira en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [0.6.0] — 2026-11-08

### Añadido

- Punto de entrada gráfico `chessstudio`, metadatos `pyproject.toml` y receta
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
