; iOSLocationSimulator.iss
; Author: saxcodez  |  Copyright (c) 2026 saxcodez  |  License: MIT
;
; Wird von build_installer.ps1 automatisch mit ISCC.exe aufgerufen.
; Ergebnis: installer_output\iOSLocationSimulator-Setup.exe

#define MyAppName "iOS Location Simulator"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "saxcodez"
#define MyAppExeName "iOSLocationSimulator.exe"

[Setup]
AppId={{B3B7B6C7-6F9B-4E9E-9A9E-9F1A6E0B7A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=iOSLocationSimulator-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\pmd3\*"; DestDir: "{app}\pmd3"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\wintun.dll"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
