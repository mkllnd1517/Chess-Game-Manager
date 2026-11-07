# Avisos de terceros (Third-Party Notices)

ChessStudio se distribuye bajo **GPL-3.0-or-later** (ver `LICENSE`). Este
archivo resume las licencias de los componentes de terceros que utiliza.

## Dependencias de Python (se instalan con pip, no se incluyen en el repo)

| Componente | Licencia | Uso | Notas |
|---|---|---|---|
| [python-chess](https://github.com/niklasf/python-chess) (`chess`) | **GPL-3.0-or-later** | Reglas, PGN, UCI | Es la razón por la que ChessStudio debe ser GPL-3.0+. |
| [PySide6 / Qt for Python](https://wiki.qt.io/Qt_for_Python) | **LGPL-3.0** (también comercial) | Interfaz gráfica | Se enlaza dinámicamente; el usuario instala PySide6 con pip. Compatible con GPL-3.0. |
| [keyring](https://github.com/jaraco/keyring) | **MIT** | Llavero del sistema para el token | Opcional; compatible con GPL-3.0. |

## Recursos gráficos incluidos en el repositorio

| Recurso | Autor | Licencia | Ubicación |
|---|---|---|---|
| Piezas de ajedrez "cburnett" (12 SVG) | Colin M. L. Burnett, vía [Lichess](https://github.com/lichess-org/lila/tree/master/public/piece/cburnett) | **GPL-2.0-or-later** | `chessstudio/pieces/` |

Las piezas se usan **sin modificar** y se redistribuyen bajo la opción
GPL-3.0+ que permite la cláusula "or any later version" de la GPLv2+.
Consulta `chessstudio/pieces/LICENSE.txt` y `chessstudio/pieces/GPL-2.0.txt`.

## Software que NO se incluye (lo aporta el usuario)

- **Stockfish** u otros motores UCI: ChessStudio no incluye ningún motor. El
  usuario selecciona su propio ejecutable. Stockfish es GPL-3.0; si decides
  distribuirlo junto a la app, debes cumplir su licencia (incluir su código
  fuente o una oferta de fuente, y su licencia).
- **Token de Lichess**: cada usuario crea el suyo. El acceso a la API de
  Lichess está sujeto a los [términos de servicio de Lichess](https://lichess.org/terms-of-service).

## Compatibilidad de licencias

GPL-3.0-or-later (app) es compatible con:
- GPL-3.0-or-later (python-chess) ✔
- GPL-2.0-or-later (piezas cburnett, vía la cláusula "or later") ✔
- LGPL-3.0 (PySide6, enlazado dinámico) ✔
- MIT (keyring) ✔

> Nota: esta información es orientativa y no constituye asesoramiento legal.
> Si vas a publicar o distribuir el proyecto, revisa las licencias enlazadas y,
> si tienes dudas, consulta a un profesional.
