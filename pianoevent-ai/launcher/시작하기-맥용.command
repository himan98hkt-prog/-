#!/bin/bash
# 피아노이벤트 - macOS 실행기 (두 번 클릭)
cd "$(dirname "$0")" || exit 1

if [ -f "pianoevent-ai/package.json" ]; then cd pianoevent-ai
elif [ -f "package.json" ]; then :
elif [ -f "../pianoevent-ai/package.json" ]; then cd ../pianoevent-ai
else
  echo "  [!] 프로그램 폴더를 찾지 못했습니다. 압축을 먼저 풀어주세요."
  read -r -p "  엔터를 누르면 닫힙니다." _
  exit 1
fi

echo
echo "  ================================================"
echo "     피아노이벤트를 시작합니다"
echo "  ================================================"
echo
echo "  이 창은 프로그램이 켜져 있는 동안 그대로 두세요."
echo

if ! command -v node >/dev/null 2>&1; then
  echo "  [준비] Node.js 가 필요합니다."
  if command -v brew >/dev/null 2>&1; then
    echo "         Homebrew 로 자동 설치합니다. (한 번만)"
    brew install node || true
  fi
fi

if ! command -v node >/dev/null 2>&1; then
  echo "  [안내] 브라우저를 열어드립니다. LTS 를 받아 설치한 뒤"
  echo "         이 창을 닫고 시작하기를 다시 눌러주세요."
  open "https://nodejs.org/ko/download"
  read -r -p "  엔터를 누르면 닫힙니다." _
  exit 0
fi

echo "  [1/3] 준비 완료 (Node.js $(node -v))"

if [ ! -f "node_modules/next/package.json" ]; then
  echo "  [2/3] 처음 실행이라 준비 작업을 합니다. 2~4분 걸립니다."
  echo
  npm install --no-audit --no-fund --loglevel=error || {
    echo
    echo "  [!] 준비 작업이 끝나지 못했습니다. 인터넷 연결을 확인해주세요."
    read -r -p "  엔터를 누르면 닫힙니다." _
    exit 1
  }
  echo "  [2/3] 준비 작업 완료"
else
  echo "  [2/3] 준비 작업은 이미 끝나 있습니다"
fi

echo "  [3/3] 프로그램을 켜는 중입니다. 잠시 후 브라우저가 저절로 열립니다."
echo

( for _ in $(seq 1 180); do
    if curl -s -o /dev/null "http://localhost:3000"; then open "http://localhost:3000"; break; fi
    sleep 1
  done ) &

npm run dev

echo
echo "  프로그램이 종료되었습니다."
read -r -p "  엔터를 누르면 닫힙니다." _
