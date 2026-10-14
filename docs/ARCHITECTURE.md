# 아키텍처

## 1. 원칙 — local-first

Lite/Pro 어느 플랜이든 **화면은 항상 로컬(IndexedDB)을 읽습니다.**
Pro 는 같은 IndexedDB 를 서버 미러 겸 오프라인 큐로 쓰고, 백그라운드에서만 서버와 주고받습니다.

```
 [화면] ──읽기──> Dexie(IndexedDB) ──(Pro)──> outbox ──push──> Supabase
                       ▲                                        │
                       └──────────── pull / Realtime ───────────┘
```

이 구조의 이점:

- 렌더 성능이 네트워크와 무관하다 (대형 학원 요구사항의 전제)
- 오프라인에서 출결을 체크해도 큐에 쌓였다가 복귀 시 자동 전송된다
- Lite 와 Pro 가 **완전히 같은 화면 코드**를 쓴다 (분기는 저장 계층에만 존재)

## 2. 데이터 모델

| 테이블 | 핵심 컬럼 | 비고 |
|---|---|---|
| `academies` | name, logo_url, brand_color, license_key_hash, plan, invite_code | Pro 전용(테넌트) |
| `users` | role(owner/teacher/desk), name, pin | PIN 로그인 |
| `subjects` | name, color | 색상이 출결 보드·시간표에 반영 |
| `classes` | subject_id, teacher_id, schedule JSON, capacity, room, fee | `schedule = [{dow,start,end}]` |
| `students` | name, school, grade, phone, parent_phone, siblings_group, status, joined_at, **custom JSON** | 계열별 확장은 custom 으로 |
| `enrollments` | student_id, class_id, started_at, ended_at, fee_override | 반 이동 이력이 남는다 |
| `attendance` | student_id, class_id, date, status, reason_tag, checked_by | 20만 건 규모 |
| `payments` | student_id, month, amount, method, paid_at, status, installments JSON | 분할납부 포함 |
| `expenses` | category, amount, memo, date | |
| `counsel_logs` | student_id, type, stage, content, next_action | 입회 상담 퍼널 |
| `notices` | student_id, channel, template_id, sent_at, body | 문구 복사/공유 이력 |
| `monthlyStats` | month, 매출·출석률·원생 증감 | **로컬 집계 캐시** |

날짜는 전부 문자열(`YYYY-MM-DD`, `YYYY-MM`)로 저장합니다. IndexedDB 와 PostgreSQL 양쪽에서
그대로 범위 인덱스로 쓸 수 있고, 타임존 때문에 하루가 밀리는 사고가 없습니다.

### custom 필드 — "전 계열 범용"의 메커니즘

계열별 차이는 코드가 아니라 **설정 데이터**입니다. 원장이 정의한 항목(`settings.customFields`)이
원생 폼 → 원생 카드 → 학부모 리포트에 자동 반영됩니다.
`normalizeValues()` 가 정의되지 않은 키를 버리므로, 항목을 지워도 저장 데이터가 오염되지 않습니다.

## 3. 성능 설계 (원생 1,000 / 반 80 / 출결 20만)

| 화면 | 전략 |
|---|---|
| 원생 목록 | 전체(1,000행)를 메모리에 두고 JS 필터 + 가상 스크롤. 인덱스 왕복보다 빠르다 |
| 출결 보드 | `[class_id+date]` 복합 인덱스로 해당 반·해당 날짜만 |
| 출결 월 조회 | `[class_id+date]` between (월초~월말) |
| 수납 | `month` 인덱스 + `[student_id+month]` |
| 현황 | `monthlyStats` 캐시. 없으면 그 달만 계산해 저장 |
| 이탈 위험 | 최근 4주 `date` 범위 질의 + 최근 2개월 수납만 |

**금지 사항**: `attendance.toArray()` 처럼 전체 로드하는 코드는 넣지 않습니다.
`npm run perf` 가 실제 브라우저에서 화면별 시간을 재고 1초 초과 시 실패로 처리합니다.

## 4. 동기화(Pro)

- **push**: `outbox` 를 200건씩 테이블/연산별로 묶어 `upsert` / `delete`. 성공한 항목만 큐에서 제거
- **pull**: 테이블별 `updated_at > syncCursor` 를 1,000행 페이지로 당겨 Dexie 에 bulkPut
- **Realtime**: `academy_id=eq.<id>` 필터로 변경 이벤트 구독 → 즉시 로컬 반영 (기기 간 3초 내 반영)
- **주기 보정**: 30초마다 push/pull (Realtime 이 놓친 변경 대비)
- **충돌**: `updated_at` 기준 last-write-wins.
  출결 체크는 "마지막에 체크한 사람이 맞다"는 현장 규칙과 일치해 실무 오차가 없습니다.
  로컬이 서버보다 최신이면 원격 이벤트를 무시합니다.

