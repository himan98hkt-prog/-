import { defineConfig } from 'vitest/config';

/**
 * `src/core/*` 는 React Native 에 의존하지 않는 순수 로직이라
 * 노드에서 그대로 돌린다. 화면 코드는 테스트 대상이 아니다.
 */
export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
});
