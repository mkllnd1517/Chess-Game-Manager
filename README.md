# Chess Games Manager

> Gestor de bases de datos de ajedrez, explorador de aperturas y herramienta de preparación de rivales.

Chess Games Manager nace con un objetivo sencillo: ofrecer una herramienta gratuita y de código abierto para organizar partidas, estudiar aperturas y preparar rivales desde un único entorno de escritorio.

Plataformas como Lichess ofrecen excelentes servicios de análisis y exploración. Chess Games Manager está pensado para un flujo de trabajo complementario: colecciones PGN propias, estudio de un rival concreto, bases locales y análisis con el motor UCI que cada persona elija instalar.

<p align="center">
  <img src="capturas/1_piezas_comentarios_rival.png" alt="Chess Games Manager con tablero, notación, explorador y preparación de rival" width="820">
</p>

## Características principales

- **Preparación de rivales:** flujo guiado para crear una base de preparación a partir de un PGN con las partidas de un oponente y estudiar su repertorio.
- **Explorador de aperturas:** consulta estadísticas de tus bases locales, repertorios personales o el explorador online de Lichess.
- **Repertorios personales:** crea perfiles con nombre —por ejemplo, `e4`, `d4` o `Agresivo`—, conserva blancas y negras por separado e indexa todas las variantes de tus PGN de aperturas.
- **Análisis con motores UCI:** utiliza Stockfish u otros motores compatibles que proporciones tú mismo, con análisis continuo, MultiPV legible, números de jugada y fijación de posiciones.
- **Gestión de partidas:** importa, organiza, busca, edita y exporta partidas PGN.
- **Edición avanzada de PGN:** conserva comentarios, variantes, flechas, casillas marcadas y símbolos de evaluación.
- **Tablero interactivo:** navega por las partidas, crea variantes y añade anotaciones directamente sobre el tablero.
- **Procesamiento en segundo plano:** importa y abre archivos PGN con indicadores de progreso y opción de cancelación.
- **Seguridad:** guarda el token de Lichess en el llavero del sistema cuando está disponible y trata los PGN externos de forma defensiva.

## Instalación desde el código fuente

Chess Games Manager se comparte como código fuente. No se proporcionan
instaladores ni ejecutables oficiales: cada persona instala las dependencias y
lo ejecuta en su propio entorno siguiendo estas instrucciones.

### Qué necesitas

- **Python 3.10 o posterior**, instalado para tu sistema operativo.
- Un entorno de escritorio compatible con Qt/PySide6.
- Conexión a internet únicamente durante la instalación de dependencias.
- Un motor compatible con el protocolo UCI, solo si quieres usar el análisis de motor.

> **Los motores de ajedrez no se incluyen ni se distribuyen con Chess Games Manager.**
> Cada usuario debe obtener e instalar su propio motor desde una fuente oficial
> o de confianza, seleccionar su ejecutable desde la aplicación y revisar su
> licencia y condiciones de distribución.

### Instalación recomendada desde el código fuente

La forma más limpia de instalar el proyecto es usar un entorno virtual. Evita
mezclar las bibliotecas de la aplicación con las del resto del sistema.

1. Clona el repositorio y entra en la carpeta:

   ```bash
   git clone https://github.com/mkllnd1517/Chess-Game-Manager.git
   cd Chess-Game-Manager
   ```

