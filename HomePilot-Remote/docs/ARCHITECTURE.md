# HomePilot Remote — 구조와 보안 설계

## 구성 요소

| 폴더 | 내용 | 언어 | 상태 |
|---|---|---|---|
| `shared/protocol` | 통신 프로토콜 + 종단간 암호화 (에이전트·앱·서버 공용) | Rust | Phase 1 완료 |
| `windows-agent` | Windows PC 에이전트 (트레이 상주) | Rust + Win32 API | Phase 1 구현 완료, Windows 실기 검증 대기 |
| `server` | 중계 서버 (개발용 최소 구현) | Rust (axum) | Phase 1 용 최소 기능, Phase 3 에서 확장 |
| `tests/test-client` | `hp-cli` — 휴대폰 앱 대신 쓰는 시험 클라이언트 | Rust | 완료 |
| `android-app` | Flutter Android 앱 | Dart | Phase 2 예정 |

## 연결 흐름

```
 휴대폰(hp-cli/앱)           중계 서버                    Windows 에이전트
       |                         |  <-- wss /v1/agent/{장치ID} --|  (항상 연결 유지, 끊기면 1→60초 재연결)
       |-- wss /v1/client/{ID} ->|                               |
       |<-- {"t":"connected"} ---|--- {"t":"open","sid":N} ----->|
       |== Noise XX 핸드셰이크 (3개 메시지, 서버는 그대로 전달) ==|
       |== Hello → (미등록이면 PC 확인창) → Welcome ==============|
       |== 명령 / 화면 프레임 (ChaCha20-Poly1305) ================|
```

### 장치 ID = PC 공개키의 지문
- 장치 ID 는 PC 의 X25519 공개키 SHA-256 앞 10바이트(16진수 20자)입니다.
- 휴대폰은 핸드셰이크에서 받은 PC 공개키로 장치 ID 를 다시 계산해 **사용자가 입력한 ID 와 다르면 즉시 중단**합니다.
  → 중계 서버나 네트워크 중간자가 PC 를 사칭할 수 없습니다.

### 휴대폰 등록 (페어링)
1. PC 트레이 메뉴 "새 휴대폰 등록" (5분) — 처음 설치 시에는 자동으로 10분 열림
2. 휴대폰이 접속하면 PC 화면에 **확인창**: 휴대폰 이름, 기기 지문, 6자리 확인 코드
3. 휴대폰에도 같은 확인 코드 표시 → 같을 때만 PC 에서 [예] (기본 버튼은 [아니요])
4. 승인되면 휴대폰 공개키가 PC 의 `trusted_clients.json` 에 저장, 등록 대기 즉시 종료
5. 거부하면 등록 대기도 즉시 종료(공격 시도 차단). 확인창은 동시에 하나만 뜸

확인 코드는 핸드셰이크 해시에서 만들어지므로 중간자가 끼면 양쪽 코드가 달라집니다.

## 메시지 형식 (Android 앱이 맞춰야 하는 규격)

### 중계 계층
- 텍스트 프레임(JSON): `{"t":"connected"}`, `{"t":"offline"}`, `{"t":"agent_gone"}` (서버→휴대폰)
- 바이너리 프레임: 휴대폰 쪽은 암호문 그대로. (에이전트 쪽은 앞에 세션 ID 4바이트)

### 암호화 계층
- Noise 프로토콜 이름: `Noise_XX_25519_ChaChaPoly_BLAKE2s`, prologue: `HomePilot-Remote/1`
- 휴대폰 = initiator, PC = responder. 핸드셰이크 페이로드는 비어 있음
- 핸드셰이크 후 Noise split 키(k1: 휴대폰→PC, k2: PC→휴대폰)로 메시지마다 ChaCha20-Poly1305
  - nonce = 0x00000000 ‖ 카운터(u64 리틀엔디언), 방향별로 0부터 1씩 증가 (재전송·순서 바뀜은 복호화 실패)
- 확인 코드 = 핸드셰이크 해시 앞 4바이트(빅엔디언) mod 1,000,000 → `"123 456"`

### 응용 계층 (평문)
- `0x01` + JSON: 제어 메시지 (`type` 필드, snake_case). 예:
  - 휴대폰→PC: `hello`, `get_status`, `list_monitors`, `start_stream{monitor,quality,scale_pct,max_fps}`, `stop_stream`, `frame_ack{frame_id}`, `mouse_move{x,y}`(0~1 비율), `mouse_button`, `mouse_click{button,double}`, `wheel{dx,dy}`, `key_text{text}`, `key{key,down}`, `key_combo{keys}`, `ping{t}`, `bye`
  - PC→휴대폰: `welcome`, `pairing_pending{sas}`, `denied{reason}`, `status`, `monitors`, `stream_started`, `stream_stopped`, `pong`, `error`, `session_ended{reason}`
- `0x02` + 29바이트 헤더 + JPEG: 화면 프레임
  `frame_id u32 | monitor u8 | width u32 | height u32 | src_width u32 | src_height u32 | captured_ms u64` (모두 리틀엔디언)
- 흐름 제어: PC 는 ack 없이 최대 2프레임만 보냄. 밀리면 최신 프레임만 남기고 버림 → 지연이 쌓이지 않음

정확한 정의는 `shared/protocol/src/app.rs` 이며 JSON 형태는 단위 테스트로 고정되어 있습니다.

## 보안 요구사항 대응표 (Phase 5 요구 중 Phase 1 에 구현된 것)

| 요구 | 구현 | 상태 |
|---|---|---|
| 최초 PC 등록 시 로컬 사용자 승인 | 확인창 + 확인 코드, 기본 [아니요] | ✅ (Linux 테스트 통과, Windows 확인창은 실기 확인 필요) |
| 암호화된 연결 | Noise XX 종단간 + (운영 시) wss | ✅ |
| 기기별 접근 권한 | 보기/조작/파일/앱 권한 분리, 신규 기기는 보기+조작만 | ✅ |
| 원격 제어 중 PC 에 표시 | 화면 상단 빨간 표시줄 + 트레이 아이콘 변경 + 알림 | 구현, 실기 확인 필요 |
| 연결 기록 | `connections.jsonl` (등록 요청/승인/거부/접속/종료/차단) | ✅ |
| 사용자가 직접 연결 종료 | 트레이 "현재 원격 연결 끊기" | 구현 |
| 긴급 차단 | Ctrl+Alt+F12 / 트레이 메뉴 → 모든 세션 즉시 종료, 재부팅 후에도 유지 | ✅ (Linux 테스트), 단축키 실기 확인 필요 |
| 기기 등록 취소 | `revoke` 명령, 트레이 "모든 휴대폰 등록 해제", 실행 중에도 즉시 적용 | ✅ |
| 인증 정보 안전한 저장 | PC 비밀키 DPAPI 암호화, 로그에 키 미기록 | 구현, DPAPI 실기 확인 필요 |
| 무단 원격접속 차단 | 미등록 기기 거부, 등록 대기 시간 제한 | ✅ |
| 백그라운드 원격제어 사전 동의 | 자동 실행 기본 꺼짐, 설치 시 체크해야만 등록 | ✅ |
| 원격 접속과 파일 전송 권한 분리 | `files` 권한 별도, 기본 꺼짐 | ✅ (파일 기능 자체는 Phase 2) |
| 계정 다중 인증 | 서버 계정 체계 필요 | ⏳ Phase 3 |
| 소스코드에 비밀번호/API 키 없음 | 키는 실행 시 생성, 저장소에 비밀 없음 | ✅ |
