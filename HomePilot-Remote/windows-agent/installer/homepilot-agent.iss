; HomePilot Remote - Windows 에이전트 설치 프로그램 (Inno Setup 6)
; 빌드: iscc /DAppVersion=0.1.0 /DSourceDir=..\..\target\release homepilot-agent.iss
;
; - 현재 사용자 범위 설치 (관리자 권한/UAC 불필요, 보안 설정 변경 없음)
; - "Windows 시작 시 자동 실행" 은 기본 해제 상태 → 사용자가 직접 체크해야 등록된다 (사전 동의)
; - 제거 시 자동 실행 등록을 지우고, 장치 키·등록 기기 목록 삭제 여부를 묻는다

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\target\release"
#endif

[Setup]
AppId={{6C1F0E52-3A4B-4C8E-9C61-0B7B5B2E4A11}
AppName=HomePilot Remote Agent
AppVersion={#AppVersion}
AppPublisher=HomePilot
DefaultDirName={localappdata}\Programs\HomePilot Remote
DefaultGroupName=HomePilot Remote
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\releases
OutputBaseFilename=HomePilot-Agent-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=HomePilot Remote Agent
SetupIconFile=..\assets\homepilot.ico
UninstallDisplayIcon={app}\homepilot-agent.exe
CloseApplications=yes
MinVersion=10.0

[Languages]
#if FileExists(AddBackslash(CompilerPath) + "Languages\Korean.isl")
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
#else
Name: "english"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "autostart"; Description: "Windows 로그인 시 HomePilot 자동 실행 (원격 접속을 받으려면 필요)"; Flags: unchecked
Name: "desktopicon"; Description: "바탕 화면 바로가기 만들기"; Flags: unchecked

[Files]
Source: "{#SourceDir}\homepilot-agent.exe"; DestDir: "{app}"; Flags: ignoreversion
; 명령 프롬프트/PowerShell 용 (결과가 화면에 출력됨)
Source: "{#SourceDir}\homepilot-cli.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\HomePilot Remote"; Filename: "{app}\homepilot-agent.exe"
Name: "{group}\HomePilot Remote 제거"; Filename: "{uninstallexe}"
Name: "{userdesktop}\HomePilot Remote"; Filename: "{app}\homepilot-agent.exe"; Tasks: desktopicon

[Registry]
; 사용자가 자동 실행을 선택한 경우에만 등록 (현재 사용자 Run 키, 관리자 권한 불필요)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "HomePilotRemoteAgent"; ValueData: """{app}\homepilot-agent.exe"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\homepilot-agent.exe"; Description: "지금 HomePilot 실행"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM homepilot-agent.exe /F"; Flags: runhidden; RunOnceId: "StopAgent"

[Code]
// 트레이 메뉴에서 켠 자동 실행 등록도 함께 제거한다
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'HomePilotRemoteAgent');
    if MsgBox('이 PC 의 장치 키와 등록된 휴대폰 목록, 접속 기록도 삭제할까요?' #13#10 +
              '(삭제하면 다시 설치할 때 휴대폰을 새로 등록해야 합니다)', mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(ExpandConstant('{userappdata}\HomePilot\Agent'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\HomePilot\Agent'), True, True, True);
    end;
  end;
end;
