import { fail, guard, ok, readJson, str } from '@/lib/http'
import { getRepository } from '@/lib/store'
import {
  categorySpec,
  FEE_MAX,
  FEE_MIN,
  normalizeBook,
  normalizeBookings,
  rememberVendor,
  STATUS_ORDER,
  type BookingStatus,
  type VendorBooking,
} from '@/lib/vendors'

/**
 * 함께할 분 한 갈래를 저장한다.
 *
 * 한 번 누르면 두 곳에 적힌다 — **이 연주회의 예약**과 **학원 수첩**.
 * 원장님은 한 번만 적으시고, 내년에는 단추 하나로 돌아온다. 「수첩에도 저장할까요?」를
 * 따로 여쭤보면 그 물음 하나 때문에 아무도 안 쓰신다.
 *
 * 지역은 학원에 저장한다 — 학원은 한 동네에 있으니 행사마다 다시 물을 이유가 없다.
 */
export async function POST(req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const event = await repo.getEvent(params.id)
    if (!event) return fail('행사를 찾을 수 없습니다.', 404)

    const body = await readJson(req)
    const spec = categorySpec(str(body.category, 20) ?? '')
    if (!spec) return fail('어느 갈래인지 알 수 없습니다.')

    const bookings = normalizeBookings(event.vendor_bookings)
    const academy = await repo.ensureAcademy(event.academy_id)

    // 지역만 고치실 수도 있다 (업체는 그대로 두고)
    const region = str(body.region, 40)
    if (region !== null && region !== (academy.region ?? '')) {
      await repo.updateAcademy(academy.id, { region: region || null })
    }

    const name = (str(body.name, 40) ?? '').trim()

    // 이름을 비우시면 그 자리를 비운다. 「지우기」 단추를 따로 두지 않는다
    if (!name) {
      delete bookings[spec.id]
      const updated = await repo.updateEvent(event.id, { vendor_bookings: bookings })
      return ok({ event: updated, bookings: normalizeBookings(updated.vendor_bookings) })
    }

    const rawFee = body.fee
    let fee: number | null = null
    if (rawFee !== null && rawFee !== undefined && String(rawFee).trim() !== '') {
      // 「30만원」처럼 적으셔도 받는다 — 숫자만 남긴다
      const digits = Number(String(rawFee).replace(/[^\d]/g, ''))
      if (!Number.isFinite(digits) || digits < FEE_MIN || digits > FEE_MAX) {
        return fail('금액은 숫자로 적어 주세요.')
      }
      fee = Math.round(digits)
    }

    const rawStatus = str(body.status, 12) as BookingStatus | null
    const booking: VendorBooking = {
      name,
      phone: (str(body.phone, 30) ?? '').trim(),
      fee,
      status: rawStatus && STATUS_ORDER.includes(rawStatus) ? rawStatus : 'asking',
      memo: (str(body.memo, 200) ?? '').trim(),
      updated_at: new Date().toISOString(),
    }

    bookings[spec.id] = booking
    const book = rememberVendor(normalizeBook(academy.vendors), spec.id, booking)

    const [updated] = await Promise.all([
      repo.updateEvent(event.id, { vendor_bookings: bookings }),
      repo.updateAcademy(academy.id, { vendors: book }),
    ])

    return ok({ event: updated, bookings: normalizeBookings(updated.vendor_bookings), book })
  })
}
