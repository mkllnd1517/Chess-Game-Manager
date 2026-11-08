# Acceso directo en Linux

Tras ejecutar `python scripts/build_release.py`, conserva la carpeta
`dist/ChessStudio` completa en una ubicación permanente, por ejemplo
`/opt/ChessStudio` o `~/.local/opt/ChessStudio`.

Copia el icono y el lanzador a las rutas de usuario (sin permisos de
administrador):

```bash
mkdir -p ~/.local/share/icons/hicolor/scalable/apps ~/.local/share/applications
cp packaging/linux/io.github.mkllnd1517.ChessStudio.svg \
  ~/.local/share/icons/hicolor/scalable/apps/
cp packaging/linux/io.github.mkllnd1517.ChessStudio.desktop \
  ~/.local/share/applications/
```

Edita el campo `Exec=` del archivo `.desktop` para que apunte a la ruta real:

```ini
Exec=/ruta/a/ChessStudio/ChessStudio %f
```

Después aparecerá como **ChessStudio** en el menú de aplicaciones y podrá
anclarse al escritorio o al panel. Para una instalación Python sin binario,
`pip install .` crea el comando gráfico `chessstudio`; en ese caso no hace
falta cambiar `Exec=chessstudio %f`.
