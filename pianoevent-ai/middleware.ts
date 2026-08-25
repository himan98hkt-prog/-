import { NextResponse, type NextRequest } from 'next/server'

export const ACADEMY_COOKIE = 'pe_academy'

/**
 * 원장 브라우저마다 학원 식별자를 하나 발급한다.
 * (MVP 의 최소 세션. Supabase Auth 로 교체할 때는 이 쿠키 대신 user.id 를 쓰면 된다.)
 */
export function middleware(request: NextRequest) {
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
