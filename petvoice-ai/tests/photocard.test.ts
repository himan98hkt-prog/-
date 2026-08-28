import { describe, expect, it } from 'vitest';
import { CARD_THEMES, layoutPhotoCard, resolveTheme, themesFor, wrapText } from '../src/core/photocard';

describe('wrapText', () => {
  it('공백 기준으로 줄을 나눈다', () => {
    // '나 지금'(5자) + ' 너무'는 8자라 넘치고, '너무 심심해'는 정확히 6자라 한 줄에 들어간다
    expect(wrapText('나 지금 너무 심심해', 6)).toEqual(['나 지금', '너무 심심해']);
    expect(wrapText('나 지금 너무 심심해', 4)).toEqual(['나 지금', '너무', '심심해']);
  });

  it('한 줄보다 긴 어절은 강제로 쪼갠다', () => {
    expect(wrapText('가나다라마바사아자차', 4)).toEqual(['가나다라', '마바사아', '자차']);
  });

  it('연속 공백을 정리하고 빈 문자열은 빈 배열로', () => {
    expect(wrapText('  안녕   하세요  ', 20)).toEqual(['안녕 하세요']);
    expect(wrapText('   ', 10)).toEqual([]);
  });
});

describe('layoutPhotoCard', () => {
  it('기본은 4:5 인스타 비율', () => {
    const layout = layoutPhotoCard({ width: 320, message: '심심해!', emotion: 'playful' });
    expect(layout.height).toBe(400);
  });

  it('말풍선이 카드 안에 들어온다', () => {
    const layout = layoutPhotoCard({
      width: 360,
      message: '지금 너무 심심해서 견딜 수가 없어 얼른 공 좀 던져줘 제발',
      emotion: 'playful',
    });
    expect(layout.bubble.x).toBeGreaterThan(0);
    expect(layout.bubble.x + layout.bubble.width).toBeLessThanOrEqual(layout.width);
    expect(layout.bubble.y + layout.bubble.height).toBeLessThan(layout.height);
  });

  it('글자가 길수록 폰트를 줄인다', () => {
    const short = layoutPhotoCard({ width: 320, message: '배고파!', emotion: 'hungry' });
    const long = layoutPhotoCard({ width: 320, message: '가'.repeat(50), emotion: 'hungry' });
    expect(long.fontSize).toBeLessThan(short.fontSize);
  });

  it('감정 뱃지에 라벨과 색이 실린다', () => {
    const layout = layoutPhotoCard({ width: 320, message: '아파…', emotion: 'pain' });
    expect(layout.badge.labelKey).toBe('emotion.pain');
    expect(layout.badge.emoji).toBe('🤕');
  });

  it('반려동물 이름이 워터마크에 들어간다', () => {
    const layout = layoutPhotoCard({ width: 320, message: '안녕', emotion: 'happy', petName: '초코' });
    expect(layout.watermark.text).toBe('초코 · PetVoice AI');
  });
});

describe('테마 잠금', () => {
  it('무료 사용자가 프로 테마를 고르면 기본 테마로 되돌린다', () => {
    expect(resolveTheme('peach', false).key).toBe('classic');
    expect(resolveTheme('peach', true).key).toBe('peach');
  });

  it('무료 사용자에게도 목록은 다 보여 주되 잠금 표시를 한다', () => {
    const list = themesFor(false);
    expect(list).toHaveLength(CARD_THEMES.length);
    expect(list.filter((t) => t.locked).length).toBeGreaterThan(0);
    expect(themesFor(true).every((t) => !t.locked)).toBe(true);
  });
});
