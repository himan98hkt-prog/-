<!-- 단계: plan · 응답 파일: plan_response.json -->
# 작업

아래 시스템 지시를 따르고, **맨 아래 JSON 스키마에 맞는 JSON 하나만** 다음 파일에 써라.

    /home/user/-/concours-composer/runs/golden/g02/plan_response.json

제안 마디 수 52. 프레이즈는 4마디 단위로 끊고 total_measures 를 빠짐없이 덮어야 한다. 클라이맥스는 전체의 60~80% 지점.

---

## 시스템 지시

<!-- version: plan-v3.1 · Stage 2 · COMPOSER_MODEL -->
# 역할
당신은 잠긴 모티브 하나를 받아 **곡 전체의 설계도**를 그리는 작곡가다.
음표는 아직 쓰지 않는다. 설계가 틀리면 뒤 단계 전부가 틀린다.

# 이 설계가 반드시 해결해야 할 것
1. **모티브가 곡을 관통한다.** 모든 프레이즈에 `motif_treatment` 를 지정하고,
   같은 기법을 세 번 연속 쓰지 마라. `statement` 다음에 바로 `statement` 는 금지다.
2. **대비가 귀에 들린다.** B(또는 대비) 섹션은 A 와 최소 두 가지가 달라야 한다 —
   조성/선법, 왼손 텍스처, 음역, 리듬 밀도 중 둘.
3. **클라이맥스가 전체의 60~80% 지점에 있다.** 그 앞은 쌓고, 그 뒤는 정리한다.
4. **학생의 강점이 드러나는 구간(`showcase_measures`)을 명시한다.**
   약점은 노출을 피한다 — 옥타브가 약하면 옥타브를 쓰지 마라.
5. **첫 8마디가 심사위원의 첫인상이다.** 모티브 제시 + 조성 확립 + 다이내믹 대비를 이 안에 넣는다.
6. **마지막 4마디는 확신 있게 끝난다.** 종지를 애매하게 흐리지 마라.
7. **제한 시간을 지킨다.** `total_measures × 한 마디 길이 × (60/tempo)` 가 제한의 95% 이하여야 한다.

# 화성
`harmony` 는 **마디마다 하나씩** 채운다. 로마숫자(`I`, `vi`, `V7`, `IV`)를 쓴다.
초·중급 학생 곡이므로 기능화성을 벗어나지 마라. 다만 8마디를 I-V-I-V 로 때우지도 마라 —
섹션마다 최소 한 번은 예상 밖의 화음(부속화음, 나폴리, 차용화음 중 하나)이 들어간다.

# 형식
`form` 은 섹션 → 프레이즈(보통 4마디) 로 쪼갠다. 프레이즈 경계가 곧 Stage 3 의 생성 단위다.
`texture_rh` / `texture_lh` 는 실제 연주 지시처럼 구체적으로 적는다.
나쁜 예: "멜로디". 좋은 예: "오른손 8분음표 순차 선율, 프레이즈 끝 2박 길게".

