# 배포 안내

## 1. Vercel (웹)

```bash
npm i -g vercel
vercel link
vercel env add GEMINI_API_KEY production
vercel env add NEXT_PUBLIC_SUPABASE_URL production
vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY production
vercel env add SUPABASE_SERVICE_ROLE_KEY production
vercel --prod
```

체크리스트

- [ ] `SUPABASE_SERVICE_ROLE_KEY` 를 **NEXT_PUBLIC_ 없이** 등록했는가
- [ ] `GEMINI_API_KEY` 를 **NEXT_PUBLIC_ 없이** 등록했는가
- [ ] `NEXT_PUBLIC_OPERATOR_NAME` · `NEXT_PUBLIC_CONTACT_EMAIL` 을 채웠는가 (개인정보처리방침 표기)
- [ ] 커스텀 도메인을 연결했는가 — 초대장 링크(`/e/{id}`)가 학부모에게 그대로 노출된다
- [ ] 카카오 개발자 콘솔에서 도메인을 등록하고 `NEXT_PUBLIC_KAKAO_JS_KEY` 를 넣었는가

> 데모 저장소(`.data/store.json`)는 서버리스 환경에서 **쓰기가 되지 않아 요청 간에 유지되지 않습니다.**
> 실제 배포에는 반드시 Supabase 를 연결하세요. (설정 화면의 배지로 확인 가능)

## 2. Supabase

1. 프로젝트 생성 후 SQL Editor 에서 `supabase/schema.sql` 실행
   - **이미 쓰고 계신 프로젝트라면 같은 파일을 다시 실행하십시오.** 새 칸은 전부
     `add column if not exists` 로 붙여 두어 여러 번 실행해도 안전합니다
     (최근 추가: `events.stage_prefs` · `events.video_prefs` · `events.video_url`).
2. 필요하면 Authentication > Providers 에서 이메일 또는 소셜 로그인 활성화
   - 현재 MVP 는 브라우저 쿠키(`pe_academy`)로 학원을 식별합니다.
   - Supabase Auth 를 붙일 때는 `academies.owner_id` 에 `auth.uid()` 를 저장하고
     `lib/session.ts` 의 쿠키 조회를 세션 조회로 바꾸면 스키마의 RLS 정책이 그대로 유효합니다.
3. Storage 버킷(`logos`)을 만들어 학원 로고를 올리면 설정에서 URL 로 연결할 수 있습니다.

## 3. 모바일 앱(Expo/RN)으로 확장할 때

```
[앱] --(Supabase 사용자 JWT)--> [gemini-proxy Edge Function] --(GEMINI_API_KEY)--> [Gemini]
```

```bash
supabase secrets set GEMINI_API_KEY=...
supabase functions deploy gemini-proxy
```

앱 번들에는 anon key 만 넣습니다. Gemini 키는 Edge Function 시크릿에만 존재합니다.

## 4. 릴리스 전 점검

```bash
npm run lint
npm test
npm run build
npm run smoke
```

네 가지가 모두 통과해야 배포합니다. `smoke` 는 실제 서버를 띄워 행사 생성 → 명단 등록 →
순서표 생성 → 인쇄물 디자인 → 초대장 → 참석 회신 → 계정 삭제까지 밟습니다.

## 5. 알려진 의존성 이슈

`npm audit` 은 Next.js 14 계열에 대한 다수의 권고(DoS·캐시 오염 등)를 보고합니다.
해당 권고들은 대부분 16.3.x 에서 수정되었고 15.x 도 영향 범위에 포함됩니다.
개발 지시서가 Next.js 14 를 명시하므로 14 최신(14.2.35)을 사용하되,
자체 호스팅으로 운영한다면 이미지 최적화·미들웨어 캐시 설정을 점검하고
가능한 시점에 상위 버전으로 올리는 것을 권장합니다.
