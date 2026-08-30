import { ArtPoster } from '@/components/design/templates/art-poster'
import {
  BookletCover,
  BookletInner,
  PerformerTags,
  ProgramLarge,
  ProgramMemo,
  SeatTicketSheet,
  StageCueCards,
  StageDivider,
  ThankYouBookmarks,
  TicketSheet,
} from '@/components/design/templates/program-book'
import { Certificates, NameTags, SocialCard, ThankYouCards, TicketStrip } from '@/components/design/templates/cards'
import { ChecklistSheet, CueSheet } from '@/components/design/templates/ops'
import { ProgramBifold, ProgramCover, ProgramInner } from '@/components/design/templates/program'
import {
  PosterClassic,
  PosterFullBleed,
  PosterModern,
  PosterPhoto,
  PosterProgram,
} from '@/components/design/templates/posters'
import { InvitationCards, StoryCard, BannerStand } from '@/components/design/templates/invites'
import {
  AfterNotice,
  AttendanceSheet,
  BudgetSheet,
  McScriptSheet,
  ProjectorCard,
  ParentNotice,
  PracticeLog,
  RehearsalSheet,
  StudentNotice,
} from '@/components/design/templates/ops-extra'
import {
  BannerHorizontal,
  GuestBook,
  PerformerCards,
  Signage,
  StageMap,
  ThanksLetter,
} from '@/components/design/templates/venue'
import { PosterDuo, PosterTypographic } from '@/components/design/templates/posters-extra'
import { ProgramNotes, ProgramTrifold } from '@/components/design/templates/program-extra'
import { AwardSheet, BackstageBoard, PhotoZone, SeatingChart } from '@/components/design/templates/stage'
import type { DesignContext } from '@/lib/design/context'

/**
 * 템플릿 id → 실제 인쇄면.
 * 미리보기에서는 반복 양식(상장·이름표)을 앞부분만 그린다.
 */
