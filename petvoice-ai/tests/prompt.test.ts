import { describe, expect, it } from 'vitest';
import { EMOTION_KEYS } from '../src/core/emotions';
import { RESPONSE_SCHEMA, buildPrompt } from '../src/core/prompt';
import type { PetProfile } from '../src/core/types';

const pet: PetProfile = { id: 'p', name: '초코', type: 'DOG', breed: '포메라니안', ageMonths: 18, createdAt: 0 };

describe('buildPrompt', () => {
  it('오디오와 이미지에 다른 지시를 넣는다', () => {
    const audio = buildPrompt({ pet, mediaType: 'audio/m4a', context: '외출 직전' });
    const image = buildPrompt({ pet, mediaType: 'image/jpeg', context: '외출 직전' });
    expect(audio).toContain('울음소리/짖는 소리');
    expect(image).toContain('행동/자세 사진');
  });

  it('프로필과 상황 맥락을 담는다', () => {
    const prompt = buildPrompt({ pet, mediaType: 'audio/m4a', context: '낯선 사람 방문' });
    expect(prompt).toContain('초코');
    expect(prompt).toContain('포메라니안');
    expect(prompt).toContain('1살 6개월');
    expect(prompt).toContain('낯선 사람 방문');
    expect(prompt).toContain('강아지');
  });

  it('감정 키 목록을 고정해 모델이 새 키를 만들지 못하게 한다', () => {
    const prompt = buildPrompt({ pet, mediaType: 'audio/m4a', context: '' });
    for (const key of EMOTION_KEYS) expect(prompt).toContain(key);
  });

  it('상황이 비면 그렇게 명시한다', () => {
    expect(buildPrompt({ pet, mediaType: 'audio/m4a', context: '   ' })).toContain('특별한 상황 설명 없음');
  });

  it('나이를 모르면 미상으로 적는다', () => {
    const prompt = buildPrompt({ pet: { ...pet, ageMonths: undefined }, mediaType: 'audio/m4a', context: '' });
    expect(prompt).toContain('나이 미상');
  });

  it('12개월 미만은 개월로 표기한다', () => {
    const prompt = buildPrompt({ pet: { ...pet, ageMonths: 5 }, mediaType: 'audio/m4a', context: '' });
    expect(prompt).toContain('5개월령');
  });

  it('확정 진단을 막는 안전 지침이 들어 있다', () => {
    expect(buildPrompt({ pet, mediaType: 'audio/m4a', context: '' })).toContain('수의사 확인이 필요하다');
  });

  it('고양이면 고양이로 부른다', () => {
    const prompt = buildPrompt({ pet: { ...pet, type: 'CAT', name: '나비' }, mediaType: 'audio/m4a', context: '' });
    expect(prompt).toContain('고양이');
    expect(prompt).toContain('나비');
  });
});

describe('RESPONSE_SCHEMA', () => {
  it('필수 필드를 강제한다', () => {
    expect(RESPONSE_SCHEMA.required).toContain('petVoiceMessage');
    expect(RESPONSE_SCHEMA.required).toContain('emotionScores');
    expect(RESPONSE_SCHEMA.properties.primaryEmotion.enum).toEqual(EMOTION_KEYS);
  });
});
