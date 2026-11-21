import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
  server: {
    // 성능 측정용 브라우저 프로필·산출물이 바뀌었다고 페이지를 리로드하지 않도록
    watch: { ignored: ['**/.perf-profile/**', '**/perf-report.json', '**/dist/**'] }
  },
  build: {
    target: 'es2020',
    outDir: 'dist',
    assetsDir: 'assets',
    rollupOptions: {
      input: {
        main: 'index.html',
        lite: 'lite.html',
        keygen: 'tools/keygen.html'
      }
    }
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.js']
  }
})
