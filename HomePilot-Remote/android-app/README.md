# HomePilot Android 앱 (Flutter)

| 화면 | 파일 |
|---|---|
| PC 목록 / 등록 안내 | `lib/screens/pc_list.dart` |
| PC 추가 (주소·장치 ID, 확인 코드) | `lib/screens/add_pc.dart`, `common.dart` |
| PC 상태 대시보드 | `lib/screens/dashboard.dart` |
| 원격 화면·조작 | `lib/screens/remote.dart`, `view_math.dart` |
| 설정 (휴대폰 이름, 기본 화질, 기기 키) | `lib/screens/settings.dart` |
| 프로토콜·암호화 (Flutter 무관, 순수 Dart) | `lib/protocol/` |

- 암호화: Noise XX(X25519·ChaCha20-Poly1305·BLAKE2s)를 `package:cryptography` 로 직접 구현.
  PC 에이전트(Rust snow)와의 호환성은 `tests/app-interop.sh` 가 실제로 연결해 확인합니다.
- 휴대폰 키는 `flutter_secure_storage`(Android Keystore 보호)에 저장.
- AI 프로그램 관리·파일 관리는 다음 단계에서 구현 (현재 화면에는 "제공 예정"으로 표시).

```bash
flutter pub get
flutter analyze && flutter test
dart run tool/interop_client.dart ws://127.0.0.1:8443 <장치ID> /tmp/app.key   # 실제 에이전트와 연결 시험
flutter build apk --release      # Android SDK 필요 (CI 에서 빌드)
```

서명: `android/key.properties`(저장소에 올리지 않음)가 있으면 그 키, 없으면 디버그 키로 서명합니다.
CI 는 저장소 Secrets `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD` 가 있으면 릴리스 키로 서명합니다.
> 디버그 키로 서명된 APK 는 빌드마다 키가 달라질 수 있어, 새 버전을 설치할 때 기존 앱을 지워야 할 수 있습니다
> (지우면 휴대폰 키가 바뀌므로 PC 에 다시 등록). 고정 서명 키 설정은 Phase 7 에서 진행합니다.
