/** 의존성 없이 충돌 확률이 충분히 낮은 로컬 ID. (Expo/노드 양쪽에서 동작) */
export function createId(prefix = ''): string {
  const time = Date.now().toString(36);
  const rand = Math.random().toString(36).slice(2, 10);
  const rand2 = Math.random().toString(36).slice(2, 6);
  return `${prefix}${time}${rand}${rand2}`;
}
