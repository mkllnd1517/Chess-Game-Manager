; Receta de instalador local para Chess Games Manager con Inno Setup 6.
; Ejecutar scripts/build_release.py en Windows compila PyInstaller y, si ISCC
; está disponible, invoca este archivo automáticamente. El proyecto no publica
; instaladores oficiales.

#define AppName "Chess Games Manager"
#define AppVersion "0.7.1"
#define AppPublisher "Chess Games Manager contributors"
#define AppURL "https://github.com/mkllnd1517/Chess-Game-Manager"
#define AppExeName "ChessGamesManager.exe"

[Setup]
AppId={{BE082B76-1393-4CC6-A013-CCEB69DCD6F2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\Chess Games Manager
DefaultGroupName=Chess Games Manager
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist\installer
OutputBaseFilename=Chess-Games-Manager-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=chessgamesmanager.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
ChangesAssociations=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
Source: "..\..\dist\ChessGamesManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Chess Games Manager"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Chess Games Manager"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Registro por usuario: no requiere permisos de administrador y permite abrir
; un PGN con doble clic tras instalar Chess Games Manager.
Root: HKCU; Subkey: "Software\Classes\.pgn"; ValueType: string; ValueName: ""; ValueData: "ChessGamesManager.pgn"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\ChessGamesManager.pgn"; ValueType: string; ValueName: ""; ValueData: "Partida PGN de Chess Games Manager"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\ChessGamesManager.pgn\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"
Root: HKCU; Subkey: "Software\Classes\ChessGamesManager.pgn\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Abrir Chess Games Manager"; Flags: nowait postinstall skipifsilent
