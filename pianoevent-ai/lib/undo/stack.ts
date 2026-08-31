/**
 * 되돌리기 한 곳으로 모으기.
 *
 * 되돌리기가 화면마다 따로 있으면 원장님은 **그 자리마다 새로 배우셔야 한다.**
 * 명단 붙여넣기에 하나, 표 고치기에 하나, 순서 바꾸기에 하나 — 셋 다 하는 일은
 * 같은데 생김새도 자리도 다르다.
 *
 * 그래서 화면 위 한 자리에만 둔다. 무엇을 하시든 "방금 하신 것" 이 거기 뜬다.
 * 배우실 것이 하나로 줄고, 겁내지 않고 눌러 보시게 된다.
 *
 * 되돌리는 방법 자체(서버에 무엇을 보낼지)는 화면마다 다르므로 그 함수는 각자 넣고,
 * 여기서는 **무엇을 쌓고 무엇을 보여 줄지**만 정한다.
 */

/** 몇 번까지 거슬러 올라가나 */
export const UNDO_KEEP = 10

/**
 * 되돌리는 방법을 **글로 적어 둔 것**.
 *
 * 화면을 옮기면 지금까지는 되돌릴 것이 사라졌다. 그런데 원장님은 명단을 고치고
 * 인쇄물을 보러 가셨다가 "아까 그거 잘못 고쳤는데" 하고 돌아오신다.
 * 그때 되돌릴 수 있어야 한다.
 *
 * 함수는 화면을 옮기면 사라지지만, **어디에 무엇을 보낼지**는 글로 남길 수 있다.
 * 그래서 되돌리기를 요청 한 줄로 적어 두고, 나중에 그대로 다시 보낸다.
 */
export interface UndoRequest {
  url: string
  method: 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
}

export interface UndoAction {
  /** 같은 것을 두 번 쌓지 않게 하는 표. 없으면 매번 새것으로 본다 */
  id: string
  /** "명단 붙여넣기" · "김서연 · 연주곡" — 무엇을 하셨는지 */
  what: string
  /** "소나티네 → 엘리제를 위하여" — 되돌리면 어떻게 되는지 */
  detail?: string
  /** 어느 행사에서 하신 일인가 — 다른 행사에서 되돌릴 수 있으면 안 된다 */
  eventId?: string
  /** 언제 하셨는지 (밀리초). 오래된 것은 스스로 사라진다 */
  at?: number
  /** 되돌릴 때 보낼 요청. 이것이 있으면 화면을 옮겨도 살아남는다 */
  request?: UndoRequest
  /** 요청으로 적을 수 없는 것만 함수로 (그 화면을 벗어나면 사라진다) */
  run?: () => Promise<void> | void
}

/** 되돌릴 것을 브라우저에 남겨 두는 자리 */
export const UNDO_KEY = 'pianoevent.undo'

/** 이만큼 지나면 스스로 사라진다 — 어제 하신 일을 오늘 되돌리면 놀라신다 */
export const UNDO_TTL_MS = 30 * 60 * 1000

/** 화면을 옮겨도 살아남을 수 있는 것만 (요청으로 적혀 있는 것) */
export function keepable(stack: UndoAction[]): UndoAction[] {
  return stack.filter((a) => a.request !== undefined)
}

/** 이 행사의 것이면서 아직 안 묵은 것만 */
export function usable(stack: UndoAction[], eventId: string, now = Date.now()): UndoAction[] {
  return stack.filter(
    (a) => (!a.eventId || a.eventId === eventId) && (!a.at || now - a.at < UNDO_TTL_MS),
  )
}

export function pushUndo(stack: UndoAction[], action: UndoAction): UndoAction[] {
  return [action, ...stack.filter((a) => a.id !== action.id)].slice(0, UNDO_KEEP)
}

export function popUndo(stack: UndoAction[]): { action: UndoAction | null; rest: UndoAction[] } {
  if (stack.length === 0) return { action: null, rest: stack }
  return { action: stack[0], rest: stack.slice(1) }
}

/** 한 화면 안에서만 볼 것을 고를 때 */
export function forScreen(stack: UndoAction[], screen: string): UndoAction[] {
  return stack.filter((a) => a.id.startsWith(`${screen}:`))
}

/** 띠에 적을 한 줄 */
export function undoLine(action: UndoAction): string {
  return action.detail ? `${action.what} (${action.detail})` : action.what
}
