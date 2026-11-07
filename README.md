# Chess Game Manager

**Gestor de bases de datos de ajedrez, explorador de aperturas y herramienta de preparación de rivales.**

Chess Game Manager nace con un objetivo: ofrecer una herramienta gratuita y de código abierto para jugadores que necesitan organizar sus partidas, estudiar aperturas y preparar a sus rivales desde un único entorno de escritorio.

Plataformas como Lichess ofrecen gratuitamente servicios excelentes de análisis y exploración de aperturas. Sin embargo, no todos los jugadores tienen las mismas necesidades ni siguen el mismo flujo de trabajo. Quienes trabajan habitualmente con colecciones PGN propias, quieren preparar a un rival concreto a partir de sus partidas o prefieren analizar posiciones con sus propios motores UCI pueden beneficiarse de una aplicación de escritorio especializada.

Con Chess Game Manager puedes importar un PGN con las partidas de un oponente y estudiar su repertorio, consultar y comparar estadísticas de tus propias bases de datos, analizar posiciones con el motor UCI que elijas y conservar comentarios, variantes y anotaciones en tus partidas. El propósito es reunir estas herramientas en una aplicación gratuita, abierta y centrada en las bases de datos del usuario.

## Características principales

- **Preparación de rivales:** flujo guiado de tres pasos para crear una base de preparación a partir de un PGN con las partidas del oponente y estudiar su repertorio.
- **Explorador de aperturas:** consulta estadísticas de tus bases de datos locales o utiliza el explorador online de Lichess.
- **Análisis con motores UCI:** utiliza Stockfish u otros motores compatibles que proporciones tú mismo, con análisis continuo, MultiPV y fijación de posiciones.
- **Gestión de partidas:** importa, organiza, busca, edita y exporta partidas PGN.
- **Edición avanzada de PGN:** conserva comentarios, variantes, flechas, casillas marcadas y símbolos de evaluación.
- **Tablero interactivo:** navega por las partidas, crea variantes y añade anotaciones directamente sobre el tablero.
- **Procesamiento en segundo plano:** importa y abre archivos PGN con indicadores de progreso y opción de cancelación.
- **Seguridad:** almacenamiento del token de Lichess mediante el llavero del sistema cuando está disponible y tratamiento defensivo de los PGN externos.

## Instalación

### Requisitos

- Python 3.10 o posterior.
- Un entorno de escritorio compatible con PySide6.
- Un motor compatible con el protocolo UCI, si quieres utilizar las funciones de análisis.

