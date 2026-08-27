'use client'

import { Check, ImagePlus, Loader2, Trash2 } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useRef, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldHint, Input, Label } from '@/components/ui/field'
import {
  ASSET_KIND_HINT,
  ASSET_KIND_LABEL,
  ASSET_MAX_COUNT,
  assetSizeLabel,
  type AcademyAsset,
  type AssetKind,
} from '@/lib/assets'
import { shrinkImage, shrinkOptionsFor } from '@/lib/image'
import type { Academy } from '@/lib/types'
import { cn } from '@/lib/utils'

const KINDS: AssetKind[] = ['logo', 'symbol', 'photo']

/**
 * 학원 이미지 보관함.
 *
 * 원장이 인쇄물마다 사진 주소를 찾아 붙여 넣던 일을 없앤다.
 * 컴퓨터에서 파일을 끌어다 놓으면 알아서 크기를 줄여 보관하고,
 * 인쇄물 화면에서는 고르기만 하면 된다.
 */
export function AssetLibrary({ academy }: { academy: Academy }) {
  const router = useRouter()
  const assets = academy.assets ?? []
  const [kind, setKind] = useState<AssetKind>('photo')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  async function upload(files: FileList | File[]) {
    const list = Array.from(files).slice(0, ASSET_MAX_COUNT)
    if (list.length === 0) return
    setBusy(true)
    setMessage(null)
    try {
      for (const file of list) {
        const url = await shrinkImage(file, shrinkOptionsFor(kind))
        const label = file.name.replace(/\.[^.]+$/, '').slice(0, 40) || ASSET_KIND_LABEL[kind]
        const res = await fetch('/api/academy/assets', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind, label, url }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.error ?? '올리지 못했습니다.')
      }
      setMessage(`${list.length}장을 보관함에 넣었습니다.`)
      router.refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '올리지 못했습니다.')
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function rename(id: string, label: string) {
    await fetch(`/api/academy/assets/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label }),
    })
    router.refresh()
  }

  /** 이 이미지를 학원 기본 로고·사진으로 삼는다 — 모든 행사의 출발점이 된다 */
  async function makeDefault(asset: AcademyAsset) {
    setBusy(true)
    setMessage(null)
    try {
      const field = asset.kind === 'photo' ? 'photo_url' : 'logo_url'
      const res = await fetch('/api/academy', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: asset.url }),
      })
      if (!res.ok) throw new Error((await res.json()).error ?? '지정하지 못했습니다.')
      setMessage(
        asset.kind === 'photo'
          ? `"${asset.label}" 을 학원 기본 사진으로 지정했습니다.`
          : `"${asset.label}" 을 학원 기본 로고로 지정했습니다.`,
      )
      router.refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '지정하지 못했습니다.')
    } finally {
      setBusy(false)
    }
  }

  async function remove(id: string, label: string) {
    if (!window.confirm(`"${label}" 을 보관함에서 지울까요?\n이미 인쇄한 종이에는 영향이 없습니다.`)) return
    setBusy(true)
    try {
      await fetch(`/api/academy/assets/${id}`, { method: 'DELETE' })
      router.refresh()
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>이미지 보관함</CardTitle>
        <CardDescription>
          로고·상징·사진을 여기에 한 번만 올려 두면, 포스터부터 진행 문서까지 모든 인쇄물에서 골라 쓸 수
          있습니다. <strong className="font-medium text-foreground">학원 기본</strong>으로 지정한 로고와 사진은
          새 행사에 자동으로 들어갑니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div>
          <Label htmlFor="asset-kind">무엇을 올리시나요</Label>
          <div id="asset-kind" className="flex flex-wrap gap-1.5">
            {KINDS.map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setKind(k)}
                aria-pressed={k === kind}
                className={cn(
                  'rounded-full border px-3 py-1 text-xs transition-colors',
                  k === kind
                    ? 'border-accent bg-accent/10 font-medium text-foreground'
                    : 'border-border text-muted-foreground hover:bg-secondary',
                )}
              >
                {ASSET_KIND_LABEL[k]}
              </button>
            ))}
          </div>
          <FieldHint>{ASSET_KIND_HINT[kind]}</FieldHint>
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            if (e.dataTransfer.files.length > 0) void upload(e.dataTransfer.files)
          }}
          className={cn(
            'flex flex-col items-center gap-2 rounded-md border-2 border-dashed px-4 py-8 text-center transition-colors',
            dragging ? 'border-accent bg-accent/5' : 'border-border',
          )}
        >
          {busy ? (
            <Loader2 className="h-5 w-5 animate-spin text-accent" aria-hidden />
          ) : (
            <ImagePlus className="h-5 w-5 text-muted-foreground" aria-hidden />
          )}
          <p className="text-sm">
            여기에 사진을 끌어다 놓거나
            <br className="sm:hidden" /> 아래 버튼으로 고르세요
          </p>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => e.target.files && void upload(e.target.files)}
          />
          <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => fileRef.current?.click()}>
            컴퓨터에서 고르기
          </Button>
          <FieldHint>
            휴대폰으로 찍은 큰 사진도 괜찮습니다. 인쇄에 필요한 크기까지 자동으로 줄여서 보관합니다.
          </FieldHint>
        </div>

        {message && (
          <p className="rounded-md border border-border bg-secondary px-3 py-2 text-sm">{message}</p>
        )}

        {assets.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            아직 올린 이미지가 없습니다. 학원 로고 한 장부터 올려 보세요.
          </p>
        ) : (
          <div className="grid gap-3">
            {KINDS.filter((k) => assets.some((a) => a.kind === k)).map((k) => (
              <div key={k}>
                <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  {ASSET_KIND_LABEL[k]} {assets.filter((a) => a.kind === k).length}장
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {assets
                    .filter((a) => a.kind === k)
                    .map((asset) => (
                      <AssetRow
                        key={asset.id}
                        asset={asset}
                        isDefault={
                          asset.kind === 'photo'
                            ? academy.photo_url === asset.url
                            : academy.logo_url === asset.url
                        }
                        onRename={rename}
                        onRemove={remove}
                        onMakeDefault={makeDefault}
                        busy={busy}
                      />
                    ))}
                </div>
              </div>
            ))}
          </div>
        )}

        <FieldHint>
          이미지는 이 학원 계정에만 저장되며 밖으로 나가지 않습니다. 보관함은 {ASSET_MAX_COUNT}장까지입니다.
        </FieldHint>
      </CardContent>
    </Card>
  )
}

function AssetRow({
  asset,
  isDefault,
  onRename,
  onRemove,
  onMakeDefault,
  busy,
}: {
  asset: AcademyAsset
  isDefault: boolean
  onRename: (id: string, label: string) => void
  onRemove: (id: string, label: string) => void
  onMakeDefault: (asset: AcademyAsset) => void
  busy: boolean
}) {
  const [label, setLabel] = useState(asset.label)

  return (
    <div className={cn('flex items-center gap-3 rounded-md border p-2', isDefault ? 'border-accent' : 'border-border')}>
      {/* 보관함 미리보기 — 원본 비율을 유지한 채 채운다 */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={asset.url}
        alt=""
        className="h-14 w-14 shrink-0 rounded border border-border bg-secondary object-cover"
      />
      <div className="min-w-0 flex-1">
        <Input
          value={label}
          maxLength={40}
          aria-label="이미지 이름"
          onChange={(e) => setLabel(e.target.value)}
          onBlur={() => label.trim() && label !== asset.label && onRename(asset.id, label.trim())}
          className="h-8 text-sm"
        />
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <span className="text-[11px] text-muted-foreground">{assetSizeLabel(asset.url)}</span>
          {isDefault ? (
            <Badge variant="accent" className="gap-1 text-[10px]">
              <Check className="h-3 w-3" aria-hidden />
              학원 기본
            </Badge>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={() => onMakeDefault(asset)}
              className="text-[11px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
            >
              학원 기본으로 지정
            </button>
          )}
        </div>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={busy}
        aria-label={`${asset.label} 지우기`}
        onClick={() => onRemove(asset.id, asset.label)}
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </Button>
    </div>
  )
}
