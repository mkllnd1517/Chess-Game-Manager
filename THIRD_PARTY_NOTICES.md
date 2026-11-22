# Avisos de terceros y distribución

> **Resumen:** Chess Games Manager se publica como código fuente bajo
> **GPL-3.0-or-later**. El texto completo está en [`LICENSE`](LICENSE) y el
> aviso colectivo de copyright y garantía del proyecto está en [`NOTICE`](NOTICE).
> El proyecto no publica instaladores ni ejecutables oficiales.
>
> Este inventario se ha contrastado con las dependencias declaradas en
> `pyproject.toml`, los archivos `requirements*.txt`, los recursos incluidos y
> las herramientas auxiliares del repositorio a fecha de la versión **0.7.1**.
> No sustituye la comprobación jurídica de una publicación concreta ni
> constituye asesoramiento legal.

## 1. Componentes ejecutados por la aplicación

Las dependencias de Python se instalan por separado al seguir las instrucciones
del repositorio. Cada una conserva su propia licencia, copyright y avisos; no
pasan a ser propiedad de Chess Games Manager por utilizarse junto al proyecto.

| Componente | Licencia declarada por el proyecto | Uso | Consideración si alguien crea y redistribuye un binario por su cuenta |
|---|---|---|---|
| [`python-chess`](https://github.com/niklasf/python-chess) (paquete PyPI `chess`) | GPL-3.0-or-later | Reglas, PGN y protocolo UCI. | Conservar su aviso y ofrecer el código fuente correspondiente conforme a GPL-3.0-or-later. |
| [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/) (`PySide6-Essentials` y `shiboken6`) | LGPL-3.0-only **o** GPL-2.0-only/GPL-3.0-only, según el componente y la modalidad elegida; Qt también ofrece opciones comerciales. | Interfaz Qt, SVG, red y widgets. | Conservar los textos y avisos de la versión concreta, usar enlace dinámico cuando corresponda y cumplir las condiciones LGPL o la alternativa de licencia elegida. |
| [`keyring`](https://github.com/jaraco/keyring) | MIT | Acceso opcional al llavero del sistema para el token de Lichess. | Conservar su aviso MIT si se incorpora a un artefacto redistribuido. Sin llavero, la aplicación funciona con configuración local alternativa sin cifrar. |

### Nota sobre PySide6/Qt

Qt no es una única licencia: los módulos instalados y el modo de distribución
son determinantes. Si una persona crea y distribuye por separado un `.exe`,
`.app`, AppImage u otro paquete, debe revisar los archivos `LICENSE*` y
`NOTICE*` de la versión exacta de PySide6/Qt usada, conservar sus avisos y
cumplir las condiciones aplicables. El proyecto no publica esos paquetes como
entregables oficiales.

## 2. Recursos incluidos en este repositorio

| Recurso | Autoría / procedencia | Licencia | Archivos y cumplimiento |
|---|---|---|---|
| Piezas SVG `cburnett` | Colin M. L. Burnett; copias distribuidas por Lichess. | GPL-2.0-or-later. | Las 12 piezas están en `chessstudio/pieces/`; se conservan [`LICENSE.txt`](chessstudio/pieces/LICENSE.txt) y [`GPL-2.0.txt`](chessstudio/pieces/GPL-2.0.txt). Se usan sin modificar. La opción «o posterior» permite su redistribución bajo GPL-3.0-or-later junto con la aplicación. |
| Iconos de la aplicación | Chess Games Manager contributors, 2026. | GPL-3.0-or-later. | El SVG está en `chessstudio/assets/`; el ICO para compilaciones locales de Windows está en `packaging/windows/`. Ambos se cubren por [`NOTICE`](NOTICE). |

Referencia de las piezas cburnett: [COPYING de Lichess](https://github.com/lichess-org/lila/blob/master/COPYING.md) y [directorio original](https://github.com/lichess-org/lila/tree/master/public/piece/cburnett).

## 3. Herramientas auxiliares de construcción local

Estas herramientas no son dependencias de ejecución ni implican una
redistribución oficial de binarios. Se mantienen para desarrollo, comprobación
de compatibilidad y para quien quiera construir localmente su propia versión de
escritorio.

| Herramienta | Licencia publicada | Papel |
|---|---|---|
| [PyInstaller](https://pyinstaller.org/) | GPL-2.0-or-later con excepción para el *bootloader*. | Puede generar una carpeta ejecutable local en `dist/ChessGamesManager`. Si alguien redistribuye esa salida, la excepción no elimina las obligaciones derivadas del código ni de las dependencias incluidas. |
| [Inno Setup 6](https://jrsoftware.org/isinfo.php) | Consulta su licencia de distribución vigente. | Puede compilar localmente la receta `packaging/windows/ChessGamesManager.iss`. No se incluye como dependencia de ejecución ni se usa para publicar instaladores oficiales. |
| [pytest](https://github.com/pytest-dev/pytest) | MIT | Ejecuta las pruebas; solo se instala para desarrollo. |
| setuptools | MIT | Construye el paquete Python. No se redistribuye como parte de la aplicación final. |

## 4. Componentes expresamente no incluidos

### Motores UCI

Chess Games Manager **no incluye, descarga, aloja ni redistribuye** Stockfish ni
ningún otro motor UCI. La aplicación solo permite seleccionar un ejecutable que
la persona usuaria ya haya obtenido de una fuente oficial o fiable. Cada motor
conserva su propia licencia y condiciones de distribución.

### Servicios de Lichess

La integración consulta el explorador de aperturas y puede abrir partidas
públicas de Lichess. La marca, los servicios y los datos de Lichess pertenecen
a sus titulares. El token es aportado por cada persona usuaria; nunca se
incluye en el repositorio ni en artefactos generados por las herramientas
auxiliares. El uso está sujeto a los [términos de
Lichess](https://lichess.org/terms-of-service) y a las condiciones de su API.
La integración no implica patrocinio, afiliación ni aprobación.

## 5. Contenido aportado por la persona usuaria

Las partidas, bases, comentarios, repertorios y archivos PGN que se importan
permanecen localmente en el equipo salvo que la persona usuaria decida
exportarlos o utilizar un servicio externo. Chess Games Manager no concede
derechos sobre esos datos ni verifica su procedencia: quien importe, comparta o
publique un PGN debe contar con los permisos necesarios y respetar las
condiciones de la fuente. Los repertorios guardan únicamente sus bases locales
y etiquetas de archivo; no suben PGN ni rutas locales al proyecto.

## 6. Compilaciones locales o redistribuciones de terceros

El proyecto comparte código fuente y **no adjunta instaladores ni ejecutables
oficiales**. Si otra persona decide crear y redistribuir un paquete por su
cuenta, debe asumir la revisión de sus obligaciones legales y, como mínimo:

1. Ejecutar las pruebas desde un entorno limpio y anotar las versiones exactas
   de las dependencias utilizadas.
2. Revisar los avisos y textos de licencia de todas las dependencias copiadas,
   especialmente Qt/PySide6, y conservar los que correspondan.
3. Mantener `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md`, las piezas cburnett
   y sus textos de licencia en cualquier paquete que los incorpore.
4. No incluir bases personales, PGN privados, repertorios, tokens, motores UCI
   ni claves procedentes del equipo de desarrollo.
5. Ofrecer el código fuente y los avisos que exijan GPL y las demás licencias
   aplicables a los componentes incluidos.

## 7. Alcance

Esta documentación pretende hacer visibles las obligaciones conocidas y evitar
atribuciones engañosas. No garantiza que todos los requisitos legales de una
jurisdicción, una dependencia transitiva o una redistribución de terceros estén
cubiertos. Para un caso de distribución comercial, datos de terceros o
requisitos especiales, consulta a una persona profesional especializada.
