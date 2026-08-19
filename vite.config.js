import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
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
