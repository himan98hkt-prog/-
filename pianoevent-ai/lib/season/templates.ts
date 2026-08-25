import type { SeasonTheme } from '@/lib/types'
import type { SeasonPack, SeasonWeek, Worksheet } from '@/lib/season/types'

/**
 * 테마별 기본 특강 팩.
 * AI 키가 없어도 원장이 그대로 인쇄해 수업에 쓸 수 있는 수준으로 채워 둔다.
 */

const HALLOWEEN_WEEKS: SeasonWeek[] = [
  {
    week: 1,
    title: '무서운 소리 만들기 — 단조와 반음',
    goal: '장조와 단조를 귀로 구분하고, 반음이 주는 긴장감을 몸으로 안다',
    activities: [
      '같은 동요를 장조·단조로 번갈아 들려주고 어느 쪽이 "무서운지" 손들기',
      '검은건반 두 개를 반음으로 번갈아 눌러 "발소리" 만들기 (저음역 8마디)',
      '저음역 트레몰로로 천둥소리 즉흥 연주 — 한 명씩 4마디',
    ],
    repertoire: ['바흐 · 토카타와 푸가 d단조 도입부 감상', '그리그 · 산왕의 궁전에서 (감상 후 리듬 따라치기)'],
    homework: '집에서 찾은 "무서운 소리" 세 가지를 적어 오고, 그중 하나를 피아노로 흉내 내 보기',
  },
  {
    week: 2,
    title: '유령의 걸음걸이 — 리듬 카드 놀이',
    goal: '4분음표·8분음표·쉼표를 걸음으로 구분해 정확히 친다',
    activities: [
      '리듬 카드를 뽑아 유령(4분음표)·박쥐(8분음표)·정지(쉼표)로 걸어 보기',
      '두 명이 짝을 지어 한 명은 리듬, 한 명은 멜로디 — 4마디 합주',
      '호박 그림 위에 리듬을 그려 넣고 친구와 바꿔서 연주하기',
    ],
    repertoire: ['생상스 · 죽음의 무도 (주제 리듬 따라치기)', '할로윈 동요 · Five Little Pumpkins 편곡'],
    homework: '리듬 카드 4장으로 나만의 8마디 만들어 오기',
  },
  {
    week: 3,
    title: '나만의 마법 주문 — 즉흥 연주',
    goal: '주어진 화음 위에서 두려움 없이 자기 소리를 낸다',
    activities: [
      '왼손 오스티나토(la-mi-la) 위에 오른손 검은건반 즉흥 8마디',
      '"마법 주문" 가사를 만들어 리듬으로 읽고, 그 리듬으로 연주하기',
      '친구의 즉흥에 이어서 연주하는 릴레이 (한 사람 4마디)',
    ],
    repertoire: ['뒤카 · 마법사의 제자 (감상 + 이야기 나누기)'],
    homework: '내 마법 주문 8마디를 녹음해서 가져오기',
  },
  {
    week: 4,
    title: '할로윈 미니 콘서트',
    goal: '분장을 하고 무대에 서서 끝까지 한 곡을 마친다',
    activities: [
      '분장하고 입장 — 이름과 곡 소개를 직접 말하기',
      '3주간 만든 즉흥·리듬 작품과 준비곡 발표',
      '친구 연주에 "좋았던 점 한 가지" 말해 주기',
      '사탕 증정과 기념사진 촬영',
    ],
    repertoire: ['각자 준비한 할로윈 소품 1곡', '전체 합주 · Halloween Medley'],
    homework: '없음 — 오늘 무대의 소감을 한 줄로 적어 오기',
  },
]

