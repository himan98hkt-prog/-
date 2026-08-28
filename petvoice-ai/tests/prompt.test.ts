import { describe, expect, it } from 'vitest';
import { EMOTION_KEYS } from '../src/core/emotions';
import { RESPONSE_SCHEMA, buildPrompt } from '../src/core/prompt';
import type { PetProfile } from '../src/core/types';

const pet: PetProfile = { id: 'p', name: '초코', type: 'DOG', breed: '포메라니안', ageMonths: 18, createdAt: 0 };
const base = { pet, locale: 'ko' as const };

describe('buildPrompt', () => {
  it('오디오와 이미지에 다른 지시를 넣는다', () => {
    const audio = buildPrompt({ ...base, mediaType: 'audio/m4a', context: '외출 직전' });
    const image = buildPrompt({ ...base, mediaType: 'image/jpeg', context: '외출 직전' });
    expect(audio).toContain('울음소리/짖는 소리');
    expect(image).toContain('행동/자세 사진');
  });

  it('프로필과 상황 맥락을 담는다', () => {
    const prompt = buildPrompt({ ...base, mediaType: 'audio/m4a', context: '낯선 사람 방문' });
    expect(prompt).toContain('초코');
    expect(prompt).toContain('포메라니안');
    expect(prompt).toContain('1살 6개월');
    expect(prompt).toContain('낯선 사람 방문');
    expect(prompt).toContain('강아지');
  });

  it('감정 키 목록을 고정해 모델이 새 키를 만들지 못하게 한다', () => {
    const prompt = buildPrompt({ ...base, mediaType: 'audio/m4a', context: '' });
    for (const key of EMOTION_KEYS) expect(prompt).toContain(key);
  });

  it('상황이 비면 그렇게 명시한다', () => {
    expect(buildPrompt({ ...base, mediaType: 'audio/m4a', context: '   ' })).toContain('특별한 상황 설명 없음');
  });

  it('나이를 모르면 미상으로 적는다', () => {
    const prompt = buildPrompt({ ...base, pet: { ...pet, ageMonths: undefined }, mediaType: 'audio/m4a', context: '' });
    expect(prompt).toContain('나이 미상');
  });

  it('12개월 미만은 개월로 표기한다', () => {
    const prompt = buildPrompt({ ...base, pet: { ...pet, ageMonths: 5 }, mediaType: 'audio/m4a', context: '' });
    expect(prompt).toContain('5개월령');
  });

  it('확정 진단을 막는 안전 지침이 들어 있다', () => {
    expect(buildPrompt({ ...base, mediaType: 'audio/m4a', context: '' })).toContain('수의사 확인이 필요하다');
  });

  it('고양이면 고양이로 부른다', () => {
    const prompt = buildPrompt({ ...base, pet: { ...pet, type: 'CAT', name: '나비' }, mediaType: 'audio/m4a', context: '' });
    expect(prompt).toContain('고양이');
    expect(prompt).toContain('나비');
  });

  it('출력 언어를 명시한다', () => {
    expect(buildPrompt({ ...base, locale: 'en', mediaType: 'audio/m4a', context: '' })).toContain('영어(English)');
    expect(buildPrompt({ ...base, locale: 'ja', mediaType: 'audio/m4a', context: '' })).toContain('일본어(日本語)');
  });

  it('품종 특성을 프롬프트에 주입한다', () => {
    expect(buildPrompt({ ...base, mediaType: 'audio/m4a', context: '' })).toContain('경계성 짖음');
    const siamese = buildPrompt({ ...base, pet: { ...pet, type: 'CAT', breed: '샴' }, mediaType: 'audio/m4a', context: '' });
    expect(siamese).toContain('발성이 매우 잦고');
  });

  it('모르는 품종이면 특성 문단을 넣지 않는다', () => {
    const prompt = buildPrompt({ ...base, pet: { ...pet, breed: '알수없는품종', ageMonths: 36 }, mediaType: 'audio/m4a', context: '' });
    expect(prompt).not.toContain('알려진 특성');
  });

  it('노령기에는 인지기능장애 가능성을 짚어 준다', () => {
    const senior = buildPrompt({ ...base, pet: { ...pet, breed: undefined, ageMonths: 130 }, mediaType: 'audio/m4a', context: '' });
    expect(senior).toContain('인지기능장애');
  });

  it('어린 개체는 사회화/에너지 특성을 넣는다', () => {
    const puppy = buildPrompt({ ...base, pet: { ...pet, breed: undefined, ageMonths: 4 }, mediaType: 'audio/m4a', context: '' });
    expect(puppy).toContain('사회화 시기');
  });
});

describe('RESPONSE_SCHEMA', () => {
  it('필수 필드를 강제한다', () => {
    expect(RESPONSE_SCHEMA.required).toContain('petVoiceMessage');
    expect(RESPONSE_SCHEMA.required).toContain('emotionScores');
    expect(RESPONSE_SCHEMA.properties.primaryEmotion.enum).toEqual(EMOTION_KEYS);
  });
});
