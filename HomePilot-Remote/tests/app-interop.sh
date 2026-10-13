#!/usr/bin/env bash
# Android 앱 프로토콜(Dart) ↔ Windows 에이전트(Rust) 상호 운용 테스트.
# 필요: cargo build --workspace 완료, dart(Flutter SDK) 사용 가능.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${1:-$ROOT/target/debug}"
WORK="$(mktemp -d)"; PORT=$((20000 + RANDOM % 20000)); URL="ws://127.0.0.1:$PORT"
export HOMEPILOT_AGENT_HOME="$WORK/agent" HOMEPILOT_LOG="info,homepilot_agent=debug"
PASS=0; FAIL=0; PIDS=()
check(){ if eval "$2"; then echo "  [성공] $1"; PASS=$((PASS+1)); else echo "  [실패] $1"; FAIL=$((FAIL+1)); fi; }
trap 'exec 3>&- 2>/dev/null; for p in "${PIDS[@]}"; do kill $p 2>/dev/null; done; wait 2>/dev/null' EXIT

"$BIN/homepilot-agent" config --relay "$URL" >/dev/null
DEV=$("$BIN/homepilot-agent" info | sed -n 's/^장치 ID *: //p')
"$BIN/homepilot-relay" --listen "127.0.0.1:$PORT" >"$WORK/relay.log" 2>&1 & PIDS+=($!)
sleep 0.5
coproc AG { exec "$BIN/homepilot-agent" run --headless --console >"$WORK/agent.out" 2>"$WORK/agent.log"; }
PIDS+=($AG_PID); exec 3>&"${AG[1]}"
for i in $(seq 1 50); do grep -q "중계 서버 연결됨" "$WORK/agent.log" && break; sleep 0.2; done

cd "$ROOT/android-app"
dart run tool/interop_client.dart "$URL" "$DEV" "$WORK/app.key" >"$WORK/app.out" 2>&1 & AP=$!
for i in $(seq 1 100); do grep -q "등록 요청" "$WORK/agent.out" && break; sleep 0.2; done
SAS=$(grep -o "확인 코드: [0-9]* [0-9]*" "$WORK/agent.out" | head -1 | cut -d' ' -f3-)
echo y >&3
wait $AP
cat "$WORK/app.out"
check "앱 쪽 확인 코드 = PC 확인 코드 ($SAS)" 'grep -q "PAIRING $SAS" "$WORK/app.out"'
check "Noise 핸드셰이크 + 등록 + 환영" 'grep -q "WELCOME .* control=true" "$WORK/app.out"'
check "상태 조회" 'grep -q "STATUS cpu=" "$WORK/app.out"'
check "모니터 목록" 'grep -q "MONITORS [1-9]" "$WORK/app.out"'
check "화면 프레임 복호화 (JPEG)" 'grep -q "FIRST_FRAME .* soi=ffd8" "$WORK/app.out"'
check "흐름 제어 하에 연속 수신" 'grep -qE "FRAMES ([5-9]|[1-9][0-9])" "$WORK/app.out"'
check "한글 입력 전달" 'grep -q "앱에서 한글 입력" "$WORK/agent.log"'
check "더블클릭 전달" '[ "$(grep -c "Button { button: Left, down: true }" "$WORK/agent.log")" -ge 2 ]'
check "핑 응답" 'grep -q "^PING" "$WORK/app.out"'
echo "결과: 성공 $PASS / 실패 $FAIL"
[ $FAIL -eq 0 ] || { tail -30 "$WORK/agent.log"; exit 1; }
