# ChessStudio

Gestor de partidas de ajedrez libre y gratuito, pensado como alternativa de
escritorio para gestionar bases de partidas, explorar aperturas, preparar
rivales y analizar con motores UCI. Interfaz en español construida con
PySide6 (Qt) y `python-chess`.

## Instalación

Requiere Python 3.10 o superior.

```bash
pip install -r requirements.txt
python main.py
```

En Linux puede ser necesario instalar las bibliotecas de sistema de Qt
(`libxcb`, `libxkbcommon`, etc.) si se ejecuta con escritorio; para pruebas
sin pantalla: `QT_QPA_PLATFORM=offscreen python main.py`.

`keyring` es opcional pero recomendado: guarda el token de Lichess en el
llavero del sistema. Si no está instalado, la aplicación funciona igual.

## Funciones

- **Bases de datos** SQLite (`.csdb`) con importación PGN, búsqueda por
  jugador, evento, fecha, resultado, ECO y posición, y **eliminación de
  partidas** con confirmación.
- **Exportación de la partida abierta** a PGN estándar, con comentarios,
  variantes y flechas (incluye los cambios sin guardar).
- **Importación y apertura en segundo plano** con barra de progreso y
  cancelación: ni los PGN grandes ni las listas con miles de partidas
  congelan la ventana.
- **Explorador de aperturas** (panel derecho) con dos pestañas:
  - *Base local*: estadísticas de tu base, del rival, o de ambas comparadas
    (selector *Ver*). Cuando hay una preparación activa, el modo *Solo rival*
    usa la base del rival como base de datos principal del explorador.
  - *Lichess*: explorador online (Maestros / Lichess) con filtros de ritmo y
    Elo, actualización automática al mover y descarga de partidas
    destacadas con doble clic.
- **Preparar rival** con un flujo guiado de 3 pasos (ver abajo).
- **Motor UCI** (Stockfish, etc.) que se inicia una vez y sigue el tablero
  automáticamente, con opción de fijar una posición para estudio en
  profundidad (ver abajo).
- **Comentarios con formato**: el texto se muestra limpio y las etiquetas
  `[%eval …]` y `[%clk …]` se presentan como distintivos de evaluación y
  reloj, en lugar de código crudo.
- **Anotaciones gráficas**: flechas y casillas de colores que se leen y se
  escriben en el PGN estándar (`%cal` / `%csl`), compatibles con Lichess,
  Chess.com y otros programas.
- **Piezas vectoriales** (SVG) nítidas a cualquier tamaño y resolución.
- Variantes, comentarios, símbolos NAG, promoción de variantes, navegación
  con teclado (`←` `→` `Inicio` `Fin`).

## Uso

### La ventana

- **Centro**: pestañas de partidas (tablero + notación). Puedes abrir varias
  a la vez, moverlas y cerrarlas.
- **Izquierda — Partidas**: la lista de la base abierta; ordena por columna
  con un clic en la cabecera y abre una partida con **doble clic**.
- **Derecha — Aperturas**: explorador local y de Lichess (ver más abajo).
- **Derecha — Motor / Preparar rival**: análisis con motor UCI y flujo de
  preparación de oponentes. Los paneles se muestran/ocultan desde el menú
  *Ver* y se pueden reorganizar arrastrando.

### Primeros pasos

1. Abre la aplicación: `python main.py`. Se crea (o abre) automáticamente tu
   base en `Documentos/ChessStudio/default.csdb`.
2. Pulsa **Importar PGN a la base...** y elige uno o varios archivos PGN.
   La importación va en segundo plano con progreso y botón *Cancelar*; las
   flechas, comentarios y variantes se conservan.
3. Haz **doble clic** en una partida de la lista para abrirla. Las flechas
   del PGN aparecen automáticamente en cada posición.

### Abrir, guardar y exportar

- **Abrir PGN...** abre un archivo directamente en una pestaña (si contiene
  varias partidas, abre la primera y te avisa). No necesita base de datos.
- **Guardar en base** (`Ctrl+S`) guarda la partida abierta con todos sus
  comentarios, variantes y flechas. Si la partida no estaba en la base,
  crea una entrada nueva.