const CHRISTMAS_WEEKS: SeasonWeek[] = [
  {
    week: 1,
    title: '캐럴의 뼈대 — 3화음 익히기',
    goal: 'C·F·G 세 화음으로 캐럴 반주가 만들어지는 원리를 안다',
    activities: [
      '「고요한 밤」을 멜로디만 먼저 노래하고, 화음 세 개로 반주 붙이기',
      '화음 카드 놀이 — 선생님이 친 화음이 무엇인지 맞히기',
      '왼손 화음 + 오른손 멜로디로 8마디 완성',
    ],
    repertoire: ['고요한 밤 거룩한 밤', '징글벨 (한 손 버전)'],
    homework: 'C·F·G 화음을 눈 감고 짚을 수 있을 때까지 연습',
  },
  {
    week: 2,
    title: '종소리와 눈송이 — 페달과 아르페지오',
    goal: '페달을 화음이 바뀔 때 갈아 밟는 습관을 만든다',
    activities: [
      '페달 없이 → 페달 넣고 같은 마디를 연주해 소리 차이 듣기',
      '아르페지오로 눈 내리는 소리 만들기 (고음역 활용)',
      '두 명이 나눠 치는 연탄 「징글벨」 맞춰 보기',
    ],
    repertoire: ['징글벨 (연탄)', '루돌프 사슴코'],
    homework: '페달을 넣은 8마디를 녹음해 스스로 들어 보기',
  },
  {
    week: 3,
    title: '캐럴 메들리 만들기',
    goal: '두 곡을 자연스럽게 이어 붙이는 연결(브리지)을 경험한다',
    activities: [
      '좋아하는 캐럴 두 곡 고르기',
      '두 곡 사이를 잇는 4마디 브리지를 함께 만들기',
      '메들리 순서를 정하고 처음부터 끝까지 통과 연습',
    ],
    repertoire: ['학생별 캐럴 2곡 메들리'],
    homework: '메들리 전체를 하루 한 번 통과로 연습',
  },
  {
    week: 4,
    title: '크리스마스 홈 콘서트',
    goal: '가족 앞에서 연주하고, 함께 노래하는 경험을 만든다',
    activities: [
      '학생 개별 발표 (메들리 또는 준비곡)',
      '학부모와 함께 부르는 캐럴 — 학생이 반주',
      '올해의 연습 기록 카드 전달',
    ],
    repertoire: ['개별 준비곡', '다 함께 · 우리 모두 메리 크리스마스'],
    homework: '없음 — 겨울방학 연습 계획 세우기',
  },
]

const VACATION_WEEKS: SeasonWeek[] = [
  {
    week: 1,
    title: '내 손 점검하기 — 자세와 스케일',
    goal: '손목·손가락 모양을 스스로 점검하는 기준을 갖는다',
    activities: [
      '손 모양 사진을 찍어 첫 주 기록으로 남기기',
      'C장조 스케일 2옥타브 — 느리게, 소리 크기를 고르게',
      '하농 1~2번을 메트로놈 60에서 시작해 4씩 올리기',
    ],
    repertoire: ['C장조 스케일·아르페지오', '하농 1~3번'],
    homework: '매일 스케일 5분 + 메트로놈 기록표 채우기',
  },
  {
    week: 2,
    title: '악보를 빨리 읽는 법 — 초견 훈련',
    goal: '처음 보는 4마디를 멈추지 않고 끝까지 친다',
    activities: [
      '4마디 초견 카드 3장 — 틀려도 멈추지 않기 규칙',
      '음자리표별 랜드마크 음(도·솔·파) 찾기 게임',
      '리듬만 먼저 읽고 → 음정 붙이는 2단계 읽기 연습',
    ],
    repertoire: ['초견용 4마디 카드 모음', '바이엘·체르니에서 새 곡 1개'],
    homework: '매일 새 악보 4마디 한 장씩 초견',
  },
  {
    week: 3,
    title: '한 곡을 끝까지 — 통과 연습법',
    goal: '어려운 마디를 골라내 부분 연습하는 방법을 익힌다',
    activities: [
      '내 곡에서 가장 자주 틀리는 3마디 찾아 표시하기',
      '그 마디만 느리게 10회 → 원래 빠르기 3회',
      '처음부터 끝까지 멈추지 않고 통과 2회 (녹음)',
    ],
    repertoire: ['개별 진도곡'],
    homework: '표시한 마디를 매일 10회씩, 통과 연습 1회 녹음',
  },
  {
    week: 4,
    title: '작은 무대 — 방학 발표회',
    goal: '한 달의 연습을 무대에서 확인하고 다음 목표를 세운다',
    activities: [
      '2주차 초견 카드 즉석 연주 도전',
      '개별 발표 + 첫 주 손 모양 사진과 비교하기',
      '개학 후 3개월 목표를 카드에 적어 학부모에게 전달',
    ],
    repertoire: ['개별 진도곡 발표'],
    homework: '없음 — 개학 후 목표 카드 붙여 두기',
  },
]

