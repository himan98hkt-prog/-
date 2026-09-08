'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { BRAND } from '@/lib/brand'

/**
 * 인증키를 넣는 화면.
 *
 * 원장님이 여기서 하실 일은 **붙여넣기 한 번**이다. 그래서
 *   · 치시는 대로 다섯 자씩 끊어서 보여 드리고(RM-…),
 *   · 소문자로 치셔도, 하이픈을 빼먹으셔도, `l`과 `1`을 헷갈리셔도 알아서 받고,
 *   · 문자로 받은 줄을 통째로 붙여넣으셔도 키만 골라낸다.
 * 틀렸을 때는 「틀렸습니다」로 끝내지 않고 **무엇을 하셔야 하는지**를 적는다.
 */
const FIX: Record<string, string> = { I: '1', L: '1', O: '0', U: 'V' }

function pretty(raw: string): string {
  const up = raw.toUpperCase().replace(/[^0-9A-Z]/g, '')
  const body = (up.startsWith('RM') ? up.slice(2) : up)
    .split('')
    .map((c) => FIX[c] ?? c)
    .join('')
    .slice(0, 20)
  const groups = body.match(/.{1,5}/g) ?? []
  return groups.length > 0 ? `RM-${groups.join('-')}` : ''
}

export function ActivateForm() {
  const router = useRouter()
  const [key, setKey] = useState('')
  const [academyName, setAcademyName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [checking, setChecking] = useState(true)
  const box = useRef<HTMLInputElement>(null)

  // 이미 넣어 두신 키가 있으면 묻지 않고 그대로 열어 드린다
  useEffect(() => {
    let alive = true
    void fetch('/api/license')
      .then((r) => r.json())
      .then((s: { active?: boolean }) => {
        if (!alive) return
        if (s.active) {
          router.replace('/events')
          router.refresh()
          return
        }
        setChecking(false)
        box.current?.focus()
      })
      .catch(() => alive && setChecking(false))
    return () => {
      alive = false
    }
  }, [router])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const res = await fetch('/api/license', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, academyName }),
      })
      const status = (await res.json()) as { active?: boolean; reason?: string }
      if (status.active) {
        router.replace('/events')
        router.refresh()
        return
      }
      setError(status.reason ?? '확인하지 못했습니다. 잠시 뒤 다시 눌러 주세요.')
    } catch {
      setError('확인하지 못했습니다. 프로그램을 닫았다가 다시 열어 주세요.')
    } finally {
      setBusy(false)
    }
  }

  const ready = key.replace(/[^0-9A-Za-z]/g, '').length >= 20

  return (
    <form onSubmit={submit} className="grid w-full max-w-[420px] gap-4">
      <div className="grid gap-1.5">
        <label htmlFor="license-key" className="text-sm font-medium text-[#f6f1e6]">
          인증키
        </label>
        <input
          id="license-key"
          ref={box}
          value={key}
          onChange={(e) => setKey(pretty(e.target.value))}
          placeholder="RM-XXXXX-XXXXX-XXXXX-XXXXX"
          autoComplete="off"
          spellCheck={false}
          inputMode="text"
          className="press h-14 w-full rounded-lg border border-[#c9a253]/40 bg-black/40 px-4 text-center text-lg tracking-[0.18em] text-[#f6f1e6] outline-none placeholder:text-[#f6f1e6]/25 focus:border-[#c9a253]"
        />
        <p className="text-xs text-[#f6f1e6]/55">
          결제하실 때 문자·이메일로 보내 드린 스무 글자입니다. 통째로 붙여넣으셔도 됩니다.
        </p>
      </div>

      <div className="grid gap-1.5">
        <label htmlFor="license-academy" className="text-sm font-medium text-[#f6f1e6]">
          학원 이름 <span className="font-normal text-[#f6f1e6]/50">(안 적으셔도 됩니다)</span>
        </label>
        <input
          id="license-academy"
          value={academyName}
          onChange={(e) => setAcademyName(e.target.value)}
          placeholder="예) 하모니 피아노학원"
          className="press h-12 w-full rounded-lg border border-white/15 bg-black/40 px-4 text-[#f6f1e6] outline-none placeholder:text-[#f6f1e6]/25 focus:border-[#c9a253]"
        />
        <p className="text-xs text-[#f6f1e6]/45">
          문의하실 때 저희가 찾아보는 이름입니다. 이 컴퓨터에만 적히고 밖으로 나가지 않습니다.
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-lg border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={!ready || busy || checking}
        className="press press-filled h-13 rounded-lg bg-[#c9a253] py-3.5 text-base font-semibold text-[#1b1712] disabled:cursor-not-allowed disabled:opacity-45"
      >
        {busy ? '확인하고 있습니다…' : checking ? '잠시만요…' : '시작하기'}
      </button>

      <p className="text-center text-xs leading-relaxed text-[#f6f1e6]/45">
        키를 못 찾으시겠으면 결제하신 문자·이메일을 확인해 주세요.
        <br />
        그래도 없으시면 <span className="text-[#c9a253]">{BRAND.site.replace('https://', '')}</span> 으로 문의해 주세요.
      </p>
    </form>
  )
}
