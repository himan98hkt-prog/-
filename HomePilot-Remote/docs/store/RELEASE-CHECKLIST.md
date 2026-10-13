# 출시 체크리스트

✅ = 이 저장소에서 완료·확인, ⬜ = 사용자 작업(계정·비용·공개 게시가 필요)

## 이미 준비된 것
- ✅ 앱 아이콘(적응형·단색), 스토어 아이콘 512, 대표 이미지 1024x500 (design/)
- ✅ 대상 Android API 36, 권한 최소화(INTERNET·결제)
- ✅ 업로드 서명 키 생성: `C:\AI-Projects\homepilot-keys\upload-keystore.jks`
  (비밀번호는 같은 폴더의 key.properties, **저장소에 없음** → USB·클라우드 비밀 보관함에 백업 필수.
  잃어버리면 앱 업데이트를 올릴 수 없음)
- ✅ 출시용 AAB 빌드 (Pro 제한 켬):
  `flutter build appbundle --release --dart-define=ENFORCE_PRO=true`
  → android-app/build/app/outputs/bundle/release/app-release.aab (업로드 키 서명 확인)
- ✅ Windows 설치 파일: releases/HomePilot-Agent-Setup-0.3.0.exe (Inno Setup, 관리자 권한 불필요)
- ✅ 등록 정보·개인정보처리방침·데이터 보안 답변 초안 (docs/store/)

## 사용자가 할 일 (순서대로)
1. ⬜ Google Play 개발자 계정 등록 (1회 $25)
2. ⬜ 개인정보처리방침을 공개 주소에 올리기 (무료: GitHub Pages, Notion 공개 페이지 등) → 문의 이메일 기입
3. ⬜ Play Console 에서 앱 만들기 → 패키지 이름 `com.homepilot.remote`
4. ⬜ "Play 앱 서명" 사용 (권장) → AAB 업로드 (내부 테스트 트랙부터)
5. ⬜ 수익 창출 › 상품: 구독 `homepilot_pro_monthly`(1,900원), `homepilot_pro_yearly`(14,900원),
   일회성 `homepilot_pro_lifetime`(39,000원) 만들기 → 활성화
6. ⬜ 라이선스 테스트 계정 추가 후, 내부 테스트로 설치해 결제·구매 복원 확인
7. ⬜ 데이터 보안 양식(docs/store/data-safety.md), 콘텐츠 등급, 대상 연령 작성
8. ⬜ 스크린샷 4~8장 업로드 → 프로덕션 출시 요청

## 출시 전 권장 개선 (선택)
- Windows 코드 서명 인증서 (연 15~50만 원): 없으면 설치 시 "알 수 없는 게시자" 경고
- 결제 영수증 서버 검증 (지금은 휴대폰에서만 확인 → 위·변조된 앱에 취약)
- 같은 Wi-Fi 바로 접속: 사용자 PC 의 네트워크가 "공용" 이면 Windows 방화벽이 막음 → 설치 프로그램에서 방화벽 허용 안내
