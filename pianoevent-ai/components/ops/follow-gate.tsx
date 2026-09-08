'use client'

import { KeyRound } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { normalizeLiveCode } from '@/lib/ops/live'

/**
 * 코드를 물어보는 화면.
 *
 * 원장님이 보내신 주소에는 코드가 이미 들어 있다. 여기까지 오셨다는 건
 * 주소만 전해 들으셨다는 뜻이라, 손으로 옮겨 적으실 수 있게 칸을 둔다.
 */
export function FollowGate({ eventId, title }: { eventId: string; title: string }) {
  const router = useRouter()
  const [code, setCode] = useState('')
  const valid = normalizeLiveCode(code)

  return (
    <form
      onSubmit={(native) => {
        native.preventDefault()
        if (valid) router.replace(`/e/${eventId}/live?k=${valid}`)
      }}
      style={{ display: 'grid', gap: 12, padding: '32px 0' }}
    >
      <p style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 15 }}>
        <KeyRound size={16} aria-hidden style={{ color: 'var(--d-accent)' }} />
        <strong>{title}</strong> 진행 상황은 코드를 아는 분만 볼 수 있습니다.
      </p>
      <p style={{ fontSize: 13.5, color: 'var(--d-muted)', lineHeight: 1.8 }}>
        원장님께 받으신 주소에는 코드가 이미 들어 있습니다. 주소만 전해 들으셨다면 아래에 코드를 적어 주세요.
      </p>
      <input
        value={code}
        onChange={(native) => setCode(native.target.value)}
        placeholder="코드 6자리"
        aria-label="따라보기 코드"
        autoCapitalize="characters"
        autoComplete="off"
        style={{
          height: 48,
          borderRadius: 10,
          border: '1px solid var(--d-line)',
          background: 'var(--d-paper)',
          color: 'var(--d-ink)',
          padding: '0 14px',
          fontSize: 20,
          letterSpacing: '0.28em',
          textTransform: 'uppercase',
          fontFamily: 'inherit',
        }}
      />
      <Button type="submit" disabled={!valid} className="h-12 text-base">
        진행 상황 보기
      </Button>
    </form>
  )
}
