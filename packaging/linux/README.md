# Acceso directo para una compilación local en Linux

Este directorio documenta cómo integrar en tu equipo una compilación local
creada con `python scripts/build_release.py`. Chess Games Manager publica código
fuente y **no distribuye binarios ni instaladores oficiales**.

Conserva la carpeta `dist/ChessGamesManager` completa en una ubicación
permanente de tu equipo, por ejemplo `/opt/ChessGamesManager` o
`~/.local/opt/ChessGamesManager`.

Copia el icono y el lanzador a las rutas de usuario (sin permisos de
administrador):

```bash
mkdir -p ~/.local/share/icons/hicolor/scalable/apps ~/.local/share/applications
cp packaging/linux/io.github.mkllnd1517.ChessGamesManager.svg \
  ~/.local/share/icons/hicolor/scalable/apps/
cp packaging/linux/io.github.mkllnd1517.ChessGamesManager.desktop \
  ~/.local/share/applications/
```

Edita el campo `Exec=` del archivo `.desktop` para que apunte a la ruta local
real:

```ini
Exec=/ruta/a/ChessGamesManager/ChessGamesManager %f
```

Después aparecerá como **Chess Games Manager** en el menú de aplicaciones y
podrá anclarse al escritorio o al panel. Para una instalación Python desde el
código fuente, `pip install .` crea el comando gráfico
`chess-games-manager`; en ese caso no hace falta cambiar
`Exec=chess-games-manager %f`.
