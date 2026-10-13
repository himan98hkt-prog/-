# 진행 상황 (중단 후 재시작용)

마지막 갱신: 2026-10-13

| Phase | 상태 | 비고 |
|---|---|---|
| 0. 환경 점검·기술 검증 | ✅ 완료 | `PHASE0-기술검토.md`. 사용자 PC 환경 값은 미확인 |
| 1. Windows 에이전트 | 🟡 구현·자동테스트 완료, **Windows 실기 검증 대기** | 아래 체크리스트 |
| 2. Android 앱 | 🟡 1차 구현 완료, **실제 휴대폰 검증 대기** | PC 목록·등록·대시보드·원격 화면·키보드. APK 는 CI 에서 빌드 |
| 3. 중계 서버 | 🟡 집 PC 단독 구성 완료 | 에이전트 내장 중계 + Cloudflare 빠른 터널(무료, 주소 변동). 고정 주소는 승인 대기 |
| 4~8 | ⏳ | |

## Phase 1 체크리스트
- [x] 설치/제거 — Inno Setup 스크립트 (`windows-agent/installer`), 현재 사용자 설치, UAC 불필요 (설치 파일 생성은 CI Windows 러너)
- [x] 사용자 동의 시 자동 실행 (설치 옵션·트레이 메뉴·`autostart on`, 기본 꺼짐)
- [x] PC 이름·장치 식별 (공개키 기반 장치 ID, DPAPI 보호 키)
- [x] 온라인/오프라인 (중계 연결 유지, 20초 핑, 90초 무응답 시 재연결)
- [x] CPU/RAM/GPU/디스크 (GPU 는 성능 카운터, 측정 불가 시 null)
- [x] 화면 캡처·실시간 전송 (GDI + JPEG, 축소/품질/FPS, 흐름 제어)
- [x] 승인된 원격 마우스·키보드 (권한 검사, 한글 유니코드 입력)
- [x] 모니터 선택
- [x] 연결 종료·긴급 차단 (Ctrl+Alt+F12, 트레이)
- [x] 실행 로그 (`%LOCALAPPDATA%\HomePilot\Agent\logs\agent.log.*`) + 접속 기록
- [x] 네트워크 재연결 (1→60초 지수 백오프 + 지터)
- [ ] **Windows 실기 확인** — 사용자 PC 에서 `docs/설치-및-시험-가이드.md` 의 시험 절차 실행 필요

## 다시 시작하는 방법
```bash
cd HomePilot-Remote
cargo test --workspace          # 단위 테스트
cargo build --workspace && bash tests/e2e.sh   # 종단간 테스트 (Linux/Git Bash)
cargo build --release --target x86_64-pc-windows-gnu -p homepilot-agent   # Linux 에서 Windows exe 만들기 (mingw-w64 필요)
```

## Phase 2 체크리스트
- [x] 프로토콜 Dart 구현 (Noise XX) + Rust 에이전트와 상호 운용 테스트 (`tests/app-interop.sh`)
- [x] PC 등록 (주소·장치 ID, 확인 코드 표시, 장치 ID 로 PC 키 검증)
- [x] PC 목록, 상태 대시보드 (CPU/메모리/GPU/디스크, 모니터 수)
- [x] 원격 화면: 확대/축소, 터치패드·직접 터치, 탭=클릭, 길게=우클릭, 드래그, 스크롤, 가로 화면, 화질, 모니터 선택, fps·지연 표시, 종료
- [x] 한글/영문 키보드 (조합 완료 문자 전송), 특수키 줄
- [x] 설정 (휴대폰 이름, 기본 화질, 기기 키 초기화)
- [ ] 로그인/계정 다중 인증 — 서버 계정 체계(Phase 3 정식 서버)와 함께
- [ ] 앱 잠금(생체 인증) — Phase 5
- [ ] AI 프로그램 관리 (Phase 4), 파일 관리
- [ ] **실제 휴대폰에서 동작 확인**

## 다음 할 일
1. 사용자: `docs/휴대폰-연결-가이드.md` 대로 설치·연결 → 결과를 `TEST-RESULTS.md` 에 기록
2. 고정 주소 (도메인 또는 VPS) 여부 결정 — **비용 발생, 사용자 승인 필요**
3. 실기 피드백 반영 후 Phase 4 (AI 프로그램 관리)
