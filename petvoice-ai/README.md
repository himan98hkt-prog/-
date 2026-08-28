# PetVoice AI 🐾

반려동물의 **울음소리 + 행동/자세 + 상황 맥락**을 함께 읽어 감정을 번역하는 멀티모달 앱.
소리만 듣고 장난스러운 멘트를 뱉는 기존 앱과 달리, 근거를 설명하고 **이상 징후가 보이면 병원 방문을 권한다.**

| | 기존 반려동물 소리 번역 앱 | PetVoice AI |
|---|---|---|
| 분석 신뢰도 | 주파수 매칭 · 랜덤 멘트 | 소리(Audio) + 행동(Vision) + 상황(Context) 결합 멀티모달 |
| 바이럴 요소 | 텍스트 표시 | 사진 위에 1인칭 말풍선이 합성된 **SNS 공유용 포토카드** |
| 실용성 | 일회성 재미 | 분리불안·통증 신호 감지 → **병원 권유 + 행동 교정 팁** |

---

## 빠른 시작

```bash
cd petvoice-ai
npm install
cp .env.example .env      # 값을 채우지 않아도 '데모 모드'로 전부 동작한다
npm start                 # Expo Go 또는 개발 빌드에서 실행
npm test                  # 핵심 로직 단위 테스트 91건
npm run typecheck         # 타입 검사
```

`.env` 를 비워 두면 **데모 모드**로 뜬다. 상황 맥락에 따라 다른 모의 결과를 돌려주므로
녹음 → 분석 → 결과 → 포토카드 → 다이어리까지 전체 흐름을 서버 없이 확인할 수 있다.

---

## 보안 아키텍처 — AI 키는 앱에 넣지 않는다

Play Console 보안 스캔에서 클라이언트 번들의 AI 키는 **거절 사유**다. 그래서 구조를 이렇게 짰다.

```
[Expo 앱] ──Bearer 사용자 토큰──> [Supabase Edge Function] ──GEMINI_API_KEY──> [Gemini API]
   키 없음                          gemini-proxy                 서버 시크릿에만 존재
```

- 앱은 `EXPO_PUBLIC_SUPABASE_URL` / `EXPO_PUBLIC_SUPABASE_ANON_KEY` 만 들고 다닌다(공개돼도 안전한 값).
- `src/api/config.ts` 의 `assertNoAiKeyInClient()` 가 개발 빌드 시작 시 클라이언트 환경변수를 훑어
  `*_GEMINI_API_KEY` 류가 섞이면 **즉시 예외를 던진다.** 실수로 커밋되는 걸 막는 안전핀.
- **무료 3회/일 제한은 서버에서도 건다.** 클라이언트 카운트는 우회 가능하므로
  `consume_quota()` SQL 함수가 진짜 방어선이다 (`supabase/schema.sql`).

### 서버 배포

```bash
supabase link --project-ref <your-ref>
supabase db push                                   # schema.sql 적용
supabase secrets set GEMINI_API_KEY=<google-ai-studio-key>
supabase functions deploy gemini-proxy
supabase functions deploy delete-account
```

Supabase 대시보드에서 **익명 로그인(Anonymous sign-ins)** 을 켜야 한다.
회원가입 없이 쓰면서도 서버가 요청자를 식별해 사용량을 제한할 수 있게 하는 장치다.

---

## 구조

