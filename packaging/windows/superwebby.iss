; Inno Setup script for Superwebby (per-user install, no admin needed).
; Build: iscc /DMyAppVersion=1.2.0 /DSourceDir=..\..\dist\superwebby /DOutDir=..\..\release packaging\windows\superwebby.iss
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\superwebby"
#endif
#ifndef OutDir
  #define OutDir "..\..\release"
#endif

[Setup]
AppId={{6F2B8C4E-2D3A-4F6B-9E51-5B1C0A7D9E21}
AppName=Superwebby
AppVersion={#MyAppVersion}
AppVerName=Superwebby {#MyAppVersion}
AppPublisher=Superwebby contributors
AppPublisherURL=https://github.com/superwebby/superwebby
AppSupportURL=https://github.com/superwebby/superwebby/issues
AppUpdatesURL=https://github.com/superwebby/superwebby/releases
DefaultDirName={localappdata}\Programs\Superwebby
DefaultGroupName=Superwebby
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutDir}
OutputBaseFilename=superwebby-{#MyAppVersion}-windows-x64-setup
SetupIconFile=..\..\assets\superwebby.ico
UninstallDisplayIcon={app}\superwebby.exe
LicenseFile=..\..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Superwebby"; Filename: "{app}\superwebby.exe"
Name: "{autoprograms}\Superwebby Dirty Browser (Private)"; Filename: "{app}\superwebby.exe"; Parameters: "--incognito"
Name: "{autoprograms}\Superwebby High Speed"; Filename: "{app}\superwebby.exe"; Parameters: "--high-speed"
Name: "{autodesktop}\Superwebby"; Filename: "{app}\superwebby.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\superwebby.exe"; Description: "{cm:LaunchProgram,Superwebby}"; Flags: nowait postinstall skipifsilent
