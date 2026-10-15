import { join } from 'node:path'

/**
 * **학원 자료가 어디에 놓이는가.**
 *
 * 지금까지는 프로그램이 놓인 폴더 안(`process.cwd()`)에 그대로 썼다. 압축을 풀어
 * 바탕화면에서 실행하는 동안에는 그래도 됐다.
 *
 * 그런데 **설치해서 쓰는 프로그램**이 되면 이야기가 달라진다. 윈도우는 설치 폴더
 * (`Program Files`)에 쓰는 것을 막는다. 거기에 학원 명단을 쓰려 들면 저장이 통째로
 * 실패하고, 원장님 눈에는 "명단을 넣었는데 다음에 여니 없어졌다" 로 보인다.
 *
 * 그래서 자리를 **바깥에서 정해 줄 수 있게** 한다. 설치판(데스크톱 앱)은 운영체제가
 * 정해 준 사용자 자료 폴더를 넣어 주고, 예전처럼 폴더째 쓰실 때는 지금까지와 똑같이
 * 프로그램 폴더를 쓴다. 어느 쪽이든 **이 컴퓨터 안**이라는 약속은 그대로다.
 */
export const DATA_DIR_ENV = 'PIANOEVENT_DATA_DIR'

export function dataRoot(): string {
  const set = process.env[DATA_DIR_ENV]?.trim()
  return set && set.length > 0 ? set : process.cwd()
}

/** 명단·행사·설정이 담기는 파일 */
export function storeFile(): string {
  return join(dataRoot(), '.data', 'store.json')
}

/** 인증키를 넣어 두는 자리. 프로그램을 다시 깔아도 자료 폴더가 남으면 그대로 열린다 */
export function licenseFile(): string {
  return join(dataRoot(), '.data', 'license.json')
}

/** 자동 저장이 쌓이는 폴더 (설정 화면에서 열어 보실 수 있다) */
export function backupRoot(dirName: string): string {
  return join(dataRoot(), dirName)
}
