<!-- 단계: phrase_05_08 · 응답 파일: phrase_05_08_response.json -->
# 작업

아래 시스템 지시를 따르고, **맨 아래 JSON 스키마에 맞는 JSON 하나만** 다음 파일에 써라.

    /home/user/-/concours-composer/runs/golden/g01/phrase_05_08_response.json

5~8마디만 만든다. 각 성부의 dur 합계는 정확히 한 마디여야 하고, 동시 타건 폭은 9반음 이하, 음역은 36~96 안이어야 한다. 왼손 최고음이 오른손 최저음을 넘으면 안 된다.

---

## 시스템 지시

<!-- version: realize-v3.1 · Stage 3 · COMPOSER_MODEL -->
# 역할
당신은 설계도의 **한 프레이즈(보통 4마디)만** 음표로 옮기는 작곡가다.
곡 전체를 쓰려 하지 마라. 지금 요청된 마디 범위 밖은 한 마디도 만들지 않는다.

# 받는 것
- `motif`: 잠긴 모티브. 이 프레이즈는 반드시 이것과 관계가 있어야 한다.
- `phrase_plan`: 마디 범위, `motif_treatment`, 텍스처, 다이내믹
- `harmony`: 이 범위의 마디별 로마숫자
- `previous_measures`: 직전 8마디의 **실제 음표**. 여기서 자연스럽게 이어져야 한다.
- `next_harmony`: 다음 프레이즈 첫 화음. 마지막 마디는 여기로 넘어갈 준비를 한다.
- `constraints`: 손 스팬(반음), 음역, 임시표 상한

# motif_treatment 를 문자 그대로 실행하라
| 값 | 해야 할 일 |
|---|---|
| `statement` | 모티브를 원형대로 제시 |
| `repeat` | 같은 높이로 반복하되 다이내믹이나 아티큘레이션을 바꿈 |
| `sequence_up_2nd` / `sequence_down_3rd` | 모티브 윤곽을 그대로 유지한 채 지정 음정만큼 옮김 |
| `inversion` | 음정 방향을 뒤집음(상행 3도 → 하행 3도) |
| `retrograde` | 음 순서를 거꾸로 |
| `augmentation` / `diminution` | 리듬 값을 2배 / 1/2배 |
| `fragment_head` / `fragment_tail` | 모티브의 앞/뒤 절반만 떼어 반복·발전 |
| `transpose_to_dominant` | 딸림조로 옮김 |
| `mode_change` | 같은 윤곽을 장↔단으로 |
| `texture_swap` | 선율을 왼손으로 넘기고 오른손이 반주 |
| `octave_shift` | 옥타브를 옮겨 음색을 바꿈 |
| `rhythmic_variation` | 음높이 윤곽은 유지, 리듬만 재구성 |

# 반드시 지킬 것
1. **마디 길이**: 각 성부의 `dur` 합계 = 박자표 한 마디. 어긋나면 그 응답은 폐기된다.
2. **손 스팬**: 동시에 누르는 음의 폭이 `constraints.max_span_semitones` 이하.
3. **손 교차 금지**: 왼손 최고음 < 오른손 최저음.
4. **프레이즈 호흡**: 프레이즈 마지막 마디의 오른손은 긴 음(2박 이상) 또는 쉼표로 끝낸다.
   숨 쉴 곳 없는 8분음표 행진은 학생이 연주할 수 없다.
5. **왼손은 반주다**: `texture_lh` 를 따르되 오른손 선율과 같은 음역에서 부딪히지 마라.
   충돌하면 한 옥타브 내린다.
6. **다이내믹**: 프레이즈 첫 마디에 `dynamics` 를 표기한다.
7. **슬러·아티큘레이션**: 프레이즈 단위로 슬러를 걸고, 성격에 맞는 스타카토·악센트를 쓴다.
   전부 무표기로 두면 학생이 기계적으로 친다.

# 난이도를 맞추는 손잡이
`constraints.target_difficulty`(1~10)는 장식이 아니라 지켜야 할 수치다.
검증기가 목표 ±1 을 벗어나면 그 곡은 저장되지 않는다. 다음을 직접 조절해 맞춰라.

