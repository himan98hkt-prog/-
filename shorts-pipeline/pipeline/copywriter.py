"""이미지에서 제목·훅·움직임 프롬프트를 자동으로 짓는다.

미드저니 파일명에는 프롬프트 문장이 그대로 들어 있다. 거기서 장면의 특징을
뽑아 한국어 제목을 조립한다. 테마별 고정 문구 하나를 돌려쓰면 같은 제목이
여러 편 나가므로, 세부 요소를 섞어 편마다 다르게 만든다.

  "descending a vast temple staircase lit by braziers"
    -> 횃불이 밝힌 신전 계단을 내려가다
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ── 장면의 수식어 — 프롬프트에 있으면 제목 앞에 붙는다 ────────────────
DETAILS: list[tuple[tuple[str, ...], str]] = [
    (("rain-soaked", "rain streak", "rainy", "rain "), "비 내리는"),
    (("aurora", "northern light"), "오로라가 흐르는"),
    (("bioluminescent", "glowing water", "luminescent"), "물이 빛나는"),
    (("milky way", "starfield", "stars filling", "constellation"), "별이 쏟아지는"),
    (("giant moon", "enormous moon", "blood moon", "twin moon", "moon rising"), "달이 걸린"),
    (("paper lantern", "floating lantern", "lantern"), "등불이 켜진"),
    (("neon",), "네온이 번지는"),
    (("brazier", "torch"), "횃불이 밝힌"),
    (("stained glass", "god ray", "light shaft", "sunlight shaft", "sunbeam",
      "volumetric light"), "빛이 쏟아지는"),
    (("half-flooded", "flooded", "submerged", "sunken"), "물에 잠긴"),
    (("overgrown", "moss", "vine"), "이끼 낀"),
    (("will-o", "wisp", "spirit light"), "혼불이 떠다니는"),
    (("glowing mushroom", "mushroom"), "버섯이 빛나는"),
    (("cherry", "sakura", "petal"), "꽃잎 흩날리는"),
    (("hydrangea", "wildflower", "sunflower"), "꽃이 핀"),
    (("waterfall",), "폭포가 쏟아지는"),
    (("snow", "frozen", "ice "), "눈 덮인"),
    (("mist", "fog", "haze"), "안개 낀"),
    (("sunset", "golden hour", "dusk"), "노을 지는"),
    (("dawn", "sunrise", "first light"), "동트는"),
    (("crystal",), "수정이 자라는"),
    (("molten", "forge", "lava"), "용암이 흐르는"),
    (("jellyfish", "coral"), "산호가 자라는"),
    (("rune", "arcane", "magic"), "마법이 깃든"),
    (("abandoned", "ruined", "collapsed", "forgotten"), "버려진"),
    (("neon tunnel", "concentric"), "빛의 고리가 이어진"),
]

# ── 장소 — 테마와 프롬프트에서 고른다 ─────────────────────────────────
PLACES: list[tuple[tuple[str, ...], str]] = [
    # 자전거 다운힐 팩이 쓰는 풍경들. 좁은 표현이라 넓은 말보다 먼저 봐야 한다.
    # 'mountain road' 를 'mountain'(설산) 뒤에 두면 고갯길이 설산이 되고,
    # 'cliff road' 를 'road'(길) 뒤에 두면 해안 도로가 그냥 길이 된다.
    (("switchback", "hairpin", "mountain road", "ridge road"), "고갯길"),
    (("coastal road", "cliff road", "seaside road"), "해안 도로"),
    (("vineyard",), "포도밭"),
    (("rice terrace", "paddy", "terrace", "terraced"), "계단식 논"),
    (("lavender", "flower field", "wildflower field"), "꽃밭"),
    (("tea plantation", "tea field"), "차밭"),
    (("fjord",), "피오르"),
    (("mesa", "desert road", "canyon road"), "사막 언덕"),
    (("lakeside", "lake road"), "호숫가"),
    (("moor", "highland", "plateau"), "고원"),
    (("rope bridge", "stone bridge", "bridge"), "다리"),
    (("staircase", "stone step", "stairs", "steps"), "계단"),
    (("cathedral",), "대성당"),
    (("temple", "shrine"), "신전"),
    (("torii",), "붉은 문"),
    (("library", "bookshelf"), "도서관"),
    (("clocktower", "clock tower"), "시계탑"),
    (("tunnel",), "터널"),
    (("corridor", "hallway"), "회랑"),
    (("cavern", "cave"), "동굴"),
    (("alley",), "골목"),
    (("canal",), "물길"),
    (("pier", "boardwalk"), "부두"),
    (("beach", "shore", "coast"), "밤바다"),
    (("ocean trench", "deep ocean", "underwater", "sunken"), "심해"),
    (("forest", "woods"), "숲"),
    (("swamp", "marsh"), "늪"),
    (("river", "stream"), "강"),
    (("floating island", "sky kingdom", "cloud sea"), "하늘 섬"),
    (("valley", "canyon"), "협곡"),
    (("mountain", "alpine", "peak"), "설산"),
    (("city", "megacity", "skyline", "street"), "도시"),
    (("windshield", "dashboard", "steering", "cockpit", "inside a car"), "밤길"),
    (("highway", "road", "asphalt"), "길"),
    (("railway", "track", "train"), "철길"),
    (("planet", "space station", "lunar", "moon surface"), "낯선 행성"),
    (("palace", "castle"), "성"),
    (("gate", "portal", "door"), "문"),
    (("field", "meadow", "grass"), "들판"),
    # 1인칭 팩(PROMPTS_HD)에서 쓰는 장소들. 없으면 제목이 기본값으로 몰린다.
    (("dragon's neck", "dragon's back", "on a dragon"), "용의 등"),
    (("airship",), "비행선"),
    (("spine of", "sleeping colossal", "colossal creature"), "거인의 등"),
    (("giant statue", "colossal statue", "seated statue"), "거상"),
    (("submersible", "porthole"), "잠수정"),
    (("catwalk", "walkway", "ledge"), "통로"),
    (("causeway",), "참배로"),
    (("glacier",), "빙하"),
    (("frozen lake", "frozen palace"), "얼음 궁전"),
    (("orrery", "rotunda"), "천체의"),
    (("market", "stall"), "장터"),
    (("sky ship", "prow"), "뱃머리"),
]

# ── 움직임 ───────────────────────────────────────────────────────────
MOVES: list[tuple[tuple[str, ...], str]] = [
    # 이동 수단이 가장 확실한 단서다. 먼저 본다.
    # 내리막이 자전거보다 앞이다. '달리는' 보다 '내려가는' 이 장면에 맞다.
    (("cycling downhill", "coasting downhill", "downhill", "switchback",
      "hairpin"), "내려가는 길"),
    (("riding a bicycle", "cycling", "handlebar", "bike"), "달리는 길"),
    (("riding on the back", "on the back of a dragon", "dragon flying",
      "dragon's neck", "riding on a dragon", "airship", "gliding",
      "flying low", "aerial flight", "low aerial"), "나는 길"),
    (("swimming", "diving", "swim through"), "헤엄치는 길"),
    (("on a boat", "boat drifting", "wooden boat", "sailing", "raft"), "떠가는 길"),
    (("inside a car", "driving", "racing through", "dashboard",
      "windshield", "cockpit", "train descending", "train"), "달리는 길"),
    # 방향은 그 단어가 실제 동사로 쓰였을 때만 잡는다.
    (("descending", "descend "), "내려가는 길"),
    (("climbing", "ascending", "walking up", "rising through"), "오르는 길"),
    (("crossing", "wading", "stepping through", "pushing through"), "건너는 길"),
    (("standing on", "standing between", "looking up along"), "올려다보는 길"),
    (("walking", "first person view", "pov", "walk "), "걷는 길"),
]

# ── 훅 — 테마별로 여러 개 두고 파일명 해시로 골라 겹치지 않게 한다 ────
HOOKS: dict[str, list[str]] = {
    "sky_islands": ["이 다리 끝에 뭐가 있을까", "떨어지면 어디로 갈까", "구름 위에도 길이 있었다"],
    "spirit_forest": ["여긴 지도에 없는 곳입니다", "따라오는 불빛이 있었다", "숲이 숨 쉬는 소리"],
    "temple": ["문을 열면 안 되는 거였는데", "천 년 만에 열린 길", "여긴 누가 지었을까"],
    "crystal_cave": ["빛이 어디서 오는 걸까", "이 아래 뭐가 있을까", "소리가 울리지 않는다"],
    "ice": ["소리 켜고 보세요", "발밑이 유리 같았다", "숨이 얼어붙는 곳"],
    "magic_city": ["30초 동안 다른 세계에", "여기 살고 싶다", "불빛이 꺼지지 않는 도시"],
    "dragon": ["돌아가는 길은 없었습니다", "내려다본 순간", "바람 소리만 남았다"],
    "underwater": ["숨을 참고 따라오세요", "여긴 아무도 못 왔다", "빛이 닿지 않는 깊이"],
    "titan": ["이게 살아있는 거라고?", "크기를 가늠해 보세요", "발밑이 움직였다"],
    "library": ["끝까지 본 사람만 아는 장면", "이 책들은 누가 읽을까", "끝이 안 보인다"],
    "spirit_path": ["여긴 존재하지 않는 곳입니다", "몇 개나 지나야 할까", "뒤돌아보면 안 됩니다"],
    "anime": ["이런 곳에 살고 싶다", "그 여름이 생각나서", "돌아가고 싶은 순간"],
    "night_drive": ["한 번도 안 멈추고 달렸습니다", "이 길 끝에 뭐가 있을까", "새벽 세 시의 도로"],
    "downhill": ["브레이크 잡지 마세요", "이 내리막이 끝나지 않았으면",
                 "소리 켜고 바람 들어보세요", "페달 한 번도 안 밟았습니다",
                 "여기서 30초만 쉬어가세요"],
    "alley_bike": ["이 길 끝에 뭐가 있을까", "골목마다 다른 빛", "비 온 뒤의 골목"],
    "train": ["창밖만 30초", "어디로 가는 기차일까", "종착역이 없는 노선"],
    "tunnel": ["출구가 보이시나요", "끝이 없는 것 같은데", "빛을 향해 계속"],
    "coast": ["파도 소리 켜고 보세요", "바다가 빛나는 밤", "여기서 멈추고 싶다"],
    "space": ["여긴 지구가 아닙니다", "하늘이 두 개였다", "돌아갈 수 있을까"],
    "misc": ["이 길 끝에 뭐가 있을까", "30초 동안 아무 생각 안 하기", "소리 켜고 보세요"],
}

# 움직임 프롬프트에 항상 붙는 꼬리. 카메라 일관성을 잡아준다.
MOTION_TAIL = ("constant forward motion, steady speed, no camera shake, "
               "no scene cut, cinematic, consistent lighting")

_STOP = re.compile(r"--\w+[^-]*")          # --ar 9:16 같은 파라미터 제거


@dataclass
class Copy:
    title: str
    hook: str
    prompt: str


_WORD_CACHE: dict[str, re.Pattern] = {}


def _matches(text: str, phrase: str) -> bool:
    """단어 경계로 찾는다.

    단순 부분 문자열로 찾으면 'mountain valley' 의 v-alley 가 'alley'(골목)로,
    'train' 의 t-rain 이 'rain'(비)으로 잡힌다. 실제로 그런 제목이 나왔다.
    """
    pat = _WORD_CACHE.get(phrase)
    if pat is None:
        # 복수형(-s/-es)까지 받아준다. brazier -> braziers, island -> islands
        pat = re.compile(
            r"(?<![a-z])" + re.escape(phrase.strip()) + r"(?:es|s)?(?![a-z])")
        _WORD_CACHE[phrase] = pat
    return bool(pat.search(text))


def _pick(text: str, table: list[tuple[tuple[str, ...], str]]) -> str | None:
    for words, korean in table:
        if any(_matches(text, w) for w in words):
            return korean
    return None


def _hash(seed: str) -> int:
    h = 2166136261
    for ch in seed:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


def clean_prompt(raw: str) -> str:
    """미드저니 프롬프트에서 파라미터와 군더더기를 걷어낸다."""
    text = _STOP.sub("", raw or "")
    text = re.sub(r"\s+", " ", text).strip(" ,.")
    return text


def motion_prompt(raw: str) -> str:
    """장면 묘사에 카메라 지시를 붙여 영상용 프롬프트로 만든다."""
    scene = clean_prompt(raw)
    if not scene:
        return f"smooth forward camera movement, {MOTION_TAIL}"
    # 이미 카메라 지시가 있으면 중복해서 붙이지 않는다
    if "forward motion" in scene.lower():
        return scene
    return f"{scene}, {MOTION_TAIL}"


def write(theme: str, raw_prompt: str, *, seed_key: str = "") -> Copy:
    """테마와 원본 프롬프트로 제목·훅·움직임 프롬프트를 짓는다."""
    text = clean_prompt(raw_prompt).lower()

    detail = _pick(text, DETAILS)
    place = _pick(text, PLACES)
    move = _pick(text, MOVES)

    # 제목 조립: [수식어] [장소]을 [움직임]
    if place and move:
        core = f"{place}을 {move}" if _has_final_consonant(place) else f"{place}를 {move}"
        title = f"{detail} {core}" if detail else core
    elif place:
        title = f"{detail} {place}" if detail else place
    elif detail:
        title = f"{detail} 풍경"
    else:
        title = "끝나지 않는 여행"

    hooks = HOOKS.get(theme, HOOKS["misc"])
    hook = hooks[_hash(seed_key or raw_prompt) % len(hooks)]

    return Copy(title=title.strip(), hook=hook, prompt=motion_prompt(raw_prompt))


def _has_final_consonant(word: str) -> bool:
    """마지막 글자에 받침이 있는지. 을/를 조사 선택에 쓴다."""
    if not word:
        return False
    ch = word[-1]
    if not ("가" <= ch <= "힣"):
        return True
    return (ord(ch) - 0xAC00) % 28 != 0
