# Avisos de terceros y distribución

> **Resumen:** Chess Games Manager se publica como
> **GPL-3.0-or-later**. El texto completo está en [`LICENSE`](LICENSE) y el
> aviso de copyright y garantía de esta distribución está en [`NOTICE`](NOTICE).
>
> Este inventario se ha contrastado con las dependencias declaradas en
> `pyproject.toml` y los archivos `requirements*.txt`, los recursos incluidos y
> la cadena de empaquetado del repositorio a fecha de la versión 0.7.0. No sustituye la
> comprobación jurídica de una publicación concreta ni constituye asesoramiento
> legal.

## 1. Componentes ejecutados por la aplicación

| Componente | Licencia declarada por el proyecto | Uso | Obligación práctica al publicar un binario |
|---|---|---|---|
| [`python-chess`](https://github.com/niklasf/python-chess) (paquete PyPI `chess`) | GPL-3.0-or-later | Reglas, PGN y protocolo UCI. | Distribuir Chess Games Manager como GPL-3.0-or-later, conservar el aviso de `python-chess` y ofrecer el código fuente correspondiente. |
| [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/) (`PySide6-Essentials` y `shiboken6`) | LGPL-3.0-only **o** GPL-2.0-only/GPL-3.0-only, según el componente y la modalidad elegida; Qt también ofrece opciones comerciales. | Interfaz Qt, SVG, red y widgets. | Para la distribución comunitaria basada en las ruedas LGPL de Qt, conservar los textos y avisos de Qt/PySide6 que acompañen a la versión empaquetada, usar enlace dinámico cuando corresponda y cumplir las condiciones LGPL aplicables. Una alternativa GPL o comercial cambia las obligaciones. |
| [`keyring`](https://github.com/jaraco/keyring) | MIT | Acceso opcional al llavero del sistema para el token de Lichess. | Conservar su aviso MIT si se redistribuye la biblioteca. La aplicación funciona con su almacenamiento alternativo si no está disponible. |

### Nota sobre PySide6/Qt

Qt no es una única licencia: los módulos instalados y el modo de distribución
son determinantes. **Antes de publicar un `.exe`, `.app`, AppImage u otro
paquete**, revisa los archivos `LICENSE*` y `NOTICE*` que entrega la versión
exacta de PySide6/Qt incorporada por PyInstaller. Inclúyelos junto al binario,
no sustituyas sus avisos y verifica que las bibliotecas de Qt se mantengan
reemplazables cuando se use la ruta LGPL. Si se usa Qt con licencia comercial,
conserva la documentación contractual correspondiente.

## 2. Recursos incluidos en este repositorio

| Recurso | Autoría / procedencia | Licencia | Archivos y cumplimiento |
|---|---|---|---|
| Piezas SVG `cburnett` | Colin M. L. Burnett; copias distribuidas por Lichess. | GPL-2.0-or-later. | Las 12 piezas están en `chessstudio/pieces/`; se conservan [`LICENSE.txt`](chessstudio/pieces/LICENSE.txt) y [`GPL-2.0.txt`](chessstudio/pieces/GPL-2.0.txt). Se usan sin modificar. La opción «o posterior» permite su redistribución bajo GPL-3.0-or-later junto con la aplicación. |
| Iconos de la aplicación | Chess Games Manager contributors, 2026. | GPL-3.0-or-later. | El SVG está en `chessstudio/assets/`; el ICO para el ejecutable e instalador de Windows está en `packaging/windows/`. El SVG declara su SPDX y ambos se cubren por [`NOTICE`](NOTICE). |

Referencia de las piezas cburnett: [COPYING de Lichess](https://github.com/lichess-org/lila/blob/master/COPYING.md) y [directorio original](https://github.com/lichess-org/lila/tree/master/public/piece/cburnett).

## 3. Herramientas de construcción (no son dependencias de ejecución)

| Herramienta | Licencia publicada | Papel |
|---|---|---|
| [PyInstaller](https://pyinstaller.org/) | GPL-2.0-or-later con excepción para el *bootloader*. | Produce la carpeta ejecutable `dist/ChessGamesManager`. La excepción permite distribuir la salida sin que PyInstaller imponga por sí mismo GPL a todo el resultado; las dependencias y el código de Chess Games Manager siguen determinando las obligaciones reales. Conserva los avisos que PyInstaller incorpore en una publicación binaria. |
| [Inno Setup 6](https://jrsoftware.org/isinfo.php) | Consulta su licencia de distribución vigente. | Compila el instalador de Windows definido en `packaging/windows/ChessGamesManager.iss`. No se incluye como dependencia de ejecución del repositorio. |
| [pytest](https://github.com/pytest-dev/pytest) | MIT | Ejecuta las pruebas; solo se instala para desarrollo. |
| setuptools | MIT | Construye el paquete Python. No se redistribuye como parte de la aplicación final. |

## 4. Componentes expresamente no incluidos

### Motores UCI

Chess Games Manager **no incluye, descarga, aloja ni redistribuye** Stockfish ni ningún
otro motor UCI. La aplicación solo permite seleccionar un ejecutable que el
usuario ya haya obtenido. Si en el futuro se distribuye un motor junto a la
aplicación, habrá que añadir su código fuente, licencia, avisos y cualquier
otra obligación exigida por su licencia antes de publicar.

### Servicios de Lichess

La integración consulta el explorador de aperturas y puede abrir partidas
públicas de Lichess. La marca, los servicios y los datos de Lichess pertenecen
a sus titulares. El token es aportado por cada persona usuaria; nunca se
incluye en el repositorio ni en los instaladores. El uso está sujeto a los
[términos de Lichess](https://lichess.org/terms-of-service) y a las condiciones
de su API. La integración no implica patrocinio, afiliación ni aprobación.

## 5. Contenido aportado por la persona usuaria

Las partidas, bases, comentarios, repertorios y archivos PGN que se importan
permanecen localmente en el equipo salvo que la persona usuaria decida
exportarlos o utilizar un servicio externo. Chess Games Manager no concede derechos
sobre esos datos ni verifica su procedencia: quien importe, comparta o publique
un PGN debe contar con los permisos necesarios y respetar las condiciones de
la fuente de la que lo obtuvo. Los repertorios guardan únicamente sus bases
locales y etiquetas de archivo; no suben PGN ni rutas locales al proyecto.

## 6. Lista de verificación para una publicación pública

Antes de adjuntar un instalador a una *release*:

1. Ejecuta `python -m pip install -e ".[test,build]"` y las pruebas.
2. Genera el paquete con `python scripts/build_release.py` desde un entorno
   limpio y anota las versiones exactas instaladas (`python -m pip freeze`).
3. Comprueba que el binario contiene `LICENSE`, `NOTICE`,
   `THIRD_PARTY_NOTICES.md`, `THIRD_PARTY_COMPONENTS.json`, las piezas
   `cburnett` y sus textos GPL. El inventario JSON se genera durante la
   compilación y deja constancia de las versiones de ejecución detectadas.
4. Revisa los avisos, textos de licencia y versiones exactas de todas las
   dependencias que PyInstaller haya copiado, especialmente Qt/PySide6. Incluye
   los avisos exigidos por esas versiones y conserva un enlace claro al código
   fuente correspondiente de esta misma versión (por ejemplo, una etiqueta de
   GitHub de la *release* y las fuentes de las dependencias GPL).
5. No empaquetes bases personales, PGN privados, repertorios, tokens, motores
   UCI ni claves. El instalador debe crear los datos de la persona usuaria tras
   la instalación, nunca incluirlos desde el equipo de desarrollo.
6. Firma el instalador y publica hashes cuando se disponga de un certificado de
   firma; prueba la instalación, apertura de un PGN y desinstalación en una
   máquina limpia.
7. Actualiza este documento si cambian dependencias, recursos, versiones o la
   forma de distribución, y realiza una revisión jurídica profesional cuando
   el caso de uso o la jurisdicción lo requieran.

## 7. Alcance

Esta documentación pretende hacer visibles las obligaciones conocidas y evitar
atribuciones engañosas. No garantiza que todos los requisitos legales de una
jurisdicción, una dependencia transitiva o una distribución futura estén
cubiertos. Para una distribución comercial, con datos de terceros o con
requisitos especiales, consulta a una persona profesional especializada.
