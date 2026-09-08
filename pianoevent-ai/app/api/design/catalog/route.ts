import { NextResponse } from 'next/server'
import { DESIGN_TEMPLATES } from '@/lib/design/templates'
import { DESIGN_THEMES } from '@/lib/design/themes'

/**
 * 양식과 테마의 목록 — **검사 도구가 읽는 자리**다.
 *
 * 그림 포스터 23종 × 테마 108종의 글씨 대비를 재려면 검사 스크립트가 그 목록을 알아야 한다.
 * 예전에는 스크립트 안에 목록을 베껴 두었는데, 양식을 늘릴 때마다 한쪽만 늘어나
 * **새로 넣은 포스터가 검사에서 조용히 빠졌다.** 그래서 프로그램 자신이 알려 주게 한다.
 *
 * 나가는 것은 디자인 상수뿐이다 — 아이 이름도, 사진도, 학원 정보도 여기에 없다.
 * 그리고 이 주소는 원장님 컴퓨터 안에서만 열린다(프로그램이 제 안에 서버를 품고 돈다).
 */
export const dynamic = 'force-dynamic'

export function GET() {
  return NextResponse.json({
    templates: DESIGN_TEMPLATES.map((t) => ({ id: t.id, name: t.name, category: t.category, page: t.page })),
    themes: DESIGN_THEMES.map((t) => ({ id: t.id, name: t.name, family: t.family, palette: t.palette, fonts: t.fonts })),
  })
}
