import { BRAND } from '@/lib/brand'
import type { DesignTheme } from '@/lib/design/themes'
import { STAGE_SLIDE_H, STAGE_SLIDE_W, type StageSlide } from '@/lib/stage/deck'
import { DEFAULT_STAGE_BACKDROP, type StageBackdrop } from '@/lib/stage/backdrops'
import {
  DEFAULT_PHOTO_SHAPE,
  DEFAULT_STAGE_LAYOUT,
  fallbackLayout,
  PIANO_SAFE_BOTTOM,
  type PhotoShape,
  type StageLayout,
} from '@/lib/stage/layouts'
import { zipStore, type ZipEntry } from '@/lib/stage/zip'

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

/** data:image/...;base64,... → [바이트, 확장자]. 주소(http)는 파일에 넣을 수 없으므로 건너뛴다 */
export function decodeDataUri(uri: string): { bytes: Uint8Array; ext: 'png' | 'jpeg' | 'gif' } | null {
  const match = /^data:image\/(png|jpe?g|gif);base64,([A-Za-z0-9+/=]+)$/i.exec(uri.trim())
  if (!match) return null
  const ext = match[1].toLowerCase().startsWith('jp') ? 'jpeg' : (match[1].toLowerCase() as 'png' | 'gif')
  const binary = typeof atob === 'function' ? atob(match[2]) : Buffer.from(match[2], 'base64').toString('binary')
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  return { bytes, ext }
}

/**
 * 사진 바이트에서 가로·세로를 읽는다.
 * 자리에 맞춰 잘라 넣으려면 원본 비율을 알아야 한다 — 모르면 늘어나거나 여백이 남는다.
 */
export function imageSize(bytes: Uint8Array, ext: string): { width: number; height: number } | null {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  if (ext === 'png' && bytes.length > 24) {
    return { width: view.getUint32(16), height: view.getUint32(20) }
  }
  if (ext === 'jpeg') {
    let i = 2
    while (i + 9 < bytes.length) {
      if (bytes[i] !== 0xff) {
        i += 1
        continue
      }
      const marker = bytes[i + 1]
      if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
        return { height: view.getUint16(i + 5), width: view.getUint16(i + 7) }
      }
      const length = view.getUint16(i + 2)
      if (length < 2) return null
      i += 2 + length
    }
  }
  return null
}

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

/**
 * 사진 한 장. 자리를 **꽉 채우고** 넘치는 부분은 잘라 낸다.
 *
 * 파워포인트는 `srcRect` 로 원본에서 쓸 영역을 정한다. 사진 비율과 자리 비율이
 * 다르면 긴 쪽을 잘라 내야 여백이 남지 않는다 — 여백이 남으면 스크린이 허전해진다.
 */
function picture(
  x: number,
  y: number,
  w: number,
  h: number,
  relId: string,
  source: { width: number; height: number } | null,
  name = '사진',
  geom = 'rect',
): string {
  shapeId += 1
  // 잘라 낼 비율을 1/1000 % 로 적는다
  let crop = '<a:srcRect/>'
  if (source && source.width > 0 && source.height > 0) {
    const boxRatio = w / h
    const imageRatio = source.width / source.height
    if (imageRatio > boxRatio) {
      // 원본이 더 넓다 — 좌우를 잘라 낸다
      const keep = boxRatio / imageRatio
      const side = Math.round(((1 - keep) / 2) * 100_000)
      crop = `<a:srcRect l="${side}" r="${side}"/>`
    } else if (imageRatio < boxRatio) {
      // 원본이 더 길다 — 위아래를 잘라 낸다. 얼굴이 위쪽에 있으므로 아래를 더 자른다
      const keep = imageRatio / boxRatio
      const total = (1 - keep) * 100_000
      const top = Math.round(total * 0.35)
      crop = `<a:srcRect t="${top}" b="${Math.round(total - top)}"/>`
    }
  }
  return (
    `<p:pic><p:nvPicPr><p:cNvPr id="${shapeId}" name="${esc(name)}"/><p:cNvPicPr>` +
    `<a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>` +
    `<p:blipFill>` +
    `<a:blip r:embed="${relId}"/>${crop}<a:stretch><a:fillRect/></a:stretch>` +
    `</p:blipFill>` +
    `<p:spPr><a:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${w}" cy="${h}"/></a:xfrm>` +
    `<a:prstGeom prst="${geom}"><a:avLst/></a:prstGeom></p:spPr></p:pic>`
  )
}