- **Exportar partida...** exporta **únicamente la partida abierta en ese
  momento** a un archivo PGN estándar, con los cambios sin guardar
  incluidos. El nombre sugerido es `Blancas - Negras.pgn`. La escritura es
  atómica: si algo falla, no queda un archivo parcial.

### Eliminar partidas de la base

1. Selecciona una o varias partidas en la lista *Partidas* (con `Ctrl` o
   `Shift` para selección múltiple).
2. Pulsa **Eliminar de la base...** (barra de herramientas o menú
   *Partida*), la tecla **Supr**, o clic derecho → *Eliminar de la base...*.
3. Confirma el borrado. La acción **no se puede deshacer**.
4. Si una partida eliminada estaba abierta en una pestaña, la pestaña se
   mantiene como copia sin vincular: puedes seguir viéndola y, si la
   guardas, creará una entrada nueva.

### Buscar

**Buscar...** (`Ctrl+F`) filtra por jugador, evento, fecha, resultado, ECO
y posición actual del tablero. El resultado se muestra en la lista.

### Navegar y editar una partida

- Navega con `←` `→`, `Inicio`/`Fin`, los botones `|< < > >|` o haciendo
  clic en cualquier jugada de la notación.
- Mueve piezas en el tablero para crear jugadas nuevas o variantes.
- **Clic derecho sobre una jugada** de la notación: editar comentario,
  poner/quitar símbolos de evaluación (`!`, `?`, `±`…), eliminar la
  variante o promoverla a línea principal.
- Las evaluaciones `[%eval]` y los relojes `[%clk]` de PGN externos se
  muestran como distintivos con formato, no como código.

### Dibujar flechas y casillas

- **Arrastrar con el botón derecho** sobre el tablero: flecha.
- **Clic derecho** en una casilla: marcarla.
- Colores: normal = verde, `Shift` = rojo, `Alt` = azul, `Shift+Alt` =
  amarillo. Repetir el trazo lo borra.
- Los dibujos se guardan dentro del PGN (`%cal` / `%csl`) y se ven también
  en Lichess, Chess.com y otros programas.

### Analizar con el motor

1. En el panel *Motor*, elige el ejecutable UCI (p. ej. Stockfish) con el
   botón `...` y pulsa **Iniciar motor**.
2. El motor se inicia **una sola vez** y sigue automáticamente la posición
   del tablero mientras navegas.
3. **Fijar posición actual** congela el análisis en esa posición para
   estudiarla en profundidad mientras sigues navegando; *soltar* reanuda
   el seguimiento.
4. Ajusta el número de líneas (**MultiPV**, 1–5) y, si quieres, marca
   *Iniciar automáticamente al abrir*.

### Atajos de teclado

| Atajo | Acción |
|---|---|
| `←` / `→` | Jugada anterior / siguiente |
| `Inicio` / `Fin` | Ir al inicio / final |
| `Ctrl+S` | Guardar en base |
| `Ctrl+F` | Buscar |
| `Ctrl+O` | Abrir base |
| `Ctrl+Shift+O` | Abrir PGN |
| `Ctrl+N` | Nueva partida |
| `Supr` | Eliminar partidas seleccionadas (en la lista) |
| `F` | Girar tablero |

## Flujo de preparación de rival

1. **Paso 1 — Cargar PGN del rival.** Pulsa *Cargar PGN...* y elige el
   archivo. La importación ocurre en segundo plano con barra de progreso y
   botón *Cancelar*. La base de preparación se guarda en
   `Documentos/ChessStudio/prep/<nombre>.csdb`.
2. **Paso 2 — Confirmar rival y color.** El programa detecta
   automáticamente al jugador con más partidas y lo propone. Puedes cambiar
   de rival o elegir si preparar sus blancas, sus negras o ambos. Las
   estadísticas se filtran al instante.
3. **Paso 3 — Explorar aperturas.** Pulsa *Abrir explorador de aperturas*
   (o se abre solo al terminar la carga). El panel *Aperturas* pasa a modo
   *Solo rival*: las estadísticas que ves son las de la base del rival.
   Mueve en el tablero para ver su repertorio; doble clic en una jugada del
   explorador la juega en el tablero. Con el selector *Ver* puedes volver a
   tu base o comparar ambas.

