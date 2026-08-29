const { AndroidConfig, withAndroidManifest, withDangerousMod } = require('@expo/config-plugins');
const fs = require('fs');
const path = require('path');

/**
 * 홈 화면 아이콘을 길게 눌렀을 때 나오는 "3초 녹음" 바로가기 (안드로이드).
 *
 * 앱을 열고 → 탭을 고르고 → 버튼을 누르는 사이에 정작 찍고 싶던 소리는 끝난다.
 * 바로가기는 그 세 단계를 한 번으로 줄인다.
 *
 * 위젯(AppWidget)이 아니라 **정적 바로가기**로 만든 이유:
 * 위젯은 별도 프로세스에서 도는 네이티브 코드가 필요해 Expo 관리형 흐름을
 * 벗어나고, 실기기 없이는 검증할 방법이 사실상 없다. 바로가기는 매니페스트와
 * XML 두 개면 끝나고 prebuild 결과로 확인할 수 있다.
 * 위젯을 나중에 붙이더라도 여기서 만든 딥링크(`petvoice://record`)를 그대로 쓴다.
 *
 * 라벨은 문자열 리소스로 빼서 기기 언어를 따라간다 — 한국어 앱을 영어 폰에서
 * 쓰는 사람이 적지 않다.
 */

const SHORTCUT_ID = 'record';
const LABELS = {
  values: { short: '3초 녹음', long: '바로 3초 녹음하기' },
  'values-en': { short: 'Record 3s', long: 'Record for 3 seconds' },
  'values-ja': { short: '3秒録音', long: 'すぐに3秒録音する' },
};

const STRINGS_XML = (labels) => `<?xml version="1.0" encoding="utf-8"?>
<resources>
  <string name="shortcut_record_short">${labels.short}</string>
  <string name="shortcut_record_long">${labels.long}</string>
</resources>
`;

/**
 * 패키지명을 매니페스트 자리표시자로 두면 안 된다.
 * 자리표시자는 AndroidManifest.xml 에서만 치환되고 res/xml 은 문자열 그대로 남아
 * 바로가기가 조용히 아무 앱도 열지 못한다 — prebuild 결과를 열어 보고 알았다.
 * 그래서 패키지명과 액티비티를 여기서 박아 넣는다.
 */
const SHORTCUTS_XML = (scheme, applicationId) => `<?xml version="1.0" encoding="utf-8"?>
<shortcuts xmlns:android="http://schemas.android.com/apk/res/android">
  <shortcut
    android:shortcutId="${SHORTCUT_ID}"
    android:enabled="true"
    android:icon="@mipmap/ic_launcher"
    android:shortcutShortLabel="@string/shortcut_record_short"
    android:shortcutLongLabel="@string/shortcut_record_long">
    <intent
      android:action="android.intent.action.VIEW"
      android:targetPackage="${applicationId}"
      android:targetClass="${applicationId}.MainActivity"
      android:data="${scheme}://record" />
  </shortcut>
</shortcuts>
`;

function write(file, contents) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, contents, 'utf8');
}

/**
 * 문자열 리소스는 별도 파일(`shortcuts.xml`)에 쓴다.
 * Expo 가 만드는 `strings.xml` 을 건드리면 다른 플러그인과 순서를 다투게 된다.
 */
function withShortcutResources(config) {
  return withDangerousMod(config, [
    'android',
    (cfg) => {
      const applicationId = cfg.android?.package;
      if (!applicationId) throw new Error('withRecordShortcut: android.package 가 필요합니다.');

      const res = path.join(cfg.modRequest.platformProjectRoot, 'app/src/main/res');
      write(path.join(res, 'xml/shortcuts.xml'), SHORTCUTS_XML(cfg.scheme ?? 'petvoice', applicationId));
      for (const [dir, labels] of Object.entries(LABELS)) {
        write(path.join(res, dir, 'shortcuts_strings.xml'), STRINGS_XML(labels));
      }
      return cfg;
    },
  ]);
}

/** 런처 액티비티에 바로가기 목록을 연결한다 */
function withShortcutManifest(config) {
  return withAndroidManifest(config, (cfg) => {
    const activity = AndroidConfig.Manifest.getMainActivityOrThrow(cfg.modResults);
    activity['meta-data'] = (activity['meta-data'] ?? []).filter(
      (item) => item.$?.['android:name'] !== 'android.app.shortcuts',
    );
    activity['meta-data'].push({
      $: { 'android:name': 'android.app.shortcuts', 'android:resource': '@xml/shortcuts' },
    });
    return cfg;
  });
}

module.exports = function withRecordShortcut(config) {
  return withShortcutManifest(withShortcutResources(config));
};
