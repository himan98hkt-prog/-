#!/usr/bin/env bash
# 집 PC 단독 구성 테스트: 내장 중계 + (가짜) Cloudflare 터널 + 에이전트 등록 토큰.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${1:-$ROOT/target/debug}"
WORK="$(mktemp -d)"; PORT=$((20000 + RANDOM % 20000))
export HOMEPILOT_AGENT_HOME="$WORK/agent" HOMEPILOT_LOG="info,homepilot_agent=debug"
PASS=0; FAIL=0; PIDS=()
check(){ if eval "$2"; then echo "  [성공] $1"; PASS=$((PASS+1)); else echo "  [실패] $1"; FAIL=$((FAIL+1)); fi; }
trap 'exec 3>&- 2>/dev/null; for p in "${PIDS[@]}"; do kill $p 2>/dev/null; done; pkill -f "$WORK/fake-cloudflared" 2>/dev/null; wait 2>/dev/null' EXIT

# cloudflared 대신: 실제와 같은 형식으로 주소를 출력하고 대기하는 가짜 프로그램
cat >"$WORK/fake-cloudflared" <<'FAKE'
#!/usr/bin/env bash
echo "INF Requesting new quick Tunnel on trycloudflare.com..." >&2
echo "INF |  https://sample-$RANDOM-words.trycloudflare.com                                  |" >&2
exec sleep 3600
FAKE
chmod +x "$WORK/fake-cloudflared"

A="$BIN/homepilot-agent"
timeout 30 "$A" setup-home >"$WORK/setup.out"
timeout 30 "$A" config --cloudflared "$WORK/fake-cloudflared" --local-relay-port "$PORT" >/dev/null
DEV=$(timeout 30 "$A" info | sed -n 's/^장치 ID *: //p')
coproc AG { exec "$A" run --headless --console >"$WORK/agent.out" 2>"$WORK/agent.log"; }
AGP=$AG_PID; PIDS+=($AGP); exec 3>&"${AG[1]}"   # coproc 종료 시 AG_PID 변수가 사라지므로 따로 보관
for i in $(seq 1 50); do grep -q "휴대폰용 중계 주소" "$WORK/agent.log" && grep -q "중계 서버 연결됨" "$WORK/agent.log" && break; sleep 0.2; done

check "내장 중계 서버 시작" 'grep -q "내장 중계 서버 시작: 127.0.0.1:$PORT" "$WORK/agent.log"'
check "에이전트가 내장 중계에 등록" 'grep -q "중계 서버 연결됨" "$WORK/agent.log"'
check "터널 주소 인식" 'grep -q "휴대폰용 중계 주소: https://sample-[0-9]*-words.trycloudflare.com" "$WORK/agent.log"'
check "info 에 휴대폰 주소 표시" 'timeout 30 "$A" info | grep -q "휴대폰 주소 : https://sample-"'
CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" "http://127.0.0.1:$PORT/v1/agent/$DEV")
check "토큰 없는 가짜 에이전트 등록 거부 (HTTP $CODE)" '[ "$CODE" = "401" ]'

"$BIN/hp-cli" --relay "ws://127.0.0.1:$PORT" --device "$DEV" --key "$WORK/p.key" connect >"$WORK/pair.out" 2>&1 & CP=$!
for i in $(seq 1 50); do grep -q "등록 요청" "$WORK/agent.out" && break; sleep 0.2; done
echo y >&3; wait $CP
check "휴대폰 등록 + 접속 (내장 중계 경유)" 'grep -q "접속 성공" "$WORK/pair.out"'
"$BIN/hp-cli" --relay "ws://127.0.0.1:$PORT" --device "$DEV" --key "$WORK/p.key" shot --out "$WORK/s.jpg" >/dev/null 2>&1
check "화면 수신" '[ -s "$WORK/s.jpg" ]'

pkill -f "^sleep 3600" 2>/dev/null || pkill -f "$WORK/fake-cloudflared"
for i in $(seq 1 60); do [ "$(grep -c '휴대폰용 중계 주소' "$WORK/agent.log")" -ge 2 ] && break; sleep 0.25; done
check "터널이 끊기면 자동 재시작 + 새 주소" '[ "$(grep -c "휴대폰용 중계 주소" "$WORK/agent.log")" -ge 2 ]'

# 포트를 다른 프로그램이 쓰고 있어도 빈 포트로 자동 전환 (사용자 PC 에서 8443 충돌 사례)
exec 3>&- 2>/dev/null; kill $AGP 2>/dev/null
for i in $(seq 1 50); do kill -0 $AGP 2>/dev/null || break; sleep 0.1; done
BPORT=$((PORT + 1))
python3 -c "import socket,time,sys;s=socket.socket();s.bind(('127.0.0.1',$BPORT));s.listen();open(sys.argv[1],'w').close();time.sleep(60)" "$WORK/blocker.ready" & PIDS+=($!)
for i in $(seq 1 50); do [ -e "$WORK/blocker.ready" ] && break; sleep 0.1; done
timeout 30 "$A" config --local-relay-port "$BPORT" >/dev/null
"$A" run --headless >/dev/null 2>"$WORK/agent2.log" & PIDS+=($!)
for i in $(seq 1 50); do grep -q "중계 서버 연결됨" "$WORK/agent2.log" && break; sleep 0.2; done
check "포트 충돌 시 빈 포트로 자동 전환" '[ -e "$WORK/blocker.ready" ] && grep -q "빈 포트를 자동으로 사용" "$WORK/agent2.log" && grep -q "중계 서버 연결됨" "$WORK/agent2.log"'

echo "결과: 성공 $PASS / 실패 $FAIL"
[ $FAIL -eq 0 ] || { tail -30 "$WORK/agent.log"; exit 1; }
