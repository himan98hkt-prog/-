'use client'

import { ClipboardPaste, History, Plus, Trash2 } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldHint, Input, Label, Select, Textarea } from '@/components/ui/field'
import { formatDuration } from '@/lib/format'
import { parseRoster } from '@/lib/program/roster'
import { LEVEL_LABEL, type EventStudent, type Level } from '@/lib/types'

const LEVELS = Object.keys(LEVEL_LABEL) as Level[]

const SAMPLE = `이름\t연주곡\t작곡가\t소요시간\t난이도\t비고
김서연\t엘리제를 위하여\t베토벤\t3:30\t중급\t세 번째 무대입니다
박지호\t즐거운 나의 집\t비숍\t1:10\t초급\t시작한 지 다섯 달`

export function RosterEditor({
  eventId,
  students,
  pastEvents = [],
}: {
  eventId: string
  students: EventStudent[]
  /** 명단을 그대로 가져올 수 있는 지난 행사들 */
  pastEvents?: { id: string; title: string; count: number }[]
}) {
  const router = useRouter()
  const [paste, setPaste] = useState('')
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])

  const preview = paste.trim() ? parseRoster(paste) : null
  const [source, setSource] = useState('')
  const [keepPieces, setKeepPieces] = useState(false)

  /** 지난 행사에서 명단을 그대로 가져온다 — 학원은 학생이 그대로다 */
  async function importFromEvent() {
    if (!source) return
    const found = pastEvents.find((e) => e.id === source)
    if (
      students.length > 0 &&
      !window.confirm(`지금 명단 ${students.length}명을 지우고 "${found?.title}" 의 명단으로 바꿉니다. 계속할까요?`)
    ) {
      return
    }
    setPending(true)
    setMessage(null)
    try {
      const res = await fetch(`/api/events/${eventId}/students/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from_event_id: source, keep_pieces: keepPieces }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '가져오지 못했습니다.')
      setMessage(
        keepPieces
          ? `${data.students.length}명을 곡까지 그대로 가져왔습니다.`
          : `${data.students.length}명을 가져왔습니다. 이제 곡만 채우시면 됩니다.`,
      )
      router.refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '가져오지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  async function importRoster(mode: 'append' | 'replace') {
    if (!paste.trim()) return
    setPending(true)
    setMessage(null)
    try {
      const res = await fetch(`/api/events/${eventId}/students${mode === 'replace' ? '?mode=replace' : ''}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: paste }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '명단을 등록하지 못했습니다.')
      setWarnings(data.warnings ?? [])
      setMessage(`${data.students.length}명을 등록했습니다.`)
      setPaste('')
      router.refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '명단을 등록하지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  async function addOne(formData: FormData) {
    setPending(true)
    setMessage(null)
    try {
      const res = await fetch(`/api/events/${eventId}/students`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          students: [
            {
              student_name: formData.get('student_name'),
              piece_title: formData.get('piece_title'),
              composer: formData.get('composer'),
              duration_sec: Number(formData.get('minutes') ?? 0) * 60 + Number(formData.get('seconds') ?? 0),
              level: formData.get('level'),
              note: formData.get('note'),
            },
          ],
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '학생을 추가하지 못했습니다.')
      router.refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '학생을 추가하지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  async function patchStudent(id: string, patch: Record<string, unknown>) {
    await fetch(`/api/students/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    router.refresh()
  }

  async function removeStudent(id: string) {
    await fetch(`/api/students/${id}`, { method: 'DELETE' })
    router.refresh()
  }

  return (
    <div className="grid gap-5">
      {pastEvents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <History className="h-4 w-4 text-accent" aria-hidden />
              지난 행사에서 명단 가져오기
            </CardTitle>
            <CardDescription>
              학원 학생은 그대로입니다. 매번 다시 치지 마시고 지난 행사에서 이름을 그대로 가져온 다음, 곡만
              바꾸세요.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[220px] flex-1">
                <Label htmlFor="import-source">어느 행사에서</Label>
                <Select id="import-source" value={source} onChange={(e) => setSource(e.target.value)}>
                  <option value="">행사를 고르세요</option>
                  {pastEvents.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.title} · {e.count}명
                    </option>
                  ))}
                </Select>
              </div>
              <Button type="button" onClick={importFromEvent} disabled={pending || !source}>
                가져오기
              </Button>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={keepPieces}
                onChange={(e) => setKeepPieces(e.target.checked)}
                className="h-4 w-4"
              />
              연주곡까지 그대로 가져오기
              <span className="text-xs text-muted-foreground">(같은 곡으로 다시 하는 경우)</span>
            </label>
            <FieldHint>
              체크하지 않으면 <strong>이름과 난이도만</strong> 가져오고 곡은 비워 둡니다. 아래 표에서 곡만
              채우시면 됩니다.
            </FieldHint>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ClipboardPaste className="h-4 w-4 text-accent" aria-hidden />
            엑셀에서 붙여넣기
          </CardTitle>
          <CardDescription>
            엑셀·구글시트에서 표를 복사해 그대로 붙여넣으세요. 헤더(이름·연주곡·작곡가·시간·난이도·비고)를 자동으로
            인식합니다. 곡은 원장님이 정하신 것을 그대로 적으시면 됩니다 — 악보는 학원에서 쓰시던 것을 씁니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          <Textarea
            value={paste}
            onChange={(e) => setPaste(e.target.value)}
            placeholder={SAMPLE}
            className="min-h-[140px] font-mono text-xs"
            aria-label="학생 명단 붙여넣기"
          />

          {preview && (
            <div className="rounded-md border border-border bg-muted/40 p-3 text-sm">
              <p className="font-medium">
                {preview.rows.length}명 인식됨
                {preview.headerDetected ? ' · 헤더 자동 인식' : ' · 열 순서로 읽음 (이름·곡·작곡가·시간·난이도·비고)'}
              </p>
              {preview.errors.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-xs text-destructive">
                  {preview.errors.slice(0, 5).map((err) => (
                    <li key={err}>{err}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => importRoster('append')} disabled={pending || !paste.trim()}>
              명단에 추가
            </Button>
            <Button variant="outline" onClick={() => importRoster('replace')} disabled={pending || !paste.trim()}>
              기존 명단 교체
            </Button>
            <Button variant="ghost" onClick={() => setPaste(SAMPLE)} disabled={pending}>
              예시 채우기
            </Button>
          </div>

          {message && <p className="text-sm text-muted-foreground">{message}</p>}
          {warnings.length > 0 && (
            <ul className="list-disc pl-5 text-xs text-destructive">
              {warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>연주자 {students.length}명</CardTitle>
          <CardDescription>칸을 눌러 바로 고칠 수 있습니다. 소요시간을 비우면 난이도로 추정합니다.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {students.length === 0 ? (
            <p className="px-5 py-10 text-center text-sm text-muted-foreground">
              아직 등록된 학생이 없습니다. 위에 명단을 붙여넣어 주세요.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="px-4 py-2 font-medium">이름</th>
                    <th className="px-4 py-2 font-medium">연주곡</th>
                    <th className="px-4 py-2 font-medium">작곡가</th>
                    <th className="px-4 py-2 font-medium">난이도</th>
                    <th className="px-4 py-2 font-medium">소요시간</th>
                    <th className="px-4 py-2 font-medium">특징 메모</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {students.map((s) => (
                    <tr key={s.id} className="border-b border-border/60 last:border-0">
                      <td className="px-2 py-1.5">
                        <Input
                          defaultValue={s.student_name}
                          onBlur={(e) =>
                            e.target.value.trim() !== s.student_name &&
                            patchStudent(s.id, { student_name: e.target.value })
                          }
                          className="h-9 border-transparent bg-transparent hover:border-input"
                          aria-label="이름"
                        />
                      </td>
                      <td className="px-2 py-1.5">
                        <Input
                          defaultValue={s.piece_title}
                          onBlur={(e) =>
                            e.target.value.trim() !== s.piece_title && patchStudent(s.id, { piece_title: e.target.value })
                          }
                          className="h-9 border-transparent bg-transparent hover:border-input"
                          aria-label="연주곡"
                        />
                      </td>
                      <td className="px-2 py-1.5">
                        <Input
                          defaultValue={s.composer}
                          onBlur={(e) =>
                            e.target.value.trim() !== s.composer && patchStudent(s.id, { composer: e.target.value })
                          }
                          className="h-9 w-28 border-transparent bg-transparent hover:border-input"
                          aria-label="작곡가"
                        />
                      </td>
                      <td className="px-2 py-1.5">
                        <Select
                          defaultValue={s.level}
                          onChange={(e) => patchStudent(s.id, { level: e.target.value })}
                          className="h-9 w-28 border-transparent bg-transparent hover:border-input"
                          aria-label="난이도"
                        >
                          {LEVELS.map((level) => (
                            <option key={level} value={level}>
                              {LEVEL_LABEL[level]}
                            </option>
                          ))}
                        </Select>
                      </td>
                      <td className="whitespace-nowrap px-2 py-1.5">
                        <Input
                          type="number"
                          min={10}
                          max={1800}
                          step={5}
                          defaultValue={s.duration_sec}
                          onBlur={(e) =>
                            Number(e.target.value) !== s.duration_sec &&
                            patchStudent(s.id, { duration_sec: Number(e.target.value) })
                          }
                          className="h-9 w-24 border-transparent bg-transparent hover:border-input"
                          aria-label="소요시간(초)"
                        />
                        <span className="ml-1 text-xs text-muted-foreground">{formatDuration(s.duration_sec)}</span>
                      </td>
                      <td className="px-2 py-1.5">
                        <Input
                          defaultValue={s.note ?? ''}
                          onBlur={(e) => e.target.value.trim() !== (s.note ?? '') && patchStudent(s.id, { note: e.target.value })}
                          className="h-9 border-transparent bg-transparent hover:border-input"
                          placeholder="사회자 멘트에 쓰일 한 줄"
                          aria-label="특징 메모"
                        />
                      </td>
                      <td className="px-2 py-1.5 text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeStudent(s.id)}
                          aria-label={`${s.student_name} 삭제`}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" aria-hidden />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="h-4 w-4 text-accent" aria-hidden />한 명 직접 추가
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form action={addOne} className="grid gap-3 sm:grid-cols-6">
            <div className="sm:col-span-2">
              <Label htmlFor="student_name">이름</Label>
              <Input id="student_name" name="student_name" required maxLength={40} />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="piece_title">연주곡</Label>
              <Input id="piece_title" name="piece_title" maxLength={120} />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="composer">작곡가</Label>
              <Input id="composer" name="composer" maxLength={80} />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="level">난이도</Label>
              <Select id="level" name="level" defaultValue="beginner">
                {LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {LEVEL_LABEL[level]}
                  </option>
                ))}
              </Select>
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="minutes">소요시간</Label>
              <div className="flex items-center gap-1">
                <Input id="minutes" name="minutes" type="number" min={0} max={30} defaultValue={0} className="w-16" />
                <span className="text-sm text-muted-foreground">분</span>
                <Input name="seconds" type="number" min={0} max={59} defaultValue={0} className="w-16" />
                <span className="text-sm text-muted-foreground">초</span>
              </div>
              <FieldHint>0 이면 난이도로 추정합니다.</FieldHint>
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="note">특징 메모</Label>
              <Input id="note" name="note" maxLength={200} placeholder="올해 처음 무대에 섭니다" />
            </div>
            <div className="sm:col-span-6">
              <Button type="submit" variant="outline" disabled={pending}>
                추가
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
