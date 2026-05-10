; =============================================================================
; ECLI — Windows Installer (NSIS, Unicode, x64)
; Accepts defines:
;   /DVERSION=0.1.0
;   /DOUTFILE="releases\0.1.0\ecli_0.1.0_win_x86_64_setup.exe"
;   /DINPUT_EXE="releases\0.1.0\ecli_0.1.0_win_x86_64.exe"
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
  !define INPUT_EXE "build\windows\dist\ecli.exe"
!endif
!ifndef OUTFILE
  !define OUTFILE "ecli_${VERSION}_win_x86_64_setup.exe"
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

; ------------------------------- Sections -------------------------------------

Section "Install" SEC_MAIN
  SetRegView 64
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
    "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "QuietUninstallString" "$\"$INSTDIR\Uninstall.exe$\" /S"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "DisplayIcon" "$INSTDIR\ecli.exe"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "NoRepair" 1

  ; Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Start Menu shortcut in folder
  CreateDirectory "$SMPROGRAMS\${COMPANY}"
  CreateShortCut "$SMPROGRAMS\${COMPANY}\${APPNAME}.lnk" "$INSTDIR\ecli.exe"
SectionEnd

Section "Uninstall"
  SetRegView 64
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
