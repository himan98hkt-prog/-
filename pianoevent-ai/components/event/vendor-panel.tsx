'use client'

import { Check, ExternalLink, MessageSquare, Phone, Pencil, Search, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Label, Select, Textarea } from '@/components/ui/field'
import { formatWon } from '@/lib/ops/budget'
import {
  CATEGORIES,
  guessRegion,
  normalizeBook,
  normalizeBookings,
  pastVendors,
  searchLinks,
  smsHref,
  STATUS_LABEL,
  STATUS_ORDER,
  summarize,
  telHref,
  type BookingStatus,
  type CategorySpec,
  type VendorBooking,
  type VendorBookings,
  type VendorMemo,
} from '@/lib/vendors'
import type { Academy, EventRecord } from '@/lib/types'
import { cn } from '@/lib/utils'

/**
 * 함께할 분들.
 *
 * 여기서 지키려는 것은 하나다 — **빈칸이 곧 할 일이 되게** 하는 것.
 * 갈래를 여섯으로 미리 정해 두면, 원장님은 「뭘 알아봐야 하지」를 떠올리실 필요 없이
 * 비어 있는 칸만 채우시면 된다.
 *
 * 업체 목록을 우리가 들고 있지 않는다. 목록은 썩고, 썩은 목록은 없느니만 못하다.
 * 대신 **지역을 붙인 검색어**를 만들어 늘 최신인 지도로 보내 드린다.
 */