| 손잡이 | 쉽게(1~3) | 보통(4~6) | 어렵게(7~10) |
|---|---|---|---|
| 리듬 세분 | 4분·2분음표 위주 | 8분음표 위주 | 16분음표·当김·붙점 섞기 |
| 오른손 두께 | 홑음만 | 강박에 3도·6도 | 3화음·옥타브 |
| 왼손 | 지속음·5도 베이스 | 알베르티 4분음표 | 넓은 분산화음·옥타브 도약 |
| 손 이동 | 5음 자리 안 | 한 옥타브 안 | 옥타브 자리바꿈·도약 |
| 리듬 어휘 | 2가지 | 3~4가지 | 5가지 이상 |

`constraints.difficulty_feasible_range` 는 템포·조표·학생 손 스팬이 이미 정해 버린
도달 가능 대역이다. 목표가 그 대역 가장자리면 위 손잡이를 끝까지 밀어야 한다.

# 출력
`PhraseRealization` 스키마. `measures[].number` 는 요청받은 실제 마디 번호를 쓴다.
쉼표는 `pitches: []`. 화음은 `pitches` 에 여러 개.


---

## 고정 컨텍스트 (곡 하나 동안 바뀌지 않는다 — 실제 API 에서는 캐시된다)

```json
{
 "student": {
  "level": 3,
  "grade": "초2",
  "years_of_study": 0,
  "hand_span_interval": 6,
  "strengths": [
   "빠른 손가락"
  ],
  "weaknesses": [
   "옥타브",
   "약한 왼손"
  ],
  "repertoire_done": [],
  "reading_level": 4,
  "tempo_comfort_max_bpm": 108,
  "notes": ""
 },
 "constraints": {
  "max_span_semitones": 9,
  "lowest_midi": 36,
  "highest_midi": 96,
  "max_tempo_bpm": 108,
  "max_accidental_ratio": 0.15,
  "time_limit_sec": 150,
  "target_difficulty": 3.0,
  "difficulty_feasible_range": [
   1.48,
   7.75
  ]
 },
 "competition": {
  "name": "골든 콩쿨",
  "division": "초2",
  "time_limit_sec": 150,
  "memorization_required": false,
  "repeats_allowed": true,
  "criteria_text": "",
  "judge_notes": ""
 },
 "style_context": [],
 "academy_data": "",
 "request": {
  "mood": "밝고 활기찬",
  "form": "ABA",
  "key_preference": [
   "C"
  ],
  "meter": "4/4",
  "tempo": 100,
  "target_difficulty": 3.0,
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
 "motif": {
  "id": "motif-3",
  "measures": [
   {
    "number": 1,
    "rh": [
     {
      "voice": 1,
      "events": [
       {
        "dur": 0.5,
        "pitches": [
         "C5"
        ],
        "tie": null,
        "artic": "none",
        "slur": "start"
       },
       {
        "dur": 0.5,
        "pitches": [
         "D5"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 0.5,
        "pitches": [
         "E5"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 0.5,
        "pitches": [
         "F5"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 1.0,
        "pitches": [
         "G5"
        ],
        "tie": null,
        "artic": "none",
        "slur": "stop"
       },
       {
        "dur": 1.0,
        "pitches": [
         "E5"
        ],
        "tie": null,
        "artic": "staccato",
        "slur": null
       }
      ]
     }
    ],
    "lh": [
     {
      "voice": 1,
      "events": [
       {
        "dur": 2.0,
        "pitches": [
         "C3"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 2.0,
        "pitches": [
         "G3"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       }
      ]
     }
    ],
    "dynamics": "f",
    "text": null,
    "pedal": false
   },
   {
    "number": 2,
    "rh": [
     {
      "voice": 1,
      "events": [
       {
        "dur": 0.5,
        "pitches": [
         "D5"
        ],
        "tie": null,
        "artic": "none",
        "slur": "start"
       },
       {
        "dur": 0.5,
        "pitches": [
         "E5"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 0.5,
        "pitches": [
         "F5"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 0.5,
        "pitches": [
         "D5"
        ],
        "tie": null,
        "artic": "none",
        "slur": "stop"
       },
       {
        "dur": 2.0,
        "pitches": [
         "C5"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       }
      ]
     }
    ],
    "lh": [
     {
      "voice": 1,
      "events": [
       {
        "dur": 2.0,
        "pitches": [
         "G2"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 2.0,
        "pitches": [
         "D3"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       }
      ]
     }
    ],
    "dynamics": null,
    "text": null,
    "pedal": false
   }
  ],
  "key": "C",
  "meter": "4/4",
  "tempo": 100,
  "character_label": "통통 튀는",
  "why_it_works": "8분음표 네 개가 계단처럼 뛰어오른 뒤 스타카토로 튕겨 나가서, 손가락이 빠른 이 학생의 장점이 첫 마디부터 들린다. 네 음 계단을 그대로 2도씩 밀면 동형진행이 되고, 리듬만 남기고 음정을 뒤집으면 같은 활기를 유지한 채 다른 색을 낼 수 있다.",
  "source": "ai",
  "selected": false
 },
 "phrase_plan": {
  "measures": [
   5,
   8
  ],
  "motif_treatment": "sequence_up_2nd",
  "texture_rh": "같은 계단을 2도 위에서. 셋째 마디에서 음역을 한 단 더 올려 종지로 내려온다",
  "texture_lh": "5도 베이스를 2분음표로",
  "dynamic": "f"
 },
 "measure_range": [
  5,
  8
 ],
 "harmony": [
  {
   "measure": 5,
   "roman": "ii"
  },
  {
   "measure": 6,
   "roman": "ii"
  },
  {
   "measure": 7,
   "roman": "V7"
  },
  {
   "measure": 8,
   "roman": "I"
  }
 ],
 "next_harmony": "vi",
 "key": "C",
 "meter": "4/4",
 "tempo": 100,
 "previous_measures": [
  {
   "number": 1,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.5,
       "pitches": [
        "C5"
       ],
       "tie": null,
       "artic": "none",
       "slur": "start"
      },
      {
       "dur": 0.5,
       "pitches": [
        "D5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.5,
       "pitches": [
        "E5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.5,
       "pitches": [
        "F5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "G5"
       ],
       "tie": null,
       "artic": "none",
       "slur": "stop"
      },
      {
       "dur": 1.0,
       "pitches": [
        "E5"
       ],
       "tie": null,
       "artic": "staccato",
       "slur": null
      }
     ]
    }
   ],
   "lh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 2.0,
       "pitches": [
        "C3"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "G3"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      }
     ]
    }
   ],
   "dynamics": "mf",
   "text": null,
   "pedal": false
  },
  {
   "number": 2,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.5,
       "pitches": [
        "D5"
       ],
       "tie": null,
       "artic": "none",
       "slur": "start"
      },
      {
       "dur": 0.5,
       "pitches": [
        "E5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.5,
       "pitches": [
        "F5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.5,
       "pitches": [
        "D5"
       ],
       "tie": null,
       "artic": "none",
       "slur": "stop"
      },
      {
       "dur": 2.0,
       "pitches": [
        "C5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      }
     ]
    }
   ],
   "lh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 2.0,
       "pitches": [
        "C3"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "E3"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      }
     ]
    }
   ],
   "dynamics": null,
   "text": null,
   "pedal": false
  },
  {
   "number": 3,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.5,
       "pitches": [
        "B4"
       ],
       "tie": null,
       "artic": "none",
       "slur": "start"
      },
      {
       "dur": 0.5,
       "pitches": [
        "C5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.5,
       "pitches": [
        "D5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.5,
       "pitches": [
        "E5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "F5"
       ],
       "tie": null,
       "artic": "none",
       "slur": "stop"
      },
      {
       "dur": 1.0,
       "pitches": [
        "D5"
       ],
       "tie": null,
       "artic": "staccato",
       "slur": null
      }
     ]
    }
   ],
   "lh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 2.0,
       "pitches": [
        "G2"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "D3"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      }
     ]
    }
   ],
   "dynamics": null,
   "text": null,
   "pedal": false
  },
  {
   "number": 4,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.5,
       "pitches": [
        "C5"
       ],
       "tie": null,
       "artic": "none",
       "slur": "start"
      },
      {
       "dur": 0.5,
       "pitches": [
        "D5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.5,
       "pitches": [
        "E5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.5,
       "pitches": [
        "C5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "B4"
       ],
       "tie": null,
       "artic": "none",
       "slur": "stop"
      }
     ]
    }
   ],
   "lh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 2.0,
       "pitches": [
        "G2"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "D3"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      }
     ]
    }
   ],
   "dynamics": null,
   "text": null,
   "pedal": false
  }
 ]
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
  "description": "Stage 3 출력 — 프레이즈(보통 4마디) 단위.",
  "properties": {
    "measures": {
      "items": {
        "$ref": "#/$defs/Measure"
      },
      "minItems": 1,
      "title": "Measures",
      "type": "array"
    }
  },
  "required": [
    "measures"
  ],
  "title": "PhraseRealization",
  "type": "object"
}
```
