# 연주회 매니저 — 개발 인수인계

피아노학원 **연주회 준비 프로그램**입니다. 폴더 이름은 `pianoevent-ai` 지만
파는 이름은 **연주회 매니저**(RECITAL MANAGER)입니다. 이름은 `lib/brand.ts` 한 곳에만
적혀 있고 거기서 화면·창 제목·설치본·문서로 퍼집니다.

아첼쌤(accelssam.com)에서 **설치형 상품**으로 팝니다. 받으시는 분은 피아노학원 원장님이고,
**컴퓨터를 잘 다루지 못하신다고 보고 만듭니다.**

---

## 처음 한 번 (내 컴퓨터에 받기)

```bash
git clone -b claude/piano-event-program-0nd8od https://github.com/himan98hkt-prog/-.git recital
cd recital/pianoevent-ai
npm install          # 1~3분
npm run dev          # → http://localhost:3000
```

Node.js 22 이상이 필요합니다(https://nodejs.org 의 LTS). 더 자세한 것은
[docs/LOCAL.md](docs/LOCAL.md) 에 그림처럼 적혀 있습니다.

처음 켜면 데모 행사(제12회 정기 연주회 · 학생 12명)가 들어 있습니다.
처음 상태로 되돌리려면 `npm run reset`.

---

## 날마다 쓰는 명령

| 명령 | 하는 일 |
| --- | --- |
| `npm run dev` | 개발 서버 (고치면 바로 반영) |
| `npm run typecheck` | 타입 검사 |
| `npm run lint` | 린트 |
| `npm test` | 단위 검사 1,000여 건 (5초) |
| `npm run smoke` | **진짜 서버를 띄워** 행사 생성→명단→인쇄물→초대장까지 밟기 |

**밀기 전에는 이 네 가지가 다 통과해야 합니다.** 깃허브에서도 같은 것을 돌립니다.

### 화면을 고쳤을 때 더 돌리는 것

| 명령 | 무엇을 지키나 |
| --- | --- |
| `npm run verify:simple` | **화면이 복잡해지지 않았는가** (아래 「원칙」 참고) |
| `npm run verify:video` | 감동영상 — 진짜 영상 파일이 나오는지까지 |
| `npm run verify:poster` | 포스터가 안 깨지는지 |
| `npm run verify:live` | 당일 진행 화면 |
| `npm run verify:web` · `verify:detail` · `verify:embed` | 파는 자리(상세페이지) |

---

## 지켜야 할 원칙

이 프로그램은 **스스로를 재는 검사**를 가지고 있습니다. 고치실 때 이 선을 넘으면
검사가 막습니다. 숫자를 올리기 전에 **정말 그만큼 필요한지** 먼저 생각하십시오.

1. **누르는 자리는 32px 이상** — 태블릿에서 손가락으로 누릅니다
2. **한 화면에 눌러 볼 것이 너무 많으면 안 됩니다** — 화면마다 문턱이
   `scripts/verify-simple.mjs` 에 적혀 있습니다 (행사 목록 22개, 감동영상 50개 …)
3. **다음에 할 일 하나만 크게** — 고르실 것을 늘리지 않습니다
4. **주석은 "왜"를 한국어로** — 무엇을 하는지는 코드가 말합니다

### 절대 하면 안 되는 것

| | 왜 |
| --- | --- |
| `RECITAL_LICENSE_SECRET` 을 코드에 적기 | 저장소가 **공개**입니다. 적는 순간 누구나 키를 찍어 냅니다 |
| `배포/인증키-발급기.html` 을 올리기 | 그 안에 비밀값이 들어 있습니다 |
| `백업/` 폴더를 커밋 | **아이 이름**이 들어 있습니다 |
| 악보·반주 음원·배경 음악 넣기 | 저작권. 학원에서 준비하시는 자료입니다 |
| 아이 사진·명단을 서버로 보내기 | **원장님 컴퓨터를 벗어나지 않는다**가 이 상품의 약속입니다 |

`detail/kids/` 의 아이 사진은 **AI로 만든 예시**입니다(실제 아이 아님).
파는 자리 설명용이고, 상품에 딸려 가는 `배포/연습용-사진` 에는 넣지 않습니다.

---

## 어디에 무엇이 있나

```
app/            화면 (Next.js App Router)
components/     화면 조각
lib/
  brand.ts      상품 이름 — 여기 한 곳
  program/      연주 순서·시간 계산 (순수 함수, AI 없이 완결)
  design/       테마 108종 · 인쇄물 양식
  video/        감동영상 (storyboard · render · fast-export)
  license/      인증키 만들기·확인하기
desktop/        설치본 껍데기 (Electron)
scripts/        검사·캡처·빌드 도구
docs/           문서 (아래)
web/            파는 자리에 올리는 것
```

| 문서 | 언제 보나 |
| --- | --- |
| [docs/LOCAL.md](docs/LOCAL.md) | 내 컴퓨터에서 켜기 |
| [docs/SELLING-LICENSE.md](docs/SELLING-LICENSE.md) | **인증키 발급·설치본 뽑기** |
| [docs/SIGNING.md](docs/SIGNING.md) | 「Windows의 PC 보호」 창 없애기 |
| [docs/SCOPE.md](docs/SCOPE.md) | 무엇까지 하는 프로그램인가 |
| [docs/MANUAL.md](docs/MANUAL.md) | 원장님께 드리는 사용설명서 |

---

## 설치본 뽑기

내 컴퓨터에서 (내 컴퓨터 운영체제용만 나옵니다):

```bash
npm run dist:win     # 윈도우
npm run dist:mac     # 맥
```

**파는 설치본은 깃허브에서 뽑습니다** — `pianoevent-ai/` 안의 파일을 고쳐
`claude/piano-event-program-**` 가지에 밀면 저절로 돕니다. 끝나면
Releases 의 `installer-latest` 에 올라옵니다.

> 「Actions → Run workflow」 단추는 이 워크플로가 기본 가지에 들어간 뒤에야 보입니다.

**인증키 비밀**이 깃허브 Secrets 에 있어야 설치본이 만들어집니다. 없으면 빌드가
**일부러 멈춥니다** — 개발용 비밀이 든 판은 파실 키를 열지 못하기 때문입니다.

---

## 검사를 쓸 때 — 겪어 본 것

* **검사가 고치기 전에도 통과하면 그 검사는 틀린 것입니다.** 고친 것을 되돌려
  **빨개지는지 확인**한 뒤에 넘어가십시오. 이 저장소에서 두 번 겪었습니다.
* 숫자를 세는 검사는 **어디를 세는지** 좁히십시오(한 번은 같은 그림을 두 군데서 세어
  개수가 두 배로 나왔습니다).
* 화면을 집는 검사는 **그 자리에 정말 그것이 있는지**(`elementFromPoint`) 보십시오.
  스크롤만 맞추면 떠 있는 다른 칸을 누르게 됩니다.
