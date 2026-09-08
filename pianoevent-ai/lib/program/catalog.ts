import type { Level } from '@/lib/types'

/**
 * 연주회 곡 사전.
 *
 * 학원 연주회에 실제로 오르는 곡만 담았다. 원장이 곡 제목만 적으면
 * 작곡가 · 난이도 · 표준 연주시간 · 곡 해설이 따라 들어온다.
 *
 * 이 사전이 이 프로그램의 핵심 자산이다. 순서 배치도, 러닝타임도, 사회자 멘트도
 * 결국 "이 곡이 어떤 곡인가"를 알아야 제대로 나온다.
 * 엑셀도 캔바도 이 정보를 가지고 있지 않다.
 *
 * duration_sec 은 학원 연주회에서 실제로 연주되는 길이다(발췌·반복 생략 반영).
 * 원장이 고치면 그 값이 이긴다 — 사전은 비어 있을 때만 채운다.
 */

export interface CatalogEntry {
  /** 대표 표기 */
  title: string
  /** 원장이 적을 법한 다른 표기 — 검색과 자동 채움에 쓴다 */
  aliases: string[]
  composer: string
  level: Level
  duration_sec: number
  /** 사회자 대본에 들어가는 한 줄 해설 */
  blurb: string
}

const E = (
  title: string,
  aliases: string[],
  composer: string,
  level: Level,
  duration_sec: number,
  blurb: string,
): CatalogEntry => ({ title, aliases, composer, level, duration_sec, blurb })

