/**
 * 앱 밖에서 들어오는 링크를 해석한다.
 *
 * 지금 필요한 건 하나뿐이다 — 홈 화면 바로가기에서 곧장 녹음으로 들어가는 것.
 * 앱을 열고 → 탭을 고르고 → 버튼을 누르는 사이에 정작 재미있는 소리는 끝난다.
 *
 * 파싱을 여기(순수 함수)에 두는 이유는 두 가지다.
 * - 테스트할 수 있다. 링크는 스토어 심사·바로가기·공유 카드가 다 건드리는 표면이다.
 * - 모르는 링크에 앱이 반응하지 않는다는 걸 **명시적으로** 못 박을 수 있다.
 */

export type DeepLinkAction = { kind: 'record' } | { kind: 'diary' } | null;

/** 우리 스킴 (app.json 의 scheme 과 같아야 한다) */
export const APP_SCHEME = 'petvoice';

/**
 * `petvoice://record` 처럼 생긴 링크를 동작으로 바꾼다.
 *
 * `URL` 파서를 쓰지 않는다 — 커스텀 스킴에서 호스트/경로를 어디에 넣는지가
 * 플랫폼마다 다르고(안드로이드는 host, iOS 는 path 로 오는 경우가 있다),
 * 런타임에 따라 URL 구현도 다르다. 스킴을 떼고 남은 첫 토막만 본다.
 */
export function parseDeepLink(url: string | null | undefined): DeepLinkAction {
  if (!url) return null;

  const trimmed = url.trim().toLowerCase();
  const prefix = `${APP_SCHEME}:`;
  if (!trimmed.startsWith(prefix)) return null;

  // petvoice://record?x=1 → record
  const rest = trimmed.slice(prefix.length).replace(/^\/+/, '');
  const token = rest.split(/[/?#]/)[0];

  if (token === 'record') return { kind: 'record' };
  if (token === 'diary') return { kind: 'diary' };
  return null;
}
