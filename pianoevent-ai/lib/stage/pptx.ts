import type { DesignTheme } from '@/lib/design/themes'
import { STAGE_SLIDE_H, STAGE_SLIDE_W, type StageSlide } from '@/lib/stage/deck'
import { zipStore } from '@/lib/stage/zip'

/**
 * 무대 화면 → 진짜 파워포인트 파일(.pptx).
 *
 * PDF 는 열어서 넘기기만 됩니다. 원장님이 공연장에서 이름 하나를 고치려면 파워포인트여야 합니다.
 * 그래서 슬라이드를 그림이 아니라 **글상자**로 만듭니다 — 열어서 바로 고칠 수 있습니다.
 *
 * 테마의 색과 서체를 그대로 옮기므로, 고른 테마가 바뀌면 파워포인트 파일도 함께 바뀝니다.
 * 외부 라이브러리를 쓰지 않습니다 (`zip.ts` + XML). 인터넷 없이 이 컴퓨터에서 만들어집니다.
 */

/** 화면 1px = 9525 EMU. 1280×720 이 16:9 슬라이드(13.333in × 7.5in)와 정확히 맞아떨어진다 */
const EMU = 9525
const px = (value: number) => Math.round(value * EMU)
/** 화면 px → 파워포인트 글자 크기(1/100 pt). 96dpi 기준 1px = 0.75pt */
const pt = (value: number) => Math.round(value * 75)

const SLIDE_W = px(STAGE_SLIDE_W)
const SLIDE_H = px(STAGE_SLIDE_H)

const encoder = new TextEncoder()
const bytes = (text: string) => encoder.encode(text)
const hex = (color: string) => color.replace('#', '').toUpperCase().slice(0, 6)

