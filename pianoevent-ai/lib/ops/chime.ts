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

/**
 * 두 음짜리 짧은 알림.
 *
 * 객석에 들리면 안 된다. 손에 든 기계에서만 들릴 만큼 작게, 0.5초 안에 끝낸다.
 */
export function playChime(ctx: AudioContext, at = ctx.currentTime): void {
  const notes = [
    { hz: 659.25, start: 0, span: 0.18 }, // 미
    { hz: 880.0, start: 0.16, span: 0.3 }, // 라
  ]
  for (const note of notes) {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.value = note.hz
    const from = at + note.start
    // 딱 끊으면 '틱' 소리가 난다 — 올렸다 내린다
    gain.gain.setValueAtTime(0.0001, from)
    gain.gain.exponentialRampToValueAtTime(0.22, from + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, from + note.span)
    osc.connect(gain).connect(ctx.destination)
    osc.start(from)
    osc.stop(from + note.span + 0.02)
  }
}
