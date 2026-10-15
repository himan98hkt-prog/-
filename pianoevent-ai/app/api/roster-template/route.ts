import { rosterTemplateCsv } from '@/lib/program/template'

/**
 * 명단 양식 파일 내려받기.
 * 엑셀에서 바로 열리는 CSV 다 — 이름만 바꿔 저장하고 붙여넣으시면 된다.
 */
export function GET() {
  return new Response(rosterTemplateCsv(), {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="roster.csv"; filename*=UTF-8''${encodeURIComponent('학생명단 양식.csv')}`,
      'Cache-Control': 'no-store',
    },
  })
}