const HALLOWEEN_WORKSHEETS: Worksheet[] = [
  {
    id: 'hw-quiz',
    kind: 'quiz',
    title: '할로윈 음악 퀴즈',
    instruction: '알맞은 답에 ○ 하세요.',
    questions: [
      { prompt: '무섭고 어두운 느낌을 주는 조성은?', choices: ['장조', '단조'], answer: '단조' },
      { prompt: '건반에서 바로 옆 건반까지의 거리를 무엇이라고 하나요?', choices: ['온음', '반음'], answer: '반음' },
      { prompt: '「산왕의 궁전에서」를 작곡한 사람은?', choices: ['그리그', '모차르트', '쇼팽'], answer: '그리그' },
      { prompt: '소리를 점점 크게 하라는 기호는?', choices: ['crescendo', 'diminuendo'], answer: 'crescendo' },
      { prompt: '아주 낮은 소리를 내려면 건반의 어느 쪽으로 가야 하나요?', choices: ['왼쪽', '오른쪽'], answer: '왼쪽' },
      { prompt: '쉼표는 무엇을 하라는 표시인가요?', choices: ['쉬어라', '크게 쳐라'], answer: '쉬어라' },
    ],
  },
  {
    id: 'hw-rhythm',
    kind: 'rhythm',
    title: '유령의 걸음 — 리듬 받아쓰기',
    instruction: '선생님이 친 리듬을 듣고 빈칸에 음표를 그려 넣으세요. (4/4박자, 4마디)',
    questions: [
      { prompt: '1마디 — 유령이 천천히 걷습니다 (4분음표 4개)', choices: [], answer: '♩ ♩ ♩ ♩' },
      { prompt: '2마디 — 박쥐가 빠르게 날아갑니다 (8분음표 8개)', choices: [], answer: '♪♪♪♪ ♪♪♪♪' },
      { prompt: '3마디 — 두 걸음 걷고 멈춥니다', choices: [], answer: '♩ ♩ 𝄽 𝄽' },
      { prompt: '4마디 — 내가 만든 리듬', choices: [], answer: '자유' },
    ],
  },
  {
    id: 'hw-color',
    kind: 'coloring',
    title: '음표 색칠하고 이름 쓰기',
    instruction: '음표를 색칠한 뒤 이름과 박수를 적으세요.',
    questions: [
      { prompt: '온음표', choices: [], answer: '4박' },
      { prompt: '2분음표', choices: [], answer: '2박' },
      { prompt: '4분음표', choices: [], answer: '1박' },
      { prompt: '8분음표', choices: [], answer: '1/2박' },
    ],
  },
]

const CHRISTMAS_WORKSHEETS: Worksheet[] = [
  {
    id: 'xmas-quiz',
    kind: 'quiz',
    title: '캐럴 음악 퀴즈',
    instruction: '알맞은 답에 ○ 하세요.',
    questions: [
      { prompt: '「고요한 밤 거룩한 밤」은 어느 나라에서 처음 만들어졌나요?', choices: ['오스트리아', '미국', '영국'], answer: '오스트리아' },
      { prompt: 'C화음을 이루는 세 음은?', choices: ['도-미-솔', '레-파-라', '미-솔-시'], answer: '도-미-솔' },
      { prompt: '페달은 언제 갈아 밟나요?', choices: ['화음이 바뀔 때', '한 곡이 끝날 때'], answer: '화음이 바뀔 때' },
      { prompt: '두 사람이 한 피아노에서 함께 치는 것을 무엇이라 하나요?', choices: ['연탄(듀엣)', '독주'], answer: '연탄(듀엣)' },
      { prompt: '「징글벨」의 박자는?', choices: ['4/4', '3/4'], answer: '4/4' },
      { prompt: '음을 하나씩 펼쳐 치는 주법은?', choices: ['아르페지오', '스타카토'], answer: '아르페지오' },
    ],
  },
  {
    id: 'xmas-listening',
    kind: 'listening',
    title: '캐럴 듣고 화음 찾기',
    instruction: '들려주는 마디의 화음이 무엇인지 적으세요. (C · F · G 중 하나)',
    questions: [
      { prompt: '고요한 밤 1마디', choices: ['C', 'F', 'G'], answer: 'C' },
      { prompt: '고요한 밤 3마디', choices: ['C', 'F', 'G'], answer: 'G' },
      { prompt: '징글벨 후렴 첫 마디', choices: ['C', 'F', 'G'], answer: 'C' },
      { prompt: '루돌프 사슴코 5마디', choices: ['C', 'F', 'G'], answer: 'F' },
    ],
  },
  {
    id: 'xmas-plan',
    kind: 'coloring',
    title: '나의 캐럴 메들리 계획표',
    instruction: '내가 연주할 두 곡과 이어 붙일 방법을 적으세요.',
    questions: [
      { prompt: '첫 번째 곡', choices: [], answer: '' },
      { prompt: '두 번째 곡', choices: [], answer: '' },
      { prompt: '두 곡을 잇는 4마디 아이디어', choices: [], answer: '' },
      { prompt: '가족에게 들려주고 싶은 부분', choices: [], answer: '' },
    ],
  },
]

