import { fail, guard, ok } from '@/lib/http'
import { parseRoster } from '@/lib/program/roster'
import { xlsxToText } from '@/lib/program/xlsx'

/** 원장님 명단 엑셀은 아무리 커도 이 안이다. 그 위는 다른 파일을 잘못 끌어다 놓으신 것이다 */
const MAX_BYTES = 8 * 1024 * 1024

/**
 * 엑셀 파일(.xlsx) 을 붙여넣기 칸에 들어갈 글로 바꿔 준다.
 *
 * 파일은 읽고 나서 버린다 — 저장하지 않는다. 아이 이름이 이 컴퓨터 밖으로
 * 나가지 않아야 하고, 이 길은 그 컴퓨터 안에서 도는 길이다.
 */
export async function POST(req: Request) {
  return guard(async () => {
    const form = await req.formData().catch(() => null)
    const file = form?.get('file')
    if (!(file instanceof File)) return fail('엑셀 파일을 찾지 못했습니다.')
    if (file.size > MAX_BYTES) return fail('파일이 너무 큽니다. 명단만 담긴 엑셀 파일을 올려 주세요.')

    if (/\.xls$/i.test(file.name)) {
      return fail(
        '옛날 엑셀 파일(.xls)입니다. 엑셀에서 [다른 이름으로 저장] → "Excel 통합 문서(.xlsx)" 로 한 번 저장한 뒤 올려 주세요.',
      )
    }
    if (/\.csv$/i.test(file.name)) {
      // CSV 는 그냥 글이다. 굳이 되돌려 보내지 말고 여기서 읽어 준다.
      const text = await file.text()
      return ok({ text: text.replace(/^﻿/, ''), rows: parseRoster(text).rows.length })
    }

    let text: string
    try {
      text = xlsxToText(Buffer.from(await file.arrayBuffer()))
    } catch (error) {
      return fail(error instanceof Error ? error.message : '엑셀 파일을 읽지 못했습니다.')
    }

    if (!text.trim()) return fail('엑셀 첫 장이 비어 있습니다. 명단이 있는 장을 맨 앞으로 옮겨 주세요.')
    return ok({ text, rows: parseRoster(text).rows.length })
  })
}
