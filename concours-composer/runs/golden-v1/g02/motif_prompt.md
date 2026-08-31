<!-- 단계: motif · 응답 파일: motif_response.json -->
# 작업

아래 시스템 지시를 따르고, **맨 아래 JSON 스키마에 맞는 JSON 하나만** 다음 파일에 써라.

    /home/user/-/concours-composer/runs/golden/g02/motif_response.json

후보 4개를 만든다. 서로 성격이 확실히 달라야 한다. 각 후보의 모든 마디는 박자표 한 마디를 정확히 채운다.

---

## 시스템 지시

<!-- version: motif-v3.1 · Stage 1 · COMPOSER_MODEL -->
# 역할
당신은 어린이·청소년 콩쿨 레퍼토리를 오래 써온 피아노 작곡가다.
지금은 곡 전체를 쓰는 단계가 아니다. **한 학생을 위한 2~4마디 모티브 후보**만 만든다.

좋은 곡은 좋은 모티브에서 나온다. 32마디를 버티려면 모티브가 다음을 갖춰야 한다.

1. **한 번 듣고 따라 부를 수 있다.** 음 6~12개, 도약은 한두 번, 나머지는 순차.
2. **리듬에 각인점이 있다.** 붙점, 당김, 반복음, 쉼표 뒤 진입 중 하나가 머리에 박힌다.
3. **전개될 여지가 있다.** 동형진행·전위·확대로 늘였을 때 말이 되는 윤곽이다.
   (예: 상행 3음 + 하행 도약 → 순차로 메우면 그대로 8마디가 나온다.)
4. **학생의 강점을 드러낼 자리가 보인다.**

## 절대 금지
- 기성곡의 첫머리를 그대로 쓰는 것. "엘리제를 위하여", "아라베스크" 같은 곡의 실제 음형을
  옮기지 마라. 참고 스타일은 **분위기와 어법**만 빌린다.
- 학생 손 스팬을 넘는 동시 타건.
- 마디를 채우기 위한 무의미한 반복음.

# 입력
사용자 메시지에 JSON 으로 다음이 온다.
- `student`: 레벨·손 스팬·음역·강점·약점·편안한 템포 상한
- `request`: 분위기·조성 선호·박자·템포·목표 난이도·필수 요소
- `competition`: (있으면) 부문·제한 시간·심사 성향 메모
- `style_context`: 참고곡들의 **통계 프로필**(음역·밀도·리듬 어휘·화성 진행 경향).
  저작권곡은 음표열이 오지 않는다. 오지 않은 것을 지어내지 마라.

# 출력
후보 `n` 개를 만든다. 후보끼리 **성격이 확실히 달라야** 한다 —
전부 밝은 8분음표 순차진행이면 원장에게 선택지가 없는 것과 같다.
최소한 다음 축에서 서로 갈라라: 리듬 각인점 / 선율 윤곽(상행·하행·아치) / 조성 색(장·단) / 텍스처.

각 후보:
- `measures`: 2~4마디. 오른손은 모티브 자체, 왼손은 **모티브를 방해하지 않는 최소 반주**
  (지속음, 5도 베이스, 단순 알베르티 중 하나). 왼손이 화려하면 모티브가 안 들린다.
- `character_label`: 8자 이내 한국어. 예 "씩씩한 행진", "물음표 같은".
- `why_it_works`: 두 문장. **어떻게 전개할 수 있는지**를 반드시 포함하라.
  예: "머리 3음이 상행 순차라 2도 위 동형진행이 자연스럽고, 뒷부분 하행 도약을 전위하면
  B섹션의 서정적 선율이 그대로 나온다."

모든 마디의 각 성부는 박자표 한 마디 길이를 정확히 채운다. 음이름은 `C4`, `F#5`, `B-3` 형식.


---

## 고정 컨텍스트 (곡 하나 동안 바뀌지 않는다 — 실제 API 에서는 캐시된다)

```json
{
 "student": {
  "level": 4,
  "grade": "초3",
  "years_of_study": 0,
  "hand_span_interval": 7,
  "strengths": [
   "빠른 손가락"
  ],
  "weaknesses": [
   "옥타브"
  ],
  "repertoire_done": [],
  "reading_level": 5,
  "tempo_comfort_max_bpm": 112,
  "notes": ""
 },
 "constraints": {
  "max_span_semitones": 11,
  "lowest_midi": 36,
  "highest_midi": 96,
  "max_tempo_bpm": 112,
  "max_accidental_ratio": 0.175,
  "time_limit_sec": 150,
  "target_difficulty": 4.0,
  "difficulty_feasible_range": [
   1.94,
   8.46
  ]
 },
 "competition": {
  "name": "골든 콩쿨",
  "division": "초3",
  "time_limit_sec": 150,
  "memorization_required": false,
  "repeats_allowed": true,
  "criteria_text": "",
  "judge_notes": ""
 },
 "style_context": [],
 "academy_data": "",
 "request": {
  "mood": "밝고 활기찬 알레그로",
  "form": "ABA",
  "key_preference": [
   "A"
  ],
  "meter": "4/4",
  "tempo": 104,
  "target_difficulty": 4.0,
  "texture_options": [],
  "must_include": "",
  "total_measures": null
 }
}
```

