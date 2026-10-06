import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { CSV_HEADERS } from '../src/core/exportData';
import { SORT_LABEL } from '../src/core/organize';
import { PRO_BENEFITS, PRO_REASON } from '../src/core/pro';
import { CONNECTOR_LABEL } from '../src/core/settings';
import { FIELD_LABEL, KIND_LABEL } from '../src/core/types';
import { langFromCode, resolveLang, t } from '../src/i18n/core';
import { EN } from '../src/i18n/en';

const HANGUL = /[가-힣]/;
function sources(dir: string): string[] {
  return fs.readdirSync(dir).flatMap((f) => {
    const p = path.join(dir, f);
    if (fs.statSync(p).isDirectory()) return sources(p);
    return /\.(ts|tsx)$/.test(f) && !p.includes(`${path.sep}i18n${path.sep}`) ? [p] : [];
  });
}
const files = sources(path.join(__dirname, '../src')).map((f) => ({ f, s: fs.readFileSync(f, 'utf8') }));
const unescape = (s: string) => s.replace(/\\'/g, "'").replace(/\\n/g, '\n').replace(/\\\\/g, '\\');

/** 화면 코드의 t('…') 문장 */
const calls = new Set<string>();
for (const { s } of files) for (const m of s.matchAll(/\bt\('((?:[^'\\]|\\.)*)'/g)) calls.add(unescape(m[1]));

/** 파일 안에 정의해 쓰는 라벨 맵 (쓰는 곳에서 t(MAP[k])) */
function mapValues(name: string): string[] {
  for (const { s } of files) {
    const at = s.search(new RegExp(`const ${name}\\b`));
    if (at < 0) continue;
    const rest = s.slice(at);
    const end = rest.search(/\n(?:\};|\];|\s*: \{\};)/);
    const block = end > 0 ? rest.slice(0, end) : rest;
    return [...block.matchAll(/'((?:[^'\\]|\\.)*[가-힣](?:[^'\\]|\\.)*)'/g)].map((x) => unescape(x[1]));
  }
  throw new Error(`${name} 를 찾지 못함`);
}

const labels = [
  ...Object.values(KIND_LABEL),
  ...Object.values(FIELD_LABEL),
  ...Object.values(CONNECTOR_LABEL),
  ...Object.values(SORT_LABEL),
  ...Object.values(PRO_REASON),
  ...PRO_BENEFITS,
  ...CSV_HEADERS,
  '확인필요',
  ...mapValues('HELP'),
  ...mapValues('WEB_LIMITS'),
  ...mapValues('PHASE_TEXT'),
  ...mapValues('FOLLOW_PRESETS'),
];

describe('영어 번역', () => {
  it('화면의 모든 한국어 문장에 영어 번역이 있다', () => {
    const missing = [...calls, ...labels].filter((k) => HANGUL.test(k) && !(k in EN));
    expect(missing).toEqual([]);
  });

  it('번역에 {숫자} 자리가 그대로 있다', () => {
    const holes = (s: string) => (s.match(/\{\d+\}/g) ?? []).sort().join();
    const bad = Object.entries(EN).filter(([k, v]) => holes(k) !== holes(v));
    expect(bad).toEqual([]);
  });

  it('영어 번역에 한글이 섞이지 않는다 (언어 선택 라벨 제외)', () => {
    const bad = Object.entries(EN).filter(([, v]) => HANGUL.test(v) && !v.includes('언어'));
    expect(bad).toEqual([]);
  });
});

describe('t()', () => {
  it('언어별 문장과 자리 채우기', () => {
    expect(t('저장', undefined, 'ko')).toBe('저장');
    expect(t('저장', undefined, 'en')).toBe('Save');
    expect(t('오늘 연락할 사람 {1}명', { 1: 3 }, 'en')).toBe('3 to follow up today');
    expect(t('번역 없는 문장', undefined, 'en')).toBe('번역 없는 문장');
  });

  it('휴대폰 언어 → 앱 언어 (한국어가 아니면 영어)', () => {
    expect(langFromCode('ko')).toBe('ko');
    expect(langFromCode('ko-KR')).toBe('ko');
    expect(langFromCode('en')).toBe('en');
    expect(langFromCode('ja')).toBe('en');
    expect(langFromCode(null)).toBe('en');
    expect(resolveLang('auto', 'ko')).toBe('ko');
    expect(resolveLang('en', 'ko')).toBe('en');
    expect(resolveLang('ko', 'de')).toBe('ko');
  });
});
