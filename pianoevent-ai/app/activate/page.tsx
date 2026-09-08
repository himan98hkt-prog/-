import { ActivateForm } from '@/components/license/activate-form'
import { APP_ART } from '@/lib/design/art'
import { BRAND } from '@/lib/brand'

export const dynamic = 'force-dynamic'
export const metadata = { title: '인증키 넣기' }

/**
 * 처음 켜셨을 때 나오는 화면.
 *
 * 시작 화면(무대 사진 · 금색 표식)과 **같은 옷**을 입힌다. 설치 → 시작 화면 → 이 화면
 * 이 한 흐름으로 보여야 「제대로 만든 물건」으로 느껴진다. 여기서 화면이 갑자기
 * 흰 문서로 바뀌면 그 느낌이 그 자리에서 깨진다.
 */
export default function ActivatePage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#08080a] px-5 py-12">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={APP_ART.splash} alt="" aria-hidden className="absolute inset-0 h-full w-full object-cover" />
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(130% 100% at 50% 40%, rgba(8,8,10,0.62) 0%, rgba(8,8,10,0.9) 60%, rgba(8,8,10,0.97) 100%)',
        }}
      />

      <div className="relative grid w-full max-w-[420px] justify-items-center gap-7">
        <div className="grid justify-items-center gap-3">
          <div
            aria-hidden
            className="h-[76px] w-[76px]"
            style={{
              background: 'linear-gradient(160deg, #f0d9a0 0%, #c9a253 52%, #8f6c26 100%)',
              WebkitMask: `url(${APP_ART.logo}) center / contain no-repeat`,
              mask: `url(${APP_ART.logo}) center / contain no-repeat`,
              maskMode: 'luminance',
              ['WebkitMaskMode' as string]: 'luminance',
            }}
          />
          <h1 className="text-2xl font-bold tracking-tight text-[#f6f1e6]">{BRAND.name}</h1>
          <p data-wordmark className="text-[11px] tracking-[0.42em] text-[#c9a253]" style={{ textIndent: '0.42em' }}>
            {BRAND.nameEn}
          </p>
          <div className="mt-1 h-px w-11 bg-[#c9a253]/55" />
          <p className="text-xs tracking-[0.12em] text-[#f6f1e6]/60">{BRAND.maker}</p>
        </div>

        <ActivateForm />
      </div>
    </main>
  )
}
