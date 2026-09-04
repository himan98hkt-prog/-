<!-- 단계: critic · 응답 파일: critic_response.json -->
# 작업

아래 시스템 지시를 따르고, **맨 아래 JSON 스키마에 맞는 JSON 하나만** 다음 파일에 써라.

    /home/user/-/concours-composer/runs/golden/g04/critic_response.json

당신은 이 곡을 쓰지 않았다. 후하게 주지 마라. 마디 참조는 1~16 안이어야 한다.

---

## 시스템 지시

<!-- version: critic-v3.1 · Stage 5 · COMPOSER_MODEL · 작곡가와 별도 호출 -->
# 역할
당신은 이 곡을 **쓰지 않았다**. 콩쿨 심사와 교재 편집을 오래 한 비평가로서,
학생에게 이 곡을 쥐여줘도 되는지 판단한다.

칭찬은 두 개면 충분하다. 당신의 가치는 **무엇을 어느 마디에서 어떻게 고쳐야 하는지**
말하는 데 있다. 두루뭉술한 총평("전개가 아쉽다")은 쓸모가 없다.

# 채점 (각 0~10)
| 키 | 보는 것 |
|---|---|
| `motif_development` | 모티브가 **발전**하는가, 그냥 반복되는가. 후반부에 모티브의 흔적이 남아 있는가 |
| `form_clarity` | 눈이 아니라 귀로 섹션이 갈리는가 |
| `harmony` | 진행이 자연스럽고 종지가 확실한가. 기능화성이 무너지지 않았는가 |
| `voice_leading` | 병행 5·8도, 어색한 도약, 왼손 반주와 오른손 선율의 음역 충돌 |
| `phrasing` | 프레이즈가 호흡하는가. 4+4 가 기계적으로만 반복되지 않는가 |
| `climax_ending` | 클라이맥스가 설득력 있게 준비되는가. 끝이 흐지부지하지 않은가 |
| `student_fit` | 이 학생의 강점이 드러나는가. 약점이 노출되지 않는가. 난이도가 맞는가 |
| `competition_effect` | 첫 8마디가 귀를 잡는가. 청중이 지루해할 구간은 없는가 |
| `notation` | 임시표·이명동음·성부 배치가 학생이 읽기 좋은가 |
| `originality` | 참고 스타일을 닮되 특정 곡을 베낀 느낌이 없는가 |

**후하게 주지 마라.** 7점은 "학생에게 줘도 된다"의 하한이다. 밋밋하면 5~6점이다.
모티브가 전개 없이 반복만 되면 `motif_development` 는 4점을 넘을 수 없다.

# revision_requests
고칠 것마다 하나씩. 각각:
- `measures`: **실제 존재하는 마디 범위**. 곡의 마디 수를 넘는 번호를 쓰지 마라.
- `issue`: 무엇이 문제인지 한 문장
- `instruction`: 작곡가가 그대로 실행할 수 있는 지시.
  나쁜 예 "더 음악적으로". 좋은 예 "25~28 클라이맥스가 ff 인데 텍스처가 얇다 —
  오른손을 옥타브 또는 3도 겹침으로 두껍게 하고 왼손은 저음역 분산화음으로".

총점 7.0 미만이면 `revision_requests` 를 **반드시** 하나 이상 낸다.
같은 마디에 대한 요청은 하나로 합쳐라. 5개를 넘기지 마라 — 우선순위가 높은 것부터.

# 입력
악보의 텍스트 표현(마디별 음표·화성·다이내믹), Plan, 학생 프로필, 규칙 기반 음악성 지표.
음악성 지표가 낮게 나온 항목은 특히 자세히 보되, 지표가 놓친 것을 찾는 게 당신의 일이다.


---

## 고정 컨텍스트 (곡 하나 동안 바뀌지 않는다 — 실제 API 에서는 캐시된다)