# 출력
`CompositionPlan` 스키마 그대로. `title_candidates` 는 한국어 3개
(학생 이름을 넣지 마라 — 곡 제목이지 헌정사가 아니다).


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
 "locked_motif": {
  "id": "motif-1",
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
         "C#5"
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
         "A5"
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
         "A2"
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
         "C#5"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 1.0,
        "pitches": [
         "B4"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 2.0,
        "pitches": [
         "C#5"
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
         "A2"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 2.0,
        "pitches": [
         "C#3"
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
  "key": "A",
  "meter": "4/4",
  "tempo": 104,
  "character_label": "계단과 도약",
  "why_it_works": "두 음 걸어 올라간 뒤 5도를 훌쩍 뛰고 곧바로 되돌아오는 모양이라, 한 번 듣고 손이 기억한다. 걷는 부분과 뛰는 부분을 따로 떼어 쓸 수 있어서 동형진행·전위 어느 쪽으로도 늘어나고, 뛰는 폭만 좁히면 그대로 서정적인 B 선율이 된다.",
  "source": "ai",
  "selected": true
 },
 "suggested_total_measures": 52
}
```

---

## 출력 JSON 스키마

```json
{
  "$defs": {
    "Climax": {
      "additionalProperties": false,
      "properties": {
        "measure": {
          "minimum": 1,
          "title": "Measure",
          "type": "integer"
        },
        "how": {
          "title": "How",
          "type": "string"
        }
      },
      "required": [
        "measure",
        "how"
      ],
      "title": "Climax",
      "type": "object"
    },
    "DynamicPoint": {
      "additionalProperties": false,
      "properties": {
        "measure": {
          "minimum": 1,
          "title": "Measure",
          "type": "integer"
        },
        "dyn": {
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
          "title": "Dyn",
          "type": "string"
        }
      },
      "required": [
        "measure",
        "dyn"
      ],
      "title": "DynamicPoint",
      "type": "object"
    },
    "Ending": {
      "additionalProperties": false,
      "properties": {
        "type": {
          "title": "Type",
          "type": "string"
        },
        "measures": {
          "items": {
            "type": "integer"
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Measures",
          "type": "array"
        }
      },
      "required": [
        "type",
        "measures"
      ],
      "title": "Ending",
      "type": "object"
    },
    "HarmonyStep": {
      "additionalProperties": false,
      "properties": {
        "measure": {
          "minimum": 1,
          "title": "Measure",
          "type": "integer"
        },
        "roman": {
          "title": "Roman",
          "type": "string"
        },
        "bass_note": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Bass Note"
        }
      },
      "required": [
        "measure",
        "roman"
      ],
      "title": "HarmonyStep",
      "type": "object"
    },
    "PhrasePlan": {
      "additionalProperties": false,
      "properties": {
        "measures": {
          "items": {
            "type": "integer"
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Measures",
          "type": "array"
        },
        "motif_treatment": {
          "enum": [
            "statement",
            "repeat",
            "sequence_up_2nd",
            "sequence_down_3rd",
            "inversion",
            "retrograde",
            "augmentation",
            "diminution",
            "fragment_head",
            "fragment_tail",
            "transpose_to_dominant",
            "mode_change",
            "texture_swap",
            "octave_shift",
            "rhythmic_variation"
          ],
          "title": "Motif Treatment",
          "type": "string"
        },
        "texture_rh": {
          "title": "Texture Rh",
          "type": "string"
        },
        "texture_lh": {
          "title": "Texture Lh",
          "type": "string"
        },
        "dynamic": {
          "default": "mf",
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
          "title": "Dynamic",
          "type": "string"
        }
      },
      "required": [
        "measures",
        "motif_treatment",
        "texture_rh",
        "texture_lh"
      ],
      "title": "PhrasePlan",
      "type": "object"
    },
    "SectionPlan": {
      "additionalProperties": false,
      "properties": {
        "label": {
          "title": "Label",
          "type": "string"
        },
        "measures": {
          "items": {
            "type": "integer"
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Measures",
          "type": "array"
        },
        "phrases": {
          "items": {
            "$ref": "#/$defs/PhrasePlan"
          },
          "minItems": 1,
          "title": "Phrases",
          "type": "array"
        }
      },
      "required": [
        "label",
        "measures",
        "phrases"
      ],
      "title": "SectionPlan",
      "type": "object"
    },
    "Showcase": {
      "additionalProperties": false,
      "properties": {
        "range": {
          "items": {
            "type": "integer"
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Range",
          "type": "array"
        },
        "strength_used": {
          "title": "Strength Used",
          "type": "string"
        }
      },
      "required": [
        "range",
        "strength_used"
      ],
      "title": "Showcase",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "description": "Stage 2 출력. 원장 승인 후에만 Realize 로 넘어간다.",
  "properties": {
    "title_candidates": {
      "items": {
        "type": "string"
      },
      "title": "Title Candidates",
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
    "total_measures": {
      "maximum": 200,
      "minimum": 8,
      "title": "Total Measures",
      "type": "integer"
    },
    "duration_est": {
      "description": "초",
      "exclusiveMinimum": 0,
      "title": "Duration Est",
      "type": "number"
    },
    "form": {
      "items": {
        "$ref": "#/$defs/SectionPlan"
      },
      "minItems": 1,
      "title": "Form",
      "type": "array"
    },
    "harmony": {
      "items": {
        "$ref": "#/$defs/HarmonyStep"
      },
      "title": "Harmony",
      "type": "array"
    },
    "climax": {
      "$ref": "#/$defs/Climax"
    },
    "showcase_measures": {
      "items": {
        "$ref": "#/$defs/Showcase"
      },
      "title": "Showcase Measures",
      "type": "array"
    },
    "contrast_section": {
      "anyOf": [
        {
          "additionalProperties": {
            "type": "string"
          },
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Contrast Section"
    },
    "modulations": {
      "items": {
        "type": "string"
      },
      "title": "Modulations",
      "type": "array"
    },
    "ending": {
      "$ref": "#/$defs/Ending"
    },
    "dynamics_curve": {
      "items": {
        "$ref": "#/$defs/DynamicPoint"
      },
      "title": "Dynamics Curve",
      "type": "array"
    },
    "pedal_plan": {
      "default": "",
      "title": "Pedal Plan",
      "type": "string"
    },
    "difficulty_target": {
      "maximum": 10,
      "minimum": 1,
      "title": "Difficulty Target",
      "type": "number"
    }
  },
  "required": [
    "key",
    "meter",
    "tempo",
    "total_measures",
    "duration_est",
    "form",
    "climax",
    "ending",
    "difficulty_target"
  ],
  "title": "CompositionPlan",
  "type": "object"
}
```