export const PIECE_CATALOG: CatalogEntry[] = [
  // ── 첫 무대 · 동요와 기초 ────────────────────────────────
  E('나비야', ['나비'], '전래', 'beginner', 45, '누구나 아는 선율이라 첫 무대에서 객석이 함께 흥얼거리게 되는 곡입니다'),
  E('학교종', ['학교 종이 땡땡땡'], '김메리', 'beginner', 40, '짧지만 또렷한 리듬으로 첫 무대의 긴장을 풀어 주는 곡입니다'),
  E('비행기', [], '전래', 'beginner', 40, '가장 먼저 배우는 선율로, 오늘 첫 무대에 어울리는 곡입니다'),
  E('작은 별', ['반짝반짝 작은별', 'twinkle'], '전래', 'beginner', 50, '누구나 아는 선율을 또박또박 짚어 가는, 시작에 어울리는 곡입니다'),
  E('작은 별 변주곡', ['아 어머니께 말씀드리죠', 'ah vous dirai'], '모차르트', 'beginner', 150, '고전 시대의 맑고 투명한 선율이 그대로 드러나 손끝의 정직함이 필요한 곡입니다'),
  E('즐거운 나의 집', ['home sweet home'], '비숍', 'beginner', 70, '작은 손으로 짚어 가는 한 음 한 음에 지난 계절의 연습이 담겨 있는 곡입니다'),
  E('도레미 송', ['do re mi'], '로저스', 'beginner', 90, '음계를 노래로 배우던 기억을 그대로 무대에 올린 곡입니다'),
  E('젓가락 행진곡', ['chopsticks', '젓가락'], '전래', 'ensemble', 120, '둘이 마주 앉아야 완성되는, 듣는 사람까지 즐거워지는 곡입니다'),
  E('고향의 봄', [], '홍난파', 'beginner', 90, '어른들이 먼저 눈시울을 붉히는, 우리에게 가장 익숙한 선율입니다'),
  E('섬집 아기', [], '이흥렬', 'beginner', 85, '자장가처럼 잔잔하게 흐르는, 여린 소리가 어울리는 곡입니다'),
  E('아리랑', [], '전래', 'beginner', 95, '우리 선율을 피아노로 옮긴, 객석이 함께 숨을 고르게 되는 곡입니다'),

  // ── 부르크뮐러 25개의 연습곡 ─────────────────────────────
  E('아라베스크', ['arabesque'], '부르크뮐러', 'beginner', 105, '오른손과 왼손이 서로를 쫓아가듯 달리는, 짧지만 또렷한 곡입니다'),
  E('목가', ['pastorale'], '부르크뮐러', 'beginner', 100, '들판에 부는 바람 같은, 마음이 놓이는 선율의 곡입니다'),
  E('진보', ['progress'], '부르크뮐러', 'beginner', 95, '한 계단씩 올라가듯 손가락이 또렷해지는 것을 들려주는 곡입니다'),
  E('맑은 시냇물', ['흐르는 시냇물', 'limpid stream'], '부르크뮐러', 'intermediate', 110, '오른손의 잔물결 위로 왼손이 노래하는, 물가에 앉은 듯한 곡입니다'),
  E('발라드', ['ballade'], '부르크뮐러', 'intermediate', 115, '어두운 첫머리에서 밝은 노래로 넘어가는 이야기 같은 곡입니다'),
  E('이별', ['adieu'], '부르크뮐러', 'intermediate', 105, '떠나는 사람의 뒷모습 같은 선율이 끝까지 이어지는 곡입니다'),
  E('귀가', ['home', '집으로'], '부르크뮐러', 'beginner', 90, '돌아오는 발걸음처럼 밝고 가벼운 리듬의 곡입니다'),
  E('제비', ['la hirondelle'], '부르크뮐러', 'intermediate', 100, '두 손을 넘나드는 선율이 제비의 날갯짓을 그리는 곡입니다'),
  E('승마', ['chevaleresque'], '부르크뮐러', 'intermediate', 105, '말을 달리듯 씩씩한 리듬으로 무대를 마무리하기 좋은 곡입니다'),
  E('순진', ['innocence'], '부르크뮐러', 'beginner', 80, '군더더기 없는 선율이라 오히려 소리의 결이 그대로 드러나는 곡입니다'),

  // ── 바흐 ─────────────────────────────────────────────────
  E('미뉴에트 G장조', ['미뉴엣', 'minuet in g'], '바흐', 'beginner', 130, '옛 궁정의 춤곡으로, 우아한 3박자의 걸음이 곡 전체를 이끕니다'),
  E('미뉴에트 g단조', ['minuet in g minor'], '바흐', 'intermediate', 130, '같은 춤곡이지만 그늘이 드리운, 차분한 표정의 곡입니다'),
  E('인벤션 1번', ['invention 1', '인벤션'], '바흐', 'intermediate', 165, '두 개의 선율이 각자 걸어가면서도 하나의 음악이 되는, 바흐의 대화 같은 곡입니다'),
  E('인벤션 4번', ['invention 4'], '바흐', 'intermediate', 150, '쉬지 않고 굴러가는 선율이 두 손 사이를 오가는 곡입니다'),
  E('인벤션 8번', ['invention 8'], '바흐', 'intermediate', 145, '경쾌하게 뛰어오르는 첫 소절이 곡 전체를 이끄는, 밝은 인벤션입니다'),
  E('프렐류드 C장조', ['prelude in c', '전주곡 c장조'], '바흐', 'intermediate', 150, '같은 화음이 물결처럼 이어지며 마음을 가라앉히는 곡입니다'),
  E('아베 마리아', ['ave maria'], '구노 · 바흐', 'intermediate', 180, '바흐의 프렐류드 위에 얹은 기도 같은 선율의 곡입니다'),

  // ── 모차르트 ─────────────────────────────────────────────
  E('터키 행진곡', ['turkish march', 'rondo alla turca'], '모차르트', 'intermediate', 205, '행진하는 군악대의 소리를 피아노로 옮긴, 경쾌한 리듬의 곡입니다'),
  E('소나타 K.545 1악장', ['소나타 c장조', 'k545'], '모차르트', 'intermediate', 250, '배우기 쉬워 보이지만 한 음도 숨을 곳이 없는, 고전의 정직한 곡입니다'),
  E('미뉴에트 K.1', ['minuet k1'], '모차르트', 'beginner', 75, '모차르트가 다섯 살에 쓴, 짧고 단정한 춤곡입니다'),

  // ── 베토벤 ───────────────────────────────────────────────
  E('엘리제를 위하여', ['fur elise', '엘리제'], '베토벤', 'intermediate', 210, '누구나 첫 소절을 흥얼거릴 수 있는 곡이지만, 여린 소리를 끝까지 고르게 유지하기가 가장 어렵습니다'),
  E('월광 소나타 1악장', ['moonlight', '월광'], '베토벤', 'advanced', 300, '고요한 물 위에 달빛이 내려앉은 듯한 첫 악장이 오래도록 남는 곡입니다'),
  E('비창 2악장', ['pathetique'], '베토벤', 'advanced', 280, '느리게 흐르는 선율 하나로 객석을 조용하게 만드는 악장입니다'),
  E('소나티네 G장조', ['sonatine in g'], '베토벤', 'intermediate', 170, '짧은 소나타 안에 밝은 성격이 또렷하게 담긴 곡입니다'),

  // ── 슈만 ─────────────────────────────────────────────────
  E('트로이메라이', ['traumerei', '꿈'], '슈만', 'intermediate', 165, '어린 시절의 꿈을 그대로 옮겨 놓은 듯한, 가장 사랑받는 소품입니다'),
  E('즐거운 농부', ['merry farmer', '행복한 농부'], '슈만', 'beginner', 85, '왼손이 노래하고 오른손이 받쳐 주는, 뒤집힌 구성이 재미있는 곡입니다'),
  E('병정의 행진', ['soldiers march'], '슈만', 'beginner', 70, '또박또박한 리듬으로 씩씩하게 걸어가는 짧은 행진곡입니다'),
  E('어린이 정경', ['kinderszenen'], '슈만', 'intermediate', 170, '어린 시절의 장면들을 짧은 곡에 담아낸 따뜻한 음악입니다'),

  // ── 쇼팽 ─────────────────────────────────────────────────
  E('녹턴 op.9 no.2', ['nocturne', '녹턴'], '쇼팽', 'advanced', 285, '밤의 노래라는 뜻 그대로, 왼손의 잔잔한 물결 위로 오른손이 노래하는 곡입니다'),
  E('즉흥환상곡', ['fantaisie impromptu'], '쇼팽', 'advanced', 320, '낭만 시대의 피아노가 사람의 목소리처럼 노래하는, 낭만의 대표적인 음악입니다'),
  E('강아지 왈츠', ['minute waltz', '왈츠 op.64 no.1'], '쇼팽', 'advanced', 115, '꼬리를 쫓아 도는 강아지를 그린, 쉬지 않고 굴러가는 왈츠입니다'),
  E('왈츠 op.64 no.2', ['waltz op64 no2'], '쇼팽', 'advanced', 210, '느린 한숨과 빠른 회전이 번갈아 나오는, 표정이 많은 왈츠입니다'),
  E('빗방울 전주곡', ['raindrop', '전주곡 op.28 no.15'], '쇼팽', 'advanced', 300, '같은 음이 빗방울처럼 끊이지 않고 떨어지는 곡입니다'),
  E('이별의 곡', ['tristesse', '연습곡 op.10 no.3'], '쇼팽', 'advanced', 230, '가장 노래하는 선율로 시작해 마음을 붙드는 연습곡입니다'),

  // ── 드뷔시 · 근대 ────────────────────────────────────────
  E('아라베스크 1번', ['debussy arabesque'], '드뷔시', 'advanced', 260, '색이 번지듯 화음이 흐르는, 그림 같은 음악입니다'),
  E('달빛', ['clair de lune'], '드뷔시', 'advanced', 300, '달빛이 내려앉는 장면을 소리로 그린, 근대의 대표적인 곡입니다'),
  E('골리워그의 케이크워크', ['golliwogg', 'cakewalk'], '드뷔시', 'intermediate', 175, '어긋난 리듬이 웃음을 자아내는, 장난기 있는 곡입니다'),
  E('인형의 세레나데', ['serenade for the doll'], '드뷔시', 'intermediate', 150, '작은 인형에게 들려주는 듯 가볍고 또렷한 곡입니다'),

  // ── 차이콥스키 · 러시아 ──────────────────────────────────
  E('사계 중 6월 뱃노래', ['barcarolle', '6월'], '차이콥스키', 'advanced', 290, '노래하듯 흐르는 선율에 러시아의 서정이 담긴 음악입니다'),
  E('꽃의 왈츠', ['waltz of the flowers'], '차이콥스키', 'advanced', 240, '호두까기인형의 가장 화려한 장면을 피아노로 옮긴 곡입니다'),
  E('사탕요정의 춤', ['sugar plum fairy'], '차이콥스키', 'intermediate', 130, '유리구슬이 구르는 듯한 맑은 소리가 인상적인 곡입니다'),
  E('어린이 앨범', ['album for the young'], '차이콥스키', 'intermediate', 140, '아이의 하루를 짧은 곡들로 그린 모음집 중 한 곡입니다'),

  // ── 그 밖의 고전 소품 ────────────────────────────────────
  E('소녀의 기도', ['maiden prayer', '처녀의 기도'], '바다르체프스카', 'intermediate', 260, '한 소녀의 기도를 그대로 옮겨 놓은 듯한 곡으로, 물결치는 아르페지오가 인상적입니다'),
  E('캐논 변주곡', ['canon', '캐논'], '파헬벨', 'intermediate', 240, '같은 선율이 시간을 두고 겹겹이 쌓이며 점점 풍성해지는 곡입니다'),
  E('사랑의 인사', ['salut damour'], '엘가', 'intermediate', 180, '사랑하는 사람에게 건네는 인사처럼 다정한 음악입니다'),
  E('헝가리 무곡 5번', ['hungarian dance'], '브람스', 'advanced', 165, '느려졌다 빨라지기를 반복하며 객석을 들썩이게 하는 곡입니다'),
  E('라 캄파넬라', ['la campanella'], '리스트', 'advanced', 290, '피아노 한 대로 종소리를 그려내는, 오늘 무대에서 손꼽히는 난이도의 곡입니다'),
  E('즉흥곡 op.90 no.4', ['impromptu'], '슈베르트', 'advanced', 300, '흘러내리는 물줄기 같은 첫머리가 끝까지 이어지는 곡입니다'),
  E('군대 행진곡', ['marche militaire'], '슈베르트', 'intermediate', 175, '두 사람이 함께 치면 더 씩씩해지는, 익숙한 행진곡입니다'),
  E('봄', ['spring', '사계 봄'], '비발디', 'intermediate', 175, '새소리로 시작하는 첫 소절만으로 계절이 그려지는 곡입니다'),
  E('터키 블루스', ['turkish blues'], '유키 구라모토', 'intermediate', 170, '익숙한 선율을 재즈의 리듬으로 다시 들려주는 곡입니다'),
  E('로망스', ['romance'], '베토벤', 'intermediate', 190, '한 줄기 선율이 끝까지 노래하는, 담백한 곡입니다'),

  // ── 영화 · 애니메이션 (학원 연주회에서 가장 반응이 큰 갈래) ──
  E('인생의 회전목마', ['하울의 움직이는 성', 'merry go round of life'], '히사이시 조', 'intermediate', 200, '왈츠의 세 박자를 타고 장면이 넘어가는, 객석이 가장 먼저 알아보는 곡입니다'),
  E('언제나 몇번이라도', ['센과 치히로', 'always with me'], '기무라 유미', 'intermediate', 175, '조용히 시작해 마음에 오래 남는 선율의 곡입니다'),
  E('이웃집 토토로', ['totoro', '산책'], '히사이시 조', 'beginner', 110, '첫 소절부터 아이들이 따라 부르게 되는 곡입니다'),
  E('캐리비안의 해적', ['pirates of the caribbean', 'he is a pirate'], '한스 짐머', 'advanced', 200, '단단한 리듬이 쉬지 않고 밀어붙이는, 무대를 뜨겁게 만드는 곡입니다'),
  E('렛 잇 고', ['let it go', '겨울왕국'], '로페즈', 'intermediate', 195, '아이들이 가장 많이 신청하는 곡으로, 후반부의 힘이 관건입니다'),
  E('어벤져스 테마', ['avengers'], '실베스트리', 'intermediate', 150, '첫 화음만으로 객석이 알아보는, 짧고 강한 곡입니다'),
  E('마리오 테마', ['super mario'], '콘도 코지', 'beginner', 100, '경쾌한 리듬으로 아이들이 가장 즐거워하는 곡입니다'),
  E('러브 스토리', ['love story'], '프란시스 레이', 'intermediate', 165, '한 선율이 끝까지 노래하는, 어른 관객에게 익숙한 곡입니다'),
  E('강남 스타일', ['gangnam style'], '편곡', 'intermediate', 140, '객석이 박수로 리듬을 맞추게 되는, 무대를 뒤집는 곡입니다'),
  E('아드린느를 위한 발라드', ['ballade pour adeline'], '폴 드 세느빌', 'intermediate', 200, '누구나 어디선가 들어 본, 편안하게 흐르는 발라드입니다'),

  // ── 크리스마스 · 시즌 ────────────────────────────────────
  E('징글벨', ['jingle bells'], '피어폰트', 'beginner', 70, '첫 소절부터 객석이 함께 박자를 맞추게 되는 곡입니다'),
  E('루돌프 사슴코', ['rudolph'], '마크스', 'beginner', 75, '아이들이 가장 먼저 외우는 크리스마스 선율입니다'),
  E('고요한 밤 거룩한 밤', ['silent night'], '그루버', 'beginner', 90, '느리게 흐르는 화음만으로 객석이 조용해지는 곡입니다'),
  E('화이트 크리스마스', ['white christmas'], '어빙 벌린', 'intermediate', 140, '눈 내리는 장면이 그대로 그려지는, 따뜻한 곡입니다'),
  E('캐롤 메들리', ['carol medley'], '편곡', 'intermediate', 180, '익숙한 캐롤들이 이어지며 겨울 무대를 마무리하는 곡입니다'),
]