2. Crea y activa un entorno virtual.

   **Windows (PowerShell):**

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   Si PowerShell bloquea la activación, ejecuta una vez
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` o usa `cmd` con
   `.venv\Scripts\activate.bat`.

   **macOS y Linux:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Actualiza `pip` e instala las dependencias necesarias:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Inicia la aplicación:

   ```bash
   python main.py
   ```

Para volver a abrirla más adelante, activa de nuevo el entorno virtual y repite
`python main.py`.

### Almacenamiento seguro del token de Lichess — opcional

La aplicación funciona sin esta dependencia. Si la instalas, puede guardar el
token de Lichess en el llavero del sistema — Windows Credential Locker, macOS
Keychain o Secret Service/KWallet en Linux — en lugar de usar el mecanismo
local alternativo sin cifrar.

> **Advertencia:** si el sistema no dispone de un llavero compatible, el token
> se guarda en la configuración local de la aplicación sin cifrado. Se
> recomienda utilizar un token sin permisos adicionales.

```bash
python -m pip install -r requirements-optional.txt
```

El archivo `requirements-optional.txt` no reemplaza al principal: instálalo
después de `requirements.txt`.

### Dependencias del sistema en Linux

Las ruedas de PySide6 incluyen Qt, pero algunas distribuciones necesitan unas
pocas bibliotecas del sistema. En Ubuntu, Debian y derivadas, prueba primero:

```bash
sudo apt update
sudo apt install libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0
```

Los nombres pueden variar en Fedora, Arch o distribuciones similares. Si al
iniciar ves un mensaje sobre un *Qt platform plugin*, consulta la documentación
de tu distribución para instalar las bibliotecas de XCB/Wayland correspondientes.

### Comprobar la instalación

Ejecuta estos comandos desde la carpeta del repositorio y con el entorno virtual
activo:

```bash
python --version
python -c "import chess; from PySide6.QtWidgets import QApplication; print('Dependencias OK')"
python main.py
```

La segunda orden confirma que Python puede importar las bibliotecas principales.
Cierra la ventana normalmente para terminar la aplicación.

### Para desarrollo y pruebas

Instala el conjunto de desarrollo, que incluye `pytest` y las dependencias
opcionales:

```bash
python -m pip install -r requirements-dev.txt
QT_QPA_PLATFORM=offscreen python -m pytest tests -q
```

En Windows puedes omitir `QT_QPA_PLATFORM=offscreen` si quieres ver las
ventanas durante las pruebas:

```powershell
python -m pytest tests -q
```

## Interfaz y primeros pasos

La ventana principal se organiza en tres zonas:

| Zona | Contenido |
|---|---|
| Izquierda | Lista de partidas de la base de datos abierta. |
| Centro | Pestañas de partidas con tablero interactivo y notación. |
| Derecha | Explorador de aperturas, motor UCI, repertorios personales y herramientas de preparación de rivales. |

Puedes abrir varias partidas simultáneamente en pestañas independientes. Los
paneles laterales se pueden mostrar u ocultar desde el menú **Ver** y
reorganizar arrastrándolos.

### Primeros pasos

Al iniciar la aplicación se crea o abre automáticamente la base de datos
principal:

```text
Documentos/Chess Games Manager/default.csdb
```

Para empezar:

1. Pulsa **Importar PGN a la base...** y selecciona uno o varios archivos PGN.
2. La importación se ejecutará en segundo plano. Puedes seguir utilizando la aplicación y cancelarla si lo necesitas.
3. Haz doble clic en una partida de la lista para abrirla.
4. Navega por sus jugadas y utiliza los paneles laterales para explorar aperturas o analizar posiciones.

Las flechas y las casillas anotadas incluidas en el PGN se muestran
automáticamente sobre el tablero.

### Gestión de bases de datos y archivos PGN

Chess Games Manager permite trabajar tanto con bases de datos locales como con archivos
PGN independientes.

| Acción | Descripción |
|---|---|
| **Importar PGN a la base...** | Incorpora uno o varios archivos PGN a la base abierta. |
| **Abrir PGN...** | Abre un archivo en una pestaña sin importarlo. Si contiene varias partidas, abre la primera y avisa. |
| **Guardar en base** (`Ctrl+S`) | Guarda la partida abierta, incluidos comentarios, variantes y anotaciones. Si todavía no está en la base, crea una entrada nueva. |
| **Exportar partida...** | Tras elegir el destino, permite revisar evento, jugadores y demás propiedades antes de exportar la partida abierta a un PGN estándar. |
| **Abrir base** (`Ctrl+O`) | Permite abrir otra base de datos. |

La exportación utiliza escritura atómica para evitar dejar archivos incompletos
si se produce un error. El nombre sugerido sigue el formato
`Blancas - Negras.pgn`.

### Buscar y eliminar partidas

**Buscar (`Ctrl+F`)** permite filtrar partidas por jugador, evento, fecha,
resultado, código ECO y posición actual del tablero.

Para eliminar, selecciona una o varias partidas en la lista y usa **Eliminar de
la base...**, disponible en la barra de herramientas, el menú **Partida**, el
menú contextual o la tecla `Supr`. La acción requiere confirmación y no se
puede deshacer. Si una partida eliminada está abierta en una pestaña, se
conserva como copia independiente; si la guardas de nuevo, se crea una entrada
nueva en la base.

### Navegar y editar partidas

Puedes navegar por una partida mediante:

- Las flechas `←` y `→`.
- Las teclas `Inicio` y `Fin`.
- Los botones de navegación.
- Un clic sobre cualquier jugada de la notación.

También puedes mover piezas directamente en el tablero para crear nuevas
jugadas o variantes. Al hacer clic derecho sobre una jugada de la notación
puedes editar comentarios, añadir o quitar símbolos de evaluación (`!`, `?`,
`±`, etc.), eliminar variantes o promover una variante a línea principal.

Las evaluaciones `[%eval]` y los relojes `[%clk]` de PGN externos se muestran
como indicadores con formato, en lugar de aparecer como código técnico.

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

Repetir el mismo trazo elimina la anotación. Las flechas y marcas se guardan
mediante las etiquetas estándar `%cal` y `%csl`, por lo que pueden visualizarse
en Lichess, Chess.com y otros programas compatibles. Las anotaciones de PGN
descargados de estas plataformas también se reconocen automáticamente.

## Repertorios personales

El panel **Repertorios** permite construir una colección de aperturas propia
sin mezclarla con la base general. Cada repertorio tiene un nombre y dos
secciones independientes: **Con blancas** y **Con negras**. Puedes crear, por
ejemplo, `Repertorio e4`, `Repertorio d4` y `Repertorio agresivo`.

1. Abre **Repertorios** desde la barra de herramientas o el menú **Ver** y pulsa **Nuevo...**.
2. Escribe un nombre y elige la pestaña **Con blancas** o **Con negras**.
3. Pulsa **Añadir PGN...**. Cada archivo queda registrado de forma independiente y se indexan **todas sus variantes**, no solo la línea principal.
4. Selecciona **Usar este repertorio en Aperturas** para estudiar todas sus continuaciones sobre el tablero actual.

La lista muestra los archivos incluidos y el número de partidas de cada uno.
Selecciona uno o varios y pulsa **Quitar seleccionados** para retirar solo sus
partidas del repertorio; los PGN originales nunca se borran. Los repertorios
se guardan localmente en `Documentos/Chess Games Manager/repertoires/`.

Si has cargado una preparación de rival, pulsa **Comparar este repertorio con
el rival**. El explorador separa claramente las fuentes: azul para jugadas
solo presentes en el repertorio, verde para jugadas solo presentes en el rival
y amarillo para las que aparecen en ambas. Estas últimas son las líneas por las
que podría transcurrir el encuentro desde la posición actual.

## Preparación de rivales

La preparación de oponentes permite crear una base de datos específica a partir
de las partidas de un rival y estudiar su repertorio.

### Paso 1 — Cargar las partidas del rival

Pulsa **Cargar PGN...** y selecciona el archivo que contiene las partidas del
oponente. La importación se realiza en segundo plano, con barra de progreso y
opción de cancelación. La base de preparación se guarda en:

```text
Documentos/Chess Games Manager/prep/<nombre>.csdb
```

### Paso 2 — Confirmar el rival y el color

La aplicación identifica al jugador con más partidas y lo propone como rival.
Puedes cambiar la selección y decidir qué partidas estudiar:

- Sus partidas con blancas.
- Sus partidas con negras.
- Ambos colores.

Las estadísticas se actualizan al cambiar la selección.

### Paso 3 — Explorar su repertorio

Al terminar la importación, abre el explorador de aperturas. El panel pasa al
modo **Solo rival**, que utiliza la base de preparación como fuente principal
de estadísticas. Mueve las piezas para explorar el repertorio del oponente y
haz doble clic en una jugada del explorador para reproducirla en el tablero.

El selector **Ver** permite alternar entre tu propia base, la base del rival o
una comparación de ambas. También puedes abrir una preparación existente,
añadir partidas desde la base principal o retirar al rival del explorador.

## Explorador de aperturas

El explorador integrado en el panel derecho ofrece dos fuentes de datos.

### Base local

Consulta estadísticas de las partidas almacenadas en tus bases. Puedes estudiar
tu base principal, un repertorio de blancas o negras, el repertorio de un rival
o comparar dos fuentes. Cuando hay una preparación activa, el modo **Solo
rival** utiliza la base del oponente; si activas un repertorio, aparece también
la opción **Repertorio + rival · líneas coincidentes**.

### Lichess

Consulta el explorador online de Lichess:

- Base de Maestros.
- Base general de Lichess.

Puedes aplicar filtros de ritmo y Elo y descargar partidas destacadas haciendo
doble clic sobre ellas.

### Configurar el token de Lichess

El explorador de aperturas de Lichess requiere un token personal gratuito:

1. Pulsa **Crear token** en la pestaña Lichess o visita <https://lichess.org/account/oauth/token>.
2. Crea un token **sin seleccionar ningún permiso**.
3. Copia el token y pégalo en el campo correspondiente de la aplicación.

Un token sin permisos adicionales permite consultar datos públicos, pero no
autoriza a jugar, modificar la cuenta ni acceder a información privada. Si no
configuras un token, el explorador muestra un aviso y el resto de la aplicación
sigue funcionando. El uso de los servicios de Lichess está sujeto a sus
[términos de servicio](https://lichess.org/terms-of-service) y a las
condiciones aplicables a su API.

## Motores UCI

Chess Games Manager puede comunicarse con motores compatibles con el protocolo UCI,
como Stockfish. La aplicación no incluye, descarga, aloja ni redistribuye esos
motores: el usuario debe obtenerlos por separado, aceptar sus condiciones y
seleccionar el ejecutable desde la aplicación. Selecciona únicamente motores
UCI procedentes de fuentes oficiales o fiables.

Para iniciar un análisis:

1. En el panel **Motor**, selecciona el ejecutable UCI mediante el botón `...`.
2. Pulsa **Iniciar motor**.
3. El motor comienza a analizar la posición actual del tablero.

Una vez iniciado, el motor permanece activo y sigue automáticamente la posición
mientras navegas por la partida.

### Opciones de análisis

- **Fijar posición actual:** congela el análisis en la posición seleccionada para estudiarla en profundidad mientras sigues navegando por la partida.
- **Soltar:** reanuda el seguimiento automático del tablero.
- **MultiPV:** permite mostrar entre 1 y 5 líneas de análisis simultáneas.
- **Iniciar automáticamente al abrir:** inicia el motor al arrancar la aplicación, siempre que haya una ruta configurada.

## Seguridad y privacidad

### Almacenamiento del token de Lichess

Cuando está disponible la dependencia opcional `keyring`, la aplicación utiliza
el llavero del sistema operativo. Si no hay un llavero compatible disponible,
el token se guarda en la configuración local de la aplicación **sin cifrado**.
Las versiones anteriores que guardaban el token en texto plano pueden migrarlo
al llavero cuando está disponible y eliminar la copia anterior.

Además:

- El token se envía mediante HTTPS únicamente a `lichess.org` y `lichess.ovh`.
- El token no se escribe en los registros de la aplicación.
- Las peticiones no siguen redirecciones HTTP.
- Se recomienda crear un token sin permisos adicionales y tratarlo como información confidencial.

### Repertorios y datos locales

Los repertorios se guardan en la carpeta de documentos del sistema, separados
de la aplicación instalada. Al añadir un PGN se conserva una copia indexada de
sus partidas y el nombre visible del archivo para poder quitarlo más adelante;
no se guardan rutas absolutas ni se envían repertorios a Lichess o a otro
servicio. Antes de compartir un repertorio o sus PGN, asegúrate de que tienes
permiso para distribuir esas partidas.

### Tratamiento de PGN externos

Los archivos PGN pueden proceder de fuentes no confiables. Para reducir riesgos:

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
Chess-Game-Manager/
├── main.py                       # Punto de entrada desde el código fuente
├── requirements.txt               # Dependencias necesarias para ejecutar
├── requirements-optional.txt      # Integración opcional con el llavero
├── requirements-dev.txt           # Pruebas y entorno de desarrollo
├── chessstudio/                   # Aplicación de escritorio
│   ├── main_window.py             # Ventana principal y pestañas
│   ├── board_widget.py            # Tablero interactivo y anotaciones
│   ├── notation_view.py           # Notación, variantes y comentarios
│   ├── database.py                # SQLite e índice de posiciones
│   ├── opening_tree.py            # Explorador local, repertorios y Lichess
│   ├── repertoire.py              # Panel de repertorios personales
│   ├── repertoire_store.py        # Perfiles y bases de blancas/negras
│   ├── opponent_prep.py           # Preparación de rivales
│   ├── engine_panel.py            # Integración con motores UCI
│   ├── pgn_utils.py               # Anotaciones y comentarios PGN
│   └── pieces/                    # Piezas SVG y sus avisos de licencia
├── capturas/                      # Capturas de la interfaz
├── tests/                         # Pruebas automatizadas
├── LICENSE                        # Licencia del proyecto
└── THIRD_PARTY_NOTICES.md         # Avisos y licencias de terceros
```

