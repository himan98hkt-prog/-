import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: {
    default: 'PianoEvent AI — 피아노학원 연주회·시즌 특강 기획',
    template: '%s · PianoEvent AI',
  },
  description:
    '학생 명단만 넣으면 연주 순서표와 사회자 대본이 나오고, 모바일 초대장과 참석 집계까지 한 번에. 피아노학원 원장님을 위한 행사 기획 도구.',
  applicationName: 'PianoEvent AI',
  openGraph: {
    title: 'PianoEvent AI',
    description: '피아노학원 연주회·시즌 특강 올인원 기획',
    type: 'website',
  },
}

export const viewport: Viewport = {
  themeColor: '#1f2a44',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  )
}