export function renderTemplate(templateId: string, ctx: DesignContext, preview = false) {
  switch (templateId) {
    case 'poster-modern':
      return <PosterModern ctx={ctx} />
    case 'art-stage-piano':
      return <ArtPoster ctx={ctx} artId="stage-piano" />
    case 'art-oil-hall':
      return <ArtPoster ctx={ctx} artId="oil-hall" />
    case 'art-keys':
      return <ArtPoster ctx={ctx} artId="keys-close" />
    case 'art-hands':
      return <ArtPoster ctx={ctx} artId="child-hands" />
    case 'art-gala':
      return <ArtPoster ctx={ctx} artId="gala-bokeh" />
    case 'art-field':
      return <ArtPoster ctx={ctx} artId="light-field" />
    case 'art-watercolor':
      return <ArtPoster ctx={ctx} artId="watercolor-piano" />
    case 'art-blossom':
      return <ArtPoster ctx={ctx} artId="blossom-piano" />
    case 'art-summer':
      return <ArtPoster ctx={ctx} artId="summer-window" />
    case 'art-autumn':
      return <ArtPoster ctx={ctx} artId="autumn-leaves" />
    case 'art-christmas':
      return <ArtPoster ctx={ctx} artId="christmas-pine" />
    case 'art-confetti':
      return <ArtPoster ctx={ctx} artId="confetti-night" />
    case 'art-line-front':
      return <ArtPoster ctx={ctx} artId="line-front" />
    case 'art-line-keys':
      return <ArtPoster ctx={ctx} artId="line-keys" />
    case 'art-line-arch':
      return <ArtPoster ctx={ctx} artId="line-arch" />
    case 'art-ill-line':
      return <ArtPoster ctx={ctx} artId="ill-line" />
    case 'art-ill-engraving':
      return <ArtPoster ctx={ctx} artId="ill-engraving" />
    case 'art-ill-riso':
      return <ArtPoster ctx={ctx} artId="ill-riso" />
    case 'art-ill-ink':
      return <ArtPoster ctx={ctx} artId="ill-ink" />
    case 'art-ill-deco':
      return <ArtPoster ctx={ctx} artId="ill-deco" />
    case 'art-real-stage':
      return <ArtPoster ctx={ctx} artId="real-stage" />
    case 'art-real-keys':
      return <ArtPoster ctx={ctx} artId="real-keys" />
    case 'art-real-hands':
      return <ArtPoster ctx={ctx} artId="real-hands" />
    case 'poster-fullbleed':
      return <PosterFullBleed ctx={ctx} />
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
    case 'cue-sheet':
      return <CueSheet ctx={ctx} />
    case 'checklist':
      return <ChecklistSheet ctx={ctx} />
    case 'certificate':
      return <Certificates ctx={ctx} limit={preview ? 1 : undefined} />
    case 'certificate-gold':
      return <Certificates ctx={ctx} limit={preview ? 1 : undefined} gold />
    case 'nametag':
      return <NameTags ctx={ctx} limitSheets={preview ? 1 : undefined} />
    case 'poster-typographic':
      return <PosterTypographic ctx={ctx} />
    case 'poster-duo':
      return <PosterDuo ctx={ctx} />
    case 'program-notes':
      return <ProgramNotes ctx={ctx} />
    case 'program-trifold':
      return <ProgramTrifold ctx={ctx} />
    case 'invitation-card':
      return <InvitationCards ctx={ctx} />
    case 'story-card':
      return <StoryCard ctx={ctx} />
    case 'banner-stand':
      return <BannerStand ctx={ctx} />
    case 'seating-chart':
      return <SeatingChart ctx={ctx} />
    case 'backstage-board':
      return <BackstageBoard ctx={ctx} />
    case 'photo-zone':
      return <PhotoZone ctx={ctx} />
    case 'award-sheet':
      return <AwardSheet ctx={ctx} />
    case 'mc-script':
      return <McScriptSheet ctx={ctx} />
    case 'projector-card':
      return <ProjectorCard ctx={ctx} />
    case 'rehearsal-sheet':
      return <RehearsalSheet ctx={ctx} />
    case 'attendance-sheet':
      return <AttendanceSheet ctx={ctx} />
    case 'budget-sheet':
      return <BudgetSheet ctx={ctx} />
    case 'parent-notice':
      return <ParentNotice ctx={ctx} />
    case 'student-notice':
      return <StudentNotice ctx={ctx} />
    case 'stage-map':
      return <StageMap ctx={ctx} />
    case 'banner-horizontal':
      return <BannerHorizontal ctx={ctx} />
    case 'signage':
      return <Signage ctx={ctx} />
    case 'practice-log':
      return <PracticeLog ctx={ctx} />
    case 'performer-cards':
      return <PerformerCards ctx={ctx} limitSheets={preview ? 1 : undefined} />
    case 'guestbook':
      return <GuestBook ctx={ctx} />
    case 'thanks-letter':
      return <ThanksLetter ctx={ctx} />
    case 'after-notice':
      return <AfterNotice ctx={ctx} />
    case 'booklet-cover':
      return <BookletCover ctx={ctx} />
    case 'booklet-inner':
      return <BookletInner ctx={ctx} />
    case 'program-large':
      return <ProgramLarge ctx={ctx} />
    case 'program-memo':
      return <ProgramMemo ctx={ctx} />
    case 'ticket-sheet':
      return <TicketSheet ctx={ctx} />
    case 'seat-ticket':
      return <SeatTicketSheet ctx={ctx} />
    case 'performer-tags':
      return <PerformerTags ctx={ctx} />
    case 'cue-cards':
      return <StageCueCards ctx={ctx} />
    case 'thankyou-bookmark':
      return <ThankYouBookmarks ctx={ctx} />
    case 'stage-divider':
      return <StageDivider ctx={ctx} />
    default:
      return <PosterClassic ctx={ctx} />
  }
}
