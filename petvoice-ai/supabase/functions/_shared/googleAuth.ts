/**
 * Google 서비스 계정으로 Android Publisher API 액세스 토큰을 얻는다.
 *
 * 라이브러리 없이 JWT 를 직접 서명한다 (Deno 표준 crypto).
 * 토큰은 만료 1분 전까지 재사용한다 — 알림이 몰려도 OAuth 를 매번 두드리지 않게.
 */

interface ServiceAccount {
  client_email: string;
  private_key: string;
}

let cached: { token: string; expiresAt: number } | null = null;

function base64url(bytes: Uint8Array | string): string {
  const raw = typeof bytes === 'string' ? bytes : String.fromCharCode(...bytes);
  return btoa(raw).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** PEM(PKCS#8) → CryptoKey */
async function importPrivateKey(pem: string): Promise<CryptoKey> {
  const body = pem
    .replace(/-----BEGIN PRIVATE KEY-----/, '')
    .replace(/-----END PRIVATE KEY-----/, '')
    .replace(/\s+/g, '');
  const der = Uint8Array.from(atob(body), (c) => c.charCodeAt(0));
  return crypto.subtle.importKey(
    'pkcs8',
    der.buffer as ArrayBuffer,
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['sign'],
  );
}

function readServiceAccount(): ServiceAccount {
  const raw = Deno.env.get('GOOGLE_SERVICE_ACCOUNT_JSON');
  if (!raw) throw new Error('GOOGLE_SERVICE_ACCOUNT_JSON 이 설정되지 않았습니다.');
  const parsed = JSON.parse(raw) as ServiceAccount;
  if (!parsed.client_email || !parsed.private_key) {
    throw new Error('서비스 계정 JSON 에 client_email / private_key 가 없습니다.');
  }
  // 환경변수로 넣을 때 개행이 \n 문자열로 들어오는 경우가 흔하다
  return { ...parsed, private_key: parsed.private_key.replace(/\\n/g, '\n') };
}

export async function getGoogleAccessToken(
  scope = 'https://www.googleapis.com/auth/androidpublisher',
): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  if (cached && cached.expiresAt - 60 > now) return cached.token;

  const account = readServiceAccount();
  const header = base64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
  const claims = base64url(
    JSON.stringify({
      iss: account.client_email,
      scope,
      aud: 'https://oauth2.googleapis.com/token',
      iat: now,
      exp: now + 3600,
    }),
  );

  const key = await importPrivateKey(account.private_key);
  const signature = new Uint8Array(
    await crypto.subtle.sign('RSASSA-PKCS1-v1_5', key, new TextEncoder().encode(`${header}.${claims}`)),
  );
  const assertion = `${header}.${claims}.${base64url(signature)}`;

  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion,
    }),
  });

  if (!response.ok) {
    throw new Error(`Google OAuth 실패: ${response.status}`);
  }
  const body = (await response.json()) as { access_token: string; expires_in: number };
  cached = { token: body.access_token, expiresAt: now + body.expires_in };
  return body.access_token;
}
