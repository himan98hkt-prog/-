# HomePilot Remote

집의 Windows PC 를 Android 스마트폰에서 안전하게 원격 제어·관리하는 프로그램입니다.

- **보안 우선**: 종단간 암호화(Noise XX), PC 에서 직접 승인해야만 휴대폰 등록, 접속 중 화면 표시, Ctrl+Alt+F12 긴급 차단, 접속 기록
- **어디서나 연결**: PC·휴대폰 모두 바깥으로 중계 서버에 접속 → 공유기 포트 개방 없이 모바일 데이터에서도 동작
- **중계 서버는 내용을 볼 수 없음**: 암호문만 전달, 화면·입력·비밀을 저장하지 않음

| 폴더 | 내용 |
|---|---|
| `windows-agent/` | Windows PC 에이전트 (Rust) + 설치 프로그램 스크립트 |
| `server/` | 중계 서버 |
| `shared/protocol/` | 공용 통신 프로토콜 · 암호화 |
| `android-app/` | Flutter Android 앱 |
| `tests/` | 종단간 테스트, 시험 클라이언트 `hp-cli` |
| `docs/` | 기술 검토, 설계, 진행 상황, 테스트 결과, 설치 가이드 |
| `releases/` | 빌드 결과물 (저장소에는 올리지 않음, CI 아티팩트로 제공) |

**휴대폰으로 쓰기: [`docs/휴대폰-연결-가이드.md`](docs/휴대폰-연결-가이드.md)** · PC 단독 시험: [`docs/설치-및-시험-가이드.md`](docs/설치-및-시험-가이드.md) · 현재 상태: [`docs/PROGRESS.md`](docs/PROGRESS.md)

이 소프트웨어는 일부 Independent JPEG Group 의 작업에 기반합니다 (jpeg-encoder, IJG 라이선스).
