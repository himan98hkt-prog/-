# 배포 · 판매 운영

## 1. 빌드

```bash
npm ci
npm test            # 실패하면 배포하지 않는다
npm run build       # dist/
```

산출물:

```
dist/index.html          Pro 앱
dist/lite.html           Lite 앱
dist/tools/keygen.html   판매자 전용 인증키 발급기 (고객 배포 금지)
dist/assets/*            해시가 붙은 JS/CSS
```

체험판을 파일 하나로 보내야 할 때는 `npm run demo` 로 `dist-demo/학원관리노트-체험판.html` 을 만듭니다.
(HTML 안에 JS·CSS 를 전부 넣은 단일 파일이라 메일 첨부·USB 전달로 바로 열립니다)

`base: './'` 상대 경로 빌드라 `https://example.com/note/` 같은 하위 경로에 올려도 그대로 동작합니다.

## 2. 웹호스팅 업로드

1. FTP/파일관리자로 `dist/` 내용을 배포 디렉터리에 업로드
2. **`tools/` 디렉터리는 고객용 배포 경로에 올리지 않습니다.** 판매자 PC 나 접근 제한 경로에서만 사용
3. HTTPS 필수 — 서비스 워커(오프라인)와 홈 화면 설치가 HTTPS 에서만 동작합니다
4. 캐시 정책: `assets/*` 는 파일명에 해시가 있으므로 장기 캐시, `*.html` 은 `no-cache` 권장

업데이트 배포 시 서비스 워커가 "네트워크 우선"으로 동작하므로, 사용자는 새로고침 한 번으로 최신 버전을 받습니다.

## 3. 판매 설정 — 구매 버튼과 자동 발급

### 구매 버튼이 여는 주소

앱의 "구매하기" 버튼(첫 화면 · 체험 안내 띠 · 설정 · 체험 종료 화면)은 빌드할 때 넣은 주소를 엽니다.

```bash
VITE_BUY_URL=https://내사이트.com/상품주소 npm run build
# 문의 창구가 있으면 도움말에 버튼이 생깁니다
VITE_SUPPORT_URL=https://pf.kakao.com/_xxxx VITE_SUPPORT_LABEL="카카오톡으로 문의하기" npm run build
```

넣지 않으면 `https://accelssam.com/` 을 엽니다. 어느 버튼에서 왔는지는 주소 끝의 `?from=app-…` 로 구분됩니다.

### 결제되면 인증키가 메일로 나가게 하기

```bash
npm run plugin      # dist-plugin/academy-note-keys.zip
```

만들어진 zip 을 퍼널모아(워드프레스)에 플러그인으로 올립니다. 설치·설정은
[`integration/funnelmoa/README.md`](../integration/funnelmoa/README.md) 를 따라가면 5분이면 끝납니다.
플러그인 설정의 **앱 주소**에는 위에서 올린 `…/lite.html` (Pro 를 팔면 `…/index.html`) 을 넣습니다.

## 3-1. 인증키(시디키) 수동 발급 흐름

플러그인을 쓰면 필요 없습니다. 계좌이체 건도 플러그인의 "직접 보내기"로 처리할 수 있습니다.

1. `dist/tools/keygen.html` 을 판매자 PC 에서 연다
2. 제품(통합 A 권장) · 플랜(Lite/Pro) · 수량을 정해 발급 → CSV 저장 (주문번호를 메모에 기록)
3. 주문 완료 시 고객에게 키 전달
4. 고객이 앱 첫 화면(인증 화면)이나 설정 > 인증키 · 플랜에 입력 → 플랜 자동 활성화
5. 고객 문의 시 발급기 하단 "키 검증"에 붙여 넣어 제품·플랜·유효성 확인

키 체계와 재발급 대응은 [LICENSE-KEYS.md](LICENSE-KEYS.md) 에 정리되어 있습니다.
**통합키(A)** 로 발급하면 피아노 관리노트와 학원 관리노트에서 같은 키를 씁니다.

> 키는 서버 없이 검증됩니다. 폐기(블랙리스트)가 필요하면 Pro 는 `academies.license_key_hash` 로
> 서버 측 차단이 가능하고, Lite 는 구조상 불가하므로 정책으로 관리합니다.
> 백업 파일에는 인증키가 담기지 않으므로 백업을 통한 라이선스 복제는 되지 않습니다.

## 4. Pro 인프라 준비 (학원별이 아니라 전체 1회)

1. Supabase 프로젝트 1개 생성 (무료 티어 기준 설계)
2. SQL Editor 에서 `supabase/schema.sql` 실행
3. Authentication > Providers > **Anonymous sign-in 활성화**
4. Project URL / anon key 를 고객 안내문에 포함하거나, 빌드 시 `.env` 에 주입
   (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`)

anon key 는 공개돼도 RLS 로 막히지만, `service_role` 키는 절대 프런트에 넣지 않습니다.

## 5. CI

| 워크플로 | 실행 시점 | 하는 일 |
|---|---|---|
| `CI` | push(main), PR | `npm ci` → 테스트 218건(플러그인 점검 포함) → 프로덕션 빌드 → 산출물 3종 + 플러그인 zip 확인 → 아티팩트 업로드 |
| `브라우저 검증` | 수동 (Actions 탭) | Chromium 설치 후 `npm run smoke` + `node scripts/perf.mjs` → `perf-report.json` 아티팩트 |

브라우저 검증은 20만 건 더미 생성 때문에 10분 이상 걸려 매 PR 자동 실행에서 제외했습니다.
릴리스 전에 한 번 돌리고 아티팩트를 보관하세요.

## 6. 릴리스 체크리스트

- [ ] **GitHub 저장소가 비공개인지** — 공개 상태면 키 규칙과 발급기가 그대로 노출됩니다
- [ ] `npm test` 전부 통과 (218건 — 플러그인이 만든 키가 앱에서 열리는지 포함)
- [ ] `npm run test:plugin` 통과 (결제 신호 → 발급 → 메일 → 관리 화면 61가지)
- [ ] `npm run perf` 전 항목 기준 이내 (perf-report.json 보관)
- [ ] `npm run smoke` 전부 통과 (84건) — 첫 화면·바로 시작 링크·체험→샘플→구매→내 학원·교재 진도·계열 전환·백업 왕복
- [ ] `VITE_BUY_URL` 을 실제 상품 주소로 넣어 빌드했는지 (구매 버튼을 눌러 확인)
- [ ] 퍼널모아: 플러그인 설치 → "내 메일로 시험 발송" → 메일의 버튼으로 앱이 인증된 채 열리는지
- [ ] 퍼널모아: **실제 결제 1건** → 발급 내역과 "최근 기록"에 한 줄이 생기고 메일이 오는지
- [ ] 샘플 학원 5종(피아노·미술·영어·수학·태권도) 눈으로 확인
- [ ] Pro: 기기 2대 동시 출결 체크 3초 내 반영, 다른 학원 데이터 접근 불가 확인
- [ ] 체험 시작 → 14일 뒤 첫 화면에 "자료는 그대로" 안내와 구매 버튼이 뜨는지
- [ ] 인쇄 미리보기: 월간 출석부 · 수납대장 A4 한 장에 들어가는지
