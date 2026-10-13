# 인수인계 — 로컬(사용자 PC)에서 이어서 개발하기

마지막 갱신: 2026-10-13 · 브랜치 `ccr-b82e9d65-r5iudt` · PR #17 (초안)

## 1. 지금 상태 한눈에
| 영역 | 상태 |
|---|---|
| Windows 에이전트 (Rust) | 구현 완료. GitHub Windows 러너 실제 환경 종단간 26/26 성공 |
| 내장 중계 + Cloudflare 빠른 터널 | 0.1.1 부터 기본값. 포트 충돌 시 빈 포트 자동 선택 |
| Android 앱 (Flutter) | 1차 완료. APK/AAB 는 CI 빌드. **실제 휴대폰 미검증** |
| 사용자 PC 실기 | **진행 중** — 터널 경유 hp-cli 접속·캡처·스트리밍 성공 (`TEST-RESULTS.md` C). 실제 휴대폰 미검증 |

## 2. 열린 문제 (사용자 PC 에서 발견)
1. ~~포트 8443 충돌~~ — 원인은 0.1.0 중복 실행(0.1.1 중복 실행 방지로 해결, 실기 확인).
   0.1.1 원본은 표시줄 `DrawTextW` 접근 위반으로 시작 직후 종료 → 수정·실기 확인 (`ERRORS.md`).
   cloudflared 가 에이전트 비정상 종료 후 남던 문제도 작업 개체로 수정·실기 확인.
   **사용자 PC 에 설치된 것은 아직 0.1.0** (자동 실행 등록이 설치본을 가리킴) → 새 설치 파일로 교체 필요.
2. `homepilot-agent.exe <명령> | Out-Host` 출력이 PowerShell 에서 한글 깨짐 → 0.1.1 의 `homepilot-cli.exe` 사용 (콘솔 프로그램)
3. 아직 확인 못 한 것: 실제 휴대폰 연결, 한글 입력·클릭(SendInput), 실제 fps, Cloudflare 터널 경유, 긴급 차단 단축키, 설치 프로그램 제거 동작

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
1. 사용자 PC 에서 0.1.1 실기 확인 → `docs/TEST-RESULTS.md` B 표 갱신
2. 실기 결과에 따른 수정 (특히 fps 가 낮으면 DXGI Desktop Duplication 캡처로 교체)
3. 고정 주소 결정 (도메인+이름 있는 터널 / VPS) — **비용 발생, 사용자 승인 필요**
4. Phase 4: AI 프로그램 관리 (등록한 프로그램만, Claude Code 는 공식 CLI 헤드리스 방식)

## 7. 지켜야 할 규칙 (원 지시서)
- 기존 프로젝트·사용자 파일 변경 금지 (`HomePilot-Remote/` 밖은 `.github/workflows/homepilot-remote.yml` 만)
- 테스트하지 않은 항목을 완료로 기록하지 않음 / 비용 발생 작업은 사전 승인 / 비밀값 소스 저장 금지
- 오류는 `docs/ERRORS.md`, 진행은 `docs/PROGRESS.md` 에 기록