### 멀티테넌트와 RLS

`academy_members(academy_id, auth_uid, role)` 가 로그인 계정과 학원을 잇고,
모든 업무 테이블 정책은 `academy_id in (select my_academies())` 한 줄로 통일돼 있습니다.
학원 생성/합류는 `security definer` RPC(`create_academy`, `join_academy`)로만 가능하며,
합류는 초대 코드를 아는 사람만, 그리고 `teacher`/`desk` 역할로만 됩니다.

## 5. 권한

| 역할 | 범위 |
|---|---|
| owner(원장) | 전체 |
| teacher(강사) | 담당 반의 출결·상담·리포트, 원생 조회/수정, 수납 조회 |
| desk(데스크) | 수납 입력, 원생 조회/수정, 출결 확인 |

`visibleClasses()` 가 강사에게는 담당 반만 노출하고, 탭 구성도 `navFor(role)` 로 달라집니다.

## 6. 화이트라벨

- `--brand` CSS 변수 하나로 전체 테마. 파생색(`--brand-dark/light/soft`)과 대비 글자색(`--on-brand`)은
  WCAG 상대 휘도로 자동 계산 → 어떤 색을 골라도 글자가 읽힌다
- 로고는 업로드 시 256px 정사각형으로 리사이즈해 dataURL 저장(Lite: IndexedDB, Pro: Storage 로 확장 가능)
- 미업로드 시 학원명 이니셜 아바타를 Canvas 로 생성
- `manifest` 를 Blob 으로 동적 생성해 `<link rel=manifest>` 에 주입 → 홈 화면 설치 시 학원명·로고 반영.
  Blob manifest 를 막는 환경에서는 경고만 남기고 기본 아이콘 + 앱 내 브랜딩으로 폴백합니다

## 7. 테스트

- `tests/*.test.js` — 수납 계산, 형제 묶기, 출결 집계, 라이선스, 시간표 충돌, 이탈 위험,
  custom 필드, 템플릿, 백업/마이그레이션
- `tests/repo.test.js` — fake-indexeddb 로 저장 계층 통합(월 청구 생성·집계 캐시·중복 방지)
- `npm run perf` — 실제 Chromium 성능 회귀 검사


## 인증(시디키) 흐름

```
boot()
  └ repo.init()                     IndexedDB 읽기 (설정·원생·반·강사 캐시)
  └ requireActivation()             ← 여기서 막힌다
       ├ 저장된 인증키 있음 → 통과 (plan = lite | pro)
       ├ 체험 기간 남음   → 통과 (헤더에 '체험 D-n')
       └ 그 외            → 인증 화면(cover) 을 띄우고 대기
  └ 시작 마법사 → PIN 로그인 → 화면 라우팅
```

- 검증은 `src/core/license.js` 한 곳에서만 한다. 발급기(`tools/keygen.html`)도 같은 모듈을 import 하므로
  앱과 발급기의 알고리즘이 어긋날 수 없다.
- 인증 정보는 `settings.license` 에 저장하고, **백업에는 담지 않는다**(`DEVICE_ONLY_SETTINGS`).
  데모 시드·초기화(`clearAll`)와 백업 복원(`restoreFromBackup`)에서도 살아남는다 —
  자료를 지운 것과 라이선스를 잃는 것은 다른 일이기 때문이다.

## 오늘 할 일 판정

`src/core/todo.js` 는 순수 함수다. 화면이 모아 온 데이터(오늘 출결·이번 달 청구·상담·발송 이력·마지막 백업)로
"무엇을 몇 건" 만 계산하고, 처리 버튼은 화면이 붙인다. 판정 기준(미체크 반, 결석 안내 대상, 납부 기준일 경과,
후속 상담 7일 방치, 백업 경과)이 전부 테스트로 고정되어 있어 나중에 규칙을 바꿔도 회귀를 잡을 수 있다.

## 청구 계산

`computeBill()` 이 기본 수강료 → 형제 할인 → 개인 할인 → 절사 순으로 계산하고, 각 단계를 `lines[]` 에 남긴다.
청구서·영수증·미리보기가 모두 이 `lines` 를 그대로 표시하므로 "왜 이 금액인지" 를 학부모에게 설명할 수 있다.
형제 그룹은 학부모 연락처로 자동 판정하며(`siblings.js`), 앱 시작 직후 한 번 재계산해
엑셀 가져오기·백업 복원처럼 앱 밖에서 들어온 명단도 할인이 바로 적용되게 한다.
