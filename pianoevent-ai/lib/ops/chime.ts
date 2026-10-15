/**
 * 다음 차례 알림음.
 *
 * 당일 무대 옆에서 원장님은 화면만 보고 계실 수가 없다. 아이를 챙기고, 학부모와 인사하고,
 * 사회자와 눈을 맞추신다. 그 사이에 다음 아이를 대기실에서 데려올 때를 놓치신다.
 *
 * 그래서 **다음 차례 1분 전**에 짧게 한 번 울린다.
 *
 * 소리 **파일은 쓰지 않는다.** 배경음악과 마찬가지로 남의 소리를 실어 파는 것이 되고,
 * 파일을 담으면 오프라인에서 못 쓰는 자리도 생긴다. 브라우저가 가진 소리 발생기로
 * 두 음(미 → 라)을 짧게 낸다. 이건 저작물이 아니라 그냥 소리다.
 */

/** 몇 초 전에 알릴지 */
export const CHIME_LEAD_SEC = 60

/**
 * 이 순서에서 **언제** 울릴지 (순서가 시작되고 몇 초 뒤).
 *
 * 예정 시간이 알림보다 짧은 곡이면 울릴 자리가 없다 — 그런 곡은 절반쯤에서 한 번 울린다.
 * 아예 안 울리면 짧은 곡만 늘어선 유아부에서는 알림이 하나도 안 온다.
 */
export function chimeAtSec(plannedSec: number, leadSec: number = CHIME_LEAD_SEC): number | null {
  if (!Number.isFinite(plannedSec) || plannedSec <= 10) return null
  if (plannedSec <= leadSec + 10) return Math.round(plannedSec / 2)
  return Math.round(plannedSec - leadSec)
}

/** 지금 울릴 때가 되었는가 */
export function chimeDue(onStageSec: number, plannedSec: number, leadSec: number = CHIME_LEAD_SEC): boolean {
  const at = chimeAtSec(plannedSec, leadSec)
  return at !== null && onStageSec >= at
}

/** 알림음을 켜 두셨는지 — 이 휴대폰에만 담긴다 */
export function chimeStorageKey(eventId: string): string {
  return `pianoevent.live.chime.${eventId}`
}

/* ────────────────────────────────────────────────────────────────────────────
 * 소리 세 가지
 *
 * 홀마다 다르다. 로비가 시끄러운 곳에서는 맑은 종소리가 묻히고, 조용한 소공연장에서는
 * 낮고 굵은 소리가 객석까지 새어 나간다. 그래서 세 가지를 두고 고르시게 한다.
 * 셋 다 파일이 아니라 브라우저가 그 자리에서 내는 소리다.
 * ──────────────────────────────────────────────────────────────────────────── */

export interface ChimeNote {
  hz: number
  start: number
  span: number
  /** 소리 세기 (0~1) */
  gain?: number
  /** 파형 — 'sine' 은 맑고, 'triangle' 은 조금 두껍다 */
  wave?: OscillatorType
}

export interface ChimeSound {
  id: string
  name: string
  /** 어떤 자리에 맞는지 */
  hint: string
  notes: ChimeNote[]
}

export const CHIME_SOUNDS: ChimeSound[] = [
  {
    id: 'bell',
    name: '맑은 종',
    hint: '조용한 소공연장. 객석에 거의 안 들립니다',
    notes: [
      { hz: 659.25, start: 0, span: 0.18 },
      { hz: 880.0, start: 0.16, span: 0.3 },
    ],
  },
  {
    id: 'triple',
    name: '또렷한 세 번',
    hint: '로비가 시끄러운 홀. 세 번 끊어 울려 놓치지 않습니다',
    notes: [
      { hz: 987.77, start: 0, span: 0.12, gain: 0.26 },
      { hz: 987.77, start: 0.18, span: 0.12, gain: 0.26 },
      { hz: 1318.51, start: 0.36, span: 0.22, gain: 0.26 },
    ],
  },
  {
    id: 'low',
    name: '낮고 부드럽게',
    hint: '무대와 가까운 자리. 높은 소리가 튀지 않습니다',
    notes: [
      { hz: 329.63, start: 0, span: 0.24, wave: 'triangle' },
      { hz: 392.0, start: 0.2, span: 0.34, wave: 'triangle' },
    ],
  },
]

export const DEFAULT_CHIME_SOUND = CHIME_SOUNDS[0].id

export function getChimeSound(id: string | null | undefined): ChimeSound {
  return CHIME_SOUNDS.find((sound) => sound.id === id) ?? CHIME_SOUNDS[0]
}

