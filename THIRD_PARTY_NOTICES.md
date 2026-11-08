# Avisos de terceros

Chess Game Manager se distribuye bajo la licencia **GNU General Public License v3.0 o cualquier versión posterior (GPL-3.0-or-later)**. El texto completo de la licencia se encuentra en el archivo [`LICENSE`](LICENSE).

Este documento identifica los componentes de terceros conocidos a partir de la información disponible del proyecto. Debe mantenerse actualizado conforme cambien `requirements.txt`, los recursos incluidos o la forma de distribuir la aplicación.

## 1. Dependencias de Python

Las dependencias indicadas a continuación se instalan mediante `pip`; no se afirma que sus paquetes estén copiados o vendorizados dentro del repositorio.

| Componente | Licencia publicada | Uso en Chess Game Manager | Referencia |
|---|---|---|---|
| `python-chess` (`chess`) | GPL-3.0-or-later | Reglas de ajedrez, lectura y escritura PGN, comunicación UCI y funciones relacionadas. | [Repositorio oficial](https://github.com/niklasf/python-chess) |
| `PySide6-Essentials` / Qt for Python | LGPLv3 y/o GPL, según el componente y las condiciones aplicables; también existe licencia comercial | Interfaz gráfica: Core, Gui, Widgets, Network y SVG. | [Licencias de Qt](https://doc.qt.io/qt-6/licensing.html) · [Qt for Python](https://wiki.qt.io/Qt_for_Python) |
| `keyring` | MIT | Acceso opcional al llavero del sistema para almacenar el token de Lichess. | [Repositorio oficial](https://github.com/jaraco/keyring) |
| `pytest` | MIT | Ejecución de pruebas; solo se instala desde `requirements-dev.txt`. | [Repositorio oficial](https://github.com/pytest-dev/pytest) |

### Notas sobre las dependencias

- **python-chess:** el proyecto publica su código bajo GPL-3.0-or-later. Su uso es un motivo relevante para que Chess Game Manager se distribuya bajo GPL-3.0-or-later. Consulta siempre la licencia de la versión concreta instalada.
- **PySide6-Essentials / Qt for Python:** el proyecto instala el subconjunto Essentials porque contiene los módulos que usa ChessStudio y evita descargar módulos no utilizados como WebEngine o PDF. Qt ofrece distintas modalidades de licencia, incluidas LGPL y GPL, además de licencias comerciales. La licencia y las obligaciones aplicables dependen de los módulos y componentes concretos utilizados y de cómo se distribuyan. No debe asumirse que la mera instalación mediante `pip` o el enlace dinámico resuelve por sí solo todas las obligaciones. Antes de empaquetar o redistribuir la aplicación, revisa los avisos y archivos de licencia de la versión concreta de PySide6/Qt y los requisitos de la licencia elegida.
- **keyring:** se publica bajo licencia MIT y solo se instala desde `requirements-optional.txt`. Si se redistribuye código o archivos de licencia de esta biblioteca, deben conservarse los avisos de copyright y el texto de licencia exigidos por sus condiciones.
- **pytest:** se publica bajo licencia MIT y es una dependencia de desarrollo, no necesaria para ejecutar ChessStudio.

Este inventario no debe considerarse exhaustivo hasta contrastarlo con todas las dependencias directas y transitivas declaradas en `requirements.txt` y con el código real del proyecto.

## 2. Recursos gráficos incluidos

| Recurso | Autoría / procedencia | Licencia indicada por la fuente | Ubicación |
|---|---|---|---|
| Conjunto de piezas de ajedrez `cburnett` (12 archivos SVG) | Colin M. L. Burnett; distribución a través de Lichess | GNU GPL versión 2 o cualquier versión posterior (GPL-2.0-or-later) | `chessstudio/pieces/` |

La información de atribución y licencia del repositorio de Lichess identifica el conjunto `cburnett` como obra de Colin M. L. Burnett y lo señala como GPLv2+. Consulta:

- [Avisos de copyright y licencias de Lichess](https://github.com/lichess-org/lila/blob/master/COPYING.md)
- [Directorio de piezas cburnett en Lichess](https://github.com/lichess-org/lila/tree/master/public/piece/cburnett)

Según la información facilitada para este proyecto, las piezas se utilizan sin modificar. Deben conservarse los avisos de autoría y el texto de licencia que acompañen a los archivos redistribuidos. Comprueba que `chessstudio/pieces/LICENSE.txt` y, si se incluye, `chessstudio/pieces/GPL-2.0.txt` estén presentes y correspondan efectivamente a los recursos distribuidos.

La indicación GPL-2.0-or-later permite al receptor aplicar una versión posterior de la GPL a ese material, conforme a los términos de la licencia. No debe presentarse como si la autoría o la licencia original de las piezas desaparecieran o se sustituyeran por la licencia del resto del proyecto.

## 3. Motores UCI: no incluidos ni redistribuidos

Chess Game Manager **no incluye, descarga, aloja ni redistribuye Stockfish ni ningún otro motor UCI**.

La aplicación permite al usuario seleccionar un ejecutable UCI que haya obtenido por su cuenta. Por tanto:

- No se incluyen ejecutables, bibliotecas ni código fuente de Stockfish en este repositorio.
- No se presenta Stockfish como parte de Chess Game Manager ni como una dependencia empaquetada.
- Cada usuario es responsable de obtener el motor de una fuente legítima y respetar las condiciones de su licencia.
- Si en el futuro se decide distribuir un motor junto con la aplicación, habrá que revisar previamente su licencia y cumplir todas las obligaciones de redistribución correspondientes.

Referencia: [sitio oficial de Stockfish](https://stockfishchess.org/).

## 4. Servicios externos y token de Lichess

La aplicación puede conectarse a servicios de Lichess para consultar su explorador de aperturas y descargar partidas destacadas.

- Cada usuario configura su propio token.
- El token no se incluye en el repositorio.
- El uso de los servicios de Lichess está sujeto a sus [términos de servicio](https://lichess.org/terms-of-service) y a las condiciones aplicables a su API.
- La marca, el nombre y los servicios de Lichess pertenecen a sus respectivos titulares. La mención de Lichess identifica una integración y no implica patrocinio, afiliación ni aprobación del proyecto.

## 5. Licencia del proyecto y compatibilidad

El código propio de Chess Game Manager se publica bajo **GPL-3.0-or-later**, según el archivo `LICENSE`.

La selección de esta licencia tiene en cuenta, entre otros aspectos, el uso de `python-chess`, que se publica bajo GPL-3.0-or-later. Los recursos y componentes de terceros conservan sus propias licencias y avisos.

No se debe interpretar esta sección como una certificación automática de compatibilidad de todos los componentes. Para cada versión pública:

1. Comprueba las dependencias exactas de `requirements.txt`.
2. Identifica las licencias de las versiones realmente utilizadas.
3. Revisa los módulos de Qt/PySide6 utilizados y sus condiciones.
4. Conserva los avisos de copyright y los textos de licencia de los recursos incluidos.
5. Actualiza este archivo cuando se añadan, retiren o sustituyan dependencias o recursos.

## 6. Aviso

Este documento es informativo y no constituye asesoramiento jurídico ni una garantía de que se hayan satisfecho todas las obligaciones de licencia. Se ha redactado a partir de los componentes y recursos identificados para el proyecto; la revisión definitiva requiere contrastar el código, los archivos distribuidos y las versiones concretas de todas las dependencias.

Si se detecta un componente de terceros que no figure aquí, debe añadirse su nombre, versión, procedencia, licencia, uso y los avisos que exija su licencia antes de publicar una distribución que lo incluya.
