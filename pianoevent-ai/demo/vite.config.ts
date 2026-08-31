import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

/**
 * 체험판 빌드.
 * 서버 없이 브라우저 하나로 도는 단일 HTML 을 만든다.
 * 순서 배치·대본·진단·인쇄물 렌더는 전부 앱과 같은 코드를 그대로 쓴다.
 */
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [react(), viteSingleFile()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('..', import.meta.url)) },
  },
  define: {
    // 브라우저에는 process 가 없다. 앱과 같은 기본값을 심어 준다.
    'process.env.NEXT_PUBLIC_APP_TIME_ZONE': JSON.stringify('Asia/Seoul'),
  },
  build: {
    outDir: fileURLToPath(new URL('../배포/demo', import.meta.url)),
    emptyOutDir: true,
    assetsInlineLimit: 100_000_000,
    cssCodeSplit: false,
    target: 'es2020',
  },
})
