/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  /**
   * 설치판을 위해 **혼자 도는 서버**로 뽑는다.
   *
   * 지금까지는 원장님 컴퓨터에서 `npm install` 이 돌아야 켜졌다. 처음 한 번에 2~4분,
   * 인터넷 필수, 검은 명령창. 제품이라기보다 개발 도구를 건네 드린 셈이다.
   *
   * standalone 으로 뽑으면 필요한 것이 한 폴더에 다 담겨, 설치본 안에서 그대로 돈다 —
   * 인터넷도, 설치 과정도, 명령창도 없다.
   */
  output: 'standalone',
  // 서버 전용 SDK 가 클라이언트 번들에 섞이지 않도록 (GEMINI_API_KEY 유출 방지의 마지막 안전핀)
  experimental: { serverComponentsExternalPackages: ['@google/genai'] },
}

export default nextConfig
