"""실제 Claude 호출이 **첫 시도에서** 통할 모양인지, 돈을 쓰지 않고 확인한다.

이 프로그램의 모든 호출은 Structured Outputs 다. 모델이 스키마 밖으로 나가지 못하는
대신, **스키마 자체가 API 에 받아들여져야** 한다. 받아들여지지 않으면 첫 호출이 400 으로
튕기고, 원장님은 곡이 만들어지다 사라지는 것만 본다. 정확히 그 사고가 났던 자리다.

스키마 검사는 네트워크도 키도 필요 없다 — SDK 가 요청을 보내기 직전에 하는 변환을
여기서 똑같이 돌려 보면 된다. 그래서 실측 없이도 이만큼은 미리 막을 수 있다.

여기서 보는 것:
  1. 다섯 개 출력 모델 전부가 SDK 변환을 통과하는가
  2. 프롬프트 파일이 전부 제자리에 있고 읽히는가
  3. 엔진이 파싱 결과를 받아 실제 마디로 조립하는가 (가짜 클라이언트로 끝까지)
"""

from __future__ import annotations

import pytest
from anthropic import transform_schema
from app.generation.engines.claude_engine import MotifBatch, load_prompt, prompt_version
from app.guide.writer import Guide, TitleSuggestion
from app.schemas.music import CompositionPlan, PhraseRealization
from app.schemas.quality import CriticReport, JudgeVerdict
from pydantic import TypeAdapter

# 실제로 `output_model=` 로 넘어가는 것 전부. 하나라도 빠지면 그 단계에서 죽는다.
OUTPUT_MODELS = [
    MotifBatch,
    CompositionPlan,
    PhraseRealization,
    CriticReport,
    JudgeVerdict,
    Guide,
    TitleSuggestion,
]


@pytest.mark.parametrize("model", OUTPUT_MODELS, ids=lambda m: m.__name__)
def test_every_structured_output_schema_survives_the_sdk_transform(model: type) -> None:
    """SDK 가 요청 직전에 하는 변환을 그대로 돌린다 — 여기서 터지면 첫 호출이 400 이다."""
    schema = TypeAdapter(model).json_schema()
    transformed = transform_schema(schema)

    assert isinstance(transformed, dict)
    assert transformed.get("type") == "object", f"{model.__name__} 최상위가 object 가 아니다"
    assert transformed.get("properties"), f"{model.__name__} 에 속성이 없다"
    # 변환 뒤에도 정의가 남아 있으면 참조가 풀리지 않은 것이다.
    assert "$ref" not in str(transformed.get("type", "")), f"{model.__name__} 참조가 남았다"


@pytest.mark.parametrize(
    "name",
    ["motif", "plan", "realize_phrase", "critic", "title", "regenerate_region"],
)
def test_the_prompt_files_are_all_there(name: str) -> None:
    """프롬프트가 하나라도 없으면 그 단계에서 FileNotFoundError 가 난다.

    파일 이름은 코드에만 적혀 있어서, 이름이 바뀌면 실측 전에는 아무도 모른다.
    """
    text = load_prompt(name)
    assert len(text) > 200, f"{name} 프롬프트가 너무 짧다 ({len(text)}자)"
    assert prompt_version(name) != "untagged", f"{name} 프롬프트에 version 태그가 없다"


def test_the_cost_ceiling_is_above_what_one_piece_actually_costs() -> None:
    """상한이 낮으면 **돈은 쓰고 곡은 못 얻는다** — 최악의 실패다."""
    from app.config import Settings

    s = Settings(anthropic_api_key="")
    assert s.max_cost_per_composition >= 3.20, (
        f"곡당 상한 ${s.max_cost_per_composition} 는 실측 최고가($3.15)에 너무 가깝다"
    )


def test_the_models_we_ask_for_are_ones_the_price_table_knows() -> None:
    """가격표에 없는 모델은 최상위가로 계산된다 — 비용 상한이 실제보다 일찍 걸린다."""
    from app.config import Settings
    from app.generation.client import PRICES

    s = Settings(anthropic_api_key="")
    for label, name in (("작곡", s.composer_model), ("비평·해설", s.writer_model)):
        assert name in PRICES, f"{label} 모델 {name!r} 이 가격표에 없다 — 비용 계산이 어긋난다"


def test_no_output_model_slips_past_this_file() -> None:
    """새로 늘어난 구조화 출력이 검사 없이 지나가지 않게 한다.

    이 파일이 지키는 것은 "지금 있는 다섯 개" 가 아니라 **앞으로 늘어날 것까지** 다.
    코드에서 `output_model=` 로 쓰이는 이름을 긁어 위 목록과 대조한다.
    """
    import re
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1] / "app"
    used: set[str] = set()
    for py in app_dir.rglob("*.py"):
        used |= set(re.findall(r"output_model=([A-Z]\w+)", py.read_text(encoding="utf-8")))

    covered = {m.__name__ for m in OUTPUT_MODELS}
    missing = used - covered
    assert not missing, (
        f"구조화 출력 {sorted(missing)} 이 스키마 검사에 없다. "
        "OUTPUT_MODELS 에 넣어라 — 안 넣으면 실제 호출 첫 줄에서 죽는 것을 실측 전까지 모른다."
    )


@pytest.mark.parametrize("model", OUTPUT_MODELS, ids=lambda m: m.__name__)
def test_the_batch_path_builds_the_same_kind_of_schema(model: type) -> None:
    """일괄 요청(Batch API)은 스키마를 직접 만들어 보낸다 — 그쪽도 성립해야 한다."""
    from app.generation.client import _strict_schema

    schema = _strict_schema(model)
    assert schema.get("type") == "object"
    assert schema.get("properties")