const norm = (v: string) => v.trim().toLowerCase().replace(/[\s.·,()]/g, '')

/** 원장이 적은 곡 제목으로 사전을 찾는다 — 표기가 조금 달라도 잡는다 */
export function findPiece(title: string): CatalogEntry | null {
  const key = norm(title)
  if (key.length < 2) return null

  // 1) 대표 표기가 정확히 맞는 경우
  for (const entry of PIECE_CATALOG) {
    if (norm(entry.title) === key) return entry
  }
  // 2) 별칭이 정확히 맞는 경우
  for (const entry of PIECE_CATALOG) {
    if (entry.aliases.some((a) => norm(a) === key)) return entry
  }
  // 3) 적은 제목이 사전 표기를 품고 있거나 그 반대인 경우
  //    ("엘리제를 위하여 (베토벤)" · "녹턴" 처럼 적는 경우가 많다)
  let best: { entry: CatalogEntry; score: number } | null = null
  for (const entry of PIECE_CATALOG) {
    for (const label of [entry.title, ...entry.aliases]) {
      const target = norm(label)
      if (target.length < 2) continue
      if (key.includes(target) || target.includes(key)) {
        const score = Math.min(key.length, target.length)
        if (!best || score > best.score) best = { entry, score }
      }
    }
  }
  return best?.entry ?? null
}

