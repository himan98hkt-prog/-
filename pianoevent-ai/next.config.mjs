/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 서버 전용 SDK 가 클라이언트 번들에 섞이지 않도록 (GEMINI_API_KEY 유출 방지의 마지막 안전핀)
  experimental: { serverComponentsExternalPackages: ['@google/genai'] },
}

export default nextConfig