function esc(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * CSS 서체 묶음에서 윈도우·맥에 실제로 깔려 있는 이름 하나를 고른다.
 * 웹폰트 이름을 그대로 넣으면 파워포인트가 못 찾아 엉뚱한 글꼴로 바뀐다.
 */
export function pptFont(stack: string): string {
  const lowered = stack.toLowerCase()
  if (lowered.includes('gaegu') || lowered.includes('gungsuh')) return '궁서'
  if (lowered.includes('jua')) return '맑은 고딕'
  // 'sans-serif' 안에 'serif' 가 들어 있다. 먼저 걸러 내지 않으면 고딕 테마가 전부 명조로 나간다.
  if (lowered.includes('sans')) return '맑은 고딕'
  if (lowered.includes('myeongjo') || lowered.includes('batang') || lowered.includes('serif')) return '바탕'
  return '맑은 고딕'
}

interface Run {
  text: string
  size: number
  color: string
  bold?: boolean
  font: string
  spacing?: number
}

interface Para {
  runs: Run[]
  align?: 'l' | 'ctr' | 'r'
  /** 줄 간격 (백분율) */
  lineHeight?: number
  spaceBefore?: number
}

let shapeId = 1

function runXml(run: Run): string {
  const spacing = run.spacing ? ` spc="${Math.round(run.spacing * 100)}"` : ''
  return (
    `<a:r><a:rPr lang="ko-KR" altLang="en-US" sz="${pt(run.size)}" b="${run.bold ? 1 : 0}"${spacing} dirty="0">` +
    `<a:solidFill><a:srgbClr val="${hex(run.color)}"/></a:solidFill>` +
    `<a:latin typeface="${esc(run.font)}"/><a:ea typeface="${esc(run.font)}"/><a:cs typeface="${esc(run.font)}"/>` +
    `</a:rPr><a:t>${esc(run.text)}</a:t></a:r>`
  )
}

function textBox(
  x: number,
  y: number,
  w: number,
  h: number,
  paras: Para[],
  anchor: 't' | 'ctr' | 'b' = 'ctr',
  name = '글상자',
): string {
  shapeId += 1
  const body = paras
    .map((para) => {
      // spcPct 는 10만분율이다 — 160% 는 160000. 1600 으로 적으면 줄이 겹쳐 글자가 사라진다.
      const props =
        `<a:pPr algn="${para.align ?? 'ctr'}">` +
        `${para.lineHeight ? `<a:lnSpc><a:spcPct val="${Math.round(para.lineHeight * 100_000)}"/></a:lnSpc>` : ''}` +
        `${para.spaceBefore ? `<a:spcBef><a:spcPts val="${pt(para.spaceBefore)}"/></a:spcBef>` : ''}` +
        `</a:pPr>`
      return `<a:p>${props}${para.runs.map(runXml).join('')}</a:p>`
    })
    .join('')
  return (
    `<p:sp><p:nvSpPr><p:cNvPr id="${shapeId}" name="${esc(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>` +
    `<p:spPr><a:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${w}" cy="${h}"/></a:xfrm>` +
    `<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>` +
    `<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="${anchor}"><a:normAutofit/></a:bodyPr>` +
    `<a:lstStyle/>${body}</p:txBody></p:sp>`
  )
}

function rect(x: number, y: number, w: number, h: number, color: string, name = '띠'): string {
  shapeId += 1
  return (
    `<p:sp><p:nvSpPr><p:cNvPr id="${shapeId}" name="${esc(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>` +
    `<p:spPr><a:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${w}" cy="${h}"/></a:xfrm>` +
    `<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>` +
    `<a:solidFill><a:srgbClr val="${hex(color)}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>` +
    `<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>`
  )
}

interface Palette {
  paper: string
  ink: string
  muted: string
  accent: string
  accentSoft: string
  line: string
}

function palette(theme: DesignTheme, dark: boolean): Palette {
  const p = theme.palette
  return dark
    ? { paper: p.ink, ink: p.paper, muted: p.paperAlt, accent: p.accent, accentSoft: p.accentSoft, line: p.accentSoft }
    : { paper: p.paper, ink: p.ink, muted: p.muted, accent: p.accent, accentSoft: p.accentSoft, line: p.line }
}

function slideXml(slide: StageSlide, theme: DesignTheme, academyName: string, dark: boolean): string {
  const c = palette(theme, dark)
  const display = pptFont(theme.fonts.display)
  const body = pptFont(theme.fonts.body)
  const shapes: string[] = [
    rect(0, 0, SLIDE_W, px(8), c.accent, '윗띠'),
    rect(0, SLIDE_H - px(3), SLIDE_W, px(3), c.accentSoft, '아랫띠'),
  ]

  const pad = px(88)
  const width = SLIDE_W - pad * 2

  if (slide.kind === 'agenda' && slide.lines) {
    shapes.push(
      textBox(pad, px(52), width, px(30), [
        { runs: [{ text: slide.eyebrow ?? '오늘의 순서', size: 20, color: c.accent, bold: true, font: body, spacing: 2 }] },
      ]),
    )
    shapes.push(
      textBox(pad, px(88), width, px(28), [
        { runs: [{ text: slide.title, size: 22, color: c.muted, font: body }] },
      ]),
    )
    const rows = slide.lines
    const half = Math.ceil(rows.length / 2)
    const columns = rows.length > 6 ? [rows.slice(0, half), rows.slice(half)] : [rows]
    const colWidth = columns.length > 1 ? (width - px(44)) / 2 : width
    columns.forEach((column, index) => {
      shapes.push(
        textBox(
          pad + index * (colWidth + px(44)),
          px(132),
          colWidth,
          px(510),
          column.map((line) => ({
            align: 'l' as const,
            spaceBefore: 9,
            runs: [
              { text: `${line.no}   `, size: 22, color: c.accent, bold: true, font: body },
              { text: `${line.name}   `, size: 25, color: c.ink, bold: true, font: body },
              { text: line.piece, size: 19, color: c.muted, font: body },
            ],
          })),
          't',
          '오늘의 순서',
        ),
      )
    })
  } else if (slide.kind === 'performance') {
    shapes.push(
      textBox(pad, px(196), width, px(30), [
        { runs: [{ text: slide.eyebrow ?? '', size: 21, color: c.accent, bold: true, font: body, spacing: 2 }] },
      ]),
    )
    shapes.push(
      textBox(pad, px(232), width, px(120), [
        { runs: [{ text: slide.title, size: slide.title.length > 8 ? 84 : 104, color: c.ink, bold: true, font: display }] },
      ]),
    )
    shapes.push(rect(SLIDE_W / 2 - px(60), px(372), px(120), px(2), c.accentSoft, '가름선'))
    shapes.push(
      textBox(pad, px(392), width, px(52), [
        { runs: [{ text: slide.subtitle ?? '', size: 38, color: c.ink, bold: true, font: body }] },
      ]),
    )
    if (slide.body) {
      shapes.push(
        textBox(px(200), px(460), SLIDE_W - px(400), px(120), [
          { runs: [{ text: slide.body, size: 23, color: c.muted, font: body }], lineHeight: 1.6 },
        ], 't', '곡 해설'),
      )
    }
  } else if (slide.kind === 'section') {
    shapes.push(
      textBox(pad, px(228), width, px(32), [
        { runs: [{ text: slide.eyebrow ?? '', size: 22, color: c.accent, bold: true, font: body, spacing: 2 }] },
      ]),
    )
    shapes.push(
      textBox(pad, px(272), width, px(130), [
        { runs: [{ text: slide.title, size: 108, color: c.ink, bold: true, font: display }] },
      ]),
    )
    shapes.push(
      textBox(pad, px(420), width, px(46), [
        { runs: [{ text: slide.subtitle ?? '', size: 30, color: c.muted, font: body }] },
      ]),
    )
  } else {
    // 대기 · 휴식 · 폐회 — 표지 성격
    shapes.push(
      textBox(pad, px(190), width, px(32), [
        { runs: [{ text: slide.eyebrow ?? '', size: 22, color: c.accent, bold: true, font: body, spacing: 2 }] },
      ]),
    )
    shapes.push(
      textBox(pad, px(234), width, px(120), [
        { runs: [{ text: slide.title, size: slide.title.length > 14 ? 74 : 96, color: c.ink, bold: true, font: display }] },
      ]),
    )
    if (slide.subtitle) {
      shapes.push(
        textBox(pad, px(372), width, px(46), [
          { runs: [{ text: slide.subtitle, size: 30, color: c.muted, font: body }] },
        ]),
      )
    }
    if (slide.body) {
      shapes.push(
        textBox(
          pad,
          px(436),
          width,
          px(120),
          slide.body.split('\n').map((line) => ({
            runs: [{ text: line, size: 23, color: c.muted, font: body }],
            lineHeight: 1.7,
          })),
          't',
          '안내',
        ),
      )
    }
  }

  shapes.push(
    textBox(pad, SLIDE_H - px(48), px(400), px(26), [
      { align: 'l', runs: [{ text: academyName, size: 17, color: c.muted, font: body }] },
    ], 'ctr', '학원 이름'),
  )
  if (slide.counter) {
    shapes.push(
      textBox(SLIDE_W - pad - px(400), SLIDE_H - px(48), px(400), px(26), [
        { align: 'r', runs: [{ text: slide.counter, size: 17, color: c.muted, font: body }] },
      ], 'ctr', '순서 번호'),
    )
  }

  return (
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" ` +
    `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ` +
    `xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">` +
    `<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="${hex(c.paper)}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>` +
    `<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>` +
    `<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>` +
    shapes.join('') +
    `</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>`
  )
}

const RELS_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
const DOC_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

function themeXml(theme: DesignTheme): string {
  const display = pptFont(theme.fonts.display)
  const body = pptFont(theme.fonts.body)
  const p = theme.palette
  const scheme = [p.paper, p.ink, p.paperAlt, p.ink, p.accent, p.accentSoft, p.band, p.muted, p.line, p.accent, p.ink, p.muted]
  const names = ['dk1', 'lt1', 'dk2', 'lt2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6', 'hlink', 'folHlink']
  const colors = names
    .map((name, index) => `<a:${name}><a:srgbClr val="${hex(scheme[index])}"/></a:${name}>`)
    .join('')
  const fill =
    `<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>` +
    `<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>` +
    `<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>`
  const line = `<a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>`
  return (
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="${esc(theme.name)}">` +
    `<a:themeElements><a:clrScheme name="${esc(theme.name)}">${colors}</a:clrScheme>` +
    `<a:fontScheme name="${esc(theme.name)}">` +
    `<a:majorFont><a:latin typeface="${esc(display)}"/><a:ea typeface="${esc(display)}"/><a:cs typeface=""/></a:majorFont>` +
    `<a:minorFont><a:latin typeface="${esc(body)}"/><a:ea typeface="${esc(body)}"/><a:cs typeface=""/></a:minorFont>` +
    `</a:fontScheme>` +
    `<a:fmtScheme name="${esc(theme.name)}">` +
    `<a:fillStyleLst>${fill}</a:fillStyleLst>` +
    `<a:lnStyleLst>${line}${line}${line}</a:lnStyleLst>` +
    `<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>` +
    `<a:bgFillStyleLst>${fill}</a:bgFillStyleLst>` +
    `</a:fmtScheme></a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>`
  )
}

const SLIDE_MASTER =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" ` +
  `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ` +
  `xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">` +
  `<p:cSld><p:bg><p:bgPr><a:solidFill><a:schemeClr val="bg1"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>` +
  `<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>` +
  `<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>` +
  `</p:spTree></p:cSld>` +
  `<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" ` +
  `accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>` +
  `<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>` +
  `</p:sldMaster>`

const SLIDE_LAYOUT =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" ` +
  `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ` +
  `xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">` +
  `<p:cSld name="빈 화면"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>` +
  `<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>` +
  `</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>`

/**
 * 무대 화면 슬라이드 → .pptx 파일 바이트.
 * 결과는 입력이 같으면 항상 같다 (시각을 기록하지 않는다) — 시험할 수 있다.
 */
export function buildPptx({
  slides,
  theme,
  academyName,
  title,
  dark = false,
}: {
  slides: StageSlide[]
  theme: DesignTheme
  academyName: string
  title: string
  dark?: boolean
}): Uint8Array {
  shapeId = 1
  const count = slides.length

  const contentTypes =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
    `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>` +
    `<Default Extension="xml" ContentType="application/xml"/>` +
    `<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>` +
    `<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>` +
    `<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>` +
    `<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>` +
    `<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>` +
    `<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>` +
    slides
      .map(
        (_, index) =>
          `<Override PartName="/ppt/slides/slide${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>`,
      )
      .join('') +
    `</Types>`

  const rootRels =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="${RELS_NS}">` +
    `<Relationship Id="rId1" Type="${DOC_REL}/officeDocument" Target="ppt/presentation.xml"/>` +
    `<Relationship Id="rId2" Type="${DOC_REL}/metadata/core-properties" Target="docProps/core.xml"/>` +
    `<Relationship Id="rId3" Type="${DOC_REL}/extended-properties" Target="docProps/app.xml"/>` +
    `</Relationships>`

  const presentationRels =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="${RELS_NS}">` +
    `<Relationship Id="rId1" Type="${DOC_REL}/slideMaster" Target="slideMasters/slideMaster1.xml"/>` +
    slides
      .map(
        (_, index) =>
          `<Relationship Id="rId${index + 2}" Type="${DOC_REL}/slide" Target="slides/slide${index + 1}.xml"/>`,
      )
      .join('') +
    `<Relationship Id="rId${count + 2}" Type="${DOC_REL}/theme" Target="theme/theme1.xml"/>` +
    `</Relationships>`

  const presentation =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" ` +
    `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ` +
    `xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" saveSubsetFonts="1">` +
    `<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>` +
    `<p:sldIdLst>` +
    slides.map((_, index) => `<p:sldId id="${256 + index}" r:id="rId${index + 2}"/>`).join('') +
    `</p:sldIdLst>` +
    `<p:sldSz cx="${SLIDE_W}" cy="${SLIDE_H}"/><p:notesSz cx="${SLIDE_H}" cy="${SLIDE_W}"/>` +
    `</p:presentation>`

  const masterRels =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="${RELS_NS}">` +
    `<Relationship Id="rId1" Type="${DOC_REL}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>` +
    `<Relationship Id="rId2" Type="${DOC_REL}/theme" Target="../theme/theme1.xml"/>` +
    `</Relationships>`

  const layoutRels =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="${RELS_NS}">` +
    `<Relationship Id="rId1" Type="${DOC_REL}/slideMaster" Target="../slideMasters/slideMaster1.xml"/>` +
    `</Relationships>`

  const slideRels =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="${RELS_NS}">` +
    `<Relationship Id="rId1" Type="${DOC_REL}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>` +
    `</Relationships>`

  const core =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" ` +
    `xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" ` +
    `xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">` +
    `<dc:title>${esc(title)}</dc:title><dc:creator>${esc(academyName)}</dc:creator>` +
    `<cp:lastModifiedBy>${esc(academyName)}</cp:lastModifiedBy></cp:coreProperties>`

  const app =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" ` +
    `xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">` +
    `<Application>PianoEvent</Application><Slides>${count}</Slides></Properties>`

  const entries = [
    { name: '[Content_Types].xml', data: bytes(contentTypes) },
    { name: '_rels/.rels', data: bytes(rootRels) },
    { name: 'docProps/core.xml', data: bytes(core) },
    { name: 'docProps/app.xml', data: bytes(app) },
    { name: 'ppt/presentation.xml', data: bytes(presentation) },
    { name: 'ppt/_rels/presentation.xml.rels', data: bytes(presentationRels) },
    { name: 'ppt/slideMasters/slideMaster1.xml', data: bytes(SLIDE_MASTER) },
    { name: 'ppt/slideMasters/_rels/slideMaster1.xml.rels', data: bytes(masterRels) },
    { name: 'ppt/slideLayouts/slideLayout1.xml', data: bytes(SLIDE_LAYOUT) },
    { name: 'ppt/slideLayouts/_rels/slideLayout1.xml.rels', data: bytes(layoutRels) },
    { name: 'ppt/theme/theme1.xml', data: bytes(themeXml(theme)) },
  ]
  slides.forEach((slide, index) => {
    entries.push({ name: `ppt/slides/slide${index + 1}.xml`, data: bytes(slideXml(slide, theme, academyName, dark)) })
    entries.push({ name: `ppt/slides/_rels/slide${index + 1}.xml.rels`, data: bytes(slideRels) })
  })

  return zipStore(entries)
}
