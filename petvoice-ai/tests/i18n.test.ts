import { describe, expect, it } from 'vitest';
import { en } from '../src/i18n/en';
import { ja } from '../src/i18n/ja';
import { ko } from '../src/i18n/ko';
import { formatMessage, formatRelative, pickLocale, translate } from '../src/i18n';
import { msg, raw } from '../src/core/message';

describe('사전 정합성', () => {
  const koKeys = Object.keys(ko).sort();

  it('영어 사전이 한국어와 같은 키를 갖는다', () => {
    expect(Object.keys(en).sort()).toEqual(koKeys);
  });

  it('일본어 사전이 한국어와 같은 키를 갖는다', () => {
    expect(Object.keys(ja).sort()).toEqual(koKeys);
  });

  it('빈 문자열로 남겨 둔 번역이 없다', () => {
    for (const [locale, dict] of Object.entries({ ko, en, ja })) {
      const empty = Object.entries(dict).filter(([, v]) => !String(v).trim());
      expect(`${locale}: ${empty.map(([k]) => k).join(', ')}`).toBe(`${locale}: `);
    }
  });

  /**
   * 원어민 검수를 대신하지는 못한다. 다만 검수자가 손으로 찾을 필요가 없는 것들 —
   * 번역을 빠뜨렸거나, 한 언어의 글자가 다른 언어에 섞여 들어간 경우는 여기서 잡는다.
   */
  it('영어 사전에 한글이 섞여 있지 않다', () => {
    const leaked = Object.entries(en).filter(([, v]) => /[가-힣]/.test(v));
    expect(leaked.map(([k]) => k)).toEqual([]);
  });

  it('일본어 사전에 한글이 섞여 있지 않다', () => {
    const leaked = Object.entries(ja).filter(([, v]) => /[가-힣]/.test(v));
    expect(leaked.map(([k]) => k)).toEqual([]);
  });

  it('영어 사전에 일본어 가나가 섞여 있지 않다', () => {
    const leaked = Object.entries(en).filter(([, v]) => /[ぁ-んァ-ン]/.test(v));
    expect(leaked.map(([k]) => k)).toEqual([]);
  });

  it('번역을 빠뜨린 채 한국어를 그대로 둔 항목이 없다', () => {
    // 이모지·기호·자리표시자만 있는 값은 세 언어가 같아도 정상이다 (예: '{value}%')
    const meaningful = (text: string) => /[가-힣A-Za-z぀-ヿ一-鿿]/.test(text.replace(/\{\w+\}/g, ''));
    for (const [locale, dict] of Object.entries({ en, ja })) {
      const copied = koKeys.filter((key) => {
        const source = ko[key as keyof typeof ko];
        return meaningful(source) && dict[key as keyof typeof en] === source;
      });
      expect(`${locale}: ${copied.join(', ')}`).toBe(`${locale}: `);
    }
  });

  it('반려동물 1인칭 대사에 성별이 드러나는 표현을 쓰지 않는다', () => {
    // 아이의 성별을 우리는 모른다. 일본어는 1인칭에서 특히 드러난다.
    const voiceKeys = koKeys.filter((key) => key.startsWith('voice.fallback.'));
    const gendered = voiceKeys.filter((key) => /ぼく|僕|おれ|俺|あたし/.test(ja[key as keyof typeof ja]));
    expect(gendered).toEqual([]);
  });

  it('한국어에 있는 자리표시자가 다른 언어에도 있다', () => {
    const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const key of koKeys) {
      const expected = placeholders(ko[key as keyof typeof ko]);
      for (const [locale, dict] of Object.entries({ en, ja })) {
        expect(`${locale}/${key}: ${placeholders(dict[key as keyof typeof en]).join(',')}`).toBe(
          `${locale}/${key}: ${expected.join(',')}`,
        );
      }
    }
  });
});

describe('translate', () => {
  it('자리표시자를 채운다', () => {
    expect(translate('ko', 'quota.freeRemaining', { remaining: 2, limit: 3 })).toBe(
      '오늘 무료 분석 2/3회 남음',
    );
    expect(translate('en', 'quota.freeRemaining', { remaining: 2, limit: 3 })).toContain('2 of 3');
  });

  it('@ 로 시작하는 값은 다시 번역한다', () => {
    const text = translate('ko', 'diary.headline.noCompare', { emoji: '🎾', emotion: '@emotion.playful' });
    expect(text).toContain('신남·놀고싶음');
  });

  it('없는 키는 키 그대로 돌려줘 빠진 번역이 눈에 띄게 한다', () => {
    expect(translate('ko', 'nope.missing')).toBe('nope.missing');
  });

  it('해당 언어에 없으면 한국어로 떨어진다', () => {
    const partial = { ...en } as Record<string, string>;
    delete partial['common.cancel'];
    // 실제 사전은 완전하므로, 폴백 동작은 존재하지 않는 언어 코드로 확인한다
    expect(translate('de' as never, 'common.cancel')).toBe('취소');
  });
});

describe('formatMessage', () => {
  it('번역 참조는 번역하고, 모델이 쓴 문장은 그대로 둔다', () => {
    expect(formatMessage('ko', msg('health.sign.pain'))).toBe('통증 의심 신호');
    expect(formatMessage('ko', raw('모델이 쓴 문장입니다'))).toBe('모델이 쓴 문장입니다');
  });

  it('중첩 참조가 붙은 문장도 조립한다', () => {
    const text = formatMessage('ko', msg('health.reason.sign', { sign: '@health.sign.gait' }));
    expect(text).toBe('보행 이상이(가) 분석 내용에 언급됐어요.');
  });
});

describe('formatRelative', () => {
  it('구조체를 언어에 맞는 문장으로 만든다', () => {
    expect(formatRelative({ kind: 'justNow' }, 'ko')).toBe('방금 전');
    expect(formatRelative({ kind: 'minutes', value: 5 }, 'en')).toBe('5 min ago');
    expect(formatRelative({ kind: 'yesterday' }, 'ja')).toBe('昨日');
  });
});

describe('pickLocale', () => {
  it('기기 언어 목록에서 지원 언어를 고른다', () => {
    expect(pickLocale(['ja-JP', 'en-US'])).toBe('ja');
    expect(pickLocale(['en-GB'])).toBe('en');
    expect(pickLocale(['ko-KR'])).toBe('ko');
  });

  it('지원하지 않는 언어뿐이면 한국어', () => {
    expect(pickLocale(['de-DE', 'fr-FR'])).toBe('ko');
    expect(pickLocale([])).toBe('ko');
  });
});
