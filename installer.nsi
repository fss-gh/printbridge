; PrintBridge — NSIS Installer Script
; Build with: makensis installer.nsi
; Requires NSIS installed on Windows: https://nsis.sourceforge.io/

!include "MUI2.nsh"

; ─── General ──────────────────────────────────────────────────────────
Name "PrintBridge"
OutFile "PrintBridge-Setup.exe"
InstallDir "$LOCALAPPDATA\PrintBridge"
RequestExecutionLevel user

; ─── Version Info ─────────────────────────────────────────────────────
VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName" "PrintBridge"
VIAddVersionKey "CompanyName" "PrintBridge"
VIAddVersionKey "LegalCopyright" "© 2024-2026 PrintBridge Contributors"
VIAddVersionKey "FileDescription" "PrintBridge Installer"
VIAddVersionKey "FileVersion" "1.0.0"
VIAddVersionKey "ProductVersion" "1.0.0"

; ─── UI ───────────────────────────────────────────────────────────────
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "PrintBridge"
!define MUI_WELCOMEPAGE_TEXT "This wizard will install PrintBridge on your computer.$\r$\n$\r$\nPrintBridge is a silent local printing agent that enables web applications to print directly to local printers.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN "$INSTDIR\PrintBridge.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch PrintBridge"

; ─── Pages ────────────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; ─── Language ─────────────────────────────────────────────────────────
!insertmacro MUI_LANGUAGE "English"

; ─── Install Section ──────────────────────────────────────────────────
Section "Install"
    SetOutPath "$INSTDIR"

    ; Stop running agent before install (ignore errors if not running)
    nsExec::ExecToLog 'taskkill /F /IM "PrintBridge.exe"'

    ; Copy files
    File "dist\PrintBridge.exe"
    File "icon.ico"
    File "icon.png"

    ; Create uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Start menu shortcuts
    CreateDirectory "$SMPROGRAMS\PrintBridge"
    CreateShortcut "$SMPROGRAMS\PrintBridge\PrintBridge.lnk" "$INSTDIR\PrintBridge.exe" "" "$INSTDIR\icon.ico"
    CreateShortcut "$SMPROGRAMS\PrintBridge\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

    ; Desktop shortcut
    CreateShortcut "$DESKTOP\PrintBridge.lnk" "$INSTDIR\PrintBridge.exe" "" "$INSTDIR\icon.ico"

    ; Auto-start on login (registry)
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" \
        "PrintBridge" '"$INSTDIR\PrintBridge.exe"'

    ; Add/Remove Programs entry
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PrintBridge" \
        "DisplayName" "PrintBridge"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PrintBridge" \
        "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PrintBridge" \
        "DisplayIcon" "$INSTDIR\icon.ico"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PrintBridge" \
        "Publisher" "PrintBridge Contributors"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PrintBridge" \
        "DisplayVersion" "1.0.0"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PrintBridge" \
        "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PrintBridge" \
        "NoRepair" 1
SectionEnd

; ─── Uninstall Section ────────────────────────────────────────────────
Section "Uninstall"
    ; Stop running agent
    nsExec::ExecToLog 'taskkill /F /IM "PrintBridge.exe"'

    ; Remove auto-start
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "PrintBridge"

    ; Remove Add/Remove Programs entry
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PrintBridge"

    ; Remove files
    Delete "$INSTDIR\PrintBridge.exe"
    Delete "$INSTDIR\icon.ico"
    Delete "$INSTDIR\icon.png"
    Delete "$INSTDIR\Uninstall.exe"

    ; Remove shortcuts
    Delete "$SMPROGRAMS\PrintBridge\PrintBridge.lnk"
    Delete "$SMPROGRAMS\PrintBridge\Uninstall.lnk"
    RMDir "$SMPROGRAMS\PrintBridge"
    Delete "$DESKTOP\PrintBridge.lnk"

    ; Remove install dir
    RMDir "$INSTDIR"
SectionEnd
