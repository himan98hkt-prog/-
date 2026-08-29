import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import reactHooks from 'eslint-plugin-react-hooks';
import tseslint from 'typescript-eslint';

/**
 * 파일이 60개를 넘으면서 스타일을 사람이 지키는 게 한계에 왔다.
 * 여기서 잡고 싶은 건 취향이 아니라 **사고로 이어지는 것들**이다 —
 * 쓰지 않는 import, 훅 의존성 누락, 빠뜨린 await.
 *
 * 서식은 Prettier 가 전담한다. eslint-config-prettier 를 마지막에 둬서
 * 서식 관련 규칙은 전부 끈다 (둘이 싸우면 CI 가 영원히 빨개진다).
 */
export default tseslint.config(
  {
    ignores: ['node_modules/**', '.expo/**', 'dist/**', 'assets/**', 'eval/dataset/**'],
  },

  js.configs.recommended,
  ...tseslint.configs.recommended,

  {
    files: ['**/*.{ts,tsx,mts,mjs}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        console: 'readonly',
        fetch: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        AbortController: 'readonly',
        TextEncoder: 'readonly',
        TextDecoder: 'readonly',
        atob: 'readonly',
        btoa: 'readonly',
        crypto: 'readonly',
        process: 'readonly',
        __DEV__: 'readonly',
        require: 'readonly',
        module: 'writable',
        URL: 'readonly',
        Response: 'readonly',
        Request: 'readonly',
        Headers: 'readonly',
        Blob: 'readonly',
        FormData: 'readonly',
        performance: 'readonly',
        Buffer: 'readonly',
      },
    },
    rules: {
      // 안 쓰는 것은 지운다. 다만 `_` 로 시작하면 "일부러 안 쓴다"는 표시로 본다.
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrors: 'none' },
      ],
      // 저장소·결제처럼 네이티브 모듈을 조건부로 부르는 자리에 require 가 꼭 필요하다.
      '@typescript-eslint/no-require-imports': 'off',
      // 모델 응답처럼 모양을 믿을 수 없는 값은 unknown 으로 받는 게 원칙이지만,
      // 외부 SDK 경계에서는 any 가 불가피할 때가 있어 경고까지만.
      '@typescript-eslint/no-explicit-any': 'warn',
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },

  {
    files: ['src/**/*.{ts,tsx}'],
    plugins: { 'react-hooks': reactHooks },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },

  {
    // babel.config.js 는 Metro 가 CommonJS 로 읽는다.
    files: ['**/*.js'],
    languageOptions: { sourceType: 'commonjs', globals: { module: 'writable', require: 'readonly' } },
  },

  {
    // Edge Function 은 Deno 런타임에서 돈다.
    files: ['supabase/functions/**/*.ts'],
    languageOptions: { globals: { Deno: 'readonly' } },
  },

  prettier,
);
