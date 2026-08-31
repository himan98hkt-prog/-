'use client'

import { useState } from 'react'

/**
 * 학부모 참석 회신 폼.
 * 초대장 테마(--d-*)를 그대로 입어 종이 초대장과 같은 인상을 준다.
 */

const field: React.CSSProperties = {
  width: '100%',
  height: 46,
  padding: '0 14px',
  borderRadius: 10,
  border: '1px solid var(--d-line)',
  background: 'var(--d-paper)',
  color: 'var(--d-ink)',
  fontSize: 15,
  fontFamily: 'inherit',
}

const label: React.CSSProperties = {
  display: 'block',
  marginBottom: 7,
  fontSize: 13,
  color: 'var(--d-muted)',
  letterSpacing: '0.02em',
}

function choiceStyle(active: boolean): React.CSSProperties {
  return {
    flex: 1,
    height: 48,
    borderRadius: 10,
    border: `1px solid ${active ? 'var(--d-accent)' : 'var(--d-line)'}`,
    background: active ? 'var(--d-accent)' : 'transparent',
    color: active ? 'var(--d-band-ink)' : 'var(--d-ink)',
    fontSize: 15,
    fontWeight: active ? 700 : 400,
    fontFamily: 'inherit',
    cursor: 'pointer',
  }
}

export function RsvpForm({ eventId }: { eventId: string }) {
  const [attending, setAttending] = useState(true)
  const [pending, setPending] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(formData: FormData) {
    setPending(true)
    setError(null)
    try {
      const res = await fetch('/api/rsvp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_id: eventId,
          parent_name: formData.get('parent_name'),
          student_name: formData.get('student_name'),
          attending,
          headcount: Number(formData.get('headcount') ?? 1),
          message: formData.get('message'),
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '회신을 보내지 못했습니다.')
      setDone(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : '회신을 보내지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  if (done) {
    return (
      <div
        style={{
          padding: '26px 20px',
          borderRadius: 12,
          border: '1px solid var(--d-accent)',
          background: 'var(--d-accent-soft)',
          textAlign: 'center',
        }}
      >
        <p style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--d-display)' }}>회신이 전달되었습니다.</p>
        <p style={{ marginTop: 8, fontSize: 14, color: 'var(--d-muted)', lineHeight: 1.7 }}>
          {attending
            ? '공연장에서 뵙겠습니다. 아이의 무대를 함께 응원해 주세요.'
            : '알려 주셔서 감사합니다. 다음 무대에서 뵙겠습니다.'}
        </p>
        <button
          type="button"
          onClick={() => setDone(false)}
          style={{
            marginTop: 16,
            background: 'none',
            border: 'none',
            color: 'var(--d-muted)',
            fontSize: 13,
            textDecoration: 'underline',
            textUnderlineOffset: 4,
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          다시 입력하기
        </button>
      </div>
    )
  }

  return (
    <form action={submit} style={{ display: 'grid', gap: 18 }}>
      <div style={{ display: 'grid', gap: 14, gridTemplateColumns: '1fr 1fr' }}>
        <div>
          <label htmlFor="student_name" style={label}>
            학생 이름
          </label>
          <input id="student_name" name="student_name" required maxLength={40} placeholder="김서연" style={field} />
        </div>
        <div>
          <label htmlFor="parent_name" style={label}>
            보호자 성함
          </label>
          <input id="parent_name" name="parent_name" required maxLength={40} placeholder="김○○" style={field} />
        </div>
      </div>

      <div>
        <span style={label}>참석 여부</span>
        <div style={{ display: 'flex', gap: 10 }}>
          <button type="button" onClick={() => setAttending(true)} aria-pressed={attending} style={choiceStyle(attending)}>
            참석합니다
          </button>
          <button
            type="button"
            onClick={() => setAttending(false)}
            aria-pressed={!attending}
            style={choiceStyle(!attending)}
          >
            어렵습니다
          </button>
        </div>
      </div>

      {attending && (
        <div>
          <label htmlFor="headcount" style={label}>
            참석 인원 (학생 포함)
          </label>
          <select id="headcount" name="headcount" defaultValue="2" style={field}>
            {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                {n}명
              </option>
            ))}
          </select>
        </div>
      )}

      <div>
        <label htmlFor="message" style={label}>
          아이에게 남기는 응원 메시지 (선택)
        </label>
        <textarea
          id="message"
          name="message"
          maxLength={300}
          placeholder="연습한 만큼만 하고 오면 돼. 우리 딸 최고!"
          style={{ ...field, height: 92, padding: '12px 14px', lineHeight: 1.6, resize: 'vertical' }}
        />
      </div>

      {error && <p style={{ fontSize: 13.5, color: '#c0392b' }}>{error}</p>}

      <button
        type="submit"
        disabled={pending}
        style={{
          height: 52,
          borderRadius: 10,
          border: 'none',
          background: 'var(--d-band)',
          color: 'var(--d-band-ink)',
          fontSize: 16,
          fontWeight: 700,
          fontFamily: 'inherit',
          cursor: pending ? 'default' : 'pointer',
          opacity: pending ? 0.6 : 1,
        }}
      >
        {pending ? '보내는 중…' : '참석 여부 보내기'}
      </button>

      <p style={{ textAlign: 'center', fontSize: 11.5, color: 'var(--d-muted)', lineHeight: 1.7 }}>
        입력하신 정보는 이 행사의 참석 집계 목적으로만 쓰이며, 행사 종료 후 학원 정책에 따라 삭제됩니다.
      </p>
    </form>
  )
}