```
petvoice-ai/
  App.tsx                  라우터 + 탭바 + 온보딩 게이트
  src/
    core/                  React Native 에 의존하지 않는 순수 로직 (전부 테스트 대상)
      types.ts             공용 타입
      emotions.ts          감정 14종 메타데이터 + 모델 표기 흔들림 흡수(별칭 정규화)
      prompt.ts            멀티모달 프롬프트 · 응답 스키마
      analysis.ts          모델 응답 파싱/정규화 (상위 3감정 합 100 보정)
      health.ts            이상 징후 판정 · 반복 패턴 감지
      quota.ts             무료 3회/일 · 프로 구독 판정
      billing.ts           구독 상태 판정 · 스토어 오퍼/영수증 정규화
      diary.ts             날짜별 집계 · 캘린더 격자 · 주간 통계
      photocard.ts         포토카드 레이아웃 계산 · 테마(무료/프로)
      date.ts, id.ts       로컬 날짜 유틸, ID
    api/
      config.ts            공개 설정 + AI 키 유출 가드
      subscription.ts      서버 구독 상태 조회 · 영수증 검증 요청
      proxy.ts             Edge Function 호출 (타임아웃·지수 백오프·에러 코드 매핑)
      supabase.ts          익명 세션, 계정 삭제
      demo.ts              서버 없이 도는 모의 응답
      errors.ts            사용자 문구로 바로 쓰는 에러 분류
    billing/
      iap.ts               react-native-iap 래퍼 (네이티브 모듈이 없으면 조용히 비활성)
      useBilling.ts        구매 → 서버 검증 → 상태 반영 → 트랜잭션 마무리
    store/usePetStore.ts   zustand + AsyncStorage 영속
    ui/
      navigation.tsx       최소 스택 라우터 (화면 8개라 react-navigation 미사용)
      permissions.ts       "설명 팝업 먼저, 그 다음 권한 요청" (Play 정책)
      media.ts             3초 녹음 / 사진 선택 / base64 변환
      useAnalyze.ts        녹음·촬영 공통 분석 흐름
      components/          PulseRecordButton, PhotoCard, EmotionBars, HealthNotice …
      screens/             Onboarding · Home · Capture · Result · History · Settings · Paywall · PetForm
  supabase/
    schema.sql             RLS + ON DELETE CASCADE + consume_quota()
    functions/_shared/          스토어 응답 → 구독 상태 매핑(순수, 테스트 대상) · 구글 서비스 계정 인증
    functions/gemini-proxy/     인증·검증·사용량 제한·Gemini 호출
    functions/verify-purchase/  영수증을 스토어에 직접 확인하고 구독 상태를 기록
    functions/play-rtdn/        Play 실시간 알림 수신 → 해지·환불·결제실패 즉시 반영
    functions/delete-account/   계정 삭제 (Play 필수 요건)
  tests/                   vitest 91건
  tools/make_placeholder_assets.py   아이콘/스플래시 자리표시 생성기
  docs/                    개인정보처리방침 초안 · 출시 체크리스트
```

## 화면 흐름

```
온보딩 → 반려동물 등록 ─┬─> 홈(3초 녹음, 상황 칩) ─┐
                        └─> 카메라(가이드라인 오버레이) ─┴─> 결과(포토카드·감정막대·행동가이드·이상징후)
                                                             ├─> 공유(인스타/카톡)
                                                             └─> 다이어리(캘린더 · 주간 리포트)
```

## 핵심 설계 메모

**모델 응답을 믿지 않는다.** `parseAnalysis()` 는 ```json 펜스, 앞뒤 잡담, 제멋대로인 감정 키
(`PLAYFUL`, `attention_seeking`, `불안`), 합이 100이 아닌 점수를 전부 흡수한다.
상위 3개만 남기고 최대잔여법으로 합을 정확히 100에 맞춘다. 화면은 이 계약만 믿으면 된다.

**이상 징후는 진단하지 않는다.** `assessHealth()` 는 통증 점수·모델의 healthAlert·행동 분석
문장의 의학적 신호(절뚝임·구토·기침 등)를 근거로 `none / watch / vet` 3단계를 매기고,
왜 그렇게 봤는지를 사용자에게 그대로 보여 준다. 한 건은 우연일 수 있어서
`assessHistoryRisk()` 가 최근 7일 반복 여부로 강도를 다시 조정한다.

**레이아웃도 순수 함수로.** 포토카드의 말풍선 위치·폰트 크기·줄바꿈은 `layoutPhotoCard()` 가
계산하고 컴포넌트는 그리기만 한다. 덕분에 "긴 문장이 카드 밖으로 나가지 않는다"를
테스트로 고정할 수 있고, 나중에 서버 사이드 OG 이미지 렌더링에도 그대로 재사용된다.

## 수익 모델

| | 무료 | 프로 (월 3,900원) |
|---|---|---|
| 분석 | 하루 3회 | 무제한 |
| 반려동물 등록 | 1마리 | 무제한 |
| 포토카드 테마 | 2종 | 6종 전부 |
| 주간 행동 리포트 | — | ✅ |

### 결제 흐름

```
[앱] 구매 요청 ──> [Play / App Store] ──> purchaseUpdatedListener
                                              │
                                              ├─ 영수증 ──> [verify-purchase] ──> 스토어에 직접 확인
                                              │                                    └─> subscriptions 테이블
                                              └─ 검증 성공 후에만 finishTransaction

