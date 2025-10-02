; =============================================================================
; ECLI — Windows Installer (NSIS, Unicode, x64)
; Accepts defines:
;   /DVERSION=0.1.0
;   /DOUTFILE="releases\0.1.0\ecli_0.1.0_win_x64.exe"
;   /DINPUT_EXE="build\windows\dist\ecli.exe"
; Defaults are provided for local runs.
; =============================================================================

Unicode true
RequestExecutionLevel admin
SetCompressor /SOLID lzma
SetCompressorDictSize 32

!define APPNAME   "ECLI"
!define COMPANY   "Cartesian School"
!ifndef VERSION
  !define VERSION "0.1.0"
!endif
!ifndef INPUT_EXE
  !define INPUT_EXE "..\..\build\windows\dist\ecli.exe"
!endif
!ifndef OUTFILE
  !define OUTFILE "ecli-${VERSION}-setup.exe"
!endif

OutFile "${OUTFILE}"
InstallDir "$PROGRAMFILES64\${COMPANY}\${APPNAME}"
InstallDirRegKey HKLM "Software\${COMPANY}\${APPNAME}" "InstallDir"

VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName"     "${APPNAME}"
VIAddVersionKey "CompanyName"     "${COMPANY}"
VIAddVersionKey "FileDescription" "${APPNAME} Installer"
VIAddVersionKey "FileVersion"     "${VERSION}"

; Pages
!include "MUI2.nsh"
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

; -------------- Helpers: PATH update with dedupe + broadcast ------------------
!define ENV_KEY 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
!macro EnvPathAppend PathToAdd
  Push $0
  Push $1
  ReadRegStr $0 HKLM ${ENV_KEY} "Path"
  StrCpy $1 "$0"
  ; ensure semicolon separation
  StrCpy $1 "$1;"
  StrCpy $1 "$1$%PathToAdd%"
  StrCpy $1 "$1;"
  ; dedupe: remove duplicate occurrences of ;%PathToAdd%;
  ; (simple approach; avoids plugin dependency)
  StrReplace $1 $1 ";%PathToAdd%;;" ";" ; collapse
  StrReplace $1 $1 ";%PathToAdd%;;" ";" ; twice for safety
  ; if not present, append
  FindStr $0 "$0" "%PathToAdd%" ; crude check
  StrCmp $0 "" 0 +3
    StrCpy $1 "$0;%PathToAdd%"
    WriteRegExpandStr HKLM ${ENV_KEY} "Path" "$1"
    System::Call 'USER32::SendMessageA(i -1, i ${WM_SETTINGCHANGE}, i 0, t "Environment")'
  Pop $1
  Pop $0
!macroend

!macro EnvPathRemove PathToRemove
  Push $0
  Push $1
  ReadRegStr $0 HKLM ${ENV_KEY} "Path"
  ; remove ;PathToRemove and PathToRemove; and standalone
  StrReplace $1 $0 ";%PathToRemove%" ""
  StrReplace $1 $1 "%PathToRemove%;" ""
  StrReplace $1 $1 "%PathToRemove%" ""
  WriteRegExpandStr HKLM ${ENV_KEY} "Path" "$1"
  System::Call 'USER32::SendMessageA(i -1, i ${WM_SETTINGCHANGE}, i 0, t "Environment")'
  Pop $1
  Pop $0
!macroend

; ------------------------------- Sections -------------------------------------

Section "Install" SEC_MAIN
  SetOutPath "$INSTDIR"
  File "/oname=ecli.exe" "${INPUT_EXE}"

  ; Write registry for uninstall + install dir
  WriteRegStr HKLM "Software\${COMPANY}\${APPNAME}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "DisplayName" "${APPNAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "Publisher"   "${COMPANY}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "UninstallString" "$INSTDIR\Uninstall.exe"

  ; Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Start Menu shortcut in folder
  CreateDirectory "$SMPROGRAMS\${COMPANY}"
  CreateShortCut "$SMPROGRAMS\${COMPANY}\${APPNAME}.lnk" "$INSTDIR\ecli.exe"

  ; Add to PATH (machine) and broadcast change
  !insertmacro EnvPathAppend "$INSTDIR"
SectionEnd

Section "Uninstall"
  ; Remove PATH entry and broadcast
  !insertmacro EnvPathRemove "$INSTDIR"

  ; Remove shortcut
  Delete "$SMPROGRAMS\${COMPANY}\${APPNAME}.lnk"
  RMDir  "$SMPROGRAMS\${COMPANY}"

  ; Remove files and registry
  Delete "$INSTDIR\ecli.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir  "$INSTDIR"

  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
  DeleteRegKey HKLM "Software\${COMPANY}\${APPNAME}"
SectionEnd
