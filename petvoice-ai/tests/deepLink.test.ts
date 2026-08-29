import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { APP_SCHEME, parseDeepLink } from '../src/core/deepLink';

describe('parseDeepLink', () => {
  it.each([
    'petvoice://record',
    'petvoice:///record',
    'petvoice:record',
    'petvoice://record/',
    'petvoice://record?from=shortcut',
    'PetVoice://Record',
    '  petvoice://record  ',
  ])('%s → 바로 녹음', (url) => {
    expect(parseDeepLink(url)).toEqual({ kind: 'record' });
  });

  it('다이어리 링크', () => {
    expect(parseDeepLink('petvoice://diary')).toEqual({ kind: 'diary' });
  });

  it.each([
    ['빈 값', ''],
    ['null', null],
    ['undefined', undefined],
    ['다른 스킴', 'https://petvoice.app/record'],
    ['비슷한 스킴', 'petvoiceX://record'],
    ['모르는 동작', 'petvoice://delete-everything'],
    ['빈 경로', 'petvoice://'],
  ])('%s 는 무시한다', (_name, url) => {
    expect(parseDeepLink(url)).toBeNull();
  });

  it('스킴 상수가 앱 설정과 같은 값이다', () => {
    // 둘이 어긋나면 바로가기가 조용히 아무것도 안 한다 — 실기기에서만 드러난다
    const appJson = JSON.parse(readFileSync(join(process.cwd(), 'app.json'), 'utf8'));
    expect(appJson.expo.scheme).toBe(APP_SCHEME);
    expect(JSON.stringify(appJson)).toContain(`${APP_SCHEME}://record`);
  });
});