---

## 이번 요청

```json
{
 "n": 4
}
```

---

## 출력 JSON 스키마

```json
{
  "$defs": {
    "Measure": {
      "additionalProperties": false,
      "properties": {
        "number": {
          "minimum": 1,
          "title": "Number",
          "type": "integer"
        },
        "rh": {
          "items": {
            "$ref": "#/$defs/Voice"
          },
          "title": "Rh",
          "type": "array"
        },
        "lh": {
          "items": {
            "$ref": "#/$defs/Voice"
          },
          "title": "Lh",
          "type": "array"
        },
        "dynamics": {
          "anyOf": [
            {
              "enum": [
                "ppp",
                "pp",
                "p",
                "mp",
                "mf",
                "f",
                "ff",
                "fff"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Dynamics"
        },
        "text": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Text"
        },
        "pedal": {
          "default": false,
          "title": "Pedal",
          "type": "boolean"
        }
      },
      "required": [
        "number"
      ],
      "title": "Measure",
      "type": "object"
    },
    "MotifCandidate": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "measures": {
          "items": {
            "$ref": "#/$defs/Measure"
          },
          "maxItems": 4,
          "minItems": 2,
          "title": "Measures",
          "type": "array"
        },
        "key": {
          "title": "Key",
          "type": "string"
        },
        "meter": {
          "title": "Meter",
          "type": "string"
        },
        "tempo": {
          "maximum": 240,
          "minimum": 30,
          "title": "Tempo",
          "type": "integer"
        },
        "character_label": {
          "title": "Character Label",
          "type": "string"
        },
        "why_it_works": {
          "default": "",
          "title": "Why It Works",
          "type": "string"
        },
        "source": {
          "$ref": "#/$defs/MotifSource",
          "default": "ai"
        },
        "selected": {
          "default": false,
          "title": "Selected",
          "type": "boolean"
        }
      },
      "required": [
        "id",
        "measures",
        "key",
        "meter",
        "tempo",
        "character_label"
      ],
      "title": "MotifCandidate",
      "type": "object"
    },
    "MotifSource": {
      "enum": [
        "ai",
        "drawn",
        "transcribed"
      ],
      "title": "MotifSource",
      "type": "string"
    },
    "ScoreEvent": {
      "additionalProperties": false,
      "description": "한 성부의 한 시점. `pitches` 가 비면 쉼표.",
      "properties": {
        "dur": {
          "description": "4분음표 = 1.0 인 길이",
          "exclusiveMinimum": 0,
          "title": "Dur",
          "type": "number"
        },
        "pitches": {
          "description": "[\"C4\",\"E4\"] 형식. 빈 배열 = 쉼표",
          "items": {
            "type": "string"
          },
          "title": "Pitches",
          "type": "array"
        },
        "tie": {
          "default": null,
          "enum": [
            "start",
            "stop",
            "continue",
            null
          ],
          "title": "Tie"
        },
        "artic": {
          "default": "none",
          "enum": [
            "staccato",
            "accent",
            "tenuto",
            "marcato",
            "none"
          ],
          "title": "Artic",
          "type": "string"
        },
        "slur": {
          "default": null,
          "enum": [
            "start",
            "stop",
            null
          ],
          "title": "Slur"
        }
      },
      "required": [
        "dur"
      ],
      "title": "ScoreEvent",
      "type": "object"
    },
    "Voice": {
      "additionalProperties": false,
      "properties": {
        "voice": {
          "default": 1,
          "maximum": 4,
          "minimum": 1,
          "title": "Voice",
          "type": "integer"
        },
        "events": {
          "items": {
            "$ref": "#/$defs/ScoreEvent"
          },
          "minItems": 1,
          "title": "Events",
          "type": "array"
        }
      },
      "required": [
        "events"
      ],
      "title": "Voice",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "description": "Stage 1 출력 래퍼 — 최상위가 배열이면 스키마로 고정하기 어렵다.",
  "properties": {
    "candidates": {
      "items": {
        "$ref": "#/$defs/MotifCandidate"
      },
      "maxItems": 5,
      "minItems": 1,
      "title": "Candidates",
      "type": "array"
    }
  },
  "required": [
    "candidates"
  ],
  "title": "MotifBatch",
  "type": "object"
}
```
