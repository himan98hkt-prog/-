# Android 앱 (Phase 2 예정)

Flutter 로 개발합니다. 아직 시작하지 않았습니다 (개발 환경에 Flutter/Android SDK 설치 필요).

구현 순서 계획:
1. 프로토콜 Dart 구현 — `docs/ARCHITECTURE.md` 의 규격 (Noise XX: `cryptography` 패키지의 X25519·ChaCha20-Poly1305·BLAKE2s 사용), Rust 쪽 테스트 벡터와 상호 검증
2. PC 등록(장치 ID 입력/QR) → 확인 코드 표시
3. PC 목록·상태 대시보드
4. 원격 화면: 확대/축소, 터치=마우스 이동, 탭=클릭, 길게 누르기=우클릭, 두 손가락 스크롤, 드래그, 가로 모드, 품질/해상도, 지연 표시
5. 한글/영문 키보드 (조합 완료 문자열을 `key_text` 로 전송), 특수키 바
6. 보안 설정: 앱 잠금(생체 인증), 등록 PC 관리
