import { defineConfig } from 'vitest/config';

// 순수 로직(src/core, src/integrations 의 HTTP 부분, 서버 함수)만 Node 에서 테스트한다.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
});
