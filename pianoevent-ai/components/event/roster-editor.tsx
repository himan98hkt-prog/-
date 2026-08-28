'use client'

import { ClipboardPaste, CopyPlus, FileSpreadsheet, History, Plus, Trash2 } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useRef, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PieceInput } from '@/components/event/piece-input'
import { NextHere } from '@/components/flow/next-here'
import { RosterGuide } from '@/components/event/roster-guide'
import { useUndo } from '@/components/undo/undo-bar'
import { FieldHint, Input, Label, Select, Textarea } from '@/components/ui/field'
import { formatDuration } from '@/lib/format'
import { averageTiming, timingHint, type TimingLog } from '@/lib/ops/timing'
import { performerCount, pieceIndex } from '@/lib/program/appearances'
import { CATALOG_SIZE, type CatalogEntry } from '@/lib/program/catalog'
import { describeChange, describeEdit, restorePatch, type RosterEdit } from '@/lib/program/edit-log'
import { buildReceipt } from '@/lib/program/receipt'
import { parseRoster } from '@/lib/program/roster'
import { rosterSampleText } from '@/lib/program/template'
import { BulkPhotoUpload, StudentPhotoCell } from '@/components/event/student-photos'
import type { AcademyAsset } from '@/lib/assets'
import { FACE_SHRINK, shrinkImage } from '@/lib/image'
import { LEVEL_LABEL, type EventStudent, type Level } from '@/lib/types'
import { cn } from '@/lib/utils'

const LEVELS = Object.keys(LEVEL_LABEL) as Level[]

const SAMPLE = rosterSampleText()

/** 값이 그대로인지 — 칸을 눌렀다 그냥 빠져나오신 것도 저장으로 들어온다 */
function sameValue(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((v, i) => v === b[i])
  return (a ?? null) === (b ?? null)
}

