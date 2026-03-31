; KiPart Search - Inno Setup Installer Script
; Compile with: iscc /DMyAppVersion=X.Y.Z /DMyOutputDir=..\dist /DMySourceDir=..\dist\__main__.dist installer\kipart-search.iss
;
; Replaces: installer/kipart-search.iss
;
; PLATFORM NOTE: Inno Setup is Windows-only.
; macOS uses .dmg (hdiutil) and Linux uses AppImage (appimagetool).
; See build_nuitka.py for cross-platform packaging stubs.
;
; UPDATE MECHANISM (2026-03-30):
; The in-app updater calls os.startfile() on the downloaded setup.exe,
; which is equivalent to the user double-clicking it.  Inno Setup handles
; everything from there:
;   - CloseApplications=yes → Restart Manager sends WM_CLOSE to the running app
;   - CloseApplicationsFilter → identifies which process to close
;   - /VERYSILENT mode → no UI, Restart Manager still works
;   - [Run] section → optional relaunch after install (interactive mode only)
;
; CHANGES FROM ORIGINAL:
;   1. ADDED [Run] section for post-install relaunch (interactive mode only)
;   2. ADDED comments explaining Restart Manager behaviour
;   3. All other settings UNCHANGED

#define MyAppName "KiPart Search"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "MecaFrog"
#define MyAppURL "https://github.com/sylvanoMTL/kipart_search"
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
; --- App closure via Windows Restart Manager ---
; These settings tell Inno Setup to use the Restart Manager to gracefully
; close kipart-search.exe before replacing its files.  This works in both
; interactive and /VERYSILENT mode.  The Restart Manager sends WM_CLOSE to
; the process, which PySide6/Qt handles as a graceful shutdown.
; This is why the old .bat shim's tasklist polling loop was redundant.
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

; --- NEW: Post-install relaunch ---
; In interactive mode (user double-clicked the installer): shows a
;   "Launch KiPart Search" checkbox on the final wizard page.
; In /VERYSILENT mode (in-app update): skipifsilent means this is skipped,
;   so the user relaunches from their shortcut.
;
; To auto-relaunch even in silent mode, remove "skipifsilent":
;   Filename: "{app}\{#MyAppExeName}"; Flags: nowait postinstall
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

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
