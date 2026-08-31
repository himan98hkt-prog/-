"""
테마 60종을 만들어 lib/design/themes.ts 에 덧붙인다.

  python3 scripts/gen-themes.py

색은 핵심 네 가지(paper · ink · accent · band)만 손으로 정하고
나머지(paperAlt · accentSoft · line · muted · bandInk)는 그 넷에서 파생시킨다.
사람이 20개 값을 손으로 맞추면 조화가 깨지고 대비가 틀어진다.

만든 뒤에는 반드시 대비 검사를 돌린다 — tests/design.test.ts 가 막아 준다.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / 'lib' / 'design' / 'themes.ts'


# ── 색 계산 ───────────────────────────────────────────────────
def hex2rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(c):
    return '#' + ''.join(f'{max(0, min(255, round(v))):02x}' for v in c)


def mix(a, b, t):
    """a 를 b 쪽으로 t 만큼 섞는다"""
    ca, cb = hex2rgb(a), hex2rgb(b)
    return rgb2hex([ca[i] + (cb[i] - ca[i]) * t for i in range(3)])


def lum(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = hex2rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    x, y = sorted([lum(a), lum(b)], reverse=True)
    return (x + 0.05) / (y + 0.05)


def darken_until(color, against, target, limit=200):
    """색조는 지키고 밝기만 낮춰 목표 대비를 맞춘다"""
    cur = color
    for _ in range(limit):
        if contrast(cur, against) >= target:
            return cur
        cur = mix(cur, '#000000', 0.02)
    return cur


def lighten_until(color, against, target, limit=200):
    cur = color
    for _ in range(limit):
        if contrast(cur, against) >= target:
            return cur
        cur = mix(cur, '#ffffff', 0.02)
    return cur


def derive(paper, ink, accent, band):
    """핵심 4색에서 나머지를 만든다. 밝은 종이와 어두운 종이를 나눠 다룬다."""
    dark = lum(paper) < 0.35

    if dark:
        paper_alt = mix(paper, '#ffffff', 0.07)
        line = mix(paper, ink, 0.16)
        accent_soft = mix(paper, accent, 0.16)
        muted = mix(ink, paper, 0.42)
        band_ink = paper if contrast(paper, band) >= 4.55 else '#0e1013'
    else:
        paper_alt = mix(paper, accent, 0.10)
        line = mix(paper, ink, 0.14)
        accent_soft = mix(paper, accent, 0.16)
        muted = mix(ink, paper, 0.46)
        band_ink = paper

    # 대비 보정 — 인쇄물은 화면보다 대비가 더 떨어져 보인다
    ink = darken_until(ink, paper, 7.05) if not dark else lighten_until(ink, paper, 7.05)
    muted = darken_until(muted, paper, 3.05) if not dark else lighten_until(muted, paper, 3.05)
    accent = darken_until(accent, paper, 3.05) if not dark else lighten_until(accent, paper, 3.05)
    band = darken_until(band, band_ink, 4.55) if lum(band_ink) > 0.5 else lighten_until(band, band_ink, 4.55)

    return dict(
        paper=paper, paperAlt=paper_alt, ink=ink, muted=muted,
        accent=accent, accentSoft=accent_soft, line=line, band=band, bandInk=band_ink,
    )


# ── 서체·장식 이름 (themes.ts 의 상수와 같아야 한다) ──────────
SERIF_CLASSIC, SERIF_SOFT, SERIF_THIN, SERIF_NOTO = 'SERIF_CLASSIC', 'SERIF_SOFT', 'SERIF_THIN', 'SERIF_NOTO'
SANS, ROUND, HAND = 'SANS', 'ROUND', 'HAND'

# id, 이름, 한 줄, mood 3개, family, paper, ink, accent, band,
# display, body, ornament, frame, texture, logo(shape,높이), photo(shape,보정)
SPEC = [
    # ── 고급 · 클래식 +18 ────────────────────────────────────
    ('ink-scholar', '먹빛 서재', '먹과 한지. 국악 협연이나 전통 있는 학원의 정기 연주회에.',
     ['정통', '차분', '깊이'], 'classic', '#faf7f0', '#1a1a1a', '#5c5346', '#1a1a1a',
     SERIF_CLASSIC, SANS, 'foil', 'thin', 'grain', ('plain', 56), ('rect', 'mono')),
    ('oxford-green', '옥스퍼드 그린', '짙은 학문의 초록. 콩쿠르 입상자 무대에.',
     ['격식', '학구', '단정'], 'classic', '#f7f9f6', '#12241a', '#265c3d', '#12241a',
     SERIF_NOTO, SANS, 'arch', 'double', 'grain', ('ring', 60), ('arch', 'natural')),
    ('bordeaux-linen', '보르도 리넨', '와인빛과 리넨 결. 저녁 정기 연주회에.',
     ['고급', '따뜻', '격식'], 'classic', '#fbf7f4', '#2c1a1c', '#8c3540', '#5e2129',
     SERIF_CLASSIC, SANS, 'pearl', 'double', 'grain', ('ring', 62), ('arch', 'warm')),
    ('slate-silver', '슬레이트 실버', '차가운 석판빛. 군더더기 없는 격식.',
     ['절제', '모던', '격식'], 'classic', '#f7f8f9', '#1d2228', '#4a5560', '#1d2228',
     SERIF_THIN, SANS, 'arch', 'thin', 'none', ('plain', 54), ('rect', 'mono')),
    ('champagne-gold', '샴페인 골드', '옅은 금빛 종이. 축하 자리에 어울립니다.',
     ['우아', '축하', '고급'], 'classic', '#fdfaf2', '#33301f', '#a8862e', '#6d5719',
     SERIF_THIN, SANS, 'foil', 'double', 'grain', ('ring', 62), ('arch', 'warm')),
    ('porcelain-blue', '포슬린 블루', '백자에 청화. 단정하고 서늘한 격식.',
     ['정통', '단정', '서늘'], 'classic', '#f8fafc', '#16233a', '#2f5580', '#16233a',
     SERIF_CLASSIC, SANS, 'pearl', 'thin', 'grain', ('circle', 58), ('arch', 'natural')),
    ('mahogany-hall', '마호가니 홀', '오래된 나무 홀의 색. 큰 무대에.',
     ['고전', '무대', '깊이'], 'classic', '#fbf6ef', '#2e1e12', '#8a4a22', '#4d2a14',
     SERIF_CLASSIC, SANS, 'lyre', 'double', 'grain', ('ring', 62), ('arch', 'warm')),
    ('pewter-ivory', '퓨터 아이보리', '무광 주석빛. 사진 없이도 무게가 잡힙니다.',
     ['절제', '여백', '단정'], 'classic', '#fbfaf7', '#26262a', '#6b6659', '#26262a',
     SERIF_NOTO, SANS, 'pearl', 'thin', 'none', ('plain', 54), ('rect', 'soft')),
    ('velvet-plum', '벨벳 플럼', '자줏빛 벨벳. 겨울 저녁 연주회에.',
     ['고급', '깊이', '저녁'], 'classic', '#faf6f9', '#2a1c2e', '#6d3a72', '#3f2144',
     SERIF_SOFT, SANS, 'candle', 'double', 'grain', ('ring', 60), ('arch', 'soft')),
    ('parchment-sepia', '파치먼트 세피아', '오래된 악보의 색. 정통성을 강조할 때.',
     ['고전', '따뜻', '아카이브'], 'classic', '#fbf6e9', '#33291a', '#8a6a2c', '#54401a',
     SERIF_CLASSIC, SANS, 'lyre', 'thin', 'grain', ('plate', 58), ('arch', 'warm')),
    ('onyx-pearl', '오닉스 펄', '검정 위의 진주. 가장 격식 있는 초청장.',
     ['고급', '격식', '밤'], 'classic', '#101114', '#f2f0ea', '#cbb27a', '#cbb27a',
     SERIF_THIN, SANS, 'pearl', 'thin', 'glow', ('plate', 60), ('rect', 'mono')),
    ('concert-black', '콘서트 블랙', '무대 조명이 켜지기 직전. 독주회에.',
     ['무대', '집중', '드라마틱'], 'classic', '#0d0f12', '#f0eee9', '#b9a06a', '#b9a06a',
     SERIF_CLASSIC, SANS, 'spotlight', 'none', 'glow', ('plate', 60), ('arch', 'mono')),
    ('royal-indigo', '로열 인디고', '깊은 남보라. 시상이 있는 자리에.',
     ['격식', '축하', '깊이'], 'classic', '#171a2e', '#eeeef6', '#b4a2e0', '#b4a2e0',
     SERIF_CLASSIC, SANS, 'foil', 'double', 'glow', ('plate', 62), ('arch', 'natural')),
    ('forest-night', '포레스트 나이트', '밤의 숲. 조용하고 단단한 무대.',
     ['차분', '무대', '깊이'], 'classic', '#111c17', '#eaf0ea', '#8fc4a2', '#8fc4a2',
     SERIF_NOTO, SANS, 'ivy', 'thin', 'glow', ('plate', 58), ('arch', 'natural')),
    ('antique-brass', '앤티크 브라스', '오래 쓴 황동. 손때 묻은 격식.',
     ['고전', '따뜻', '단정'], 'classic', '#faf7f0', '#2b2519', '#8a6f2e', '#54431a',
     SERIF_CLASSIC, SANS, 'foil', 'deco', 'grain', ('ring', 60), ('arch', 'warm')),
    ('stone-gray', '스톤 그레이', '돌결 회색. 어떤 사진과도 부딪히지 않습니다.',
     ['중립', '절제', '사진'], 'classic', '#f8f8f7', '#232426', '#5a5c60', '#232426',
     SERIF_NOTO, SANS, 'arch', 'thin', 'grain', ('plain', 54), ('rect', 'natural')),
    ('cathedral-navy', '커시드럴 네이비', '높은 천장의 남색. 큰 홀 정기 연주회에.',
     ['정통', '격식', '웅장'], 'classic', '#f7f8fb', '#131c33', '#2c4272', '#131c33',
     SERIF_CLASSIC, SANS, 'arch', 'double', 'grain', ('ring', 62), ('arch', 'natural')),
    ('rosewood-cream', '로즈우드 크림', '붉은 나뭇결과 크림. 살롱 연주회에.',
     ['우아', '따뜻', '살롱'], 'classic', '#fcf8f3', '#33231e', '#93513c', '#5c2e22',
     SERIF_SOFT, SANS, 'pearl', 'thin', 'grain', ('ring', 60), ('arch', 'soft')),

    # ── 사랑스러운 +12 ───────────────────────────────────────
    ('marshmallow', '마시멜로', '폭신한 흰빛. 유아 첫 발표회에.',
     ['사랑스러움', '포근', '밝음'], 'lovely', '#fffdfd', '#3b3134', '#d98aa0', '#a8556c',
     SERIF_SOFT, SANS, 'heart', 'rounded', 'gradient', ('circle', 62), ('rounded', 'bright')),
    ('apricot-cream', '애프리콧 크림', '살구빛 크림. 아침 시간 발표회에.',
     ['사랑스러움', '따뜻', '밝음'], 'lovely', '#fffaf4', '#3d2e22', '#d98a4a', '#a35f24',
     SERIF_SOFT, SANS, 'ribbon', 'rounded', 'none', ('circle', 60), ('rounded', 'warm')),
    ('mint-blossom', '민트 블라썸', '민트와 꽃. 봄 소규모 연주회에.',
     ['사랑스러움', '산뜻', '봄'], 'lovely', '#f8fdfa', '#22332b', '#4aa885', '#2b7157',
     SERIF_SOFT, SANS, 'cherry', 'rounded', 'none', ('circle', 60), ('rounded', 'bright')),
    ('baby-sky', '베이비 스카이', '아기 하늘빛. 남아 학부모에게도 잘 맞습니다.',
     ['사랑스러움', '맑음', '가벼움'], 'lovely', '#f9fcff', '#233040', '#5590c4', '#2f5f8e',
     SERIF_SOFT, SANS, 'stars', 'rounded', 'gradient', ('circle', 60), ('rounded', 'bright')),
    ('cocoa-milk', '코코아 밀크', '따뜻한 코코아색. 겨울 소규모 발표회에.',
     ['사랑스러움', '포근', '겨울'], 'lovely', '#fdfaf6', '#3a2c22', '#a5714a', '#6d4526',
     SERIF_SOFT, SANS, 'heart', 'rounded', 'none', ('circle', 60), ('rounded', 'warm')),
    ('lilac-note', '라일락 노트', '연보라와 음표. 조용한 사랑스러움.',
     ['사랑스러움', '서정', '차분'], 'lovely', '#fcfaff', '#2f2a3f', '#8272c0', '#574a92',
     SERIF_THIN, SANS, 'note', 'rounded', 'gradient', ('circle', 58), ('rounded', 'soft')),
    ('strawberry-cream', '스트로베리 크림', '딸기와 생크림. 아이들이 가장 좋아합니다.',
     ['사랑스러움', '화사', '달콤'], 'lovely', '#fffafb', '#3d2a2e', '#d96e80', '#a8404f',
     ROUND, SANS, 'heart', 'rounded', 'none', ('circle', 62), ('rounded', 'bright')),
    ('vanilla-ribbon', '바닐라 리본', '바닐라빛에 리본 띠. 선물 같은 초대장.',
     ['사랑스러움', '선물', '단정'], 'lovely', '#fffdf7', '#3a3326', '#c19a4e', '#7d6127',
     SERIF_THIN, SANS, 'ribbon', 'ribbon', 'none', ('ring', 58), ('rounded', 'soft')),
    ('rose-quartz', '로즈 쿼츠', '장밋빛 수정. 봄 학부모 초청에.',
     ['사랑스러움', '우아', '봄'], 'lovely', '#fffafb', '#3a2d33', '#c47b93', '#93465f',
     SERIF_SOFT, SANS, 'pearl', 'rounded', 'gradient', ('circle', 60), ('rounded', 'soft')),
    ('honey-butter', '허니 버터', '꿀과 버터. 오후 햇살 아래 연주회에.',
     ['사랑스러움', '따뜻', '밝음'], 'lovely', '#fffcf2', '#3b3320', '#c79a2e', '#836219',
     SERIF_SOFT, SANS, 'sun', 'rounded', 'none', ('circle', 60), ('rounded', 'warm')),
    ('powder-blue', '파우더 블루', '분첩 같은 파랑. 겨울 소규모 발표회에.',
     ['사랑스러움', '차분', '겨울'], 'lovely', '#fafcfe', '#26303c', '#6b8fae', '#3f5f7e',
     SERIF_THIN, SANS, 'snow', 'rounded', 'none', ('circle', 58), ('rounded', 'soft')),
    ('candy-pop', '캔디 팝', '알록달록 사탕. 놀이형 미니 콘서트에.',
     ['사랑스러움', '경쾌', '축하'], 'lovely', '#fffcfd', '#33293a', '#c25fa8', '#8e2f74',
     ROUND, SANS, 'confetti', 'rounded', 'none', ('circle', 62), ('rounded', 'bright')),

    # ── 계절 · 시즌 +16 ──────────────────────────────────────
    ('plum-blossom', '매화 스프링', '이른 봄 매화. 2~3월 발표회에.',
     ['봄', '단아', '한국'], 'season', '#fffafc', '#33262c', '#c4708c', '#8e3f5c',
     SERIF_CLASSIC, SANS, 'cherry', 'thin', 'none', ('circle', 58), ('arch', 'bright')),
    ('forsythia', '개나리 옐로', '노란 개나리. 3~4월 신입생 발표회에.',
     ['봄', '화사', '경쾌'], 'season', '#fffdf3', '#3b3620', '#c2a020', '#7d6812',
     SERIF_SOFT, SANS, 'garland', 'thin', 'none', ('circle', 58), ('arch', 'bright')),
    ('spring-meadow', '봄 들판', '연둣빛 들판. 야외 봄 음악회에.',
     ['봄', '산뜻', '자연'], 'season', '#fafdf6', '#2a3320', '#6b9a3a', '#41651f',
     SERIF_SOFT, SANS, 'leaf', 'thin', 'none', ('circle', 58), ('arch', 'bright')),
    ('summer-lime', '서머 라임', '여름 라임빛. 방학 특강 발표회에.',
     ['여름', '경쾌', '시원'], 'season', '#f9fdf6', '#26331f', '#5f9a2e', '#3b6418',
     SANS, SANS, 'sun', 'thin', 'none', ('plain', 56), ('rect', 'bright')),
    ('ocean-deep', '오션 딥', '깊은 바다. 여름 저녁 연주회에.',
     ['여름', '깊이', '시원'], 'season', '#f5fafd', '#12293a', '#1f6b91', '#12293a',
     SANS, SANS, 'wave', 'thin', 'none', ('plain', 56), ('rect', 'bright')),
    ('watermelon', '수박 서머', '수박빛 초록과 빨강. 아이들 여름 발표회에.',
     ['여름', '경쾌', '아이'], 'season', '#fafdf8', '#2b3327', '#4d9450', '#2f6533',
     ROUND, SANS, 'sun', 'rounded', 'none', ('circle', 60), ('rounded', 'bright')),
    ('harvest-gold', '하베스트 골드', '가을 들녘의 금빛. 10월 정기 연주회에.',
     ['가을', '따뜻', '풍성'], 'season', '#fdfaf1', '#38301c', '#a58224', '#6b5314',
     SERIF_CLASSIC, SANS, 'maple', 'thin', 'grain', ('ring', 60), ('arch', 'warm')),
    ('persimmon', '감빛 어텀', '잘 익은 감색. 11월 늦가을 무대에.',
     ['가을', '따뜻', '한국'], 'season', '#fffaf5', '#3a2a1e', '#b55f22', '#7a3d12',
     SERIF_CLASSIC, SANS, 'maple', 'thin', 'grain', ('ring', 60), ('arch', 'warm')),
    ('chestnut-brown', '체스트넛 브라운', '밤빛 갈색. 차분한 가을 연주회에.',
     ['가을', '차분', '따뜻'], 'season', '#fcf8f3', '#332721', '#8a5b38', '#59371f',
     SERIF_SOFT, SANS, 'leaf', 'thin', 'grain', ('ring', 58), ('arch', 'warm')),
    ('frost-white', '프로스트 화이트', '서리 내린 아침. 12~1월 발표회에.',
     ['겨울', '맑음', '조용'], 'season', '#fafcfe', '#1f2a35', '#5d7f9e', '#1f2a35',
     SERIF_THIN, SANS, 'snow', 'thin', 'none', ('circle', 58), ('rounded', 'soft')),
    ('candle-night', '캔들 나이트', '촛불 하나. 겨울 저녁 캔들 콘서트에.',
     ['겨울', '따뜻', '저녁'], 'season', '#1c1712', '#f4ece0', '#d9a441', '#d9a441',
     SERIF_CLASSIC, SANS, 'candle', 'thin', 'glow', ('plate', 60), ('arch', 'warm')),
    ('holly-red', '홀리 레드', '호랑가시나무 빨강. 크리스마스 발표회에.',
     ['겨울', '시즌', '축하'], 'season', '#fffaf8', '#2e2020', '#b53030', '#7a1c1c',
     SERIF_CLASSIC, SANS, 'holly', 'double', 'grain', ('ring', 60), ('arch', 'warm')),
    ('silver-bell', '실버 벨', '은빛 종. 크리스마스를 차분하게.',
     ['겨울', '시즌', '단정'], 'season', '#f9fafb', '#232830', '#54606e', '#232830',
     SERIF_THIN, SANS, 'snow', 'thin', 'none', ('circle', 58), ('rounded', 'soft')),
    ('lunar-new-year', '설날 색동', '색동과 홍백. 설 명절 특강 발표에.',
     ['새해', '한국', '경사'], 'season', '#fffcf6', '#2e1d18', '#c23a2c', '#8a2119',
     SERIF_CLASSIC, SANS, 'foil', 'double', 'grain', ('ring', 62), ('arch', 'warm')),
    ('graduation-navy', '졸업 네이비', '학사모의 남색. 수료식·졸업 연주회에.',
     ['졸업', '격식', '축하'], 'season', '#f8f9fc', '#1a2140', '#39508c', '#1a2140',
     SERIF_CLASSIC, SANS, 'garland', 'double', 'grain', ('ring', 62), ('arch', 'natural')),
    ('anniversary-rose', '기념일 로즈', '개원 기념·주년 행사에.',
     ['축하', '기념', '우아'], 'season', '#fffafb', '#352429', '#b8506b', '#832a44',
     SERIF_SOFT, SANS, 'ribbon', 'double', 'grain', ('ring', 60), ('arch', 'soft')),

    # ── 모던 · 편집 +9 ───────────────────────────────────────
    ('editorial-mono', '에디토리얼 모노', '잡지 같은 흑백 편집. 사진이 강할 때.',
     ['모던', '편집', '대담'], 'modern', '#ffffff', '#111111', '#111111', '#111111',
     SANS, SANS, 'note', 'none', 'none', ('plain', 50), ('rect', 'mono')),
    ('paper-craft', '페이퍼 크래프트', '크라프트 종이결. 손으로 만든 느낌.',
     ['모던', '따뜻', '자연'], 'modern', '#faf6ee', '#332e26', '#8a6f45', '#574429',
     SANS, SANS, 'leaf', 'thin', 'grain', ('plain', 54), ('rect', 'warm')),
    ('grid-blue', '그리드 블루', '격자와 파랑. 정보가 많은 인쇄물에.',
     ['모던', '명확', '정보'], 'modern', '#f9fbfd', '#18202e', '#2f5f9e', '#18202e',
     SANS, SANS, 'arch', 'thin', 'none', ('plain', 52), ('rect', 'natural')),
    ('neon-charcoal', '네온 차콜', '어두운 회색에 형광 한 점. 고학년 무대에.',
     ['모던', '대담', '무대'], 'modern', '#16181b', '#f0f1f3', '#7fd4a8', '#7fd4a8',
     SANS, SANS, 'wave', 'none', 'glow', ('plate', 54), ('rect', 'natural')),
    ('warm-minimal', '웜 미니멀', '따뜻한 회색의 최소주의.',
     ['모던', '절제', '따뜻'], 'modern', '#faf9f7', '#2a2724', '#7a6f60', '#2a2724',
     SANS, SANS, 'none', 'none', 'none', ('plain', 50), ('rect', 'soft')),
    ('duotone-teal', '듀오톤 틸', '청록 한 색으로 밀어붙인 편집.',
     ['모던', '대담', '산뜻'], 'modern', '#f6fbfb', '#12292b', '#1f6b70', '#12292b',
     SANS, SANS, 'wave', 'thin', 'none', ('plain', 52), ('rect', 'bright')),
    ('poster-red', '포스터 레드', '강한 빨강 한 색. 멀리서도 읽힙니다.',
     ['모던', '대담', '게시'], 'modern', '#fffafa', '#26191a', '#c32d2d', '#8c1c1c',
     SANS, SANS, 'none', 'none', 'none', ('plain', 52), ('rect', 'natural')),
    ('gallery-sand', '갤러리 샌드', '모래빛 전시장. 사진을 조용히 받칩니다.',
     ['모던', '사진', '중립'], 'modern', '#faf8f4', '#2b2823', '#8a7c66', '#2b2823',
     SANS, SANS, 'none', 'none', 'none', ('plain', 50), ('rect', 'natural')),
    ('blueprint', '블루프린트', '설계도 같은 청사진. 진행 문서에 잘 맞습니다.',
     ['모던', '정보', '명확'], 'modern', '#f5f8fb', '#152234', '#2a5580', '#152234',
     SANS, SANS, 'arch', 'thin', 'grain', ('plain', 52), ('rect', 'mono')),

    # ── 아이들 · 활기 +5 ─────────────────────────────────────
    ('crayon-box', '크레용 박스', '색연필 상자. 유아 발표회 안내문에.',
     ['아이', '활발', '놀이'], 'kids', '#fffdf8', '#3b3325', '#c4762a', '#82471a',
     ROUND, ROUND, 'confetti', 'rounded', 'none', ('circle', 64), ('circle', 'bright')),
    ('bubble-pop', '버블 팝', '동글동글한 거품. 놀이형 미니 콘서트에.',
     ['아이', '경쾌', '놀이'], 'kids', '#f8fdff', '#233038', '#2f8fae', '#175d75',
     ROUND, ROUND, 'confetti', 'rounded', 'none', ('circle', 64), ('circle', 'bright')),
    ('picnic-check', '피크닉 체크', '소풍 가는 날. 야외 미니 발표회에.',
     ['아이', '밝음', '야외'], 'kids', '#fbfdf7', '#2d3325', '#6f9a30', '#456418',
     ROUND, ROUND, 'sun', 'rounded', 'none', ('circle', 62), ('rounded', 'bright')),
    ('storybook', '스토리북', '그림책 같은 색. 이야기가 있는 발표회에.',
     ['아이', '포근', '이야기'], 'kids', '#fffcf4', '#38301f', '#b5823a', '#75521d',
     ROUND, ROUND, 'heart', 'rounded', 'none', ('circle', 62), ('rounded', 'warm')),
    ('rainbow-play', '레인보우 플레이', '무지개빛. 가장 밝고 활발한 무대에.',
     ['아이', '활발', '축하'], 'kids', '#fffbfd', '#332734', '#b5479a', '#7d2a68',
     ROUND, ROUND, 'confetti', 'rounded', 'gradient', ('circle', 64), ('circle', 'bright')),
]

FAMILY_HEADER = {
    'classic': '고급 · 클래식 (추가)',
    'lovely': '사랑스러운 (추가)',
    'season': '계절 · 시즌 (추가)',
    'modern': '모던 · 편집 (추가)',
    'kids': '아이들 · 활기 (추가)',
}


def render(entry):
    (tid, name, tagline, mood, family, paper, ink, accent, band,
     display, body, ornament, frame, texture, logo, photo) = entry
    p = derive(paper, ink, accent, band)
    mood_s = ', '.join(f"'{m}'" for m in mood)
    treat = f", treatment: '{photo[1]}'" if photo[1] else ''
    return f"""  {{
    id: '{tid}',
    name: '{name}',
    tagline: '{tagline}',
    mood: [{mood_s}],
    family: '{family}',
    palette: {{
      paper: '{p['paper']}',
      paperAlt: '{p['paperAlt']}',
      ink: '{p['ink']}',
      muted: '{p['muted']}',
      accent: '{p['accent']}',
      accentSoft: '{p['accentSoft']}',
      line: '{p['line']}',
      band: '{p['band']}',
      bandInk: '{p['bandInk']}',
    }},
    fonts: {{ display: {display}, body: {body} }},
    ornament: '{ornament}',
    frame: '{frame}',
    texture: '{texture}',
    logo: {{ shape: '{logo[0]}', height: {logo[1]} }},
    photo: {{ shape: '{photo[0]}'{treat} }},
  }},