export function VendorPanel({
  academy,
  event,
}: {
  academy: Academy
  event: EventRecord
}) {
  const [bookings, setBookings] = useState<VendorBookings>(() => normalizeBookings(event.vendor_bookings))
  const [book, setBook] = useState<VendorMemo[]>(() => normalizeBook(academy.vendors))
  const [region, setRegion] = useState(() => academy.region ?? guessRegion(event.venue))
  const [editing, setEditing] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState('')

  const summary = useMemo(() => summarize(bookings), [bookings])

  async function save(category: string, patch: Partial<VendorBooking> & { name: string }) {
    setBusy(category)
    setError('')
    try {
      const res = await fetch(`/api/events/${event.id}/vendors`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category, region, ...patch }),
      })
      const json = (await res.json()) as { bookings?: VendorBookings; book?: VendorMemo[]; error?: string }
      if (!res.ok) throw new Error(json.error || '저장하지 못했습니다.')
      setBookings(normalizeBookings(json.bookings))
      if (json.book) setBook(normalizeBook(json.book))
      setEditing(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장하지 못했습니다.')
    } finally {
      setBusy(null)
    }
  }

  /**
   * 접어 둔다.
   *
   * 갈래가 여섯이라 펼쳐 두면 이 화면 하나에 눌러 볼 것이 76개가 된다 —
   * 「고르실 것이 없게」를 지키지 못하게 된다(`npm run verify:simple` 이 잡아냈다).
   * 대신 **접힌 줄에 빠진 갈래를 그대로 적어** 둔다. 열지 않으셔도 무엇이
   * 비었는지는 보이고, 채우실 때만 펼치신다.
   */
  return (
    <Card>
      <details data-testid="vendor-details">
        <summary className="cursor-pointer list-none">
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2">
                  함께할 분들
                  <Badge variant={summary.filled === summary.total ? 'accent' : 'outline'}>
                    {summary.filled} / {summary.total}
                  </Badge>
                </CardTitle>
                <CardDescription>
                  {summary.missing.length > 0 ? (
                    <>아직 안 정하신 것 — <b className="text-foreground">{summary.missing.map((m) => m.label).join(' · ')}</b></>
                  ) : (
                    '여섯 자리가 모두 찼습니다. 연락처는 당일에 여기서 바로 거실 수 있습니다.'
                  )}
                </CardDescription>
              </div>
              {summary.totalFee > 0 && (
                <div className="text-right">
                  <div className="text-xs text-muted-foreground">적어 두신 금액 합계</div>
                  <div className="text-lg font-bold tabular-nums">{formatWon(summary.totalFee)}</div>
                </div>
              )}
            </div>
          </CardHeader>
        </summary>

      <CardContent className="space-y-4">
        {/* 지역 — 한 번만 넣으시면 학원에 남아 다음 행사에서도 쓰인다 */}
        <div className="flex flex-wrap items-end gap-2 rounded-lg border border-dashed border-accent/40 bg-secondary/40 p-3">
          <div className="min-w-0 flex-1">
            <Label htmlFor="vendor-region">우리 학원 지역</Label>
            <Input
              id="vendor-region"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              placeholder="예: 일산동구"
              className="max-w-xs"
            />
          </div>
          <p className="pb-2 text-xs text-muted-foreground">
            찾기 단추를 누르면 이 지역으로 지도에서 검색합니다.
            <br />
            나가는 것은 <b>지역과 갈래뿐</b>입니다 — 아이 명단은 나가지 않습니다.
          </p>
        </div>

        {error && (
          <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          {CATEGORIES.map((spec) => (
            <VendorCard
              key={spec.id}
              spec={spec}
              booking={bookings[spec.id] ?? null}
              past={pastVendors(book, spec.id)}
              region={region}
              open={editing === spec.id}
              busy={busy === spec.id}
              onOpen={() => setEditing(editing === spec.id ? null : spec.id)}
              onSave={(patch) => save(spec.id, patch)}
            />
          ))}
        </div>

        <p className="text-xs text-muted-foreground">
          한 번 적으신 곳은 <b className="text-foreground">학원 수첩</b>에 남습니다.
          내년 연주회에서는 「지난번 그대로」 한 번이면 됩니다.
        </p>
      </CardContent>
      </details>
    </Card>
  )
}

function VendorCard({
  spec,
  booking,
  past,
  region,
  open,
  busy,
  onOpen,
  onSave,
}: {
  spec: CategorySpec
  booking: VendorBooking | null
  past: VendorMemo[]
  region: string
  open: boolean
  busy: boolean
  onOpen: () => void
  onSave: (patch: Partial<VendorBooking> & { name: string }) => void
}) {
  const [showSearch, setShowSearch] = useState(false)
  const links = useMemo(() => searchLinks(spec.id, region), [spec.id, region])
  const tel = booking?.phone ? telHref(booking.phone) : null
  const sms = booking?.phone ? smsHref(booking.phone) : null

  return (
    <div
      data-testid={`vendor-${spec.id}`}
      className={cn(
        'rounded-xl border p-3.5 transition-colors',
        booking ? 'border-accent/40 bg-card' : 'border-dashed border-input bg-secondary/30',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-semibold">{spec.label}</span>
            {booking && (
              <Badge variant={booking.status === 'asking' ? 'outline' : 'accent'}>
                {STATUS_LABEL[booking.status]}
              </Badge>
            )}
          </div>
          {!booking && <p className="mt-1 text-xs text-muted-foreground">{spec.detail}</p>}
        </div>
        <Button variant="ghost" size="sm" onClick={onOpen} aria-label={`${spec.label} ${booking ? '고치기' : '적기'}`}>
          {open ? <X className="h-4 w-4" /> : booking ? <Pencil className="h-4 w-4" /> : '직접 적기'}
        </Button>
      </div>

      {/* 정해진 것 — 이름·연락처·금액과 바로 걸기 */}
      {booking && !open && (
        <div className="mt-2 space-y-1.5">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-medium">{booking.name}</span>
            {booking.phone && <span className="text-sm text-muted-foreground">{booking.phone}</span>}
          </div>
          {(booking.fee !== null || booking.memo) && (
            <p className="text-sm text-muted-foreground">
              {booking.fee !== null && <b className="text-foreground tabular-nums">{formatWon(booking.fee)}</b>}
              {booking.fee !== null && booking.memo && ' · '}
              {booking.memo}
            </p>
          )}
          {(tel || sms) && (
            <div className="flex gap-2 pt-0.5">
              {tel && (
                <a href={tel} className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
                  <Phone className="h-3.5 w-3.5" aria-hidden /> 전화
                </a>
              )}
              {sms && (
                <a href={sms} className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
                  <MessageSquare className="h-3.5 w-3.5" aria-hidden /> 문자
                </a>
              )}
            </div>
          )}
        </div>
      )}

      {/* 아직 비어 있는 자리 — 찾기와 지난번 그대로 */}
      {!booking && !open && (
        <div className="mt-2.5 space-y-2">
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowSearch((v) => !v)}>
              <Search className="h-3.5 w-3.5" aria-hidden /> 찾아보기
            </Button>
            {past.slice(0, 2).map((m) => (
              <Button
                key={m.name}
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => onSave({ name: m.name, phone: m.phone, fee: m.fee, memo: m.memo, status: 'asking' })}
              >
                <Check className="h-3.5 w-3.5" aria-hidden /> {m.name}
                {m.fee !== null && <span className="text-muted-foreground">· {formatWon(m.fee)}</span>}
              </Button>
            ))}
          </div>

          {showSearch && (
            <div className="rounded-lg bg-secondary/60 p-2.5 text-xs">
              {!region.trim() ? (
                /* 지역 없이 검색하면 전국이 나온다 — 그건 안 찾아 준 것과 같다 */
                <p className="text-muted-foreground">
                  먼저 위의 <b className="text-foreground">「우리 학원 지역」</b>을 넣어 주세요.
                  넣으시면 그 동네로 찾아 드립니다. (한 번만 넣으시면 계속 쓰입니다)
                </p>
              ) : spec.findable ? (
                <>
                  <p className="mb-2 text-muted-foreground">
                    <b className="text-foreground">{region.trim()}</b> {spec.query} — 새 창에서 열립니다
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {links.map((link) => (
                      <a
                        key={link.label}
                        href={link.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
                      >
                        {link.label} <ExternalLink className="h-3 w-3" aria-hidden />
                      </a>
                    ))}
                  </div>
                </>
              ) : (
                <>
                  <p className="text-muted-foreground">{spec.hint}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {links.slice(2).map((link) => (
                      <a
                        key={link.label}
                        href={link.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
                      >
                        그래도 검색해 보기 <ExternalLink className="h-3 w-3" aria-hidden />
                      </a>
                    ))}
                  </div>
                </>
              )}
              {spec.findable && spec.hint && <p className="mt-2 text-muted-foreground">{spec.hint}</p>}
            </div>
          )}
        </div>
      )}

      {open && <VendorForm booking={booking} past={past} busy={busy} onSave={onSave} />}
    </div>
  )
}

function VendorForm({
  booking,
  past,
  busy,
  onSave,
}: {
  booking: VendorBooking | null
  past: VendorMemo[]
  busy: boolean
  onSave: (patch: Partial<VendorBooking> & { name: string }) => void
}) {
  const [name, setName] = useState(booking?.name ?? '')
  const [phone, setPhone] = useState(booking?.phone ?? '')
  const [fee, setFee] = useState(booking?.fee !== null && booking?.fee !== undefined ? String(booking.fee) : '')
  const [status, setStatus] = useState<BookingStatus>(booking?.status ?? 'asking')
  const [memo, setMemo] = useState(booking?.memo ?? '')

  return (
    <form
      className="mt-3 space-y-2.5 border-t pt-3"
      onSubmit={(e) => {
        e.preventDefault()
        onSave({ name: name.trim(), phone, fee: fee.trim() === '' ? null : Number(fee.replace(/[^\d]/g, '')), status, memo })
      }}
    >
      {past.length > 0 && !booking && (
        <div className="flex flex-wrap gap-1.5">
          {past.map((m) => (
            <Button
              key={m.name}
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setName(m.name)
                setPhone(m.phone)
                setFee(m.fee !== null ? String(m.fee) : '')
                setMemo(m.memo)
              }}
            >
              {m.name} 불러오기
            </Button>
          ))}
        </div>
      )}

      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <Label htmlFor="v-name">이름 · 상호</Label>
          <Input id="v-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="예: 하모니홀" autoFocus />
        </div>
        <div>
          <Label htmlFor="v-phone">연락처</Label>
          <Input id="v-phone" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="010-0000-0000" inputMode="tel" />
        </div>
        <div>
          <Label htmlFor="v-fee">금액</Label>
          <Input id="v-fee" value={fee} onChange={(e) => setFee(e.target.value)} placeholder="300000" inputMode="numeric" />
        </div>
        <div>
          <Label htmlFor="v-status">어디까지</Label>
          <Select id="v-status" value={status} onChange={(e) => setStatus(e.target.value as BookingStatus)}>
            {STATUS_ORDER.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="v-memo">메모</Label>
        <Textarea
          id="v-memo"
          value={memo}
          onChange={(e) => setMemo(e.target.value)}
          placeholder="주차 10대 · 리허설 2시간 포함 · 아이들 잘 봐주심"
          className="min-h-[64px]"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy || !name.trim()}>
          {busy ? '저장하는 중…' : '저장'}
        </Button>
        {booking && (
          <Button type="button" variant="ghost" disabled={busy} onClick={() => onSave({ name: '' })}>
            이 자리 비우기
          </Button>
        )}
      </div>
    </form>
  )
}
