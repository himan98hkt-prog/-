#!/usr/bin/env bash
# HomePilot Remote 종단간 자동 테스트 (중계 서버 + 에이전트 + 시험 클라이언트).
# Linux 에서는 에이전트가 테스트 화면/입력 기록 모드로, Windows(Git Bash) 에서는 실제 화면으로 동작한다.
#   사용법: tests/e2e.sh [빌드폴더]   (기본: target/debug)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${1:-$ROOT/target/debug}"
EXE=""; [[ "$(uname -s)" == MINGW* || "$(uname -s)" == MSYS* ]] && EXE=".exe"
AGENT="$BIN/homepilot-agent$EXE"; RELAY="$BIN/homepilot-relay$EXE"; CLI="$BIN/hp-cli$EXE"
WORK="$(mktemp -d)"; PORT=$((20000 + RANDOM % 20000)); URL="ws://127.0.0.1:$PORT"
# Windows(Git Bash)에서는 네이티브 프로그램에 넘길 경로를 Windows 형식으로 바꾼다
P(){ if [ -n "$EXE" ]; then cygpath -w "$1"; else echo "$1"; fi; }
export HOMEPILOT_AGENT_HOME="$(P "$WORK/agent")" HOMEPILOT_LOG="info,homepilot_agent=debug"
PASS=0; FAIL=0; PIDS=()
ok()   { echo "  [성공] $1"; PASS=$((PASS+1)); }
bad()  { echo "  [실패] $1"; FAIL=$((FAIL+1)); }
check(){ if eval "$2"; then ok "$1"; else bad "$1"; fi; }
cleanup(){ exec 3>&- 2>/dev/null; for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null; done; wait 2>/dev/null; }
trap cleanup EXIT

start_relay(){ "$RELAY" --listen "127.0.0.1:$PORT" >>"$WORK/relay.log" 2>&1 & RELAY_PID=$!; PIDS+=($RELAY_PID); sleep 0.5; }
start_agent(){
  # coproc: 에이전트 표준입력으로 콘솔 명령(y/n/block/...)을 보내기 위한 파이프 (fd 3)
  coproc AGENTP { exec "$AGENT" run --headless --console >>"$WORK/agent.out" 2>>"$WORK/agent.log"; }
  AGENT_PID=$AGENTP_PID; PIDS+=($AGENT_PID)
  exec 3>&"${AGENTP[1]}"
  for i in $(seq 1 50); do grep -q "중계 서버 연결됨" "$WORK/agent.log" 2>/dev/null && return 0; sleep 0.2; done
  return 1
}
# 어떤 경우에도 테스트가 멈추지 않도록 명령마다 시간 제한
cli(){ timeout 60 "$CLI" --relay "$URL" --device "$DEV" --key "$(P "$WORK/${KEY:-phone}.key")" --name "${NAME:-테스트폰}" "$@"; }
wait_online(){ for i in $(seq 1 ${1:-40}); do cli connect >/dev/null 2>&1 && return 0; sleep 0.5; done; return 1; }

echo "== 준비 (작업 폴더 $WORK)"
"$AGENT" config --relay "$URL" --name "테스트 PC" >/dev/null
DEV=$("$AGENT" info | sed -n 's/^장치 ID *: //p')
check "장치 ID 생성 ($DEV)" '[[ "$DEV" =~ ^[0-9a-f]{20}$ ]]'
start_relay
check "에이전트 시작 + 중계 서버 연결" 'start_agent'

echo "== 1. 최초 등록: PC 사용자 승인"
cli connect >"$WORK/pair.out" 2>&1 & CP=$!
for i in $(seq 1 50); do grep -q "등록 요청" "$WORK/agent.out" && break; sleep 0.2; done
check "PC 에 등록 요청 표시 (확인 코드 포함)" 'grep -q "확인 코드: [0-9]\{3\} [0-9]\{3\}" "$WORK/agent.out"'
echo y >&3
wait $CP; check "승인 후 접속 성공" 'grep -q "접속 성공" "$WORK/pair.out"'
SAS_PC=$(grep -o "확인 코드: [0-9]* [0-9]*" "$WORK/agent.out" | head -1 | cut -d' ' -f3-)
check "휴대폰/PC 확인 코드 일치 ($SAS_PC)" 'grep -q "확인 코드 \[$SAS_PC\]" "$WORK/pair.out"'

echo "== 2. 무단 접근 차단"
KEY=stranger NAME=모르는폰 cli connect >"$WORK/stranger.out" 2>&1
check "등록 안 된 기기 거부 (등록 대기 종료 후)" 'grep -q "등록되지 않은 기기" "$WORK/stranger.out"'
timeout 30 "$CLI" --relay "$URL" --device "0000000000000000aaaa" --key "$(P "$WORK/phone.key")" connect >"$WORK/wrongid.out" 2>&1
check "없는 장치 ID → 오프라인" 'grep -q "오프라인" "$WORK/wrongid.out"'
echo pair >&3; sleep 0.3
KEY=stranger NAME=모르는폰 cli connect >"$WORK/stranger2.out" 2>&1 & SP=$!
for i in $(seq 1 50); do [ "$(grep -c '등록 요청' "$WORK/agent.out")" -ge 2 ] && break; sleep 0.2; done
echo n >&3; wait $SP
check "PC 에서 거부하면 접속 불가" 'grep -q "승인하지 않았습니다" "$WORK/stranger2.out"'

