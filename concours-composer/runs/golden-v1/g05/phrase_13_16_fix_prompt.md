<!-- 단계: phrase_13_16_fix · 응답 파일: phrase_13_16_fix_response.json -->
# 작업

아래 시스템 지시를 따르고, **맨 아래 JSON 스키마에 맞는 JSON 하나만** 다음 파일에 써라.

    /home/user/-/concours-composer/runs/golden/g05/phrase_13_16_fix_response.json

13~16마디만 만든다. 각 성부의 dur 합계는 정확히 한 마디여야 하고, 동시 타건 폭은 14반음 이하, 음역은 36~96 안이어야 한다. 왼손 최고음이 오른손 최저음을 넘으면 안 된다.

---

## 시스템 지시

<!-- version: regen-v3.1 · Stage 3(구간 재생성) · COMPOSER_MODEL -->
# 역할
이미 있는 곡의 **지정된 마디 구간만** 다시 쓴다. 그 밖은 건드리지 않는다.

# 받는 것
- `region`: 다시 쓸 마디 범위
- `instruction`: 원장의 요청 또는 비평가의 `revision_request`
  (예: "왼손 더 쉽게", "13~16 왼손 알베르티가 멜로디와 부딪힌다 — 한 옥타브 아래로")
- `context_before` / `context_after`: 앞뒤 4마디의 실제 음표
- `motif`, `phrase_plan`, `harmony`, `constraints`: Stage 3 과 동일

# 지켜야 할 것
1. **경계가 이어져야 한다.** 구간 첫 마디는 `context_before` 마지막 음에서 자연스럽게 받고,
   구간 마지막 마디는 `context_after` 첫 화음으로 넘어갈 준비를 한다.
2. **지시만 고친다.** "왼손 더 쉽게" 라고 했으면 오른손 선율을 바꾸지 마라.
   원장은 이미 마음에 든 부분을 그대로 두려고 구간을 지정한 것이다.
3. 마디 길이·손 스팬·손 교차·프레이즈 호흡 규칙은 Stage 3 과 똑같이 적용된다.

# 출력
`PhraseRealization` 스키마. 요청 구간의 마디만.


---

## 고정 컨텍스트 (곡 하나 동안 바뀌지 않는다 — 실제 API 에서는 캐시된다)