const VACATION_WORKSHEETS: Worksheet[] = [
  {
    id: 'vac-quiz',
    kind: 'quiz',
    title: '기초 음악 이론 점검',
    instruction: '알맞은 답에 ○ 하세요.',
    questions: [
      { prompt: '높은음자리표 첫째 줄의 음이름은?', choices: ['미', '솔', '시'], answer: '미' },
      { prompt: '낮은음자리표 넷째 줄의 음이름은?', choices: ['라', '파', '레'], answer: '라' },
      { prompt: '#(샾)은 음을 어떻게 하나요?', choices: ['반음 올린다', '반음 내린다'], answer: '반음 올린다' },
      { prompt: '메트로놈 숫자가 커지면?', choices: ['빨라진다', '느려진다'], answer: '빨라진다' },
      { prompt: '점4분음표는 몇 박인가요?', choices: ['1.5박', '2박'], answer: '1.5박' },
      { prompt: 'C장조에는 조표가 몇 개 있나요?', choices: ['0개', '1개'], answer: '0개' },
    ],
  },
  {
    id: 'vac-log',
    kind: 'coloring',
    title: '4주 연습 기록표',
    instruction: '연습한 날은 칸을 색칠하고, 메트로놈 빠르기를 적으세요.',
    questions: [
      { prompt: '1주차 (월~일)', choices: [], answer: '' },
      { prompt: '2주차 (월~일)', choices: [], answer: '' },
      { prompt: '3주차 (월~일)', choices: [], answer: '' },
      { prompt: '4주차 (월~일)', choices: [], answer: '' },
    ],
  },
  {
    id: 'vac-sight',
    kind: 'listening',
    title: '초견 도전 카드',
    instruction: '처음 보는 4마디를 멈추지 않고 연주한 뒤 스스로 점수를 매기세요.',
    questions: [
      { prompt: '1일차 — 멈추지 않았나요?', choices: ['예', '아니오'], answer: '' },
      { prompt: '2일차 — 박자를 지켰나요?', choices: ['예', '아니오'], answer: '' },
      { prompt: '3일차 — 손을 보지 않고 쳤나요?', choices: ['예', '아니오'], answer: '' },
      { prompt: '4일차 — 셈여림을 지켰나요?', choices: ['예', '아니오'], answer: '' },
    ],
  },
]

const PACKS: Record<SeasonTheme, Omit<SeasonPack, 'source' | 'fallbackReason'>> = {
  halloween: {
    theme: 'halloween',
    title: '할로윈 음악 탐험 4주 특강',
    subtitle: '무서운 소리는 어떻게 만들까? — 단조·반음·즉흥으로 배우는 음악',
    target: '피아노 6개월~2년차 (초등 저·중학년)',
    weeks: HALLOWEEN_WEEKS,
    worksheets: HALLOWEEN_WORKSHEETS,
    parentNotice:
      '10월 한 달간 할로윈 테마 음악 특강을 진행합니다. 단조와 반음, 리듬을 놀이로 익히고 마지막 주에는 분장을 하고 미니 콘서트를 엽니다. 4주차에는 간단한 분장 소품을 준비해 주세요.',
  },
  christmas: {
    theme: 'christmas',
    title: '크리스마스 캐럴 4주 특강',
    subtitle: '세 개의 화음으로 캐럴 반주하기 — 가족 앞 홈 콘서트까지',
    target: '피아노 1년차 이상 (양손 연주 가능)',
    weeks: CHRISTMAS_WEEKS,
    worksheets: CHRISTMAS_WORKSHEETS,
    parentNotice:
      '12월 한 달간 캐럴 특강을 진행합니다. C·F·G 세 화음으로 캐럴 반주를 배우고, 마지막 주에는 가족과 함께하는 홈 콘서트를 엽니다. 4주차 콘서트에 꼭 참석해 주세요.',
  },
  vacation: {
    theme: 'vacation',
    title: '방학 집중 4주 기본기 특강',
    subtitle: '자세 · 스케일 · 초견 · 통과 연습 — 학기 중 진도를 위한 기본기 다지기',
    target: '전 학년 (진도 무관)',
    weeks: VACATION_WEEKS,
    worksheets: VACATION_WORKSHEETS,
    parentNotice:
      '방학 동안 기본기 집중 특강을 진행합니다. 자세 점검·스케일·초견·통과 연습으로 학기 중 진도가 빨라지는 토대를 만듭니다. 매일 15분 연습 기록표를 가정에서 함께 확인해 주세요.',
  },
}

export function templatePack(theme: SeasonTheme): SeasonPack {
  const base = PACKS[theme]
  return { ...base, source: 'template', fallbackReason: null }
}

export const SEASON_THEMES: SeasonTheme[] = ['halloween', 'christmas', 'vacation']