```json
{
 "student": {
  "level": 2,
  "grade": "유치",
  "years_of_study": 0,
  "hand_span_interval": 5,
  "strengths": [
   "또렷한 리듬"
  ],
  "weaknesses": [
   "손가락 힘"
  ],
  "repertoire_done": [],
  "reading_level": 3,
  "tempo_comfort_max_bpm": 96,
  "notes": ""
 },
 "constraints": {
  "max_span_semitones": 7,
  "lowest_midi": 36,
  "highest_midi": 96,
  "max_tempo_bpm": 96,
  "max_accidental_ratio": 0.125,
  "time_limit_sec": 90,
  "target_difficulty": 2.0,
  "difficulty_feasible_range": [
   1.37,
   7.4
  ]
 },
 "competition": {
  "name": "골든 콩쿨",
  "division": "유치",
  "time_limit_sec": 90,
  "memorization_required": false,
  "repeats_allowed": true,
  "criteria_text": "",
  "judge_notes": ""
 },
 "style_context": [],
 "academy_data": "",
 "request": {
  "mood": "귀여운 행진",
  "form": "ABA",
  "key_preference": [
   "C"
  ],
  "meter": "4/4",
  "tempo": 88,
  "target_difficulty": 2.0,
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
 "score_text": "m1 | [I] | (mf) | RH C5/1 C5/1 E5/1 E5/1 | LH C3/2 G3/2\nm2 | [I] | RH G5/2 E5/2 | LH C3/2 E3/2\nm3 | [V7] | RH D5/1 D5/1 F5/1 F5/1 | LH D3/2 G2/2\nm4 | [V7] | RH G5/2 D5/2 | LH G2/2 D3/2\nm5 | [ii] | (f) | RH D5/1 D5/1 F5/1 F5/1 | LH D3/2 A3/2\nm6 | [ii] | RH A5/2 F5/2 | LH D3/2 F3/2\nm7 | [V7] | RH B4/1 B4/1 D5/1 D5/1 | LH G2/2 D3/2\nm8 | [I] | RH C5/2 E5/2 | LH C3/2 G3/2\nm9 | [vi] | (p) | RH A4/1 A4/1 C5/1 C5/1 | LH E2/4\nm10 | [vi] | RH E5/2 C5/2 | LH A2/4\nm11 | [IV] | RH A5/1 A5/1 C6/1 C6/1 | LH F2/4\nm12 | [V7] | RH B5/2 G5/2 | LH G2/4\nm13 | [I] | (mf) | RH C5/1 C5/1 E5/1 E5/1 | LH C3/2 G3/2\nm14 | [I] | RH G5/2 E5/2 | LH C3/2 E3/2\nm15 | [V7] | RH B4/1 B4/1 D5/1 D5/1 | LH G2/2 D3/2\nm16 | [I] | RH C5/4 | LH C3/4",
 "plan": {
  "title_candidates": [
   "작은 북",
   "씩씩한 걸음",
   "둥둥 행진"
  ],
  "key": "C",
  "meter": "4/4",
  "tempo": 88,
  "total_measures": 16,
  "duration_est": 65.5,
  "form": [
   {
    "label": "A",
    "measures": [
     1,
     8
    ],
    "phrases": [
     {
      "measures": [
       1,
       4
      ],
      "motif_treatment": "statement",
      "texture_rh": "같은 음을 두 번씩 또렷하게. 다섯 손가락 자리 안에서만 움직인다",
      "texture_lh": "홑음 베이스를 2분음표로. 화음은 쓰지 않는다",
      "dynamic": "mf"
     },
     {
      "measures": [
       5,
       8
      ],
      "motif_treatment": "sequence_up_2nd",
      "texture_rh": "같은 두드림을 한 계단 위에서. 8마디는 으뜸음으로 내려앉는다",
      "texture_lh": "홑음 베이스를 2분음표로",
      "dynamic": "f"
     }
    ]
   },
   {
    "label": "B",
    "measures": [
     9,
     12
    ],
    "phrases": [
     {
      "measures": [
       9,
       12
      ],
      "motif_treatment": "mode_change",
      "texture_rh": "단조 색으로 두드리다 11마디에서 곡의 가장 높은 자리까지 올라간다",
      "texture_lh": "온음표 하나만. 왼손이 쉬는 동안 오른손 리듬이 앞으로 나온다",
      "dynamic": "p"
     }
    ]
   },
   {
    "label": "A'",
    "measures": [
     13,
     16
    ],
    "phrases": [
     {
      "measures": [
       13,
       16
      ],
      "motif_treatment": "repeat",
      "texture_rh": "1~2마디를 음까지 그대로 되돌린 뒤 온음표로 마무리",
      "texture_lh": "1~2마디와 동일",
      "dynamic": "mf"
     }
    ]
   }
  ],
  "harmony": [
   {
    "measure": 1,
    "roman": "I",
    "bass_note": null
   },
   {
    "measure": 2,
    "roman": "I",
    "bass_note": null
   },
   {
    "measure": 3,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 4,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 5,
    "roman": "ii",
    "bass_note": null
   },
   {
    "measure": 6,
    "roman": "ii",
    "bass_note": null
   },
   {
    "measure": 7,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 8,
    "roman": "I",
    "bass_note": null
   },
   {
    "measure": 9,
    "roman": "vi",
    "bass_note": null
   },
   {
    "measure": 10,
    "roman": "vi",
    "bass_note": null
   },
   {
    "measure": 11,
    "roman": "IV",
    "bass_note": null
   },
   {
    "measure": 12,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 13,
    "roman": "I",
    "bass_note": null
   },
   {
    "measure": 14,
    "roman": "I",
    "bass_note": null
   },
   {
    "measure": 15,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 16,
    "roman": "I",
    "bass_note": null
   }
  ],
  "climax": {
   "measure": 11,
   "how": "곡에서 한 번만 나오는 C6 을 두 번 두드려 가장 높은 자리를 만든다"
  },
  "showcase_measures": [
   {
    "range": [
     1,
     4
    ],
    "strength_used": "또렷한 리듬"
   },
   {
    "range": [
     9,
     12
    ],
    "strength_used": "또렷한 리듬"
   }
  ],
  "contrast_section": {
   "label": "B",
   "how": "나란한 단조 색으로 바꾸고, 왼손을 2분음표 홑음에서 온음표 하나로 멈춰 세워 오른손 리듬만 남긴다"
  },
  "modulations": [],
  "ending": {
   "type": "완전종지 — V7 에서 I 로, 온음표로 길게",
   "measures": [
    13,
    16
   ]
  },
  "dynamics_curve": [
   {
    "measure": 1,
    "dyn": "mf"
   },
   {
    "measure": 5,
    "dyn": "f"
   },
   {
    "measure": 9,
    "dyn": "p"
   },
   {
    "measure": 13,
    "dyn": "mf"
   }
  ],
  "pedal_plan": "페달은 쓰지 않는다. 유치부는 손과 귀만으로 또렷하게 치는 것이 먼저다",
  "difficulty_target": 2.0
 },
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
        "dur": 1.0,
        "pitches": [
         "C5"
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
        "dur": 2.0,
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
   }
  ],
  "key": "C",
  "meter": "4/4",
  "tempo": 88,
  "character_label": "작은 북",
  "why_it_works": "같은 음을 두 번씩 또렷하게 두드리며 한 계단씩 올라가는 모양이라, 리듬이 강점인 유치부 학생이 첫 마디부터 박을 정확히 짚는다. 두 번 두드리는 습관만 유지하면 음을 어디로 옮겨도 같은 곡으로 들려서, 화성을 바꿔가며 얼마든지 늘릴 수 있다.",
  "source": "ai",
  "selected": false
 },
 "rule_based_musicality": {
  "score": 0.9791,
  "score_10": 9.79,
  "metrics": {
   "motif_consistency": {
    "value": 1.0,
    "target": 0.7,
    "met": true,
    "detail": "4/4 프레이즈에 등장 · 1-4:statement, 5-8:statement, 9-12:statement, 13-16:statement"
   },
   "repetition_balance": {
    "value": 0.9375,
    "target": 0.6,
    "met": true,
    "detail": "정확 반복 19% (권장 20~45%)"
   },
   "melodic_contour": {
    "value": 0.9217,
    "target": 0.6,
    "met": true,
    "detail": "도약 13% (권장 15~35%) · 최고음 11마디 / 클라이맥스 11마디"
   },
   "harmonic_consistency": {
    "value": 1.0,
    "target": 0.85,
    "met": true,
    "detail": "코드톤 비율 100%"
   },
   "phrase_balance": {
    "value": 1.0,
    "target": 0.8,
    "met": true,
    "detail": "4/4 프레이즈가 호흡으로 끝난다"
   },
   "dynamic_curve": {
    "value": 1.0,
    "target": 0.7,
    "met": true,
    "detail": "Plan 대비 상관 1.00 (4개 지점)"
   },
   "texture_contrast": {
    "value": 1.0,
    "target": 0.5,
    "met": true,
    "detail": "A→B: 음역·리듬; B→A': 음역·리듬"
   },
   "playability": {
    "value": 0.95,
    "target": 0.7,
    "met": true,
    "detail": "스팬 초과 0회 · 평균 이동 3.5반음 · 연속 도약 최대 1회"
   }
  },
  "unmet": []
 },
 "validator_warnings": [],
 "total_measures": 16
}
```

