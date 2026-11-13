; Instalador de Windows para ChessStudio — generado con Inno Setup 6.
; Ejecutar scripts/build_release.py en Windows: compila PyInstaller y, si
; ISCC está disponible, invoca este archivo automáticamente.

#define AppName "ChessStudio"
#define AppVersion "0.7.0"
#define AppPublisher "Chess Game Manager contributors"
#define AppURL "https://github.com/mkllnd1517/Chess-Game-Manager"
#define AppExeName "ChessStudio.exe"

[Setup]
AppId={{BE082B76-1393-4CC6-A013-CCEB69DCD6F2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\ChessStudio
DefaultGroupName=ChessStudio
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist\installer
OutputBaseFilename=ChessStudio-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=chessstudio.ico
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
Source: "..\..\dist\ChessStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\ChessStudio"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\ChessStudio"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Registro por usuario: no requiere permisos de administrador y permite abrir
; un PGN con doble clic tras instalar ChessStudio.
Root: HKCU; Subkey: "Software\Classes\.pgn"; ValueType: string; ValueName: ""; ValueData: "ChessStudio.pgn"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\ChessStudio.pgn"; ValueType: string; ValueName: ""; ValueData: "Partida PGN de ChessStudio"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\ChessStudio.pgn\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"
Root: HKCU; Subkey: "Software\Classes\ChessStudio.pgn\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Abrir ChessStudio"; Flags: nowait postinstall skipifsilent
