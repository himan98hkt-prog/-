/**
 * 구경용 행사.
 *
 * 처음 켜시면 목록이 비어 있다. 무엇을 눌러도 볼 것이 없으니, 원장님은 이 프로그램이
 * 무엇을 해 주는지 **끝까지 못 보신 채** 닫으신다. 명단을 먼저 넣으셔야 보이는데,
 * 명단을 넣는 일이 가장 무거운 일이다.
 *
 * 그래서 한 번에 다 채운 행사를 하나 만들어 드린다. 아이도, 곡도, 사진도, 순서도 들어 있어
 * 인쇄물·무대 화면·감동영상까지 그 자리에서 다 보실 수 있다.
 *
 * 이름에 **(구경용 · 지우셔도 됩니다)** 를 박아 둔다 — 진짜 행사와 헷갈리면 안 된다.
 */
import type { NewStudent } from '@/lib/store/types'

export const DEMO_TITLE = '구경용 연주회 (지우셔도 됩니다)'

export const DEMO_VENUE = '연습실'

/** 구경용 명단 — 난이도가 골고루 섞여 있어야 순서 짜기가 실제처럼 보인다 */
export const DEMO_ROSTER: NewStudent[] = [
  { student_name: '이서준', piece_title: '작은 별 변주곡', composer: '모차르트', duration_sec: 95, level: 'beginner', note: '올해 처음 무대에 섭니다' },
  { student_name: '김하윤', piece_title: '즐거운 나의 집', composer: '비숍', duration_sec: 70, level: 'beginner', note: null },
  { student_name: '박도윤', piece_title: '미뉴에트 G장조', composer: '바흐', duration_sec: 130, level: 'beginner', note: '할머니가 오십니다' },
  { student_name: '최서아', piece_title: '아라베스크', composer: '부르크뮐러', duration_sec: 105, level: 'intermediate', note: null },
  { student_name: '정지호', piece_title: '엘리제를 위하여', composer: '베토벤', duration_sec: 210, level: 'intermediate', note: '세 번째 무대입니다' },
  { student_name: '강유나', piece_title: '인형의 꿈', composer: '오귀스트', duration_sec: 150, level: 'intermediate', note: null },
  { student_name: '윤채원', piece_title: '터키 행진곡', composer: '모차르트', duration_sec: 200, level: 'advanced', note: '올해 콩쿠르 준비 중' },
  { student_name: '임하람', piece_title: '즉흥환상곡', composer: '쇼팽', duration_sec: 310, level: 'advanced', note: '올해 마지막 무대' },
  { student_name: '오시우', piece_title: '캐논 변주곡', composer: '파헬벨', duration_sec: 240, level: 'ensemble', note: '누나와 함께 연탄' },
  { student_name: '오하은', piece_title: '캐논 변주곡', composer: '파헬벨', duration_sec: 240, level: 'ensemble', note: '동생과 함께 연탄' },
]

/**
 * 구경용 아이 사진.
 *
 * 진짜 아이 사진을 넣을 수는 없다. 그럴 사진도 없고, 넣어서도 안 된다.
 * 얼굴 자리에 무엇이 들어가는지만 보이면 되므로 색이 다른 그림 카드로 만든다.
 * 사진이 있어야 무대 화면과 감동영상이 **비어 보이지 않는다.**
 */
export function demoFace(index: number, total: number): string {
  const hue = Math.round((index * 360) / Math.max(1, total))
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="480" viewBox="0 0 480 480">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="hsl(${hue} 60% 80%)"/><stop offset="1" stop-color="hsl(${hue} 52% 58%)"/>
</linearGradient></defs>
<rect width="480" height="480" fill="url(#g)"/>
<circle cx="240" cy="192" r="84" fill="rgba(255,255,255,.78)"/>
<path d="M104 424c0-80 61-130 136-130s136 50 136 130z" fill="rgba(255,255,255,.78)"/>
</svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

/** 행사 날짜 — 오늘로부터 넉넉히 뒤로. 지난 날짜면 "이미 끝난 행사" 처럼 보인다 */
export function demoEventAt(now = new Date()): string {
  const at = new Date(now)
  at.setDate(at.getDate() + 45)
  at.setHours(15, 0, 0, 0)
  return at.toISOString()
}

/** 구경용인지 — 목록에서 표를 붙이고, 지우실 때 겁내지 않으시게 */
export function isDemoEvent(title: string): boolean {
  return title.includes('구경용')
}