/** 입력 중인 글자로 후보를 뽑는다 — 자동완성 목록 */
export function searchPieces(query: string, limit = 8): CatalogEntry[] {
  const key = norm(query)
  if (key.length < 1) return []
  const starts: CatalogEntry[] = []
  const contains: CatalogEntry[] = []
  for (const entry of PIECE_CATALOG) {
    const labels = [entry.title, ...entry.aliases, entry.composer].map(norm)
    if (labels.some((l) => l.startsWith(key))) starts.push(entry)
    else if (labels.some((l) => l.includes(key))) contains.push(entry)
  }
  return [...starts, ...contains].slice(0, limit)
}

export interface RosterGap {
  composer: boolean
  duration: boolean
  level: boolean
}

/**
 * 곡 사전으로 빈칸을 채운다.
 * 원장이 적은 값이 언제나 이긴다 — 비어 있는 칸만 채운다.
 */
export function completeFromCatalog(row: {
  piece_title: string
  composer: string
  duration_sec: number | null
  level: Level
  /** 명단에 난이도가 실제로 적혀 있었는지 */
  levelGiven?: boolean
}): { composer: string; duration_sec: number | null; level: Level; filled: RosterGap } {
  const entry = findPiece(row.piece_title)
  const filled: RosterGap = { composer: false, duration: false, level: false }
  if (!entry) return { composer: row.composer, duration_sec: row.duration_sec, level: row.level, filled }

  let composer = row.composer
  if (!composer.trim()) {
    composer = entry.composer
    filled.composer = true
  }

  let duration = row.duration_sec
  if (!duration || duration <= 0) {
    duration = entry.duration_sec
    filled.duration = true
  }

  let level = row.level
  if (row.levelGiven === false) {
    level = entry.level
    filled.level = true
  }

  return { composer, duration_sec: duration, level, filled }
}

export const CATALOG_SIZE = PIECE_CATALOG.length
