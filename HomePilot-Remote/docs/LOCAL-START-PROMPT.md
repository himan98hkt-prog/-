# 로컬 Claude Code 에 붙여넣을 시작 프롬프트

아래 내용을 사용자 PC 의 Claude Code(데스크톱 앱 또는 터미널)에 그대로 붙여넣으면 이어서 작업을 시작합니다.

---

HomePilot Remote 프로젝트를 이 Windows PC 에서 이어서 진행해 줘. 한국어로, 초보자도 이해하게 안내해 줘.

1. 저장소 준비 (이미 있으면 건너뜀):
   `git clone https://github.com/himan98hkt-prog/-.git C:\AI-Projects\HomePilot-src` 후
   `cd C:\AI-Projects\HomePilot-src` → `git checkout ccr-b82e9d65-r5iudt`
2. `HomePilot-Remote/docs/HANDOFF.md` 를 먼저 읽고 그 규칙·순서를 따를 것.
   (모든 작업은 `HomePilot-Remote/` 안에서만. 같은 저장소의 기존 앱 파일은 절대 수정 금지)
3. 지금 상황: 사용자 PC 에 0.1.0 설치됨, cloudflared 설치됨, config.json 에 local_relay=true / tunnel=quick.
   0.1.0 은 "포트 8443 사용 중(os error 10048)" 오류로 종료됨 → 브랜치 최신(0.1.1)은 빈 포트 자동 선택으로 수정됨.
4. 할 일:
   - 개발 도구(Rust 등) 확인. 설치가 필요하면 무엇을 왜 설치하는지 먼저 설명하고 동의받기
   - `cd HomePilot-Remote` → `cargo test --workspace` → `cargo build --release --workspace`
   - 이전 HomePilot 종료(`taskkill /IM homepilot-agent.exe /F`) 후 `target\release\homepilot-agent.exe` 실행
   - 1분 안에 "휴대폰 연결 주소" 알림 확인, `target\release\homepilot-cli.exe info` 로 장치 ID·주소 확인
   - 문제 시 `%LOCALAPPDATA%\HomePilot\Agent\logs\` 의 agent.log·crash.log 로 원인 분석 후 수정
   - 휴대폰 APK 설치·연결을 안내하고 결과를 `docs/TEST-RESULTS.md` 에 성공/실패/미검증으로 기록
   - 수정 후 `cargo fmt`, `cargo clippy --workspace --all-targets -- -D warnings`, 테스트 통과 → 같은 브랜치에 커밋·푸시
5. 규칙: 테스트 안 한 항목은 완료 처리 금지 / 비용 발생 작업은 사전 승인 / UAC 우회·보안 해제 금지 / 비밀값 소스 저장 금지 /
   실제 PC 에서 tests/e2e.sh 를 돌릴 때는 `HOMEPILOT_INPUT_DRY_RUN=1` 설정 (테스트가 Ctrl+C 등을 실제로 입력함)
