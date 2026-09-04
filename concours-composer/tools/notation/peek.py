"""critic_prompt.md 안의 지표·경고만 꺼내 본다 — 프롬프트를 통째로 읽지 않기 위해."""
from __future__ import annotations

from _paths import RUNS
import json
import sys


def main(gid: str) -> None:
    t = (RUNS / gid / "critic_prompt.md").read_text(encoding="utf-8")
    body = t[t.find("## 이번 요청"):t.find("출력 JSON 스키마")]
    d = json.loads(body[body.find("{"):body.rfind("}") + 1])
    m = d["rule_based_musicality"]
    print("score", m["score_10"], "unmet", m["unmet"])
    for k, v in m["metrics"].items():
        print(f"  {k:22s} {v['value']:<7} {v['met']!s:5s} {v['detail'][:150]}")
    print("warn", d["validator_warnings"])
    for row in d.get("measured_texture", []):
        print(f"  {row['섹션']} {row['마디']} RH={row['오른손']['모양']} LH={row['왼손']['모양']}")


if __name__ == "__main__":
    main(sys.argv[1])
