# Contribuir a ChessStudio

Gracias por dedicar tiempo a mejorar ChessStudio. El proyecto busca ser útil,
claro y respetuoso con los datos de las personas usuarias.

## Antes de empezar

1. Busca si ya existe una incidencia o propuesta relacionada.
2. Crea una rama desde la versión actual y limita cada cambio a un objetivo
   comprensible.
3. Instala el entorno de desarrollo:

   ```bash
   python -m pip install -e ".[test]"
   ```

4. Ejecuta la batería antes de proponer cambios:

   ```bash
   QT_QPA_PLATFORM=offscreen python -m pytest
   python -m compileall chessstudio
   ```

## Criterios de calidad

- Escribe mensajes, comentarios y documentación claros en español. Conserva los
  identificadores técnicos en inglés cuando mejoren la interoperabilidad.
- Añade una prueba de regresión al corregir un error, especialmente para PGN,
  variantes, navegación, importación y exportación.
- No bloquees la interfaz con lecturas de PGN, red o cálculos costosos; usa los
  trabajadores existentes cuando proceda.
- Trata los PGN, cabeceras, comentarios y respuestas de red como contenido no
  confiable. No introduzcas HTML sin escapar, SQL interpolado ni cargas de
  recursos externas en el visor de notación.
- Mantén la compatibilidad con Python 3.10 o posterior y con la ejecución
  `QT_QPA_PLATFORM=offscreen` de las pruebas.

## Dependencias, recursos y licencias

No añadas una dependencia, icono, conjunto de piezas, motor o archivo de datos
sin comprobar primero su procedencia y licencia. Toda incorporación debe:

1. Ser compatible con GPL-3.0-or-later y la forma de distribución prevista.
2. Incluir los avisos, textos de licencia y atribuciones exigidos.
3. Documentarse en [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
4. Incluirse en la configuración de PyInstaller si hace falta en el instalador.

No subas bases `.csdb`, archivos PGN personales, capturas con datos privados,
tokens, claves, ejecutables UCI ni otros secretos.

## Propuestas de cambio

Describe el problema, el comportamiento esperado, las pruebas realizadas y,
para cambios visuales, una captura antes/después. Si modifica el instalador,
indica el sistema operativo y prueba también abrir y desinstalar el paquete.

## Licencia de las contribuciones

Al enviar una contribución declaras que tienes derecho a hacerlo y aceptas que
se distribuya bajo **GPL-3.0-or-later**, la misma licencia del proyecto.