/**
 * 진동.
 *
 * 로비가 시끄러우면 어떤 소리도 묻힌다. 주머니 속 진동은 안 묻힌다.
 * 소리를 끄고 진동만 켜 두실 수도 있다 — 객석에서 소리가 나면 안 되는 홀도 있다.
 */
export const CHIME_VIBRATE_MS = [180, 90, 180] as const

export function vibrate(pattern: readonly number[] = CHIME_VIBRATE_MS): boolean {
  const nav = typeof navigator === 'undefined' ? null : (navigator as Navigator & { vibrate?: (p: number | number[]) => boolean })
  if (!nav?.vibrate) return false
  try {
    return nav.vibrate([...pattern])
  } catch {
    return false
  }
}

/* ── 켜 두신 설정 ────────────────────────────────────────────────────────── */

export interface ChimePrefs {
  on: boolean
  soundId: string
  buzz: boolean
  /** 이름까지 말로 읽어 줄지 */
  speak: boolean
}

export const DEFAULT_CHIME_PREFS: ChimePrefs = {
  on: false,
  soundId: DEFAULT_CHIME_SOUND,
  buzz: false,
  speak: false,
}

/**
 * 담아 둔 설정을 되읽는다.
 *
 * 예전 판은 `'on'` / `'off'` 한 낱말만 담았다. 그때 켜 두신 원장님의 설정이
 * 사라지면 안 되므로 그 형태도 그대로 읽어 준다.
 */
export function parseChimePrefs(raw: string | null): ChimePrefs {
  if (!raw) return { ...DEFAULT_CHIME_PREFS }
  if (raw === 'on') return { ...DEFAULT_CHIME_PREFS, on: true }
  if (raw === 'off') return { ...DEFAULT_CHIME_PREFS }
  try {
    const data = JSON.parse(raw) as Partial<ChimePrefs>
    return {
      on: data.on === true,
      soundId: getChimeSound(typeof data.soundId === 'string' ? data.soundId : null).id,
      buzz: data.buzz === true,
      speak: data.speak === true,
    }
  } catch {
    return { ...DEFAULT_CHIME_PREFS }
  }
}

export function serializeChimePrefs(prefs: ChimePrefs): string {
  return JSON.stringify(prefs)
}

/**
 * 짧은 알림 한 번.
 *
 * 객석에 들리면 안 된다. 손에 든 기계에서만 들릴 만큼 작게, 0.6초 안에 끝낸다.
 */
export function playChime(ctx: AudioContext, soundId?: string | null, at = ctx.currentTime): void {
  for (const note of getChimeSound(soundId).notes) {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = note.wave ?? 'sine'
    osc.frequency.value = note.hz
    const from = at + note.start
    // 딱 끊으면 '틱' 소리가 난다 — 올렸다 내린다
    gain.gain.setValueAtTime(0.0001, from)
    gain.gain.exponentialRampToValueAtTime(note.gain ?? 0.22, from + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, from + note.span)
    osc.connect(gain).connect(ctx.destination)
    osc.start(from)
    osc.stop(from + note.span + 0.02)
  }
}

/* ── 말로도 ──────────────────────────────────────────────────────────────── */

/**
 * **"다음, 김서연" 을 말로.**
 *
 * 소리는 "무슨 일이 났다" 만 알려 준다. 그러면 화면을 봐야 누구인지 아신다.
 * 그런데 그때 원장님 손에는 아이가 있고 눈은 무대에 있다. 이름까지 말해 주면
 * 화면을 아예 안 보셔도 된다.
 *
 * 브라우저가 가진 읽어 주기를 쓴다 — 소리 파일도, 인터넷도 필요 없다.
 * (읽어 주기가 없는 브라우저·기계도 있다. 그때는 조용히 지나간다.)
 */
export function nextCallText(title: string, orderNo?: number | null): string {
  const name = title.trim()
  if (!name) return '다음 순서입니다'
  return orderNo ? `다음, ${orderNo}번 ${name}` : `다음, ${name}`
}

/** 이 브라우저가 말을 할 수 있는가 */
export function canSpeak(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

export function speak(text: string, lang = 'ko-KR'): boolean {
  if (!canSpeak()) return false
  try {
    // 앞서 읽던 것이 남아 있으면 겹친다 — 지우고 새로 읽는다
    window.speechSynthesis.cancel()
    const said = new SpeechSynthesisUtterance(text)
    said.lang = lang
    // 무대 옆이라 또박또박, 객석에 안 들릴 크기로
    said.rate = 0.95
    said.volume = 0.7
    window.speechSynthesis.speak(said)
    return true
  } catch {
    return false
  }
}
