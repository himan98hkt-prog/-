'use client'

import { AlertTriangle } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldHint, Input, Label } from '@/components/ui/field'

/**
 * Google Play 계정 삭제 요건 대응 UI.
 * 학원·행사·학생·참석 회신을 모두 삭제하고 세션 쿠키까지 폐기한다.
 */
export function DeleteAccount() {
  const router = useRouter()
  const [confirm, setConfirm] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  async function remove() {
    setPending(true)
    setError(null)
    try {
      const res = await fetch('/api/account/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '삭제하지 못했습니다.')
      setDone(true)
      setTimeout(() => {
        router.push('/')
        router.refresh()
      }, 1500)
    } catch (e) {
      setError(e instanceof Error ? e.message : '삭제하지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  return (
    <Card className="border-destructive/30">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="h-4 w-4" aria-hidden />
          계정 및 모든 데이터 삭제
        </CardTitle>
        <CardDescription>
          학원 정보, 모든 행사, 학생 명단, 사회자 대본, 학부모 참석 회신이 즉시 영구 삭제됩니다. 되돌릴 수 없습니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {done ? (
          <p className="text-sm text-muted-foreground">삭제가 완료되었습니다. 첫 화면으로 이동합니다.</p>
        ) : (
          <>
            <div>
              <Label htmlFor="confirm">확인을 위해 &ldquo;삭제&rdquo; 라고 입력하세요</Label>
              <Input
                id="confirm"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="삭제"
                className="max-w-xs"
              />
              <FieldHint>삭제 요청은 즉시 처리되며 백업본도 남기지 않습니다.</FieldHint>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div>
              <Button variant="destructive" onClick={remove} disabled={pending || confirm !== '삭제'}>
                {pending ? '삭제 중…' : '영구 삭제'}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
