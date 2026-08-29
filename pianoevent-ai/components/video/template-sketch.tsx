import { getVideoTemplate } from '@/lib/video/templates'

/**
 * 영상 템플릿 한 가지를 **화면 모양 그림**으로.
 *
 * "꽉 찬 사진 · 위 자막" 이라는 이름만으로는 무엇이 다른지 알 수 없다.
 * 원장님이 알고 싶은 것은 **사진이 어디에 오고 이름이 어디에 뜨나** 뿐이다.
 * 무대 모양을 그림 격자로 바꾼 것과 같은 이유로, 16:9 상자에 그 둘만 그린다.
 *
 * 실제 영상을 스무 개 돌려 보여 줄 수는 없다 — 그건 만드는 데만 몇 분이 걸린다.
 */
export function VideoTemplateSketch({ id, width = 82 }: { id: string; width?: number }) {
  const item = getVideoTemplate(id)
  const height = Math.round((width * 9) / 16)

  // 사진이 놓이는 자리 (0~1 비율)
  const photo =
    item.fit === 'full'
      ? { x: 0, y: 0, w: 1, h: 1 }
      : item.fit === 'half'
        ? { x: 0, y: 0, w: 0.5, h: 1 }
        : item.fit === 'polaroid'
          ? { x: 0.28, y: 0.1, w: 0.44, h: 0.66 }
          : { x: 0.3, y: 0.14, w: 0.4, h: 0.62 }

  // 이름이 뜨는 자리
  const caption =
    item.caption === 'top'
      ? { top: '10%', height: '14%' }
      : item.caption === 'center'
        ? { top: '43%', height: '14%' }
        : item.caption === 'none'
          ? null
          : { top: '76%', height: '14%' }

  const pct = (b: { x: number; y: number; w: number; h: number }) => ({
    left: `${b.x * 100}%`,
    top: `${b.y * 100}%`,
    width: `${b.w * 100}%`,
    height: `${b.h * 100}%`,
  })

  return (
    <span
      className="relative block overflow-hidden rounded-sm border border-black/10 bg-neutral-800"
      style={{ width, height }}
      aria-hidden
    >
      {/* 배경 — 단색이 아니면 은은한 결이 있다는 것만 표시한다 */}
      {item.backdrop !== 'plain' && (
        <span className="absolute inset-0 bg-gradient-to-br from-neutral-600 to-neutral-900" />
      )}
      {/* 사진 자리 */}
      <span
        className="absolute bg-white/70"
        style={{
          ...pct(photo),
          borderRadius: item.shape === 'circle' ? '50%' : item.fit === 'polaroid' ? 2 : 3,
          border: item.fit === 'polaroid' ? '2px solid #fff' : undefined,
        }}
      />
      {/* 사진을 어둡게 깔았다면 그만큼 덮어 준다 */}
      {item.dim > 0 && <span className="absolute inset-0 bg-black" style={{ opacity: item.dim * 0.6 }} />}
      {/* 이름 자리 */}
      {caption && (
        <span
          className="absolute left-[12%] w-[76%] rounded-[1px] bg-white"
          style={{ top: caption.top, height: caption.height }}
        />
      )}
    </span>
  )
}
