/**
 * 옛 양식 이름 → 그림 이름.
 *
 * 처음에는 `switch` 에 한 줄씩 적었다. 그림을 새로 넣을 때 그 한 줄을 빠뜨리면
 * **조용히 기본 포스터가 나왔다** — 원장님은 고른 것과 다른 것이 뽑히는 줄만 아신다.
 * 지금은 `art-<그림이름>` 규칙으로 곧장 찾고, 규칙과 다른 옛 이름만 여기 남긴다.
 */
const ART_ALIAS: Record<string, string> = {
  'art-keys': 'keys-close',
  'art-hands': 'child-hands',
  'art-gala': 'gala-bokeh',
  'art-field': 'light-field',
  'art-watercolor': 'watercolor-piano',
  'art-blossom': 'blossom-piano',
  'art-summer': 'summer-window',
  'art-autumn': 'autumn-leaves',
  'art-christmas': 'christmas-pine',
  'art-confetti': 'confetti-night',
}

/** 양식 id 로 그림 id 를 낸다. 그림 포스터가 아니면 null */
export function artIdOf(templateId: string): string | null {
  if (!templateId.startsWith('art-')) return null
  return ART_ALIAS[templateId] ?? templateId.slice('art-'.length)
}
