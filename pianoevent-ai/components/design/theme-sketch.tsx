import { getTheme } from '@/lib/design/themes'

/**
 * 테마 한 장을 **포스터 모양 그림**으로.
 *
 * 이름("빈 홀의 저녁")과 색 동그라미 세 개로는 무엇이 나올지 알 수가 없다.
 * 원장님이 알고 싶은 것은 **"우리 포스터가 어떻게 보이나"** 하나뿐이다.
 *
 * 실제 인쇄물을 통째로 그리면 서른 장이 넘어 느려지므로, 테마에서 실제로
 * 눈에 띄는 것만 종이 모양에 옮긴다 — 바탕색 · 머리띠 색 · 강조색 · 제목 서체.
 * 무대 화면처럼 인쇄물 문맥이 없는 곳에서도 쓸 수 있다.
 */
export function ThemeSketch({ id, width = 84 }: { id: string; width?: number }) {
  const theme = getTheme(id)
  const height = Math.round(width * 1.414) // A4 세로 비율

  return (
    <span
      className="block overflow-hidden rounded-sm border border-black/10"
      style={{ width, height, background: theme.palette.paper }}
      aria-hidden
    >
      {/* 위쪽 머리띠 — 테마마다 가장 크게 달라지는 자리 */}
      <span
        className="flex items-center justify-center"
        style={{ height: Math.round(height * 0.26), background: theme.palette.band }}
      >
        <span
          style={{
            fontFamily: theme.fonts.display,
            fontSize: Math.round(width * 0.15),
            fontWeight: 700,
            color: theme.palette.bandInk,
            letterSpacing: '0.02em',
          }}
        >
          연주회
        </span>
      </span>

      {/* 제목 자리 · 강조선 · 본문 줄 */}
      <span className="block" style={{ padding: Math.round(width * 0.09) }}>
        <span
          className="block"
          style={{
            height: Math.round(height * 0.045),
            width: '78%',
            background: theme.palette.ink,
            opacity: 0.8,
            borderRadius: 1,
          }}
        />
        <span
          className="mt-1 block"
          style={{ height: Math.round(height * 0.02), width: '38%', background: theme.palette.accent, borderRadius: 1 }}
        />
        {[0.62, 0.5, 0.56].map((w, i) => (
          <span
            key={i}
            className="mt-1 block"
            style={{
              height: Math.round(height * 0.016),
              width: `${w * 100}%`,
              background: theme.palette.ink,
              opacity: 0.28,
              borderRadius: 1,
            }}
          />
        ))}
      </span>
    </span>
  )
}
