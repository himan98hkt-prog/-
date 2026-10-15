/**
 * 코어는 화면에 보여 줄 **문장을 만들지 않는다.** 대신 "무엇을 말할지"를 가리키는
 * 참조를 돌려주고, 번역은 UI 에서 한다. 그래야 같은 로직이 한국어·영어·일본어에서 함께 돈다.
 *
 * 예외는 모델이 만든 문장(behaviorAnalysis, healthAlert 등)이다.
 * 그건 이미 사용자 언어로 쓰여 있으므로 `raw()` 로 그대로 흘려보낸다.
 */
export type Message = { key: string; params?: Record<string, string | number> } | { text: string };

export function msg(key: string, params?: Record<string, string | number>): Message {
  return params ? { key, params } : { key };
}

export function raw(text: string): Message {
  return { text };
}

export function isRaw(message: Message): message is { text: string } {
  return 'text' in message;
}