/** 사진 창 모양 → 파워포인트가 아는 도형 이름 */
function shapeGeom(shape: PhotoShape): string {
  switch (shape) {
    case 'circle':
    case 'oval':
      return 'ellipse'
    case 'rounded':
      return 'roundRect'
    case 'square':
      return 'rect'
    case 'arch':
      return 'round2SameRect'
    case 'hexagon':
      return 'hexagon'
    case 'leaf':
      return 'round2DiagRect'
    case 'diamond':
      return 'diamond'
  }
}

/** 도형 하나를 색으로 채운다 (액자 테두리를 뒤에 까는 용도) */
function geomFill(x: number, y: number, w: number, h: number, geom: string, color: string, name: string): string {
  shapeId += 1
  return (
    `<p:sp><p:nvSpPr><p:cNvPr id="${shapeId}" name="${esc(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>` +
    `<p:spPr><a:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${w}" cy="${h}"/></a:xfrm>` +
    `<a:prstGeom prst="${geom}"><a:avLst/></a:prstGeom>` +
    `<a:solidFill><a:srgbClr val="${hex(color)}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>` +
    `<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>`
  )
}

/** 테두리를 두른 카드 */
function frame(x: number, y: number, w: number, h: number, fill: string, border: string, name = '카드'): string {
  shapeId += 1
  return (
    `<p:sp><p:nvSpPr><p:cNvPr id="${shapeId}" name="${esc(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>` +
    `<p:spPr><a:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${w}" cy="${h}"/></a:xfrm>` +
    `<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>` +
    `<a:solidFill><a:srgbClr val="${hex(fill)}"/></a:solidFill>` +
    `<a:ln w="28575"><a:solidFill><a:srgbClr val="${hex(border)}"/></a:solidFill></a:ln></p:spPr>` +
    `<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>`
  )
}

