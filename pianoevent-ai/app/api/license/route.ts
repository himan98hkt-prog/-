import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { LICENSE_COOKIE } from '@/lib/license/cookie'
import { activate, licenseStatus } from '@/lib/license/store'

/**
 * 인증키 확인.
 *
 * 확인은 **이 컴퓨터 안에서** 끝난다 — 밖으로 나가는 요청이 없다.
 * 확인이 끝나면 브라우저 쪽에 표를 하나 남겨 두어(쿠키), 화면을 열 때마다 파일을
 * 다시 읽지 않게 한다. 표가 지워져도 자료 폴더의 키가 남아 있으면 다시 살아난다.
 */
export const dynamic = 'force-dynamic'


function withCookie(status: ReturnType<typeof licenseStatus>) {
  const res = NextResponse.json(status)
  if (status.active) {
    res.cookies.set(LICENSE_COOKIE, '1', {
      httpOnly: true,
      sameSite: 'lax',
      path: '/',
      maxAge: 60 * 60 * 24 * 365,
    })
  } else {
    res.cookies.delete(LICENSE_COOKIE)
  }
  return res
}

export function GET() {
  return withCookie(licenseStatus())
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { key?: string; academyName?: string }
  if (!body.key) {
    return NextResponse.json({ ok: false, active: false, required: true, reason: '인증키를 넣어 주세요.' }, { status: 400 })
  }
  return withCookie(activate(body.key, body.academyName))
}

/** 다른 컴퓨터로 옮기실 때 — 이 컴퓨터에서 키를 내린다 */
export function DELETE() {
  cookies().delete(LICENSE_COOKIE)
  const res = NextResponse.json({ ok: true })
  res.cookies.delete(LICENSE_COOKIE)
  return res
}
