'use client'

import { ImagePlus, Loader2, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import type { AcademyAsset } from '@/lib/assets'
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
  onPick: (assetId: string | null) => void
  onUpload: (file: File) => void
  busy: boolean
}) {
  const [open, setOpen] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const current = assets.find((asset) => asset.id === student.photo_asset_id) ?? null
  const photos = assets.filter((asset) => asset.kind === 'photo')

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => (current ? setOpen((prev) => !prev) : fileRef.current?.click())}
        className={cn(
          'flex h-11 w-11 items-center justify-center overflow-hidden rounded-full border transition-colors',
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

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) onUpload(file)
          event.target.value = ''
        }}
      />

      {open && (
        <div className="absolute left-0 top-12 z-20 w-64 rounded-md border border-border bg-background p-2 shadow-lg">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-medium">{student.student_name} 사진</p>
            <button type="button" onClick={() => setOpen(false)} aria-label="닫기" className="text-muted-foreground">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="grid max-h-44 grid-cols-4 gap-1.5 overflow-y-auto">
            {photos.map((asset) => (
              <button
                key={asset.id}
                type="button"
                onClick={() => {
                  onPick(asset.id)
                  setOpen(false)
                }}
                aria-pressed={asset.id === student.photo_asset_id}
                title={asset.label}
                className={cn(
                  'aspect-square overflow-hidden rounded border',
                  asset.id === student.photo_asset_id ? 'border-accent ring-1 ring-accent' : 'border-border',
                )}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={asset.url} alt={asset.label} className="h-full w-full object-cover" />
              </button>
            ))}
          </div>
          <div className="mt-2 flex gap-1.5">
            <Button variant="outline" size="sm" className="flex-1" onClick={() => fileRef.current?.click()}>
              새 사진 올리기
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                onPick(null)
                setOpen(false)
              }}
            >
              빼기
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * 사진 한꺼번에 올리기.
 * 파일 이름에서 아이 이름을 찾아 짝지어 준다 — `김서연.jpg`, `2026 윤채원 연습.jpg` 둘 다 걸린다.
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
    let matched = 0
    const skipped: string[] = []
    try {
      const list = Array.from(files)
      for (let index = 0; index < list.length; index += 1) {
        const file = list[index]
        setProgress(`${index + 1} / ${list.length}`)
        const base = file.name.replace(/\.[^.]+$/, '')
        // 파일 이름 안에 아이 이름이 들어 있으면 그 아이 것으로 본다. 긴 이름부터 맞춰 오해를 줄인다
        const student = [...students]
          .sort((a, b) => b.student_name.length - a.student_name.length)
          .find((row) => row.student_name && base.includes(row.student_name))
        if (!student) {
          skipped.push(file.name)
          continue
        }
        const url = await shrinkImage(file, FACE_SHRINK)
        const created = await fetch('/api/academy/assets', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: 'photo', label: `${student.student_name} 사진`, url }),
        })
        const body = await created.json()
        if (!created.ok) {
          skipped.push(`${file.name} — ${body.error ?? '올리지 못했습니다'}`)
          continue
        }
        const assigned = await fetch(`/api/students/${student.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ photo_asset_id: body.asset.id }),
        })
        if (assigned.ok) matched += 1
        else skipped.push(file.name)
      }
    } finally {
      setBusy(false)
      setProgress('')
      onDone(matched, skipped)
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
        파일 이름에 아이 이름이 들어 있으면 <strong>알아서 짝지어</strong> 줍니다 — <code>김서연.jpg</code>
      </span>
    </div>
  )
}