"""


src = TARGET.read_text()
existing = set(re.findall(r"^    id: '([^']+)',$", src, re.M))
new_entries = [e for e in SPEC if e[0] not in existing]
if not new_entries:
    print('추가할 테마가 없습니다 (이미 반영됨)')
    raise SystemExit(0)

blocks = []
for fam in ['classic', 'lovely', 'season', 'modern', 'kids']:
    rows = [e for e in new_entries if e[4] == fam]
    if not rows:
        continue
    blocks.append(
        '\n  // ─────────────────────────────────────────────────────────────\n'
        f'  // {FAMILY_HEADER[fam]}\n'
        '  // ─────────────────────────────────────────────────────────────\n'
    )
    blocks += [render(r) for r in rows]

addition = ''.join(blocks)
marker = '\n]\n\nexport const DEFAULT_THEME_ID'
assert marker in src, 'DESIGN_THEMES 배열 끝을 찾지 못했습니다'
src = src.replace(marker, '\n' + addition + ']\n\nexport const DEFAULT_THEME_ID')
TARGET.write_text(src)

total = len(re.findall(r"^    family: '", src, re.M))
print(f'{len(new_entries)}종 추가 · 총 {total}종')
for fam in ['classic', 'lovely', 'season', 'modern', 'kids']:
    n = len(re.findall(rf"^    family: '{fam}',$", src, re.M))
    print(f'  {FAMILY_HEADER[fam].replace(" (추가)", "")}: {n}')