```json
{
 "student": {
  "level": 6,
  "grade": "초6",
  "years_of_study": 0,
  "hand_span_interval": 9,
  "strengths": [
   "화려한 스케일"
  ],
  "weaknesses": [
   "여린 소리"
  ],
  "repertoire_done": [],
  "reading_level": 7,
  "tempo_comfort_max_bpm": 132,
  "notes": ""
 },
 "constraints": {
  "max_span_semitones": 14,
  "lowest_midi": 36,
  "highest_midi": 96,
  "max_tempo_bpm": 132,
  "max_accidental_ratio": 0.225,
  "time_limit_sec": 210,
  "target_difficulty": 6.0,
  "difficulty_feasible_range": [
   1.8,
   8.7
  ]
 },
 "competition": {
  "name": "골든 콩쿨",
  "division": "초6",
  "time_limit_sec": 210,
  "memorization_required": false,
  "repeats_allowed": true,
  "criteria_text": "",
  "judge_notes": ""
 },
 "style_context": [],
 "academy_data": "",
 "request": {
  "mood": "화려하고 당당한",
  "form": "ABA",
  "key_preference": [
   "G"
  ],
  "meter": "4/4",
  "tempo": 120,
  "target_difficulty": 6.0,
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
  "id": "motif-1",
  "measures": [
   {
    "number": 1,
    "rh": [
     {
      "voice": 1,
      "events": [
       {
        "dur": 0.75,
        "pitches": [
         "D5"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 0.25,
        "pitches": [
         "D5"
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
        "slur": null
       },
       {
        "dur": 1.0,
        "pitches": [
         "B5"
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
         "G2",
         "G3"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 2.0,
        "pitches": [
         "D3",
         "B3"
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
    "pedal": true
   },
   {
    "number": 2,
    "rh": [
     {
      "voice": 1,
      "events": [
       {
        "dur": 0.25,
        "pitches": [
         "A5"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 0.25,
        "pitches": [
         "B5"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 0.25,
        "pitches": [
         "C6"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 0.25,
        "pitches": [
         "D6"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 1.0,
        "pitches": [
         "B5"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 2.0,
        "pitches": [
         "G5"
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
         "G2",
         "G3"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 2.0,
        "pitches": [
         "D3",
         "B3"
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
    "pedal": true
   }
  ],
  "key": "G",
  "meter": "4/4",
  "tempo": 120,
  "character_label": "당당한 팡파르",
  "why_it_works": "붙점으로 같은 음을 두드린 뒤 4도와 3도를 연달아 뛰어올라 팡파르를 세우고, 곧바로 16분음표 스케일로 쏟아져 내려온다. 팡파르와 스케일이 한 몸이라 어느 쪽만 떼어 써도 곡이 이어지고, 스케일 부분이 학생의 강점인 화려한 스케일을 그대로 무대에 올린다.",
  "source": "ai",
  "selected": false
 },
 "phrase_plan": {
  "measures": [
   13,
   16
  ],
  "motif_treatment": "inversion",
  "texture_rh": "팡파르의 도약을 뒤집어 아래로. 스케일은 상행으로 되돌린다",
  "texture_lh": "세 음 지속 화음(온마디)",
  "dynamic": "mp"
 },
 "measure_range": [
  13,
  16
 ],
 "harmony": [
  {
   "measure": 13,
   "roman": "I"
  },
  {
   "measure": 14,
   "roman": "IV"
  },
  {
   "measure": 15,
   "roman": "ii"
  },
  {
   "measure": 16,
   "roman": "V7"
  }
 ],
 "next_harmony": "I",
 "key": "G",
 "meter": "4/4",
 "tempo": 120,
 "previous_measures": [
  {
   "number": 5,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.75,
       "pitches": [
        "E5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
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
        "A5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "C6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "A5"
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
        "A2",
        "A3"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "E3",
        "C4"
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
   "pedal": true
  },
  {
   "number": 6,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.25,
       "pitches": [
        "B5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "C6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "D6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "E6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "C6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "A5"
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
        "A2",
        "A3"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "E3",
        "C4"
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
   "pedal": true
  },
  {
   "number": 7,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.75,
       "pitches": [
        "A5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "A5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "D6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "F#6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "D6"
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
        "D2",
        "D3"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "A2",
        "F#3"
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
   "pedal": true
  },
  {
   "number": 8,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.25,
       "pitches": [
        "E6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "D6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "B5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "G5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "D5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "G5"
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
        "G2",
        "G3"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "D3",
        "B3"
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
   "pedal": true
  },
  {
   "number": 9,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.75,
       "pitches": [
        "B4"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "B4"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
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
        "G5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "E5"
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
       "dur": 4.0,
       "pitches": [
        "E2",
        "B2",
        "E3"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      }
     ]
    }
   ],
   "dynamics": "p",
   "text": null,
   "pedal": true
  },
  {
   "number": 10,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.25,
       "pitches": [
        "F#5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "G5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "A5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "B5"
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
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "E5"
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
       "dur": 4.0,
       "pitches": [
        "E2",
        "B2",
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
   "pedal": true
  },
  {
   "number": 11,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.75,
       "pitches": [
        "C6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "C6"
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
       "slur": null
      },
      {
       "dur": 1.0,
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
       "dur": 4.0,
       "pitches": [
        "C3",
        "G3",
        "C4"
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
   "pedal": true
  },
  {
   "number": 12,
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
        "F#5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "A5"
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
       "dur": 4.0,
       "pitches": [
        "A2",
        "D3",
        "F#3"
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
   "pedal": true
  }
 ],
 "instruction": "12마디 왼손을 근음 자리에서 벗어나게 하라. D2+A2+D3 대신 A2+D3+F#3 로 놓으면 베이스가 5음이 되어 앞뒤 옥타브 평행이 한 번에 끊기고, 딸림7화음의 긴장도 오히려 살아난다. 학생 스팬 14반음 안이다. / 21~24마디를 6마디로 늘려라. 22마디의 스케일을 두 마디에 걸쳐 올리면 클라이맥스 도달이 더 멀어지고, 여덟 번 반복되던 4마디 호흡이 딱 한 번 깨지면서 그 자리가 곡의 정점으로 각인된다. / B 섹션을 8마디에서 16마디로 늘려라. 단조 구간에서 팡파르를 딸림조로 한 번 더 굴리고 스케일을 하행으로 뒤집으면, 재료를 새로 만들지 않고도 2분에 가까워진다.",
 "region": [
  13,
  16
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