---

## 출력 JSON 스키마

```json
{
  "$defs": {
    "RevisionRequest": {
      "additionalProperties": false,
      "properties": {
        "measures": {
          "description": "고칠 마디 범위 [시작, 끝]",
          "items": {
            "type": "integer"
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Measures",
          "type": "array"
        },
        "issue": {
          "description": "무엇이 문제인가",
          "title": "Issue",
          "type": "string"
        },
        "instruction": {
          "description": "어떻게 고칠 것인가 — 작곡가가 그대로 실행할 수 있게",
          "title": "Instruction",
          "type": "string"
        }
      },
      "required": [
        "measures",
        "issue",
        "instruction"
      ],
      "title": "RevisionRequest",
      "type": "object"
    },
    "RubricScores": {
      "additionalProperties": false,
      "description": "§7.5 루브릭 10항목. Structured Outputs 로 강제하려면 필드가 명시적이어야 한다\n(자유 키 dict 는 JSON Schema 로 고정할 수 없어 모델이 항목을 빠뜨린다).",
      "properties": {
        "motif_development": {
          "maximum": 10,
          "minimum": 0,
          "title": "Motif Development",
          "type": "number"
        },
        "form_clarity": {
          "maximum": 10,
          "minimum": 0,
          "title": "Form Clarity",
          "type": "number"
        },
        "harmony": {
          "maximum": 10,
          "minimum": 0,
          "title": "Harmony",
          "type": "number"
        },
        "voice_leading": {
          "maximum": 10,
          "minimum": 0,
          "title": "Voice Leading",
          "type": "number"
        },
        "phrasing": {
          "maximum": 10,
          "minimum": 0,
          "title": "Phrasing",
          "type": "number"
        },
        "climax_ending": {
          "maximum": 10,
          "minimum": 0,
          "title": "Climax Ending",
          "type": "number"
        },
        "student_fit": {
          "maximum": 10,
          "minimum": 0,
          "title": "Student Fit",
          "type": "number"
        },
        "competition_effect": {
          "maximum": 10,
          "minimum": 0,
          "title": "Competition Effect",
          "type": "number"
        },
        "notation": {
          "maximum": 10,
          "minimum": 0,
          "title": "Notation",
          "type": "number"
        },
        "originality": {
          "maximum": 10,
          "minimum": 0,
          "title": "Originality",
          "type": "number"
        }
      },
      "required": [
        "motif_development",
        "form_clarity",
        "harmony",
        "voice_leading",
        "phrasing",
        "climax_ending",
        "student_fit",
        "competition_effect",
        "notation",
        "originality"
      ],
      "title": "RubricScores",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "description": "§7.5 비평가 출력.",
  "properties": {
    "scores": {
      "$ref": "#/$defs/RubricScores"
    },
    "strengths": {
      "items": {
        "type": "string"
      },
      "maxItems": 4,
      "title": "Strengths",
      "type": "array"
    },
    "revision_requests": {
      "items": {
        "$ref": "#/$defs/RevisionRequest"
      },
      "title": "Revision Requests",
      "type": "array"
    },
    "overall_comment": {
      "default": "",
      "title": "Overall Comment",
      "type": "string"
    }
  },
  "required": [
    "scores"
  ],
  "title": "CriticReport",
  "type": "object"
}
```