## Distribución

Chess Games Manager se publica como proyecto de código abierto bajo la licencia
GNU GPL v3 o posterior. El repositorio contiene el código fuente, los recursos
y las herramientas auxiliares necesarias para desarrollar y ejecutar la
aplicación.

**No se distribuyen instaladores ni ejecutables oficiales.** Cada persona puede
obtener el código fuente, instalar las dependencias necesarias y ejecutar la
aplicación en su propio entorno.

El proyecto incluye scripts auxiliares para construir paquetes de escritorio
mediante PyInstaller e Inno Setup. Se proporcionan para desarrollo, validación
y compilaciones locales; su presencia no implica que el proyecto publique
versiones binarias oficiales.

### Motores de ajedrez

Chess Games Manager no incluye, descarga, aloja ni redistribuye motores de
ajedrez. Para usar análisis con motor, obtén por separado un motor compatible
con UCI, como Stockfish, desde una fuente oficial o fiable y configúralo en la
aplicación. Cada motor conserva sus propias condiciones de licencia y
distribución.

### Dependencias

Las dependencias de Python se instalan por separado siguiendo las instrucciones
de este repositorio. Cada dependencia conserva su propia licencia y sus avisos
de copyright; consulta [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Licencia

Chess Games Manager se distribuye bajo la licencia **GNU General Public License
v3.0 o, a elección del usuario, cualquier versión posterior
(GPL-3.0-or-later)**. Consulta [`LICENSE`](LICENSE).

El proyecto utiliza `python-chess`, distribuido bajo GPL-3.0-or-later. Los
componentes, bibliotecas y recursos de terceros conservan sus respectivas
licencias y avisos de autoría; consulta
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

La información de licencias identifica los componentes conocidos del proyecto;
no sustituye una revisión de las versiones concretas incluidas en una futura
redistribución de terceros.

## Contribuciones

Las sugerencias, informes de errores y contribuciones son bienvenidos.

Antes de enviar cambios:

- Comprueba que las pruebas existentes siguen pasando.
- No incluyas bases de datos personales, PGN privados, tokens ni otras credenciales.
- Conserva los avisos de copyright y las licencias de componentes de terceros.
- Documenta nuevas dependencias y recursos en `THIRD_PARTY_NOTICES.md`.
- No añadas motores UCI ni otros binarios de terceros sin revisar previamente sus obligaciones de redistribución.
