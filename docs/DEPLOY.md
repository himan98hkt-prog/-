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
dist/tools/keygen.html   판매자 전용 키 발급기 (고객 배포 금지)
dist/assets/*            해시가 붙은 JS/CSS
```

`base: './'` 상대 경로 빌드라 `https://example.com/note/` 같은 하위 경로에 올려도 그대로 동작합니다.

## 2. 웹호스팅 업로드

1. FTP/파일관리자로 `dist/` 내용을 배포 디렉터리에 업로드
2. **`tools/` 디렉터리는 고객용 배포 경로에 올리지 않습니다.** 판매자 PC 나 접근 제한 경로에서만 사용
3. HTTPS 필수 — 서비스 워커(오프라인)와 홈 화면 설치가 HTTPS 에서만 동작합니다
4. 캐시 정책: `assets/*` 는 파일명에 해시가 있으므로 장기 캐시, `*.html` 은 `no-cache` 권장

업데이트 배포 시 서비스 워커가 "네트워크 우선"으로 동작하므로, 사용자는 새로고침 한 번으로 최신 버전을 받습니다.

## 3. 라이선스 키 발급 흐름

1. `tools/keygen.html` 을 브라우저로 연다
2. 플랜(Lite/Pro)과 수량을 정해 발급 → CSV 저장 (주문번호를 메모에 기록)
3. WooCommerce 주문 완료 시 고객에게 키 전달
4. 고객이 앱 설정 > 라이선스에 입력 → 플랜 자동 활성화
5. 고객 문의 시 발급기 하단 "키 검증"에 키를 붙여 유효성/플랜 확인

> 키는 서버 없이 검증됩니다. 폐기(블랙리스트)가 필요하면 Pro 는 `academies.license_key_hash` 로
> 서버 측 차단이 가능하고, Lite 는 구조상 불가하므로 정책으로 관리합니다.

## 4. Pro 인프라 준비 (학원별이 아니라 전체 1회)

1. Supabase 프로젝트 1개 생성 (무료 티어 기준 설계)
2. SQL Editor 에서 `supabase/schema.sql` 실행
3. Authentication > Providers > **Anonymous sign-in 활성화**
4. Project URL / anon key 를 고객 안내문에 포함하거나, 빌드 시 `.env` 에 주입
   (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`)

anon key 는 공개돼도 RLS 로 막히지만, `service_role` 키는 절대 프런트에 넣지 않습니다.

## 5. 릴리스 체크리스트

- [ ] `npm test` 전부 통과
- [ ] `npm run perf` 전 항목 1초 이내 (perf-report.json 보관)
- [ ] 데모 3종(영어학원·태권도장·피아노학원) 전환 확인
- [ ] 브랜딩 변경이 헤더·리포트·설치 아이콘에 반영되는지 확인
- [ ] 백업 → 초기화 → 복원 왕복 확인
- [ ] Pro: 기기 2대 동시 출결 체크 3초 내 반영, 다른 학원 데이터 접근 불가 확인
- [ ] 라이선스 키 발급 → 입력 → 플랜 활성화 확인
