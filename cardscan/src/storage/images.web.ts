// 명함 사진 보관 — 웹(아이폰 홈 화면 웹앱): 브라우저 IndexedDB 에 JPEG 를 저장하고 'idb:<키>' 로 가리킨다.
// localStorage 는 5MB 한도라 사진을 넣으면 금방 차므로 쓰지 않는다.
import { useEffect, useState } from 'react';

const DB = 'cardscan';
const STORE = 'images';
const PREFIX = 'idb:';

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, run: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const req = run(db.transaction(STORE, mode).objectStore(STORE));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function persistImage(tempUri: string, key: string): Promise<string> {
  const blob = await (await fetch(tempUri)).blob();
  await tx('readwrite', (s) => s.put(blob, key));
  // 브라우저가 저장 공간을 임의로 비우지 않도록 요청 (홈 화면 웹앱이면 대개 허용)
  navigator.storage?.persist?.().catch(() => {});
  return PREFIX + key;
}

export function deleteImage(uri?: string) {
  if (!uri?.startsWith(PREFIX)) return;
  tx('readwrite', (s) => s.delete(uri.slice(PREFIX.length))).catch(() => {});
}

/** 'idb:' 주소를 화면에 띄울 수 있는 blob URL 로 바꾼다 */
export function useImageUri(uri?: string): string | undefined {
  const [url, setUrl] = useState<string | undefined>(uri?.startsWith(PREFIX) ? undefined : uri);
  useEffect(() => {
    if (!uri?.startsWith(PREFIX)) {
      setUrl(uri);
      return;
    }
    let objectUrl: string | undefined;
    let alive = true;
    tx<Blob | undefined>('readonly', (s) => s.get(uri.slice(PREFIX.length)))
      .then((blob) => {
        if (!alive || !blob) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {});
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [uri]);
  return url;
}
