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

export interface UndoAction {
  /** 같은 것을 두 번 쌓지 않게 하는 표. 없으면 매번 새것으로 본다 */
  id: string
  /** "명단 붙여넣기" · "김서연 · 연주곡" — 무엇을 하셨는지 */
  what: string
  /** "소나티네 → 엘리제를 위하여" — 되돌리면 어떻게 되는지 */
  detail?: string
  /** 되돌릴 때 부를 것 */
  run: () => Promise<void> | void
}

export function pushUndo(stack: UndoAction[], action: UndoAction): UndoAction[] {
  return [action, ...stack.filter((a) => a.id !== action.id)].slice(0, UNDO_KEEP)
}

export function popUndo(stack: UndoAction[]): { action: UndoAction | null; rest: UndoAction[] } {
  if (stack.length === 0) return { action: null, rest: stack }
  return { action: stack[0], rest: stack.slice(1) }
}

/** 화면을 옮기시면 앞의 것은 지운다 — 다른 화면의 일을 여기서 되돌리면 놀라신다 */
export function forScreen(stack: UndoAction[], screen: string): UndoAction[] {
  return stack.filter((a) => a.id.startsWith(`${screen}:`))
}

/** 띠에 적을 한 줄 */
export function undoLine(action: UndoAction): string {
  return action.detail ? `${action.what} (${action.detail})` : action.what
}
