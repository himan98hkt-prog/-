import { Certificates, NameTags, SocialCard, ThankYouCards, TicketStrip } from '@/components/design/templates/cards'
import { ProgramBifold, ProgramCover, ProgramInner } from '@/components/design/templates/program'
import { PosterClassic, PosterModern, PosterPhoto, PosterProgram } from '@/components/design/templates/posters'
import type { DesignContext } from '@/lib/design/context'

/**
 * 템플릿 id → 실제 인쇄면.
 * 미리보기에서는 반복 양식(상장·이름표)을 앞부분만 그린다.
 */
export function renderTemplate(templateId: string, ctx: DesignContext, preview = false) {
  switch (templateId) {
    case 'poster-modern':
      return <PosterModern ctx={ctx} />
    case 'poster-photo':
      return <PosterPhoto ctx={ctx} />
    case 'poster-program':
      return <PosterProgram ctx={ctx} />
    case 'program-cover':
      return <ProgramCover ctx={ctx} />
    case 'program-inner':
      return <ProgramInner ctx={ctx} />
    case 'program-bifold':
      return <ProgramBifold ctx={ctx} />
    case 'ticket-strip':
      return <TicketStrip ctx={ctx} />
    case 'social-card':
      return <SocialCard ctx={ctx} />
    case 'thankyou-card':
      return <ThankYouCards ctx={ctx} />
    case 'certificate':
      return <Certificates ctx={ctx} limit={preview ? 1 : undefined} />
    case 'nametag':
      return <NameTags ctx={ctx} limitSheets={preview ? 1 : undefined} />
    default:
      return <PosterClassic ctx={ctx} />
  }
}