echo "== 3. 상태·모니터·화면"
MON2=1; [ -n "$EXE" ] && MON2=0   # Windows CI 러너는 모니터 1개
cli status >"$WORK/status.out" 2>&1
check "CPU/RAM/디스크 상태 수신" 'grep -q "cpu_percent" "$WORK/status.out" && grep -q "mem_total_bytes" "$WORK/status.out"'
cli monitors >"$WORK/mon.out" 2>&1
check "모니터 목록" '[ "$(grep -c "\"index\"" "$WORK/mon.out")" -ge 1 ]'
cli shot --monitor 0 --out "$(P "$WORK/s0.jpg")" >/dev/null 2>&1
check "모니터 0 화면 캡처(JPEG)" '[ -s "$WORK/s0.jpg" ] && [ "$(head -c2 "$WORK/s0.jpg" | od -An -tx1 | tr -d " ")" = "ffd8" ]'
cli shot --monitor "$MON2" --scale 50 --out "$(P "$WORK/s1.jpg")" >"$WORK/s1.out" 2>&1
check "모니터 선택 + 축소 전송" 'grep -q "저장" "$WORK/s1.out"'
cli stream --secs 3 --fps 10 >"$WORK/stream.out" 2>&1
check "실시간 전송 (흐름 제어) $(grep -o '[0-9.]* fps' "$WORK/stream.out")" 'grep -q "fps" "$WORK/stream.out" && ! grep -q "^0 프레임" "$WORK/stream.out"'

echo "== 4. 입력"
cli click 0.5 0.5 --right >/dev/null 2>&1; cli type "안녕하세요 HomePilot" >/dev/null 2>&1; cli combo ctrl c >/dev/null 2>&1; cli scroll -- -2 >/dev/null 2>&1
if [ -z "$EXE" ]; then
  check "마우스 우클릭 전달" 'grep -q "button: Right, down: true" "$WORK/agent.log"'
  check "한글 문자열 전달" 'grep -q "안녕하세요 HomePilot" "$WORK/agent.log"'
  check "조합키 전달" 'grep -qF "Key { key: \"ctrl\", down: false }" "$WORK/agent.log"'
else
  echo "  (Windows: 실제 입력이 발생했는지는 화면으로 확인 필요)"
fi
NAME=보기전용 KEY=viewer cli keygen >/dev/null 2>&1
"$AGENT" trust-client --name 보기전용 --public-key "$(KEY=viewer cli keygen)" --view-only >/dev/null
KEY=viewer NAME=보기전용 cli click 0.1 0.1 >"$WORK/viewer.out" 2>&1
check "보기 전용 기기의 조작 거부 (권한 분리)" 'grep -q "조작 권한이 없습니다" "$WORK/viewer.out"'
"$AGENT" revoke 보기전용 >/dev/null
KEY=viewer NAME=보기전용 cli connect >"$WORK/revoked.out" 2>&1
check "등록 해제한 기기는 실행 중에도 즉시 거부" 'grep -q "등록되지 않은 기기" "$WORK/revoked.out"'

echo "== 5. 긴급 차단"
cli stream --secs 20 >"$WORK/block.out" 2>&1 & BP=$!
sleep 1.5; echo block >&3; wait $BP
check "스트리밍 중 긴급 차단 → 즉시 종료" 'grep -q "차단했습니다" "$WORK/block.out"'
cli connect >"$WORK/blocked.out" 2>&1
check "차단 상태에서 접속 거부" 'grep -q "차단되어 있습니다" "$WORK/blocked.out"'
echo unblock >&3; sleep 0.3
check "차단 해제 후 다시 접속" 'cli connect >/dev/null 2>&1'

echo "== 6. 네트워크 끊김 후 복구"
kill $RELAY_PID; wait $RELAY_PID 2>/dev/null; sleep 1
start_relay
check "중계 서버 재시작 후 자동 재연결" 'wait_online 60'

echo "== 7. 에이전트 재시작(재부팅 가정)"
exec 3>&-; kill $AGENT_PID 2>/dev/null; wait $AGENT_PID 2>/dev/null; sleep 0.5
DEV2=$("$AGENT" info | sed -n 's/^장치 ID *: //p')
check "재시작 후 장치 ID 유지" '[ "$DEV" = "$DEV2" ]'
start_agent >/dev/null
check "재시작 후 등록 기기 그대로 접속" 'wait_online 20'
check "접속 기록 남음" 'grep -q "pairing_approved" "$HOMEPILOT_AGENT_HOME/logs/connections.jsonl" && grep -q "denied_unknown" "$HOMEPILOT_AGENT_HOME/logs/connections.jsonl"'
check "로그에 비밀키/세션키 없음" '! grep -qi "private" "$WORK/agent.log"'

echo
echo "결과: 성공 $PASS / 실패 $FAIL"
[ -n "${E2E_ARTIFACTS:-}" ] && { mkdir -p "$E2E_ARTIFACTS"; cp "$WORK"/*.jpg "$WORK"/*.out "$WORK"/*.log "$E2E_ARTIFACTS"/ 2>/dev/null; cp "$WORK/agent/logs/connections.jsonl" "$E2E_ARTIFACTS"/ 2>/dev/null; }
[ $FAIL -eq 0 ] || { echo "--- agent.log (마지막 40줄)"; tail -40 "$WORK/agent.log"; exit 1; }