/** 사진 위에 까는 반투명 판 — 그 위 글자가 읽히게 */
function shade(x: number, y: number, w: number, h: number, alpha: number, name = '그늘'): string {
  shapeId += 1
  return (
    `<p:sp><p:nvSpPr><p:cNvPr id="${shapeId}" name="${esc(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>` +
    `<p:spPr><a:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${w}" cy="${h}"/></a:xfrm>` +
    `<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>` +
    `<a:solidFill><a:srgbClr val="000000"><a:alpha val="${Math.round(alpha * 100_000)}"/></a:srgbClr></a:solidFill>` +
    `<a:ln><a:noFill/></a:ln></p:spPr>` +
    `<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>`
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
  paperAlt: string
  ink: string
  muted: string
  accent: string
  accentSoft: string
  line: string
}

function palette(theme: DesignTheme, dark: boolean): Palette {
  const p = theme.palette
  return dark
    ? {
        paper: p.ink,
        paperAlt: p.ink,
        ink: p.paper,
        muted: p.paperAlt,
        accent: p.accent,
        accentSoft: p.accentSoft,
        line: p.accentSoft,
      }
    : {
        paper: p.paper,
        paperAlt: p.paperAlt,
        ink: p.ink,
        muted: p.muted,
        accent: p.accent,
        accentSoft: p.accentSoft,
        line: p.line,
      }
}

/**
 * 무대 배경 — 화면과 같은 그림을 파워포인트 도형으로 그린다.
 * SVG 를 그대로 넣을 수 없으므로 사각형·타원·선으로 같은 인상을 만든다.
 */
function backdropShapes(id: StageBackdrop, theme: DesignTheme, dark: boolean): string[] {
  if (id === 'plain') return []
  const p = theme.palette
  const accent = p.accent
  const deep = p.ink
  const light = p.paper
  const ink = dark ? p.paper : p.ink
  const out: string[] = []

  if (id === 'keys') {
    const whites = 26
    const step = SLIDE_W / whites
    const top = SLIDE_H - px(150)
    out.push(rect(0, top, SLIDE_W, px(150), dark ? deep : light, '건반 바탕'))
    for (let i = 0; i < whites; i += 1) {
      out.push(rect(Math.round(i * step) + px(1), top + px(8), Math.round(step) - px(2), px(142), light, '흰건반'))
    }
    for (let i = 0; i < whites; i += 1) {
      if (![1, 2, 4, 5, 6].includes(i % 7)) continue
      out.push(
        rect(Math.round(i * step + step * 0.62), top + px(8), Math.round(step * 0.62), px(88), deep, '검은건반'),
      )
    }
    out.push(rect(0, top, SLIDE_W, px(7), accent, '건반 띠'))
    return out
  }

  if (id === 'curtain') {
    out.push(shade(0, 0, px(250), SLIDE_H, dark ? 0.28 : 0.14, '왼쪽 커튼'))
    out.push(shade(SLIDE_W - px(250), 0, px(250), SLIDE_H, dark ? 0.28 : 0.14, '오른쪽 커튼'))
    for (let i = 0; i < 6; i += 1) {
      out.push(rect(px(10 + i * 34), 0, px(2), SLIDE_H, accent, '주름'))
      out.push(rect(SLIDE_W - px(12 + i * 34), 0, px(2), SLIDE_H, accent, '주름'))
    }
    out.push(rect(0, 0, SLIDE_W, px(48), accent, '커튼 봉'))
    return out
  }

  if (id === 'spotlight') {
    out.push(geomFill(SLIDE_W / 2 - px(330), 0, px(660), SLIDE_H, 'triangle', accent, '조명 빛'))
    out.push(geomFill(SLIDE_W / 2 - px(340), SLIDE_H - px(94), px(680), px(108), 'ellipse', accent, '무대 바닥'))
    return out
  }

  if (id === 'score') {
    for (const base of [px(110), px(470)]) {
      for (let i = 0; i < 5; i += 1) {
        out.push(rect(0, base + px(i * 17), SLIDE_W, px(2), ink, '오선'))
      }
    }
    for (const [x, y] of [[180, 144], [330, 178], [520, 127], [700, 161], [880, 144], [1060, 178], [250, 504], [470, 538], [760, 487], [1010, 521]]) {
      out.push(geomFill(px(x - 13), px(y - 9), px(26), px(18), 'ellipse', accent, '음표'))
      out.push(rect(px(x + 10), px(y - 56), px(3), px(56), accent, '음표 대'))
    }
    return out
  }

  if (id === 'bokeh') {
    for (const [cx, cy, r] of [[140, 120, 70], [1120, 180, 96], [300, 560, 54], [980, 600, 74], [640, 90, 44], [1210, 460, 60], [60, 420, 48], [820, 300, 36]]) {
      out.push(geomFill(px(cx - r), px(cy - r), px(r * 2), px(r * 2), 'ellipse', accent, '조명 방울'))
    }
    return out
  }

  if (id === 'grand') {
    out.push(geomFill(SLIDE_W - px(640), SLIDE_H - px(140), px(610), px(140), 'round2SameRect', accent, '피아노 몸통'))
    out.push(geomFill(SLIDE_W - px(600), SLIDE_H - px(212), px(520), px(80), 'round2DiagRect', accent, '피아노 뚜껑'))
    out.push(rect(0, SLIDE_H - px(8), SLIDE_W, px(8), accent, '무대 선'))
    return out
  }

  if (id === 'starry') {
    for (let i = 0; i < 40; i += 1) {
      const x = Math.round((((i * 137) % 127) / 127) * STAGE_SLIDE_W)
      const y = Math.round((((i * 61) % 89) / 89) * STAGE_SLIDE_H * 0.72)
      const r = (i % 3) + 1
      out.push(geomFill(px(x), px(y), px(r * 2), px(r * 2), 'ellipse', accent, '별'))
    }
    return out
  }

  if (id === 'ribbon') {
    out.push(rect(0, px(70), SLIDE_W, px(5), accent, '위 띠'))
    out.push(rect(0, px(92), SLIDE_W, px(2), p.accentSoft, '위 가는 띠'))
    out.push(rect(0, SLIDE_H - px(75), SLIDE_W, px(5), accent, '아래 띠'))
    out.push(rect(0, SLIDE_H - px(94), SLIDE_W, px(2), p.accentSoft, '아래 가는 띠'))
    return out
  }

  // arc
  out.push(geomFill(SLIDE_W / 2 - px(430), px(320), px(860), px(640), 'arc', accent, '아치'))
  out.push(rect(0, SLIDE_H - px(10), SLIDE_W, px(10), accent, '무대 선'))
  return out
}

function slideXml(
  slide: StageSlide,
  theme: DesignTheme,
  academyName: string,
  dark: boolean,
  photoRelId: string | null,
  layout: StageLayout,
  photoSize: { width: number; height: number } | null,
  shape: PhotoShape,
  backdrop: StageBackdrop,
): string {
  const c = palette(theme, dark)
  const display = pptFont(theme.fonts.display)
  const body = pptFont(theme.fonts.body)
  const shapes: string[] = [
    ...backdropShapes(backdrop, theme, dark),
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
  } else if (slide.kind === 'performance' && photoRelId) {
    const order = slide.counter?.split('/')[0]?.trim() ?? ''
    const white = '#FFFFFF'
    const safeH = SLIDE_H * (1 - PIANO_SAFE_BOTTOM)

    if (layout === 'photo-frame') {
      const geom = shapeGeom(shape)
      const size = px(420)
      const fx = px(64) + (px(480) - size) / 2
      const fy = (SLIDE_H * (1 - PIANO_SAFE_BOTTOM)) / 2 - size / 2 + px(20)
      // 액자는 테두리가 아니라 뒤에 깔린 같은 모양이다 — 잘라 낸 모양은 테두리가 사라진다
      shapes.push(geomFill(fx - px(16), fy - px(16), size + px(32), size + px(32), geom, c.accent, '액자'))
      shapes.push(geomFill(fx - px(8), fy - px(8), size + px(16), size + px(16), geom, c.paper, '액자 안'))
      shapes.push(picture(fx, fy, size, size, photoRelId, photoSize, `${slide.title} 사진`, geom))

      const tx = px(64) + px(480) + px(52)
      const tw = SLIDE_W - tx - px(64)
      const mid = (SLIDE_H * (1 - PIANO_SAFE_BOTTOM)) / 2 + px(20)
      shapes.push(
        textBox(tx, mid - px(150), tw, px(28), [
          { align: 'l', runs: [{ text: slide.eyebrow ?? '', size: 20, color: c.accent, bold: true, font: body, spacing: 2 }] },
        ]),
      )
      shapes.push(
        textBox(tx, mid - px(114), tw, px(104), [
          { align: 'l', runs: [{ text: slide.title, size: slide.title.length > 7 ? 76 : 92, color: c.ink, bold: true, font: display }] },
        ]),
      )
      shapes.push(rect(tx, mid + px(4), px(260), px(3), c.accent, '가름선'))
      shapes.push(
        textBox(tx, mid + px(26), tw, px(48), [
          { align: 'l', runs: [{ text: slide.subtitle ?? '', size: 34, color: c.ink, bold: true, font: body }] },
        ]),
      )
      if (slide.body) {
        shapes.push(
          textBox(tx, mid + px(88), tw, px(120), [
            { align: 'l', runs: [{ text: slide.body, size: 22, color: c.muted, font: body }], lineHeight: 1.6 },
          ], 't', '곡 해설'),
        )
      }
    } else if (layout === 'photo-side') {
      const photoW = Math.round(SLIDE_W * 0.54)
      shapes.push(picture(0, 0, photoW, SLIDE_H, photoRelId, photoSize, `${slide.title} 사진`))
      const tx = photoW + px(44)
      const tw = SLIDE_W - tx - px(56)
      shapes.push(
        textBox(tx, px(180), tw, px(28), [
          { align: 'l', runs: [{ text: slide.eyebrow ?? '', size: 20, color: c.accent, bold: true, font: body, spacing: 2 }] },
        ]),
      )
      shapes.push(
        textBox(tx, px(214), tw, px(100), [
          { align: 'l', runs: [{ text: slide.title, size: slide.title.length > 7 ? 74 : 88, color: c.ink, bold: true, font: display }] },
        ]),
      )
      shapes.push(rect(tx, px(324), px(220), px(3), c.accent, '가름선'))
      shapes.push(
        textBox(tx, px(346), tw, px(46), [
          { align: 'l', runs: [{ text: slide.subtitle ?? '', size: 32, color: c.ink, bold: true, font: body }] },
        ]),
      )
      if (slide.body) {
        shapes.push(
          textBox(tx, px(404), tw, px(120), [
            { align: 'l', runs: [{ text: slide.body, size: 22, color: c.muted, font: body }], lineHeight: 1.6 },
          ], 't', '곡 해설'),
        )
      }
    } else if (layout === 'photo-band') {
      shapes.push(picture(0, 0, SLIDE_W, SLIDE_H, photoRelId, photoSize, `${slide.title} 사진`))
      shapes.push(shade(0, 0, SLIDE_W, px(280), 0.72, '위쪽 그늘'))
      shapes.push(
        textBox(px(72), px(38), SLIDE_W - px(144), px(30), [
          { align: 'l', runs: [{ text: slide.eyebrow ?? '', size: 21, color: c.accent, bold: true, font: body, spacing: 2 }] },
        ]),
      )
      shapes.push(
        textBox(px(72), px(74), SLIDE_W - px(144), px(100), [
          {
            align: 'l',
            runs: [
              { text: `${slide.title}   `, size: slide.title.length > 7 ? 74 : 88, color: white, bold: true, font: display },
              { text: slide.subtitle ?? '', size: 34, color: white, bold: true, font: body },
            ],
          },
        ]),
      )
      if (slide.body) {
        shapes.push(
          textBox(px(72), px(186), SLIDE_W - px(200), px(70), [
            { align: 'l', runs: [{ text: slide.body, size: 22, color: white, font: body }], lineHeight: 1.5 },
          ], 't', '곡 해설'),
        )
      }
    } else if (layout === 'photo-corner') {
      shapes.push(picture(0, 0, SLIDE_W, SLIDE_H, photoRelId, photoSize, `${slide.title} 사진`))
      shapes.push(shade(0, 0, SLIDE_W, px(300), 0.68, '위쪽 그늘'))
      shapes.push(
        textBox(px(60), px(30), px(300), px(150), [
          { align: 'l', runs: [{ text: order, size: 132, color: c.accent, bold: true, font: display }] },
        ], 't', '순서 번호'),
      )
      const tw = px(820)
      shapes.push(
        textBox(SLIDE_W - px(60) - tw, px(40), tw, px(28), [
          { align: 'r', runs: [{ text: slide.eyebrow ?? '', size: 19, color: c.accent, bold: true, font: body, spacing: 2 }] },
        ]),
      )
      shapes.push(
        textBox(SLIDE_W - px(60) - tw, px(74), tw, px(96), [
          { align: 'r', runs: [{ text: slide.title, size: slide.title.length > 7 ? 72 : 84, color: white, bold: true, font: display }] },
        ]),
      )
      shapes.push(
        textBox(SLIDE_W - px(60) - tw, px(178), tw, px(44), [
          { align: 'r', runs: [{ text: slide.subtitle ?? '', size: 32, color: white, bold: true, font: body }] },
        ]),
      )
    } else {
      // photo-panel — 사진 전체 + 오른쪽 판
      shapes.push(picture(0, 0, SLIDE_W, SLIDE_H, photoRelId, photoSize, `${slide.title} 사진`))
      const panelW = px(500)
      shapes.push(shade(SLIDE_W - panelW - px(120), 0, panelW + px(120), SLIDE_H, 0.5, '오른쪽 그늘'))
      shapes.push(shade(SLIDE_W - panelW, 0, panelW, SLIDE_H, 0.42, '오른쪽 판'))
      const tx = SLIDE_W - panelW + px(48)
      const tw = panelW - px(96)
      const mid = safeH / 2
      shapes.push(
        textBox(tx, mid - px(150), tw, px(28), [
          { align: 'l', runs: [{ text: slide.eyebrow ?? '', size: 20, color: c.accent, bold: true, font: body, spacing: 2 }] },
        ]),
      )
      shapes.push(
        textBox(tx, mid - px(114), tw, px(104), [
          { align: 'l', runs: [{ text: slide.title, size: slide.title.length > 7 ? 76 : 92, color: white, bold: true, font: display }] },
        ]),
      )
      shapes.push(rect(tx, mid + px(2), px(200), px(3), c.accent, '가름선'))
      shapes.push(
        textBox(tx, mid + px(24), tw, px(48), [
          { align: 'l', runs: [{ text: slide.subtitle ?? '', size: 33, color: white, bold: true, font: body }] },
        ]),
      )
      if (slide.body) {
        shapes.push(
          textBox(tx, mid + px(84), tw, px(130), [
            { align: 'l', runs: [{ text: slide.body, size: 21, color: white, font: body }], lineHeight: 1.55 },
          ], 't', '곡 해설'),
        )
      }
    }
  } else if (slide.kind === 'performance') {
    const order = slide.counter?.split('/')[0]?.trim() ?? ''
    if (layout === 'text-number') {
      const bandW = px(340)
      // 강조색 블록 — 어두운 화면에서도 배경에 묻히지 않는다
      shapes.push(rect(0, 0, bandW, SLIDE_H, c.accent, '번호 띠'))
      shapes.push(
        textBox(0, SLIDE_H / 2 - px(120), bandW, px(220), [
          { runs: [{ text: order, size: 200, color: c.paper, bold: true, font: display }] },
        ]),
      )
      const tx = bandW + px(72)
      const tw = SLIDE_W - tx - px(72)
      shapes.push(
        textBox(tx, px(190), tw, px(30), [
          { align: 'l', runs: [{ text: slide.eyebrow ?? '', size: 21, color: c.accent, bold: true, font: body, spacing: 2 }] },
        ]),
      )
      shapes.push(
        textBox(tx, px(228), tw, px(116), [
          { align: 'l', runs: [{ text: slide.title, size: slide.title.length > 8 ? 88 : 104, color: c.ink, bold: true, font: display }] },
        ]),
      )
      shapes.push(rect(tx, px(354), px(280), px(3), c.accent, '가름선'))
      shapes.push(
        textBox(tx, px(378), tw, px(52), [
          { align: 'l', runs: [{ text: slide.subtitle ?? '', size: 38, color: c.ink, bold: true, font: body }] },
        ]),
      )
      if (slide.body) {
        shapes.push(
          textBox(tx, px(444), tw, px(110), [
            { align: 'l', runs: [{ text: slide.body, size: 22, color: c.muted, font: body }], lineHeight: 1.6 },
          ], 't', '곡 해설'),
        )
      }
    } else if (layout === 'text-card') {
      const cardX = px(90)
      const cardY = px(56)
      const cardW = SLIDE_W - cardX * 2
      const cardH = SLIDE_H * (1 - PIANO_SAFE_BOTTOM) - cardY
      shapes.push(frame(cardX, cardY, cardW, cardH, c.paperAlt, c.accent, '카드'))
      shapes.push(
        textBox(cardX, cardY + px(46), cardW, px(30), [
          { runs: [{ text: slide.eyebrow ?? '', size: 21, color: c.accent, bold: true, font: body, spacing: 2 }] },
        ]),
      )
      shapes.push(
        textBox(cardX, cardY + px(84), cardW, px(108), [
          { runs: [{ text: slide.title, size: slide.title.length > 8 ? 80 : 96, color: c.ink, bold: true, font: display }] },
        ]),
      )
      shapes.push(rect(SLIDE_W / 2 - px(160), cardY + px(200), px(320), px(3), c.accent, '가름선'))
      shapes.push(
        textBox(cardX, cardY + px(222), cardW, px(50), [
          { runs: [{ text: slide.subtitle ?? '', size: 36, color: c.ink, bold: true, font: body }] },
        ]),
      )
      if (slide.body) {
        shapes.push(
          textBox(cardX + px(60), cardY + px(288), cardW - px(120), px(110), [
            { runs: [{ text: slide.body, size: 22, color: c.muted, font: body }], lineHeight: 1.6 },
          ], 't', '곡 해설'),
        )
      }
    } else {
      // text-hero — 이름만 크게. 아래쪽(피아노에 가리는 자리)은 비워 둔다
      const mid = (SLIDE_H * (1 - PIANO_SAFE_BOTTOM)) / 2
      shapes.push(
        textBox(pad, mid - px(180), width, px(32), [
          { runs: [{ text: slide.eyebrow ?? '', size: 22, color: c.accent, bold: true, font: body, spacing: 2 }] },
        ]),
      )
      shapes.push(
        textBox(pad, mid - px(140), width, px(126), [
          { runs: [{ text: slide.title, size: slide.title.length > 8 ? 96 : 116, color: c.ink, bold: true, font: display }] },
        ]),
      )
      shapes.push(rect(SLIDE_W / 2 - px(180), mid + px(6), px(360), px(3), c.accentSoft, '가름선'))
      shapes.push(
        textBox(pad, mid + px(30), width, px(56), [
          { runs: [{ text: slide.subtitle ?? '', size: 40, color: c.ink, bold: true, font: body }] },
        ]),
      )
      if (slide.body) {
        shapes.push(
          textBox(px(200), mid + px(104), SLIDE_W - px(400), px(120), [
            { runs: [{ text: slide.body, size: 23, color: c.muted, font: body }], lineHeight: 1.6 },
          ], 't', '곡 해설'),
        )
      }
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

  // 연주자 화면에는 아래 줄을 두지 않는다 — 그랜드피아노 뚜껑이 가리는 자리다
  if (slide.kind !== 'performance') {
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
  layout = DEFAULT_STAGE_LAYOUT,
  shape = DEFAULT_PHOTO_SHAPE,
  backdrop = DEFAULT_STAGE_BACKDROP,
}: {
  slides: StageSlide[]
  theme: DesignTheme
  academyName: string
  title: string
  dark?: boolean
  /** 연주자 화면 모양 */
  layout?: StageLayout
  /** 아이 사진을 담는 창 모양 */
  shape?: PhotoShape
  /** 무대 배경 그림 */
  backdrop?: StageBackdrop
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

  const slideRels = (photoTarget: string | null) =>
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="${RELS_NS}">` +
    `<Relationship Id="rId1" Type="${DOC_REL}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>` +
    (photoTarget ? `<Relationship Id="rId2" Type="${DOC_REL}/image" Target="../media/${photoTarget}"/>` : '') +
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
    `<Application>${BRAND.slug}</Application><Slides>${count}</Slides></Properties>`

  const entries: ZipEntry[] = [
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
  // 사진은 ppt/media/ 에 실제 파일로 넣는다. 같은 사진을 두 번 담지 않게 모아 둔다
  const media = new Map<string, { file: string; ext: string; size: { width: number; height: number } | null }>()
  const photoOf = (slide: StageSlide) => {
    if (!slide.photo) return null
    const known = media.get(slide.photo)
    if (known) return known
    const decoded = decodeDataUri(slide.photo)
    if (!decoded) return null // http 주소는 파일에 넣을 수 없다 — 사진 없이 그린다
    const file = `image${media.size + 1}.${decoded.ext === 'jpeg' ? 'jpg' : decoded.ext}`
    const entry = { file, ext: decoded.ext, size: imageSize(decoded.bytes, decoded.ext) }
    media.set(slide.photo, entry)
    entries.push({ name: `ppt/media/${file}`, data: decoded.bytes })
    return entry
  }

  slides.forEach((slide, index) => {
    const photo = photoOf(slide)
    // 사진이 없으면 사진용 모양 대신 글자 모양으로 내려간다 — 빈 상자를 찍지 않는다
    const used = photo ? layout : fallbackLayout(layout)
    entries.push({
      name: `ppt/slides/slide${index + 1}.xml`,
      data: bytes(
        slideXml(slide, theme, academyName, dark, photo ? 'rId2' : null, used, photo?.size ?? null, shape, backdrop),
      ),
    })
    entries.push({ name: `ppt/slides/_rels/slide${index + 1}.xml.rels`, data: bytes(slideRels(photo?.file ?? null)) })
  })

  // 그림 확장자는 [Content_Types].xml 에 선언해야 파워포인트가 연다
  const extensions = new Set([...media.values()].map((entry) => (entry.ext === 'jpeg' ? 'jpg' : entry.ext)))
  if (extensions.size > 0) {
    const defaults = [...extensions]
      .map((ext) => `<Default Extension="${ext}" ContentType="image/${ext === 'jpg' ? 'jpeg' : ext}"/>`)
      .join('')
    const index = entries.findIndex((entry) => entry.name === '[Content_Types].xml')
    entries[index] = {
      name: '[Content_Types].xml',
      data: bytes(contentTypes.replace('<Default Extension="xml"', `${defaults}<Default Extension="xml"`)),
    }
  }

  return zipStore(entries)
}
