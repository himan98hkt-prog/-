'use client'

import { ImagePlus, Loader2, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { STUDENT_PHOTO_MAX, type AcademyAsset } from '@/lib/assets'
import { matchPhotoFiles } from '@/lib/ops/photo-match'
import { FACE_SHRINK, shrinkImage } from '@/lib/image'
import type { EventStudent } from '@/lib/types'
import { cn } from '@/lib/utils'

/**
 * 아이 사진 넣기.
 *
 * 연주회 화면에 아이 얼굴이 뜨면 객석이 조용해진다. 그런데 30명 사진을 한 장씩
 * 고르는 일은 명단을 다시 치는 것만큼 지겹다. 그래서 두 길을 둔다.
 *   · 한꺼번에 올리기 — 파일 이름이 아이 이름이면 알아서 짝지어 준다
 *   · 칸을 눌러 한 장씩 — 이미 보관함에 있는 사진은 고르기만 한다
 */
export function StudentPhotoCell({
  student,
  assets,
  onPick,
  onUpload,
  busy,
}: {
  student: EventStudent
  assets: AcademyAsset[]
  /** 고른 사진들 — 맨 앞이 대표 사진(무대 화면·파워포인트에 쓰인다) */
  onPick: (assetIds: string[]) => void
  /** append 면 이미 있는 사진 뒤에 붙인다 */
  onUpload: (file: File, append: boolean) => void
  busy: boolean
}) {
  const [open, setOpen] = useState(false)
  const appendRef = useRef(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const byId = new Map(assets.map((asset) => [asset.id, asset]))
  /** 이 아이의 사진들 — 대표 사진이 늘 맨 앞 */
  const picked = [student.photo_asset_id, ...(student.photo_asset_ids ?? [])].filter(
    (id, at, all): id is string => !!id && byId.has(id) && all.indexOf(id) === at,
  )
  const current = picked[0] ? byId.get(picked[0]) ?? null : null
  const photos = assets.filter((asset) => asset.kind === 'photo')
  const full = picked.length >= STUDENT_PHOTO_MAX

  /** 누르면 넣고, 이미 있으면 뺀다. 맨 앞은 대표 사진이므로 차례가 곧 뜻이다 */
  function toggle(assetId: string) {
    if (picked.includes(assetId)) {
      onPick(picked.filter((id) => id !== assetId))
      return
    }
    if (full) return
    onPick([...picked, assetId])
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          if (current) {
            setOpen((prev) => !prev)
          } else {
            appendRef.current = false
            fileRef.current?.click()
          }
        }}
        className={cn(
          'relative flex h-11 w-11 items-center justify-center overflow-hidden rounded-full border transition-colors',
          current ? 'border-accent' : 'border-dashed border-input hover:bg-secondary',
        )}
        aria-label={current ? `${student.student_name} 사진 바꾸기` : `${student.student_name} 사진 넣기`}
      >
        {busy ? (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-hidden />
        ) : current ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={current.url} alt="" className="h-full w-full object-cover" />
        ) : (
          <ImagePlus className="h-4 w-4 text-muted-foreground" aria-hidden />
        )}
      </button>
      {picked.length > 1 && (
        <span
          className="pointer-events-none absolute -right-1 -top-1 rounded-full bg-accent px-1.5 text-xs font-medium tabular-nums text-accent-foreground"
          aria-hidden
        >
          {picked.length}
        </span>
      )}

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) onUpload(file, appendRef.current)
          event.target.value = ''
        }}
      />

      {open && (
        <div className="absolute left-0 top-12 z-20 w-64 rounded-md border border-border bg-background p-2 shadow-lg">
          <div className="mb-1 flex items-center justify-between">
            <p className="text-xs font-medium">
              {student.student_name} 사진 {picked.length > 0 ? `${picked.length}장` : ''}
            </p>
            <button type="button" onClick={() => setOpen(false)} aria-label="닫기" className="text-muted-foreground">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <p className="mb-2 text-xs leading-snug text-muted-foreground">
            여러 장 고르시면 <strong>감동영상</strong>에서 넘겨 가며 나옵니다. 맨 앞 <strong>①</strong> 이 대표
            사진이라 무대 화면과 파워포인트에 들어갑니다.
          </p>
          <div className="grid max-h-44 grid-cols-4 gap-1.5 overflow-y-auto">
            {photos.map((asset) => {
              const at = picked.indexOf(asset.id)
              return (
                <button
                  key={asset.id}
                  type="button"
                  onClick={() => toggle(asset.id)}
                  aria-pressed={at >= 0}
                  disabled={at < 0 && full}
                  title={at >= 0 ? `${asset.label} — 누르면 뺍니다` : asset.label}
                  className={cn(
                    'relative aspect-square overflow-hidden rounded border disabled:opacity-40',
                    at >= 0 ? 'border-accent ring-1 ring-accent' : 'border-border',
                  )}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={asset.url} alt={asset.label} className="h-full w-full object-cover" />
                  {at >= 0 && (
                    <span className="absolute left-0 top-0 rounded-br bg-accent px-1 text-xs font-medium tabular-nums text-accent-foreground">
                      {at + 1}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
          {full && (
            <p className="mt-1 text-xs text-muted-foreground">
              한 아이당 {STUDENT_PHOTO_MAX}장까지입니다. 빼시려면 고른 사진을 다시 누르세요.
            </p>
          )}
          <div className="mt-2 flex gap-1.5">
            <Button
              variant="outline"
              size="sm"
              className="flex-1"
              disabled={full}
              onClick={() => {
                appendRef.current = picked.length > 0
                fileRef.current?.click()
              }}
            >
              새 사진 올리기
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                onPick([])
                setOpen(false)
              }}
            >
              모두 빼기
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * 사진 한꺼번에 올리기.
 *
 * 파일 이름에서 아이 이름을 찾아 짝지어 준다 — `김서연.jpg`, `2026 윤채원 연습.jpg` 둘 다 걸린다.
 * 한 아이에 여러 장이면 이름 뒤 번호대로 넣는다 — `김서연-1.jpg` `김서연-2.jpg`.
 */
export function BulkPhotoUpload({
  students,
  onDone,
}: {
  students: EventStudent[]
  onDone: (matched: number, skipped: string[]) => void
}) {
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  async function handle(files: FileList) {
    setBusy(true)
    const list = Array.from(files)
    const { matched, skipped } = matchPhotoFiles(
      list.map((file) => file.name),
      students,
      STUDENT_PHOTO_MAX,
    )
    const byName = new Map(list.map((file) => [file.name, file]))
    let done = 0
    let step = 0
    const total = matched.reduce((sum, row) => sum + row.files.length, 0)

    try {
      for (const row of matched) {
        const ids: string[] = []
        for (const fileName of row.files) {
          const file = byName.get(fileName)
          if (!file) continue
          step += 1
          setProgress(`${step} / ${total}`)
          try {
            const url = await shrinkImage(file, FACE_SHRINK)
            const created = await fetch('/api/academy/assets', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ kind: 'photo', label: `${row.student.student_name} 사진`, url }),
            })
            const body = await created.json()
            if (!created.ok) {
              skipped.push(`${fileName} — ${body.error ?? '올리지 못했습니다'}`)
              continue
            }
            ids.push(body.asset.id as string)
          } catch {
            skipped.push(fileName)
          }
        }
        if (ids.length === 0) continue
        // 맨 앞이 대표 사진 — 무대 화면과 파워포인트는 한 장만 쓴다
        const assigned = await fetch(`/api/students/${row.student.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            photo_asset_id: ids[0],
            photo_asset_ids: ids.length > 1 ? ids : null,
          }),
        })
        if (assigned.ok) done += ids.length
        else skipped.push(...row.files)
      }
    } finally {
      setBusy(false)
      setProgress('')
      onDone(done, skipped)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        multiple
        className="sr-only"
        onChange={(event) => {
          if (event.target.files?.length) void handle(event.target.files)
          event.target.value = ''
        }}
      />
      <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={busy}>
        {busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <ImagePlus className="mr-1 h-4 w-4" />}
        사진 한꺼번에 올리기 {progress}
      </Button>
      <span className="text-xs text-muted-foreground">
        파일 이름에 아이 이름이 들어 있으면 <strong>알아서 짝지어</strong> 줍니다 — <code>김서연.jpg</code>.
        한 아이에 <strong>여러 장</strong>이면 이름 뒤에 번호를 붙이세요 — <code>김서연-1.jpg</code>{' '}
        <code>김서연-2.jpg</code>
      </span>
    </div>
  )
}
