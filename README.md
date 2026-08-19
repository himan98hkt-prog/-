# 학원 관리노트

전 계열 학원·공부방(교과·어학·예체능·체육·공부방)을 위한 원생/출결/수납 관리 PWA.
피아노 전용이던 기존 제품을 **계열 무관 범용 + 대형 학원(원생 1,000명)** 규모까지 감당하도록 새로 설계했습니다.

| | **Lite** (`lite.html`) | **Pro** (`index.html`) |
|---|---|---|
| 저장소 | IndexedDB (Dexie) | Supabase(PostgreSQL) + 로컬 미러 |
| 동시 사용 | 1대 | 강사·데스크 여러 명 실시간 |
| 오프라인 | 완전 오프라인 | 오프라인 큐잉 후 자동 동기화 |
| 라이선스 키 | `L`로 시작 | `P`로 시작 |

## 빠른 시작

```bash
npm install
npm run dev       # http://localhost:5173/lite.html (Lite) · /index.html (Pro)
npm test          # 단위·통합 테스트
npm run build     # dist/ 정적 산출물 — 웹호스팅에 그대로 업로드
npm run perf      # 원생 1,000명·출결 20만 건 실제 브라우저 성능 측정
```

빌드 산출물은 `dist/index.html`(Pro), `dist/lite.html`(Lite), `dist/tools/keygen.html`(판매자용 키 발급기)입니다.
`base: './'` 상대 경로 빌드라 하위 디렉터리에 올려도 동작합니다.

## 제품 구조

```
src/
  core/         저장소와 무관한 순수 로직 (전부 단위 테스트 대상)
    license.js      자체검증 라이선스 키 (신규 salt, 플랜 문자 L/P)
    fees.js         수납 상태·분할납부·월 마감 계산
    siblings.js     학부모 번호 매칭 형제 묶기
    attendance.js   출결 집계
    risk.js         이탈 위험 감지
    schedule.js     시간표 배치·강의실/강사 중복 검사
    customfields.js 계열별 확장 필드(전 계열 범용의 핵심)
    templates.js    알림 문구 템플릿
    backup.js       백업/복원 · Pro 마이그레이션
    perm.js         owner/teacher/desk 권한
  data/
    db.js           Dexie(IndexedDB) 스키마와 인덱스
    repo.js         저장소 파사드 (화면은 이 모듈만 사용)
    sync.js         Pro: Supabase push/pull/Realtime + 오프라인 큐
    seed.js         데모 시나리오 · 성능 테스트 더미 생성기
    perf.js         앱 내 성능 측정
  ui/
    shell.js        헤더/탭/라우팅/PIN 로그인
    branding.js     화이트라벨(학원명·로고·컬러·동적 manifest)
    report.js       Canvas 학부모 리포트카드
    virtual-list.js 가상 스크롤
    views/          출결·원생·수납·시간표·상담·지출·현황·설정·마법사·키오스크
supabase/schema.sql  Pro 스키마 + academy_id 기반 RLS + 실시간 publication
tools/keygen.html    판매자용 라이선스 키 발급기 (앱과 동일 알고리즘을 import)
docs/                아키텍처 · 사용설명서 목차 · 배포 안내
```

## 전 계열 범용의 작동 방식

계열마다 다른 것은 **"원생에게 무엇을 기록하는가"** 뿐입니다.
설정 > 학습 항목에서 원장이 항목을 직접 정의하면 원생 카드와 학부모 리포트에 자동으로 나타납니다.

| 계열 | 예시 항목 |
|---|---|
| 교과 | 진도 교재, 진도(단원), 최근 시험 점수 |
| 어학 | 레벨, 레벨 테스트 점수, 교재 |
| 예체능 | 진도 곡/작품, 교재, 대회·발표회 |
| 체육 | 띠 급수, 최근 승급일, 목표 |

설정 > 개발자·데모 도구에서 **영어학원 / 태권도장 / 피아노학원** 데모를 즉시 전환해 확인할 수 있습니다.

## 성능

기준은 원생 1,000명 · 반 80개 · 출결 20만 건에서 **모든 화면 1초 내**입니다. 이를 위해:

- 출결·수납은 절대 전체 로드하지 않고 **월/반 단위 복합 인덱스 범위 질의**만 사용
- 원생 목록은 **가상 스크롤**(보이는 행만 DOM) + 메모리 필터 검색(입력 디바운스 200ms)
- 현황 통계는 **월별 집계 캐시 테이블**(`monthlyStats`)에서 읽고 마감 시 갱신
- `npm run perf` 가 실제 Chromium + 실제 IndexedDB 로 더미를 만들고 화면별 렌더 시간을 측정해
  `perf-report.json` 을 남깁니다 (하나라도 기준 초과 시 종료 코드 1)

## 라이선스 키

12자리 `[플랜 1자][랜덤 7자][체크섬 4자]`, 표기는 `PXXX-XXXX-XXXX`.
서버 없이 앱에서 검증하며(`src/core/license.js`), **이 제품 전용 신규 salt**를 사용하므로 구제품 키와 호환되지 않습니다.
판매용 키는 `tools/keygen.html`(빌드 후 `dist/tools/keygen.html`)에서 발급하고 CSV로 저장합니다.
발급기는 앱과 같은 모듈을 import 하므로 알고리즘이 어긋날 수 없습니다.

> ⚠️ 출시 후에는 `LICENSE_SALT` 를 절대 변경하지 마세요. 이미 판매된 키가 모두 무효가 됩니다.

## Pro 설정 (Supabase)

1. Supabase 프로젝트 생성 → SQL Editor 에서 `supabase/schema.sql` 실행
2. Authentication > Providers 에서 **Anonymous sign-in** 활성화
3. 앱 설정 > Pro 동기화에 Project URL 과 anon key 입력
4. 원장 기기에서 "학원 만들기" → 표시되는 **초대 코드 6자리**를 강사 기기에서 입력해 합류
5. Lite 백업 파일(JSON)을 업로드하면 그대로 Pro 로 마이그레이션됩니다

RLS 정책상 `academy_id` 가 내 소속 학원인 행만 읽고 쓸 수 있어, 다른 학원 데이터는 조회 자체가 되지 않습니다.

## 문서

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 데이터 모델, 동기화·충돌 정책, 성능 설계
- [docs/MANUAL_OUTLINE.md](docs/MANUAL_OUTLINE.md) — 사용설명서 목차
- [docs/DEPLOY.md](docs/DEPLOY.md) — 빌드·배포·판매 운영 절차
