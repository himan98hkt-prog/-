# 인수인계 — 로컬(사용자 PC)에서 이어서 개발하기

마지막 갱신: 2026-10-13 · 브랜치 `ccr-b82e9d65-r5iudt` · PR #17 (초안)

## 1. 지금 상태 한눈에 (에이전트 0.3.0 · 앱 1.0.0)
| 영역 | 상태 (실기 결과: `TEST-RESULTS.md` C~I) |
|---|---|
| 원격 화면·조작 | 실기 성공. H.264 하드웨어 동영상(데이터 1/15), JPEG 대체 |
| 60fps·게임 키패드 | DXGI 캡처로 휴대폰 실측 45~55fps (Pro). 게임 키패드(조이스틱·시점 패드·꾹 누르기 버튼, 3종) 무료. 결과 J |
| 고정 접속 | 같은 Wi-Fi 자동 찾기 + 무료 주소 안내판(ntfy.sh). PC 재시작 후 자동 재연결 실기 성공 |
| 파일·클립보드·소리 | 실기 성공 (휴대폰→PC 붙여넣기 Ctrl+V 는 실기 생략) |
| AI 작업 관리 | Ollama 실기 성공. Claude Code 는 이 PC 가 미로그인이라 실제 작업 미검증 |
| 결제(Pro) | Google Play 결제 코드·화면 완료. 상품 미등록이라 실제 결제 미검증 |
| 디자인 | 새 아이콘(앱·트레이 4상태·실행 파일·설치 파일), 스토어 이미지 |
| 출시 준비 | 서명 AAB(키패드 포함 재빌드), 설치 파일 0.3.0, 스토어 문서 → `docs/store/RELEASE-CHECKLIST.md` |
| 사용자 PC | 설치본 0.3.0 으로 업그레이드 |

## 2. 열린 문제
1. 같은 Wi-Fi 바로 접속: 사용자 PC 네트워크가 "공용" 이고 Windows 방화벽이 차단 규칙을 만들어 둠 → 인터넷 경로로 동작. (방화벽 허용은 사용자 판단)
2. 미검증: 실제 게임 안에서 키패드(스캔코드) 동작, 한글 입력(adb 로 입력 불가), 로그인된 Claude Code 작업, 실제 Play 결제, 설치 프로그램 제거, 여러 모니터
3. 터치패드 모드 첫 이동 시 커서가 앱이 기억한 위치로 순간이동 (PC 의 실제 커서 위치를 받아오도록 개선 필요)
4. 결제 확인은 휴대폰에서만 함 (서버 검증 없음)

## 3. 로컬 개발 환경 준비 (Windows)
```powershell
# 저장소
git clone https://github.com/himan98hkt-prog/-.git C:\AI-Projects\HomePilot-src
cd C:\AI-Projects\HomePilot-src
git checkout ccr-b82e9d65-r5iudt
cd HomePilot-Remote

# Rust (MSVC) — https://rustup.rs 설치 후
cargo test --workspace
cargo build --release --workspace        # target\release\homepilot-agent.exe, homepilot-cli.exe, homepilot-relay.exe, hp-cli.exe

# 설치 파일 (선택) — Inno Setup 6 설치 후
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DAppVersion=0.1.1 /DSourceDir=..\..\target\release windows-agent\installer\homepilot-agent.iss

# Android 앱 (선택) — Flutter 3.47.x + Android Studio(SDK) 설치 후
cd android-app; flutter pub get; flutter test; flutter build apk --release
```
> 테스트 스크립트(`tests/*.sh`)는 Git Bash 에서 실행. Windows 에서 e2e 를 돌릴 때는 **반드시**
> `HOMEPILOT_INPUT_DRY_RUN=1` 을 설정하거나, 실제 입력이 들어가도 괜찮은 상태로 실행 (테스트가 Ctrl+C·문자열을 실제로 입력함).

## 4. 빠른 실기 확인 순서 (사용자 PC)
1. 실행 중인 HomePilot 종료: `taskkill /IM homepilot-agent.exe /F`
2. 새로 빌드한 `target\release\homepilot-agent.exe` 실행 (또는 0.1.1 설치 파일)
3. 1분 내 "휴대폰 연결 주소" 알림 → 트레이 우클릭 → "휴대폰 연결 정보"
4. 문제 시 로그: `%LOCALAPPDATA%\HomePilot\Agent\logs\agent.log.*`, 비정상 종료: `crash.log`
5. 같은 PC 안에서 휴대폰 없이 시험: `hp-cli.exe --relay ws://127.0.0.1:<포트> --device <장치ID> connect` (포트는 로그의 "내장 중계 서버 시작" 줄)
6. 휴대폰: APK 설치 → PC 추가 (터널 주소 + 장치 ID) → PC 확인창 [예] → 원격 화면

## 5. 코드 지도
| 경로 | 내용 |
|---|---|
| `shared/protocol/` | Noise XX + AEAD, 메시지 규격 (앱이 따라야 하는 규격) |
| `windows-agent/src/lib.rs` | 명령줄·실행 진입점 (`homepilot-agent` = 트레이, `homepilot-cli` = 콘솔) |
| `windows-agent/src/session.rs` | 핸드셰이크·등록 승인·권한·명령 처리 |
| `windows-agent/src/home_relay.rs` | 내장 중계 + cloudflared 실행·감시 |
| `windows-agent/src/platform/win/` | GDI 캡처, SendInput, 트레이·표시줄·단축키, DPAPI, PDH(GPU) |
| `server/` | 중계 서버 (라이브러리 + 단독 실행) |
| `android-app/lib/` | Flutter 앱 (`protocol/` 은 순수 Dart) |
| `tests/` | e2e.sh, home-mode.sh, app-interop.sh, hp-cli |
| `docs/` | 기술검토, 설계, 진행, 오류기록, 테스트결과, 가이드 |

## 6. 다음 할 일 (우선순위)
1. 출시: `docs/store/RELEASE-CHECKLIST.md` 의 사용자 작업 (Play 계정 $25, 상품 등록, 개인정보처리방침 공개)
2. 경쟁력: 60fps (DXGI Desktop Duplication 캡처 + 하드웨어 H.264), 게임용 가상 키패드, 여러 모니터 동시 보기
3. AI 작업 완료를 앱이 꺼져 있어도 휴대폰 알림으로 (ntfy 구독 또는 FCM)
4. 터치패드 커서 위치 동기화, 결제 서버 검증

## 7. 지켜야 할 규칙 (원 지시서)
- 기존 프로젝트·사용자 파일 변경 금지 (`HomePilot-Remote/` 밖은 `.github/workflows/homepilot-remote.yml` 만)
- 테스트하지 않은 항목을 완료로 기록하지 않음 / 비용 발생 작업은 사전 승인 / 비밀값 소스 저장 금지
- 오류는 `docs/ERRORS.md`, 진행은 `docs/PROGRESS.md` 에 기록
