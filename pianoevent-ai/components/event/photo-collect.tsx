'use client'

import { Camera, Check, ImagePlus, Loader2 } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { STUDENT_PHOTO_MAX, type AcademyAsset } from '@/lib/assets'
import { FACE_SHRINK, shrinkImage } from '@/lib/image'
import { groupByPerformer } from '@/lib/program/appearances'
import type { EventStudent } from '@/lib/types'
import { cn } from '@/lib/utils'

/**
 * 당일 사진 모으기 — 휴대폰으로.
 *
 * 리허설에서 찍은 사진은 그날 저녁 감동영상에 들어가야 값이 있다. 그런데 지금은
 * 컴퓨터 앞에 앉아야 넣을 수 있다. 휴대폰으로 아이를 누르고 찍으면 바로 들어가게 한다.
 *
 * 사진은 이 휴대폰에서 줄여 학원 보관함에 담긴다 — 바깥으로 나가지 않는다.
 */
export function PhotoCollect({
  eventId,
  students,
  assets,
}: {
  eventId: string
  students: EventStudent[]
  assets: AcademyAsset[]
}) {
  const router = useRouter()
  const byId = new Map(assets.map((asset) => [asset.id, asset]))
  // 한 아이가 두 줄(독주·듀엣)이어도 사람 한 명으로 보여 준다 — 사진은 사람의 것이다
  const people = groupByPerformer(students)

  const [busy, setBusy] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [done, setDone] = useState<Record<string, number>>({})
  const targetRef = useRef<EventStudent | null>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const albumRef = useRef<HTMLInputElement>(null)

  function photosOf(student: EventStudent): string[] {
    return [student.photo_asset_id, ...(student.photo_asset_ids ?? [])].filter(
      (id, at, all): id is string => !!id && byId.has(id) && all.indexOf(id) === at,
    )
  }

  async function upload(files: FileList) {
    const student = targetRef.current
    if (!student) return
    setBusy(student.id)
    setNote(null)
    const before = photosOf(student)
    const added: string[] = []
    try {
      for (const file of Array.from(files)) {
        if (before.length + added.length >= STUDENT_PHOTO_MAX) break
        const url = await shrinkImage(file, FACE_SHRINK)
        const created = await fetch('/api/academy/assets', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: 'photo', label: `${student.student_name} 사진`, url }),
        })
        const body = await created.json()
        if (!created.ok) throw new Error(body.error ?? '올리지 못했습니다.')
        added.push(body.asset.id as string)
      }
      if (added.length === 0) {
        setNote(`${student.student_name} — 사진은 ${STUDENT_PHOTO_MAX}장까지입니다.`)
        return
      }
      const ids = [...before, ...added]
      const res = await fetch(`/api/students/${student.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ photo_asset_id: ids[0], photo_asset_ids: ids.length > 1 ? ids : null }),
      })
      if (!res.ok) throw new Error((await res.json()).error ?? '붙이지 못했습니다.')
      setDone((prev) => ({ ...prev, [student.id]: (prev[student.id] ?? 0) + added.length }))
      setNote(`${student.student_name} 사진 ${added.length}장을 넣었습니다.`)
      router.refresh()
    } catch (e) {
      setNote(e instanceof Error ? e.message : '올리지 못했습니다.')
    } finally {
      setBusy(null)
      targetRef.current = null
    }
  }

  function pick(student: EventStudent, from: 'camera' | 'album') {
    targetRef.current = student
    ;(from === 'camera' ? cameraRef : albumRef).current?.click()
  }

  const withPhoto = people.filter((person) => photosOf(person.rows[0]).length > 0).length

  return (
    <div className="grid gap-3" data-testid="photo-collect">
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        onChange={(native) => {
          if (native.target.files?.length) void upload(native.target.files)
          native.target.value = ''
        }}
      />
      <input
        ref={albumRef}
        type="file"
        accept="image/*"
        multiple
        className="sr-only"
        onChange={(native) => {
          if (native.target.files?.length) void upload(native.target.files)
          native.target.value = ''
        }}
      />

      <p className="text-sm text-muted-foreground" data-testid="photo-progress">
        <strong className="text-foreground">
          {people.length}명 중 {withPhoto}명
        </strong>{' '}
        사진이 들어 있습니다.
      </p>
      {note && <p className="rounded-md border border-accent/40 bg-accent/5 px-3 py-2 text-sm">{note}</p>}

      <ul className="grid gap-2">
        {people.map((person) => {
          const student = person.rows[0]
          const shots = photosOf(student)
          const added = done[student.id] ?? 0
          return (
            <li
              key={person.key}
              className={cn(
                'flex items-center gap-3 rounded-lg border p-3',
                shots.length > 0 ? 'border-accent/40 bg-accent/5' : 'border-border',
              )}
            >
              {/* 장수 표시는 동그란 사진 **밖에** 둔다 — 안에 두면 잘려 숫자가 안 보인다 */}
              <span className="relative h-14 w-14 shrink-0">
                <span className="flex h-full w-full items-center justify-center overflow-hidden rounded-full border border-border">
                  {shots[0] ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={byId.get(shots[0])!.url} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <ImagePlus className="h-5 w-5 text-muted-foreground" aria-hidden />
                  )}
                </span>
                {shots.length > 1 && (
                  <span className="absolute -right-1 -top-1 rounded-full bg-accent px-1.5 text-[11px] font-medium leading-5 tabular-nums text-accent-foreground">
                    {shots.length}
                  </span>
                )}
              </span>

              <span className="min-w-0 flex-1">
                <span className="block truncate text-base font-medium">{person.name}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {shots.length > 0 ? `사진 ${shots.length}장` : '사진 없음'}
                  {added > 0 && ' · 방금 넣었습니다'}
                </span>
              </span>

              {busy === student.id ? (
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-label="올리는 중" />
              ) : added > 0 ? (
                <Check className="h-5 w-5 text-accent" aria-hidden />
              ) : null}

              <Button
                size="sm"
                className="h-11 shrink-0 px-3"
                disabled={busy !== null || shots.length >= STUDENT_PHOTO_MAX}
                onClick={() => pick(student, 'camera')}
                aria-label={`${person.name} 사진 찍기`}
              >
                <Camera className="h-5 w-5" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-11 shrink-0 px-3"
                disabled={busy !== null || shots.length >= STUDENT_PHOTO_MAX}
                onClick={() => pick(student, 'album')}
                aria-label={`${person.name} 앨범에서 고르기`}
              >
                <ImagePlus className="h-5 w-5" />
              </Button>
            </li>
          )
        })}
      </ul>

      <p className="text-xs text-muted-foreground">
        사진은 이 휴대폰에서 크기를 줄여 <strong>학원 보관함</strong>에 담깁니다. 넣는 즉시 무대 화면과
        감동영상에 들어갑니다. 한 아이당 {STUDENT_PHOTO_MAX}장까지.
      </p>
      <a href={`/events/${eventId}?tab=roster`} className="text-xs underline underline-offset-4">
        명단 화면에서 자세히 고치기 →
      </a>
    </div>
  )
}
