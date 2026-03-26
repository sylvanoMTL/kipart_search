; KiPart Search - Inno Setup Installer Script
; Compile with: iscc /DMyAppVersion=X.Y.Z /DMyOutputDir=..\dist /DMySourceDir=..\dist\__main__.dist installer\kipart-search.iss

#define MyAppName "KiPart Search"
#define MyAppVersion "0.1.4"
#define MyAppPublisher "MecaFrog"
#define MyAppURL "https://github.com/sylvanoMTL/kipart-search"
#define MyAppExeName "kipart-search.exe"

; Overridable paths — build script passes these via /D flags
#ifndef MyOutputDir
  #define MyOutputDir "..\dist"
#endif
#ifndef MySourceDir
  #define MySourceDir "..\dist\__main__.dist"
#endif

[Setup]
; NOTE: AppId must NEVER change between versions - it is how Inno Setup
; detects existing installs for upgrade. Double braces escape literal braces.
AppId={{62ac5603-5867-4e62-9bdf-30df22d7bc2c}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir={#MyOutputDir}
OutputBaseFilename=kipart-search-{#MyAppVersion}-setup
Compression=lzma
SolidCompression=yes
CloseApplications=yes
CloseApplicationsFilter={#MyAppExeName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
DisableProgramGroupPage=yes

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\KiPartSearch');
    if DirExists(DataDir) then
    begin
      if MsgBox('Remove user data (search cache, settings, JLCPCB database)?'#13#10#13#10 +
                'Location: ' + DataDir, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