export function RosterEditor({
  eventId,
  students,
  pastEvents = [],
  assets = [],
  timings = null,
  hasProgram = false,
}: {
  eventId: string
  students: EventStudent[]
  /** 명단을 그대로 가져올 수 있는 지난 행사들 */
  pastEvents?: { id: string; title: string; count: number }[]
  /** 이미지 보관함 — 아이 사진을 여기서 고른다 */
  assets?: AcademyAsset[]
  /** 아이별로 지난 무대에서 실제로 걸린 시간 */
  timings?: TimingLog | null
  /** 순서표를 이미 만드셨는가 — 만드셨으면 다음 안내를 띄우지 않는다 */
  hasProgram?: boolean
}) {
  const [photoBusy, setPhotoBusy] = useState<string | null>(null)

  /** 이 아이의 사진들을 통째로 정한다 — 맨 앞이 대표 사진이다 */
  function pickPhotos(student: EventStudent, ids: string[]) {
    return patchStudent(student.id, {
      photo_asset_id: ids[0] ?? null,
      photo_asset_ids: ids.length > 1 ? ids : null,
    })
  }

  async function uploadPhoto(student: EventStudent, file: File, append: boolean) {
    setPhotoBusy(student.id)
    try {
      const url = await shrinkImage(file, FACE_SHRINK)
      const created = await fetch('/api/academy/assets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: 'photo', label: `${student.student_name} 사진`, url }),
      })
      const body = await created.json()
      if (!created.ok) throw new Error(body.error ?? '사진을 올리지 못했습니다.')
      // 이미 있는 사진 뒤에 붙일지, 대표 사진으로 앉힐지
      const before = append
        ? [student.photo_asset_id, ...(student.photo_asset_ids ?? [])].filter((id): id is string => !!id)
        : []
      await pickPhotos(student, [...new Set([...before, body.asset.id as string])])
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '사진을 올리지 못했습니다.')
    } finally {
      setPhotoBusy(null)
    }
  }
  const router = useRouter()
  const undo = useUndo()
  const [paste, setPaste] = useState('')
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])

  const preview = paste.trim() ? parseRoster(paste) : null
  const receipt = preview ? buildReceipt(preview) : null
  const [source, setSource] = useState('')
  const [dropping, setDropping] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  /** 방금 읽은 엑셀 파일과 그 안의 장들 — 장이 여럿일 때만 화면에 나온다 */
  const [excel, setExcel] = useState<{ file: File; sheets: string[]; sheet: number } | null>(null)
  const [keepPieces, setKeepPieces] = useState(false)
  // 곡 사전 자동완성 — 곡을 고르면 나머지 칸이 함께 채워진다
  const [draft, setDraft] = useState({ piece: '', composer: '', level: 'beginner', minutes: 0, seconds: 0 })

  function applyCatalog(entry: CatalogEntry) {
    setDraft({
      piece: entry.title,
      composer: entry.composer,
      level: entry.level,
      minutes: Math.floor(entry.duration_sec / 60),
      seconds: entry.duration_sec % 60,
    })
  }

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
      const photoNote = data.with_photo > 0 ? ` 아이 사진 ${data.with_photo}명 분도 그대로 따라왔습니다.` : ''
      const timingNote =
        data.with_timing > 0
          ? ` ${data.with_timing}명은 지난 무대에서 실제로 걸린 시간으로 채웠습니다.`
          : ''
      setMessage(
        (keepPieces
          ? `${data.students.length}명을 곡까지 그대로 가져왔습니다.`
          : `${data.students.length}명을 가져왔습니다. 이제 곡만 채우시면 됩니다.`) +
          photoNote +
          timingNote,
      )
      router.refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '가져오지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  /**
   * 엑셀 파일을 그대로 받아 붙여넣기 칸을 채운다 — 복사·붙여넣기 다섯 걸음이 한 걸음이 된다.
   *
   * 파일을 손에 들고 있어야 장(시트)을 바꿔 다시 읽을 수 있어서 그대로 담아 둔다.
   * 담아 두는 곳은 이 화면 안이고, 어디로도 보내지 않는다.
   */
  async function readFile(file: File, sheet = 0) {
    setPending(true)
    setMessage(null)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('sheet', String(sheet))
      const res = await fetch('/api/roster/xlsx', { method: 'POST', body: form })
      const data = await res.json()
      setExcel({ file, sheets: data.sheets ?? [], sheet: data.sheet ?? sheet })
      if (!res.ok) throw new Error(data.error ?? '엑셀 파일을 읽지 못했습니다.')
      setPaste(data.text)
      const which = (data.sheets?.length ?? 0) > 1 ? ` "${data.sheets[data.sheet]}" 장에서` : ''
      setMessage(`${file.name}${which} ${data.rows}줄을 읽었습니다. 아래에서 확인하시고 넣으세요.`)
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '엑셀 파일을 읽지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  async function importRoster(mode: 'append' | 'replace') {
    if (!paste.trim()) return
    setPending(true)
    setMessage(null)
    // 넣기 **전에** 지금 명단을 담아 둔다. 넣고 나서 담으면 되돌릴 곳이 없다.
    const before = students.map((s) => ({ ...s }))
    try {
      const res = await fetch(`/api/events/${eventId}/students${mode === 'replace' ? '?mode=replace' : ''}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: paste }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '명단을 등록하지 못했습니다.')
      setWarnings(data.warnings ?? [])
      const filled = preview?.autofilled ?? []
      setMessage(
        filled.length > 0
          ? `${data.students.length}명을 등록했습니다. 곡 사전이 ${filled.length}곡의 빈칸을 대신 채웠습니다.`
          : `${data.students.length}명을 등록했습니다.`,
      )
      undo.remember({
        id: 'roster:paste',
        what: mode === 'replace' ? '명단 교체' : '명단 붙여넣기',
        detail: before.length === 0 ? '넣기 전에는 비어 있었습니다' : `${before.length}줄로 돌아갑니다`,
        request: {
          url: `/api/events/${eventId}/students/restore`,
          method: 'POST',
          body: { students: before },
        },
      })
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
      setDraft({ piece: '', composer: '', level: 'beginner', minutes: 0, seconds: 0 })
      router.refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '학생을 추가하지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  /**
   * 표의 칸 하나를 고친다.
   *
   * 고치기 전 값을 화면 위 되돌리기 띠에 담아 둔다. 표에서 엉뚱한 줄을 고치셨을 때
   * 화면에는 아무 표시도 안 나므로, 어디를 고치셨는지조차 잊으신다.
   * `remember: false` 는 되돌리기가 스스로를 다시 담지 않게 하는 것이다.
   */
  async function patchStudent(id: string, patch: Record<string, unknown>, remember = true) {
    const student = students.find((s) => s.id === id)
    if (remember && student) {
      const keys = Object.keys(patch)
      const field = keys.find((k) => !sameValue((student as never)[k], patch[k])) ?? keys[0]
      if (field && !sameValue((student as never)[field], patch[field])) {
        const edit: RosterEdit = {
          student_id: id,
          student_name: student.student_name,
          field,
          before: (student as never)[field] ?? null,
          after: patch[field] ?? null,
          // 두 칸이 함께 바뀌는 곳(사진)은 함께 되돌린다
          restore:
            keys.length > 1 ? Object.fromEntries(keys.map((k) => [k, (student as never)[k] ?? null])) : undefined,
        }
        undo.remember({
          // 같은 칸을 이어서 고치시면 한 줄로 합쳐진다 — 목록이 같은 말로 차지 않게
          id: `roster:edit:${id}:${field}`,
          what: describeEdit(edit),
          detail: describeChange(edit),
          // 요청으로 적어 두면 인쇄물 화면에 갔다 오셔도 되돌릴 수 있다
          request: { url: `/api/students/${edit.student_id}`, method: 'PATCH', body: restorePatch(edit) },
        })
      }
    }
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

  /**
   * 이 아이에게 곡을 하나 더 준다.
   *
   * 독주도 하고 듀엣도 하는 아이는 흔하다. 순서표에서는 두 줄이 맞다 —
   * 무대에 두 번 오르니까. 그런데 이름과 사진을 다시 치게 하는 건 말이 안 된다.
   * 이름·난이도·사진을 그대로 물려주고 곡만 비워 둔다.
   */
  async function addPiece(student: EventStudent) {
    setPending(true)
    setMessage(null)
    try {
      const res = await fetch(`/api/events/${eventId}/students`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          students: [
            {
              student_name: student.student_name,
              piece_title: '',
              composer: '',
              duration_sec: 0,
              level: student.level,
              note: student.note,
            },
          ],
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '곡을 추가하지 못했습니다.')
      // 사진은 보관함에 있는 것만 붙일 수 있으므로 검사를 거치는 쪽으로 따로 보낸다
      const created = data.students?.[data.students.length - 1]
      if (created && student.photo_asset_id) {
        await fetch(`/api/students/${created.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ photo_asset_id: student.photo_asset_id }),
        })
      }
      setMessage(`${student.student_name} 학생의 곡을 한 줄 더 넣었습니다. 곡명만 채우시면 됩니다.`)
      router.refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '곡을 추가하지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="grid gap-5">
      {/* 명단이 들어오면 곧바로 다음 것을 여기서 끝내 드린다 — 화면을 옮기는 것 자체가 부담이다 */}
      {students.length > 0 && !hasProgram && (
        <NextHere
          step="program"
          eventId={eventId}
          label="여기서 순서표 만들기"
          hint={`${students.length}줄이 들어왔습니다. 연주 순서와 사회자 멘트를 지금 한 번에 만들어 드릴까요? 몇 초면 됩니다.`}
          run={async () => {
            const res = await fetch(`/api/events/${eventId}/program`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({}),
            })
            if (!res.ok) throw new Error((await res.json()).error ?? '순서표를 만들지 못했습니다.')
          }}
        />
      )}

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
              채우시면 됩니다. <strong>아이 사진은 늘 따라옵니다</strong> — 보관함은 학원 것이고 아이도 그
              아이니까요.
            </FieldHint>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ClipboardPaste className="h-4 w-4 text-accent" aria-hidden />
            학생 명단 넣기
          </CardTitle>
          <CardDescription>
            엑셀 파일을 <strong className="text-foreground">그대로 끌어다 놓으시면</strong> 됩니다. 복사해
            붙여넣으셔도 되고, 머리글이 있어도 없어도 알아서 읽습니다.
            <strong className="text-foreground">
              {' '}
              작곡가나 연주시간을 비워 두시면 곡 사전 {CATALOG_SIZE}곡에서 알아서 채웁니다.
            </strong>{' '}
            악보는 학원에서 쓰시던 것을 그대로 쓰십니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          <RosterGuide />

          {/* 엑셀 파일을 그대로 끌어다 놓기 — 복사·붙여넣기를 못 하시는 분이 훨씬 많다 */}
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setDropping(true)
            }}
            onDragLeave={() => setDropping(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDropping(false)
              const file = e.dataTransfer.files?.[0]
              if (file) readFile(file)
            }}
            className={cn(
              'grid gap-2 rounded-lg border-2 border-dashed p-4 text-center transition-colors',
              dropping ? 'border-accent bg-accent/10' : 'border-border bg-muted/30',
            )}
            data-testid="roster-drop"
          >
            <p className="flex items-center justify-center gap-2 text-sm font-medium">
              <FileSpreadsheet className="h-4 w-4 text-accent" aria-hidden />
              엑셀 파일을 여기로 끌어다 놓으세요
            </p>
            <p className="text-xs text-muted-foreground">
              복사·붙여넣기를 하지 않으셔도 됩니다. <strong>.xlsx</strong> 파일을 그대로 놓으시면 아래 칸이 저절로
              채워집니다. 파일은 읽고 나서 버립니다 — 이 컴퓨터 밖으로 나가지 않습니다.
            </p>
            <div>
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) readFile(file)
                  e.target.value = ''
                }}
                aria-label="엑셀 파일 고르기"
              />
              <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={pending}>
                파일 고르기
              </Button>
            </div>

            {/* 학년별로 장을 나눠 두신 원장님이 계신다. 장이 하나면 이 칸은 뜨지 않는다 */}
            {excel && excel.sheets.length > 1 && (
              <div className="mt-1 grid gap-1.5" data-testid="sheet-picker">
                <p className="text-xs text-muted-foreground">
                  이 파일에는 장이 <strong>{excel.sheets.length}개</strong> 있습니다. 지금은{' '}
                  <strong>{excel.sheets[excel.sheet]}</strong> 을(를) 읽었습니다.
                </p>
                <div className="flex flex-wrap justify-center gap-1.5">
                  {excel.sheets.map((name, index) => (
                    <Button
                      key={`${name}-${index}`}
                      variant={index === excel.sheet ? 'default' : 'outline'}
                      size="sm"
                      aria-pressed={index === excel.sheet}
                      disabled={pending}
                      onClick={() => readFile(excel.file, index)}
                    >
                      {name}
                    </Button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <p className="text-sm font-medium">여기에 붙여넣으세요</p>
          <Textarea
            value={paste}
            onChange={(e) => setPaste(e.target.value)}
            placeholder={SAMPLE}
            className="min-h-[140px] font-mono text-xs"
            aria-label="학생 명단 붙여넣기"
          />

          {receipt && (
            <div
              className={cn(
                'rounded-md border p-3 text-sm',
                receipt.needsLook ? 'border-destructive/40 bg-destructive/5' : 'border-border bg-muted/40',
              )}
              data-testid="roster-receipt"
            >
              <p className="font-medium">이렇게 읽었습니다 — 맞으면 아래 단추를 누르세요</p>
              <ul className="mt-2 grid gap-1">
                {receipt.lines.map((line) => (
                  <li
                    key={line.text}
                    className={cn('text-xs', line.tone === 'warn' ? 'text-destructive' : 'text-muted-foreground')}
                  >
                    {line.tone === 'warn' ? '⚠ ' : '· '}
                    {line.text}
                  </li>
                ))}
              </ul>
              {!receipt.needsLook && (
                <p className="mt-2 text-xs text-muted-foreground">
                  살펴보실 것은 없습니다. 넣으신 뒤에도 표에서 언제든 고치실 수 있고,{' '}
                  <strong>[되돌리기]</strong> 로 통째로 되돌릴 수 있습니다.
                </p>
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
          <CardTitle>
            연주자 {performerCount(students)}명
            {performerCount(students) !== students.length && (
              <span className="ml-1.5 text-sm font-normal text-muted-foreground">· {students.length}곡</span>
            )}
          </CardTitle>
          <CardDescription>
            칸을 눌러 바로 고칠 수 있습니다. 소요시간을 비우면 난이도로 추정합니다.
            <br />
            <strong>아이 사진</strong>을 넣으면 무대 화면과 감동영상에 그 얼굴이 함께 올라갑니다. 사진 칸을 눌러{' '}
            <strong>여러 장</strong>을 고르시면 감동영상에서 넘겨 가며 나옵니다.
            <br />한 아이가 <strong>독주와 듀엣</strong>을 함께 맡으면 오른쪽 <strong>곡 추가</strong>를 누르세요 —
            이름과 사진은 그대로 두고 곡만 한 줄 더 생깁니다.
          </CardDescription>
        </CardHeader>
        {students.length > 0 && (
          <div className="px-5 pb-3">
            <BulkPhotoUpload
              students={students}
              onDone={(matched, skipped) => {
                setMessage(
                  skipped.length === 0
                    ? `사진 ${matched}장을 아이들과 짝지었습니다.`
                    : `사진 ${matched}장을 짝지었습니다. 짝짓지 못한 파일 ${skipped.length}개는 건너뛰었습니다 — ${skipped.slice(0, 3).join(', ')}`,
                )
                router.refresh()
              }}
            />
          </div>
        )}
        <CardContent className="p-0">
          {students.length === 0 ? (
            <p className="px-5 py-10 text-center text-sm text-muted-foreground">
              아직 등록된 학생이 없습니다. 위에 명단을 붙여넣어 주세요.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm" data-testid="roster-table">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="px-4 py-2 font-medium">사진</th>
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
                        <StudentPhotoCell
                          student={s}
                          assets={assets}
                          busy={photoBusy === s.id}
                          onPick={(ids) => pickPhotos(s, ids)}
                          onUpload={(file, append) => void uploadPhoto(s, file, append)}
                        />
                      </td>
                      <td className="px-2 py-1.5">
                        <Input
                          key={`${s.id}-student_name-${s.student_name ?? ''}`}
                          defaultValue={s.student_name}
                          onBlur={(e) =>
                            e.target.value.trim() !== s.student_name &&
                            patchStudent(s.id, { student_name: e.target.value })
                          }
                          className="h-9 border-transparent bg-transparent hover:border-input"
                          aria-label="이름"
                        />
                        {(() => {
                          // 같은 아이의 두 번째·세 번째 곡임을 표시한다 — 이름이 두 번 보이는 이유가 보이게
                          const many = pieceIndex(students, s)
                          return many ? (
                            <Badge variant="outline" className="ml-1 mt-1 text-[11px]">
                              {many.total}곡 중 {many.index}번째
                            </Badge>
                          ) : null
                        })()}
                      </td>
                      <td className="px-2 py-1.5">
                        <Input
                          key={`${s.id}-piece_title-${s.piece_title ?? ''}`}
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
                          key={`${s.id}-composer-${s.composer ?? ''}`}
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
                          key={`${s.id}-level-${s.level ?? ''}`}
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
                          key={`${s.id}-duration_sec-${s.duration_sec ?? ''}`}
                          defaultValue={s.duration_sec}
                          onBlur={(e) =>
                            Number(e.target.value) !== s.duration_sec &&
                            patchStudent(s.id, { duration_sec: Number(e.target.value) })
                          }
                          className="h-9 w-24 border-transparent bg-transparent hover:border-input"
                          aria-label="소요시간(초)"
                        />
                        <span className="ml-1 text-xs text-muted-foreground">{formatDuration(s.duration_sec)}</span>
                        {(() => {
                          // 이 아이가 지난 무대에서 실제로 걸린 시간 — 책의 평균보다 이쪽이 낫다.
                          // 지금 값과 같으면 굳이 보여 주지 않는다
                          const known = averageTiming(timings, s.student_name, s.level)
                          const hint = timingHint(timings, s.student_name, s.level)
                          if (known === null || !hint || Math.abs(known - s.duration_sec) <= 5) return null
                          return (
                            <button
                              type="button"
                              onClick={() => patchStudent(s.id, { duration_sec: known })}
                              className="mt-0.5 block text-left text-[11px] text-accent underline underline-offset-2"
                              title="당일 진행 화면에서 쌓인 실제 시간입니다. 누르면 이 값으로 바꿉니다"
                            >
                              {hint} · 이 값으로
                            </button>
                          )
                        })()}
                      </td>
                      <td className="px-2 py-1.5">
                        <Input
                          key={`${s.id}-note-${s.note ?? ''}`}
                          defaultValue={s.note ?? ''}
                          onBlur={(e) => e.target.value.trim() !== (s.note ?? '') && patchStudent(s.id, { note: e.target.value })}
                          className="h-9 border-transparent bg-transparent hover:border-input"
                          placeholder="사회자 멘트에 쓰일 한 줄"
                          aria-label="특징 메모"
                        />
                      </td>
                      <td className="whitespace-nowrap px-2 py-1.5 text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => void addPiece(s)}
                          disabled={pending}
                          title="이 아이에게 곡을 하나 더"
                          aria-label={`${s.student_name} 곡 추가`}
                        >
                          <CopyPlus className="h-4 w-4 text-accent" aria-hidden />
                        </Button>
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
              <PieceInput
                id="piece_title"
                name="piece_title"
                value={draft.piece}
                onChange={(piece) => setDraft((d) => ({ ...d, piece }))}
                onPick={applyCatalog}
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="composer">작곡가</Label>
              <Input
                id="composer"
                name="composer"
                maxLength={80}
                value={draft.composer}
                onChange={(e) => setDraft((d) => ({ ...d, composer: e.target.value }))}
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="level">난이도</Label>
              <Select
                id="level"
                name="level"
                value={draft.level}
                onChange={(e) => setDraft((d) => ({ ...d, level: e.target.value }))}
              >
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
                <Input
                  id="minutes"
                  name="minutes"
                  type="number"
                  min={0}
                  max={30}
                  value={draft.minutes}
                  onChange={(e) => setDraft((d) => ({ ...d, minutes: Number(e.target.value) || 0 }))}
                  className="w-16"
                />
                <span className="text-sm text-muted-foreground">분</span>
                <Input
                  name="seconds"
                  type="number"
                  min={0}
                  max={59}
                  value={draft.seconds}
                  onChange={(e) => setDraft((d) => ({ ...d, seconds: Number(e.target.value) || 0 }))}
                  className="w-16"
                />
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
