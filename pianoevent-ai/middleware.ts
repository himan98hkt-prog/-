import { NextResponse, type NextRequest } from 'next/server'
import { LICENSE_COOKIE } from '@/lib/license/cookie'

export const ACADEMY_COOKIE = 'pe_academy'

/** 인증키 없이도 열려야 하는 자리 — 인증 화면 자신과, 학부모가 여는 초대장 */
const OPEN = ['/activate', '/api/license', '/e/', '/api/rsvp', '/privacy', '/terms']

/**
 * 원장 브라우저마다 학원 식별자를 하나 발급하고, 설치판이면 **인증키를 확인한다.**
 *
 * 인증은 설치판에서만 묻는다(`PIANOEVENT_REQUIRE_LICENSE`). 상세페이지의 체험판은
 * 그냥 열려야 하기 때문이다 — 사러 오신 분께 키부터 물으면 그 자리에서 닫으신다.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  if (
    process.env.PIANOEVENT_REQUIRE_LICENSE === '1' &&
    !request.cookies.get(LICENSE_COOKIE) &&
    !OPEN.some((at) => pathname === at || pathname.startsWith(`${at}/`) || pathname.startsWith(at))
  ) {
    const to = request.nextUrl.clone()
    to.pathname = '/activate'
    to.search = ''
    return NextResponse.redirect(to)
  }

  const response = NextResponse.next()
  if (!request.cookies.get(ACADEMY_COOKIE)) {
    response.cookies.set(ACADEMY_COOKIE, crypto.randomUUID(), {
      httpOnly: true,
      sameSite: 'lax',
      secure: process.env.NODE_ENV === 'production',
      path: '/',
      maxAge: 60 * 60 * 24 * 365,
    })
  }
  return response
}

export const config = {
  // 공개 초대장(/e/*) 과 정적 자산에는 쿠키를 심지 않는다
  matcher: ['/((?!_next/static|_next/image|favicon.ico|e/|api/rsvp).*)'],
}
