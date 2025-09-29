; Simple NSIS installer for ECLI
!define APPNAME "ECLI"
!define COMPANY "Cartesian School"
!define VERSION "0.1.0"
!define BINARY "ecli.exe"

OutFile "ecli-${VERSION}-setup.exe"
InstallDir "$PROGRAMFILES64\${COMPANY}\${APPNAME}"
RequestExecutionLevel admin

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  File /oname=${BINARY} "..\..\build\windows\dist\ecli.exe"
  ; Add to PATH
  WriteRegStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path" "$%PATH%;$INSTDIR"
  ; Start menu shortcut
  CreateShortCut "$SMPROGRAMS\${APPNAME}.lnk" "$INSTDIR\${BINARY}"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\${BINARY}"
  RMDir "$INSTDIR"
SectionEnd