También puedes abrir una base de preparación existente, añadir partidas de
la base principal, o quitar al rival del explorador cuando termines.

## Explorador de Lichess y token

Desde 2026 el explorador de aperturas de Lichess requiere un **token personal
gratuito**. En la pestaña *Lichess*:

1. Pulsa *Crear token* (abre `lichess.org/account/oauth/token`).
2. Crea un token **sin marcar ningún permiso**.
3. Pégalo en el campo *Token* de la aplicación.

### ¿Está seguro mi token?

- Un token de Lichess **sin permisos** solo puede leer datos públicos: no
  permite jugar, modificar ni acceder a nada privado de tu cuenta. Aunque
  se filtrara, el impacto sería muy bajo. Aun así, conviene tratarlo con
  cuidado.
- El token se guarda en el **llavero del sistema operativo** (Windows
  Credential Locker, macOS Keychain o Secret Service en Linux) mediante la
  biblioteca `keyring`. La aplicación indica debajo del campo dónde está
  guardado. Si no hay llavero disponible, usa la configuración local como
  respaldo.
- Si tenías un token guardado en texto plano de una versión anterior, se
  **migra automáticamente** al llavero y se elimina la copia en claro.
- El token **solo se envía por HTTPS a dominios de Lichess**
  (`lichess.org` / `lichess.ovh`). Nunca se envía a otros servidores, no se
  escribe en registros y la aplicación **no sigue redirecciones** que
  pudieran desviar la petición.
- Sin token, el explorador muestra un aviso claro; el resto de la
  aplicación funciona igual.

### Contenido de PGN no confiable

Los PGN que abres pueden venir de cualquier sitio, así que su contenido se
trata como no confiable:

- Los nombres de jugadores, eventos y comentarios se muestran como **texto
  plano** (no se interpretan como HTML), evitando inyección de contenido y
  cargas de recursos externos que podrían filtrar tu IP.
- El visor de notación **bloquea la carga de recursos externos o locales**
  (imágenes, etc.) por defensa en profundidad.
- Las consultas a la base de datos están **parametrizadas** (sin inyección
  SQL) y los identificadores de partida de Lichess se validan antes de usarlos.

## Flechas y casillas sobre el tablero

- **Arrastrar con el botón derecho**: dibuja una flecha.
- **Clic derecho** sobre una casilla: la marca.
- Colores: normal = verde, `Shift` = rojo, `Alt` = azul, `Shift+Alt` =
  amarillo. Repetir el mismo trazo borra la anotación.
- Las flechas de los PGN descargados de Lichess, Chess.com, etc. se
  reconocen automáticamente al abrir el archivo o la partida.
- Al guardar o exportar, tus dibujos se escriben como tags PGN estándar, de
  modo que otros programas los vuelven a mostrar.

## Motor de análisis

En el panel *Motor*, selecciona el ejecutable UCI (por ejemplo Stockfish) y
pulsa *Iniciar motor*. A partir de ahí:

- El motor **se inicia una sola vez** y queda residente: analiza
  automáticamente la posición que haya en el tablero y la **sigue al
  navegar** por la partida, sin reiniciarse en cada jugada.
- **Fijar posición actual**: congela el análisis en la posición presente
  para estudiarla en profundidad mientras sigues navegando por el resto de
  la partida. Pulsa de nuevo (*soltar*) para volver a seguir el tablero.
- **Iniciar automáticamente al abrir**: arranca el motor al abrir la
  aplicación si hay una ruta configurada.
- **MultiPV**: número de líneas de análisis simultáneas (1 a 5).

## Rendimiento y robustez con PGN grandes

- La lista de partidas usa un modelo/vista: mostrar decenas de miles de
  partidas es instantáneo y la ordenación es por columna.
- **Abrir un PGN** (archivo o partida guardada en la base) se hace en segundo
  plano; la ventana nunca se bloquea ni siquiera con archivos enormes.
- **Notación iterativa**: las variantes muy anidadas ya no desbordan la pila
  (antes provocaban un cierre inesperado). El renderizado usa una pila
  explícita, sin recursión.
