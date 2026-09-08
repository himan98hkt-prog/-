'use client'

import Link from 'next/link'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldHint } from '@/components/ui/field'
import { ASSET_KIND_LABEL, type AcademyAsset, type ImageMap } from '@/lib/assets'
import { CATEGORY_LABEL, type TemplateCategory } from '@/lib/design/templates'
import { cn } from '@/lib/utils'

/** 갈래별로 다른 사진을 쓰고 싶을 때 고르는 자리 */
const CATEGORY_HINT: Record<TemplateCategory, string> = {
  poster: '벽에 붙는 포스터. 단체사진이나 학원 전경이 잘 맞습니다.',
  program: '관객이 손에 드는 순서지. 표지 사진입니다.',
  invite: '초대장·SNS·배너. 아이들 얼굴이 보이는 사진이 반응이 좋습니다.',
  stage: '상장·이름표·포토존. 사진이 거의 쓰이지 않습니다.',
  ops: '진행 문서. 사진 없이 글만 나옵니다.',
}

function Thumb({ asset, selected, onClick }: { asset: AcademyAsset; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      title={asset.label}
      className={cn(
        'group relative overflow-hidden rounded-md border-2 transition-colors',
        selected ? 'border-accent' : 'border-transparent hover:border-border',
      )}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={asset.url} alt={asset.label} className="h-16 w-full bg-secondary object-cover" />
      <span className="block truncate px-1 py-0.5 text-xs text-muted-foreground">{asset.label}</span>
    </button>
  )
}

function NoneTile({ selected, onClick, label }: { selected: boolean; onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        'flex h-[86px] flex-col items-center justify-center gap-1 rounded-md border-2 border-dashed text-xs transition-colors',
        selected ? 'border-accent text-foreground' : 'border-border text-muted-foreground hover:bg-secondary',
      )}
    >
      {label}
    </button>
  )
}

/**
 * 인쇄물에 쓸 이미지 고르기.
 *
 * 기본은 한 장이면 끝난다 — 사진 하나를 고르면 포스터·표지·초대장이 전부 그 사진을 쓴다.
 * 갈래마다 다르게 쓰고 싶은 원장만 아래를 펼쳐 따로 지정한다.
 */
export function ImagePicker({
  assets,
  value,
  onChange,
}: {
  assets: AcademyAsset[]
  value: ImageMap
  onChange: (next: ImageMap) => void
}) {
  const photos = assets.filter((a) => a.kind === 'photo')
  const marks = assets.filter((a) => a.kind === 'logo' || a.kind === 'symbol')

  const set = (key: keyof ImageMap, id: string | undefined) => {
    const next = { ...value }
    if (id) next[key] = id
    else delete next[key]
    onChange(next)
  }

  if (assets.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>이미지</CardTitle>
          <CardDescription>학원 로고와 사진을 인쇄물에 넣습니다.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border border-dashed border-border px-4 py-6 text-center">
            <p className="text-sm">보관함이 비어 있습니다.</p>
            <p className="mt-1.5 text-xs text-muted-foreground">
              설정 화면에서 로고와 사진을 한 번만 올려 두면, 이 화면에서 고르기만 하면 됩니다.
            </p>
            <Link
              href="/settings"
              className="mt-3 inline-block rounded-md border border-border px-3 py-1.5 text-sm hover:bg-secondary"
            >
              이미지 올리러 가기
            </Link>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>이미지</CardTitle>
        <CardDescription>고르는 즉시 오른쪽 인쇄물에 들어갑니다.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {marks.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              로고 자리
            </p>
            <div className="grid grid-cols-4 gap-1.5">
              <NoneTile selected={!value.logo} onClick={() => set('logo', undefined)} label="학원 기본" />
              {marks.map((asset) => (
                <Thumb
                  key={asset.id}
                  asset={asset}
                  selected={value.logo === asset.id}
                  onClick={() => set('logo', asset.id)}
                />
              ))}
            </div>
            <FieldHint>
              {ASSET_KIND_LABEL.logo}와 {ASSET_KIND_LABEL.symbol} 중에서 고릅니다. 테마마다 동그랗게 잘리거나
              테두리가 붙는 등 모양이 다르게 적용됩니다.
            </FieldHint>
          </div>
        )}

        {photos.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              사진 — 모든 인쇄물
            </p>
            <div className="grid grid-cols-4 gap-1.5">
              <NoneTile selected={!value.default} onClick={() => set('default', undefined)} label="사진 없이" />
              {photos.map((asset) => (
                <Thumb
                  key={asset.id}
                  asset={asset}
                  selected={value.default === asset.id}
                  onClick={() => set('default', asset.id)}
                />
              ))}
            </div>

            <details className="mt-3">
              <summary className="cursor-pointer text-sm text-accent">
                포스터와 표지에 다른 사진 쓰기
              </summary>
              <div className="mt-3 grid gap-3">
                {(['poster', 'program', 'invite'] as TemplateCategory[]).map((category) => (
                  <div key={category}>
                    <p className="text-xs font-medium">{CATEGORY_LABEL[category]}</p>
                    <p className="mb-1.5 text-xs text-muted-foreground">{CATEGORY_HINT[category]}</p>
                    <div className="grid grid-cols-4 gap-1.5">
                      <NoneTile
                        selected={!value[category]}
                        onClick={() => set(category, undefined)}
                        label="위와 같이"
                      />
                      {photos.map((asset) => (
                        <Thumb
                          key={asset.id}
                          asset={asset}
                          selected={value[category] === asset.id}
                          onClick={() => set(category, asset.id)}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}

        <Link href="/settings" className="text-sm text-muted-foreground hover:text-foreground">
          + 보관함에 이미지 더 올리기
        </Link>
      </CardContent>
    </Card>
  )
}