**Los motores de ajedrez no se incluyen ni se distribuyen con Chess Game Manager.** Cada usuario debe obtener e instalar su propio motor y seleccionar el ejecutable desde la aplicación. Consulta la sección [Motores UCI](#motores-uci) y las condiciones de licencia del motor que decidas utilizar.

### Instalar desde el código fuente

Clona el repositorio e instala las dependencias:

```bash
git clone https://github.com/<tu-usuario>/chess-game-manager.git
cd chess-game-manager

pip install -r requirements.txt
python main.py
```

En Linux puede ser necesario instalar bibliotecas del sistema requeridas por Qt, como `libxcb` o `libxkbcommon`.

Para ejecutar las pruebas sin mostrar una ventana:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests -q
```

**Dependencia opcional:** se recomienda `keyring` para guardar el token de Lichess en el llavero del sistema operativo. Si no está instalado o no hay un llavero disponible, la aplicación utiliza el mecanismo alternativo de almacenamiento local implementado por el proyecto.

## Interfaz y primeros pasos

La ventana principal se organiza en tres zonas:

| Zona | Contenido |
|---|---|
| Izquierda | Lista de partidas de la base de datos abierta. |
| Centro | Pestañas de partidas con tablero interactivo y notación. |
| Derecha | Explorador de aperturas, motor UCI y herramientas de preparación de rivales. |

Puedes abrir varias partidas simultáneamente en pestañas independientes. Los paneles laterales se pueden mostrar u ocultar desde el menú **Ver** y reorganizar arrastrándolos.

### Primeros pasos

Al iniciar la aplicación se crea o abre automáticamente la base de datos principal:

```text
Documentos/ChessStudio/default.csdb
```

Para empezar:

1. Pulsa **Importar PGN a la base...** y selecciona uno o varios archivos PGN.
2. La importación se ejecutará en segundo plano. Puedes seguir utilizando la aplicación y cancelar el proceso si es necesario.
3. Haz doble clic en una partida de la lista para abrirla.
4. Navega por sus jugadas y utiliza los paneles laterales para explorar aperturas o analizar posiciones.

Las flechas y las casillas anotadas que estén incluidas en el PGN se muestran automáticamente sobre el tablero.

### Gestión de bases de datos y archivos PGN

Chess Game Manager permite trabajar tanto con bases de datos locales como con archivos PGN independientes.

| Acción | Descripción |
|---|---|
| **Importar PGN a la base...** | Incorpora uno o varios archivos PGN a la base de datos abierta. |
| **Abrir PGN...** | Abre un archivo directamente en una pestaña, sin importarlo a la base. Si contiene varias partidas, abre la primera y muestra un aviso. |
| **Guardar en base** (`Ctrl+S`) | Guarda la partida abierta, incluidos comentarios, variantes y anotaciones. Si todavía no está en la base, crea una entrada nueva. |
| **Exportar partida...** | Exporta únicamente la partida abierta a un PGN estándar, incluidos los cambios todavía no guardados. |
| **Abrir base** (`Ctrl+O`) | Permite abrir otra base de datos. |

La exportación utiliza escritura atómica para evitar dejar archivos incompletos si se produce un error. El nombre sugerido sigue el formato `Blancas - Negras.pgn`.

### Buscar y eliminar partidas

**Buscar (`Ctrl+F`)**

Permite filtrar partidas por jugador, evento, fecha, resultado, código ECO y posición actual del tablero.

**Eliminar partidas**

Selecciona una o varias partidas en la lista y utiliza **Eliminar de la base...**, disponible en la barra de herramientas, el menú **Partida**, el menú contextual o la tecla `Supr`.

La eliminación requiere confirmación y no se puede deshacer. Si una partida eliminada estaba abierta en una pestaña, esta se conserva como copia independiente. Si posteriormente la guardas, se crea una nueva entrada en la base de datos.

### Navegar y editar partidas

Puedes navegar por una partida mediante:

- Las flechas `←` y `→`.
- Las teclas `Inicio` y `Fin`.
- Los botones de navegación.
- Un clic sobre cualquier jugada de la notación.

También puedes mover piezas directamente en el tablero para crear nuevas jugadas o variantes.

Al hacer clic derecho sobre una jugada de la notación puedes editar comentarios, añadir o quitar símbolos de evaluación (`!`, `?`, `±`, etc.), eliminar variantes o promover una variante a línea principal.

Las evaluaciones `[%eval]` y los relojes `[%clk]` de PGN externos se muestran como indicadores con formato, en lugar de mostrarse como código.

### Flechas y casillas

Puedes dibujar flechas y marcar casillas directamente sobre el tablero:

| Acción | Resultado |
|---|---|
| Arrastrar con el botón derecho | Dibuja una flecha. |
| Clic derecho sobre una casilla | Marca la casilla. |
| `Shift` | Rojo. |
| `Alt` | Azul. |
| `Shift` + `Alt` | Amarillo. |
| Sin modificadores | Verde. |

Repetir el mismo trazo elimina la anotación. Las flechas y marcas se guardan en el PGN mediante las etiquetas estándar `%cal` y `%csl`, por lo que pueden visualizarse en Lichess, Chess.com y otros programas compatibles.

Las anotaciones incluidas en PGN descargados de estas plataformas también se reconocen automáticamente.

## Preparación de rivales

La preparación de oponentes es una de las funciones centrales de Chess Game Manager. Permite crear una base de datos específica a partir de las partidas de un rival y estudiar su repertorio.

### Paso 1 — Cargar las partidas del rival

Pulsa **Cargar PGN...** y selecciona el archivo que contiene las partidas del oponente.

La importación se realiza en segundo plano, con barra de progreso y opción de cancelación. La base de preparación se guarda en:

```text
Documentos/ChessStudio/prep/<nombre>.csdb
```

### Paso 2 — Confirmar el rival y el color

La aplicación identifica al jugador con más partidas y lo propone como rival. Puedes cambiar la selección y decidir qué partidas quieres estudiar:

- Sus partidas con blancas.
- Sus partidas con negras.
- Ambos colores.

Las estadísticas se actualizan al cambiar la selección.

### Paso 3 — Explorar su repertorio

Al terminar la importación, puedes abrir el explorador de aperturas. El panel pasa al modo **Solo rival**, que utiliza la base de preparación como fuente principal de estadísticas.

Mueve las piezas en el tablero para explorar el repertorio del oponente. Al hacer doble clic en una jugada del explorador, esta se reproduce en el tablero.

El selector **Ver** permite alternar entre tu propia base, la base del rival o una comparación de ambas.

También puedes abrir una preparación existente, añadir partidas desde la base principal o retirar al rival del explorador cuando termines.

## Explorador de aperturas

El explorador está integrado en el panel derecho y ofrece dos fuentes de datos.

### Base local

Consulta estadísticas de las partidas almacenadas en tus bases de datos. Puedes estudiar tu propio repertorio, el de un rival o comparar ambos.

Cuando hay una preparación activa, el modo **Solo rival** utiliza la base del oponente.

### Lichess

Consulta el explorador online de Lichess:

- Base de Maestros.
- Base general de Lichess.

Puedes aplicar filtros de ritmo y Elo y descargar partidas destacadas haciendo doble clic sobre ellas.

### Configurar el token de Lichess

El explorador de aperturas de Lichess requiere un token personal gratuito.

1. Pulsa **Crear token** en la pestaña Lichess o visita <https://lichess.org/account/oauth/token>.
2. Crea un token **sin seleccionar ningún permiso**.
3. Copia el token y pégalo en el campo correspondiente de la aplicación.

Un token sin permisos adicionales permite consultar datos públicos, pero no autoriza a jugar, modificar la cuenta ni acceder a información privada. Si no configuras un token, el explorador muestra un aviso y el resto de la aplicación sigue funcionando.

El uso de los servicios de Lichess está sujeto a sus [términos de servicio](https://lichess.org/terms-of-service) y a las condiciones aplicables a su API.

## Motores UCI

Chess Game Manager puede comunicarse con motores compatibles con el protocolo UCI, como Stockfish.

**Importante:** Chess Game Manager no incluye, descarga, aloja ni redistribuye Stockfish ni otros motores. El usuario debe obtener el motor por separado, aceptar las condiciones aplicables y seleccionar su ejecutable desde la aplicación.

Para iniciar un análisis:

1. En el panel **Motor**, selecciona el ejecutable UCI mediante el botón `...`.
2. Pulsa **Iniciar motor**.
3. El motor comienza a analizar la posición actual del tablero.

Una vez iniciado, el motor permanece activo y sigue automáticamente la posición del tablero mientras navegas por la partida. No es necesario reiniciarlo en cada jugada.

### Opciones de análisis

- **Fijar posición actual:** congela el análisis en la posición seleccionada para estudiarla en profundidad mientras sigues navegando por la partida.
- **Soltar:** reanuda el seguimiento automático del tablero.
- **MultiPV:** permite mostrar entre 1 y 5 líneas de análisis simultáneas.
- **Iniciar automáticamente al abrir:** inicia el motor al arrancar la aplicación, siempre que haya una ruta configurada.

## Seguridad y privacidad

Chess Game Manager incorpora medidas para proteger los datos del usuario y reducir los riesgos asociados a archivos externos.

### Almacenamiento del token de Lichess

Cuando está disponible, la aplicación utiliza la biblioteca opcional `keyring` para guardar el token en el llavero del sistema operativo:

- Windows Credential Locker.
- macOS Keychain.
- Secret Service en Linux.

Si no hay un llavero disponible, se utiliza el mecanismo alternativo de almacenamiento local de la aplicación. Las versiones anteriores que guardaban el token en texto plano pueden migrarlo al llavero cuando este está disponible y eliminar la copia anterior.

Además:

- El token se envía mediante HTTPS únicamente a los dominios de Lichess (`lichess.org` y `lichess.ovh`).
- La aplicación no debe enviar el token a servidores de terceros.
- El token no se escribe en los registros de la aplicación.
- Las peticiones no siguen redirecciones HTTP.

Se recomienda crear un token sin permisos adicionales y tratarlo como información confidencial.

### Tratamiento de PGN externos

Los archivos PGN pueden proceder de fuentes no confiables. Para reducir posibles riesgos:

- Los nombres de jugadores, eventos y comentarios se muestran como texto plano, sin interpretarse como HTML.
- El visor de notación bloquea la carga de recursos externos o locales, como imágenes.
- Las consultas SQL utilizan parámetros.
- Los identificadores de partidas de Lichess se validan antes de utilizarlos.

## Atajos de teclado

| Atajo | Acción |
|---|---|
| `←` / `→` | Jugada anterior / siguiente |
| `Inicio` / `Fin` | Ir a la primera / última posición |
| `Ctrl+S` | Guardar partida en la base |
| `Ctrl+F` | Buscar partidas |
| `Ctrl+O` | Abrir base de datos |
| `Ctrl+Shift+O` | Abrir archivo PGN |
| `Ctrl+N` | Nueva partida |
| `Supr` | Eliminar partidas seleccionadas |
| `F` | Girar el tablero |

## Estructura del proyecto

```text
chess-game-manager/
│
├── main.py                  # Punto de entrada
│
├── chessstudio/
│   ├── main_window.py       # Ventana principal y pestañas
│   ├── board_widget.py      # Tablero interactivo y anotaciones
│   ├── piece_renderer.py    # Renderizado SVG y caché
│   ├── notation_view.py     # Notación, variantes y comentarios
│   ├── game_model.py        # Modelo de partida y navegación
│   ├── database.py          # SQLite e índice de posiciones
│   ├── opening_tree.py      # Explorador local y Lichess
│   ├── lichess_explorer.py  # Cliente de la API de Lichess
│   ├── secure_store.py      # Almacenamiento del token
│   ├── opponent_prep.py     # Preparación de rivales
│   ├── engine_panel.py      # Integración con motores UCI
│   ├── game_list.py         # Lista de partidas
│   ├── search_dialog.py     # Diálogo de búsqueda
│   ├── pgn_utils.py         # Anotaciones y comentarios PGN
│   ├── workers.py           # Tareas en segundo plano
│   └── pieces/              # Piezas SVG y sus avisos de licencia
│
├── tests/                   # Pruebas automatizadas
├── LICENSE                  # Licencia del proyecto
├── THIRD_PARTY_NOTICES.md   # Avisos y licencias de terceros
└── requirements.txt         # Dependencias de Python
```

## Pruebas

Para ejecutar las pruebas automatizadas:

```bash
pip install pytest
QT_QPA_PLATFORM=offscreen python -m pytest tests -q
```

## Licencia

Chess Game Manager se distribuye bajo la licencia **GNU General Public License v3.0 o, a elección del usuario, cualquier versión posterior (GPL-3.0-or-later)**. Consulta el archivo [`LICENSE`](LICENSE).

El proyecto utiliza `python-chess`, que se distribuye bajo GPL-3.0-or-later. Los componentes, bibliotecas y recursos de terceros conservan sus respectivas licencias y avisos de autoría. Consulta [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

**Los motores UCI, incluido Stockfish, no forman parte de este repositorio ni se distribuyen con la aplicación.** Cada usuario los obtiene y configura por separado. Sus licencias corresponden a sus respectivos proyectos.

La información de licencias de este repositorio se ofrece para identificar los componentes conocidos y sus avisos. No sustituye una revisión de las versiones y licencias efectivamente incluidas en cada publicación.

## Contribuciones

Las sugerencias, informes de errores y contribuciones son bienvenidos.

Antes de enviar cambios:

- Comprueba que las pruebas existentes siguen pasando.
- No incluyas bases de datos personales, PGN privados, tokens ni otras credenciales.
- Conserva los avisos de copyright y las licencias de los componentes de terceros.
- Documenta las nuevas dependencias y recursos en `THIRD_PARTY_NOTICES.md`.
- No añadas motores UCI ni otros binarios de terceros sin revisar previamente sus licencias y obligaciones de redistribución.

## Publicar el repositorio en GitHub

Antes de hacer público el repositorio:

1. Revisa `.gitignore` y comprueba qué archivos están preparados para el commit.
2. Asegúrate de que no se incluyen bases de datos personales (`*.csdb`), PGN privados, tokens, archivos de configuración sensibles ni registros.
3. Conserva `LICENSE`, `THIRD_PARTY_NOTICES.md` y los avisos de licencia de las piezas SVG.
4. Comprueba que el inventario de dependencias y sus licencias coincide con `requirements.txt` y con el código que realmente se distribuye.
5. No incluyas ejecutables de Stockfish ni de otros motores UCI.

Comandos iniciales para publicar el repositorio:

```bash
git init
git add .
git status
git commit -m "Primera versión de Chess Game Manager"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/chess-game-manager.git
git push -u origin main
```

Revisa siempre el resultado de `git status` antes de confirmar los cambios.

---

**Chess Game Manager — Tus partidas, tus aperturas y tu preparación, en un mismo lugar.**