- **Navegación O(1)**: el resaltado de la jugada actual usa un mapa de anclas
  construido una sola vez, en lugar de recorrer todo el documento en cada
  paso. Moverse por una partida de miles de jugadas es instantáneo.
- **Presupuesto de renderizado**: en partidas desmesuradas se pintan las
  primeras jugadas y la vista se amplía automáticamente al navegar (o con el
  enlace «Mostrar toda la partida»), evitando documentos de varios MB.
- El procesamiento de dibujos es lineal (sin copias cuadráticas del historial).
- Todas las señales de los workers se entregan en el hilo de la interfaz
  (nada de crear widgets desde hilos en segundo plano).

## Estructura

```
main.py                  Punto de entrada
chessstudio/
  main_window.py         Ventana principal y pestañas de partida
  board_widget.py        Tablero interactivo y anotaciones
  piece_renderer.py      Renderizado de piezas SVG (con caché)
  notation_view.py       Notación con variantes, NAG y comentarios
  game_model.py          Modelo de partida (árbol, dibujos, navegación)
  database.py            Base SQLite + índice de posiciones
  opening_tree.py        Explorador de aperturas (local + Lichess)
  lichess_explorer.py    Cliente de la API de Lichess (red endurecida)
  secure_store.py        Almacenamiento seguro del token (llavero)
  opponent_prep.py       Preparación de rival (flujo de 3 pasos)
  engine_panel.py        Panel de motor UCI (continuo + fijar posición)
  game_list.py           Lista de partidas (modelo/vista)
  search_dialog.py       Diálogo de búsqueda
  pgn_utils.py           Tags %cal/%csl y comentarios con formato
  workers.py             Importación, exportación y apertura en segundo plano
  pieces/                Piezas SVG (cburnett, GPLv2+) + licencia
LICENSE                  GPL-3.0-or-later (licencia de la aplicación)
THIRD_PARTY_NOTICES.md   Licencias de los componentes de terceros
```

## Importación y exportación de PGN

- **Importación robusta** en segundo plano, con progreso y cancelación. Tolera
  PGN con errores sin abortar, y conserva comentarios, variantes y flechas
  (`%cal` / `%csl`). Las partidas con posición inicial personalizada (FEN) se
  guardan y reabren correctamente.
- **Exportación de la partida abierta**: *Exportar partida...* escribe solo
  la partida de la pestaña actual (con los cambios sin guardar) a un PGN
  estándar. La escritura es **atómica**: un fallo nunca deja un archivo
  parcial. Los dibujos se reinyectan como tags `%cal` / `%csl`.

## Pruebas

```bash
pip install pytest
QT_QPA_PLATFORM=offscreen python -m pytest tests -q
```

## Licencia

ChessStudio es software libre bajo **GPL-3.0-or-later** (ver `LICENSE`).

Esto es necesario porque la aplicación depende de **python-chess**, que es
GPL-3.0+. Las piezas SVG "cburnett" son de Colin M. L. Burnett (GPLv2+, vía
Lichess) y se usan sin modificar; consulta `chessstudio/pieces/LICENSE.txt`.
El detalle de todas las licencias está en `THIRD_PARTY_NOTICES.md`.

### Publicar en GitHub (repositorio público)

El proyecto está listo para publicarse. Antes de subirlo:

1. **No subas datos personales ni secretos.** El `.gitignore` ya excluye las
   bases de datos (`*.csdb`), PGN generados y cachés. Asegúrate de no añadir
   tu token de Lichess ni partidas privadas al repositorio.
2. **Conserva los archivos de licencia** (`LICENSE`, `THIRD_PARTY_NOTICES.md`,
   `chessstudio/pieces/LICENSE.txt` y `GPL-2.0.txt`) y la atribución de las piezas.
3. **No incluyas un motor UCI** (Stockfish, etc.) en el repo; cada usuario
   aporta el suyo. Si lo empaquetas, cumple su licencia (GPL-3.0).
4. Revisa que el nombre del proyecto no entre en conflicto con marcas existentes.

Pasos típicos:

```bash
git init
git add .
git commit -m "ChessStudio: versión inicial"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/chessstudio.git
git push -u origin main
```

> La información de licencias es orientativa y no constituye asesoramiento
> legal. Revisa las licencias enlazadas antes de distribuir.