[Play] 해지·환불·결제실패 ──> Pub/Sub ──> [play-rtdn] ──> subscriptions 테이블 갱신
```

**앱이 보내온 "프로예요"는 절대 믿지 않는다.** 권한의 유일한 출처는 서버의 `subscriptions`
테이블이고, 그 행은 Edge Function 이 스토어에 직접 물어본 결과로만 갱신된다.
클라이언트는 이 테이블에 쓰기 권한이 없다(RLS 는 select 만 허용).

순서에 신경 쓴 지점:
- **검증 전에 `finishTransaction` 을 부르면** 영수증이 사라져 "결제는 됐는데 프로가 안 열리는" 상태가 된다.
  그래서 서버 검증이 끝난 뒤에만 마무리한다. 검증에 실패하면 마무리하지 않아 다음 실행에서 다시 전달된다.
- **끝내 마무리하지 않으면** Play 가 3일 뒤 자동 환불한다. 그래서 검증 성공 시 서버가 곧바로 acknowledge 한다.
- **해지 예약(`canceled`)은 남은 기간을 열어 준다.** 여기서 바로 끊으면 이미 결제된 기간을 뺏는 셈이라 환불 분쟁이 된다.
- **결제 실패 유예(`grace`)에도 기능을 유지한다.** 카드가 잠깐 막힌 사용자를 즉시 잠그면 그대로 이탈한다.
- 느린 결제 수단(계좌이체)의 `pending` 구매는 마무리하지 않고 승인 알림을 기다린다.

### 스토어 설정

```bash
# 1) Play Console ▸ 수익 창출 ▸ 구독에서 상품 생성
#    구독 ID: petvoice_pro_monthly   (기본 요금제 + 원하면 무료 체험 오퍼)
# 2) 서비스 계정을 만들어 Play Console 에 '재무 데이터 보기' 권한 부여 후 JSON 키 발급
supabase secrets set GOOGLE_SERVICE_ACCOUNT_JSON="$(cat service-account.json)"
supabase secrets set ANDROID_PACKAGE_NAME=app.petvoice.ai
supabase secrets set APPLE_SHARED_SECRET=<App Store Connect 공유 비밀>
supabase secrets set RTDN_SECRET=<임의의 긴 문자열>

supabase functions deploy verify-purchase
supabase functions deploy play-rtdn --no-verify-jwt   # Pub/Sub 는 사용자 토큰이 없다

# 3) Play Console ▸ 실시간 개발자 알림에 Pub/Sub 주제를 연결하고,
#    그 주제의 push 엔드포인트를 아래로 지정
#    https://<project>.functions.supabase.co/play-rtdn?secret=<RTDN_SECRET>
```

> 결제는 **네이티브 모듈**이라 Expo Go·웹 미리보기에서는 동작하지 않는다.
> 그런 환경에서는 결제 버튼이 비활성화되고 이유를 화면에 그대로 알린다(앱은 죽지 않는다).
> 실제 결제 테스트는 EAS 개발 빌드 + Play Console 내부 테스트 트랙에서 한다.

## 검증 상태

```
✅ npm test          137건 통과 (core 로직 + 프록시 계약 + 구독 상태 판정)
✅ npm run typecheck  tsc --noEmit 클린 (앱 전체)
✅ npx expo export --platform android   번들 성공
✅ 웹 빌드 스모크      온보딩→등록→홈→결과→다이어리→설정→페이월 렌더 확인 (결제 비활성 경로 포함)
⬜ 실기기 스모크      녹음·촬영·공유·실제 결제는 기기에서만 검증 가능
⬜ 결제 E2E          Play 내부 테스트 트랙에서 구매→검증→해지→복원 한 바퀴
```

## 다음 할 일

1. Play Console 에 구독 상품(`petvoice_pro_monthly`) 등록 + 서비스 계정 발급 후 위 시크릿 설정
2. `assets/` 자리표시 이미지를 실제 아트워크로 교체
3. `src/ui/links.ts` 의 개인정보처리방침·약관 URL 을 실제 배포 주소로 교체
4. `docs/PLAY_STORE_CHECKLIST.md` 의 출시 항목 진행 (14일 20인 비공개 테스트 포함)
