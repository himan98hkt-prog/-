// 구글 플레이 업로드 키로 서명하는 release 빌드 설정.
// - 빌드할 때 아래 환경 변수가 있으면 그 키로 서명하고(스토어용 AAB),
//   없으면 예전처럼 디버그 키로 서명한다(직접 설치용 APK).
//   CARDSCAN_UPLOAD_STORE_FILE, CARDSCAN_UPLOAD_STORE_PASSWORD, CARDSCAN_UPLOAD_KEY_ALIAS, CARDSCAN_UPLOAD_KEY_PASSWORD
const { withAppBuildGradle } = require('expo/config-plugins');

const MARK = '// cardscan-upload-signing';

module.exports = function withUploadSigning(config) {
  return withAppBuildGradle(config, (cfg) => {
    let gradle = cfg.modResults.contents;
    if (gradle.includes(MARK)) return cfg;
    const signing = `
        ${MARK}
        release {
            def uploadStore = System.getenv('CARDSCAN_UPLOAD_STORE_FILE')
            if (uploadStore) {
                storeFile file(uploadStore)
                storePassword System.getenv('CARDSCAN_UPLOAD_STORE_PASSWORD')
                keyAlias System.getenv('CARDSCAN_UPLOAD_KEY_ALIAS')
                keyPassword System.getenv('CARDSCAN_UPLOAD_KEY_PASSWORD')
            }
        }`;
    if (!/signingConfigs\s*\{/.test(gradle)) throw new Error('withUploadSigning: signingConfigs 블록을 찾지 못했습니다');
    gradle = gradle.replace(/signingConfigs\s*\{/, (m) => m + signing);
    // buildTypes.release 의 서명만 바꾼다 (debug 빌드는 그대로)
    const release = /(buildTypes\s*\{[\s\S]*?release\s*\{[\s\S]*?)signingConfig signingConfigs\.debug/;
    if (!release.test(gradle)) throw new Error('withUploadSigning: release 서명 설정을 찾지 못했습니다');
    gradle = gradle.replace(release, "$1signingConfig System.getenv('CARDSCAN_UPLOAD_STORE_FILE') ? signingConfigs.release : signingConfigs.debug");
    cfg.modResults.contents = gradle;
    return cfg;
  });
};
