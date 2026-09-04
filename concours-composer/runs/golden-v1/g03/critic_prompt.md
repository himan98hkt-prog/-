<!-- 단계: critic · 응답 파일: critic_response.json -->
# 작업

아래 시스템 지시를 따르고, **맨 아래 JSON 스키마에 맞는 JSON 하나만** 다음 파일에 써라.

    /home/user/-/concours-composer/runs/golden/g03/critic_response.json

당신은 이 곡을 쓰지 않았다. 후하게 주지 마라. 마디 참조는 1~24 안이어야 한다.

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
  "level": 5,
  "grade": "초4",
  "years_of_study": 0,
  "hand_span_interval": 8,
  "strengths": [
   "서정적 표현"
  ],
  "weaknesses": [
   "빠른 패시지"
  ],
  "repertoire_done": [],
  "reading_level": 6,
  "tempo_comfort_max_bpm": 96,
  "notes": ""
 },
 "constraints": {
  "max_span_semitones": 12,
  "lowest_midi": 36,
  "highest_midi": 96,
  "max_tempo_bpm": 96,
  "max_accidental_ratio": 0.2,
  "time_limit_sec": 180,
  "target_difficulty": 5.0,
  "difficulty_feasible_range": [
   1.37,
   8.03
  ]
 },
 "competition": {
  "name": "골든 콩쿨",
  "division": "초4",
  "time_limit_sec": 180,
  "memorization_required": false,
  "repeats_allowed": true,
  "criteria_text": "",
  "judge_notes": ""
 },
 "style_context": [],
 "academy_data": "",
 "request": {
  "mood": "서정적이고 노래하는",
  "form": "ABA",
  "key_preference": [
   "F"
  ],
  "meter": "3/4",
  "tempo": 72,
  "target_difficulty": 5.0,
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
 "score_text": "m1 | [I] | (p) | RH F5/1 D6/2 | LH F2+F3/1 A3+C4/1 A3+C4/1 | ped\nm2 | [I] | RH C6/1 B-5/1 A5/1 | LH F2+F3/1 A3+C4/1 A3+C4/1 | ped\nm3 | [V7] | RH G5/1 E6/2 | LH C3+C4/1 G3+E4/1 G3+E4/1 | ped\nm4 | [V7] | RH D6/0.5 C6/0.5 B-5/2 | LH C3+C4/1 G3+E4/1 G3+E4/1 | ped\nm5 | [ii] | (mp) | RH G5/1 E6/2 | LH G2+G3/1 B-3+D4/1 B-3+D4/1 | ped\nm6 | [ii] | RH D6/1 C6/1 B-5/1 | LH G2+G3/1 B-3+D4/1 B-3+D4/1 | ped\nm7 | [V7] | RH G5/1 E6/2 | LH C3+C4/1 G3+E4/1 G3+E4/1 | ped\nm8 | [I] | RH D6/0.5 C6/0.5 A5/2 | LH F2+F3/1 A3+C4/1 A3+C4/1 | ped\nm9 | [vi] | (mf) | RH A5/1 F6/2 | LH D2+A2+D3/3 | ped\nm10 | [vi] | RH E6/1 D6/1 C6/1 | LH D2+A2+D3/3 | ped\nm11 | [IV] | RH B-5/1 A5/1 F5/1 | LH B-2+F3+B-3/3 | ped\nm12 | [V7] | RH E5/1 G5/2 | LH C3+G3+C4/3 | ped\nm13 | [vi] | (mp) | RH D6/1 F5/1 G5/1 | LH D2+A2+D3/3 | ped\nm14 | [IV] | RH A5/1 B-5/1 A5/1 | LH B-2+F3+B-3/3 | ped\nm15 | [ii] | RH G5/1 B-5/1 G5/1 | LH G2+D3+G3/3 | ped\nm16 | [V7] | RH E5/1 G5/2 | LH C3+G3+C4/3 | ped\nm17 | [I] | (f) | RH C6/1 A6/2 | LH F2+F3/1 A3+C4/1 A3+C4/1 | ped\nm18 | [V7] | RH G6/1 F6/1 E6/1 | LH G2+G3/1 E4+G4/1 E4+G4/1 | ped\nm19 | [IV] | RH D6/1 C6/1 A5/1 | LH B-2+B-3/1 D4+F4/1 D4+F4/1 | ped\nm20 | [V7] | RH G5/1 E5/2 | LH C3+C4/1 G3+E4/1 G3+E4/1 | ped\nm21 | [I] | (p) | RH F5/1 D6/2 | LH F2+F3/1 A3+C4/1 A3+C4/1 | ped\nm22 | [I] | RH C6/1 B-5/1 A5/1 | LH F2+F3/1 A3+C4/1 A3+C4/1 | ped\nm23 | [V7] | RH G5/1 E5/1 C5/1 | LH C3+C4/1 G3+E4/1 G3+E4/1 | ped\nm24 | [I] | RH A4+C5+F5/3 | LH F2+F3/3 | ped",
 "plan": {
  "title_candidates": [
   "올려다본 하늘",
   "느린 강",
   "저녁 언덕"
  ],
  "key": "F",
  "meter": "3/4",
  "tempo": 72,
  "total_measures": 24,
  "duration_est": 60.0,
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
      "texture_rh": "6도 도약 후 긴 음, 그리고 한 음씩 걸어 내려오기. 4마디 끝은 2박 긴 음",
      "texture_lh": "왈츠 베이스 — 1박 옥타브, 2·3박 화음",
      "dynamic": "p"
     },
     {
      "measures": [
       5,
       8
      ],
      "motif_treatment": "sequence_up_2nd",
      "texture_rh": "같은 도약을 2도 위에서. 8마디는 으뜸음으로 내려앉는다",
      "texture_lh": "왈츠 베이스",
      "dynamic": "mp"
     }
    ]
   },
   {
    "label": "B",
    "measures": [
     9,
     16
    ],
    "phrases": [
     {
      "measures": [
       9,
       12
      ],
      "motif_treatment": "mode_change",
      "texture_rh": "나란한 단조(d단조) 색. 도약 폭을 8도로 좁히고 하행을 길게 늘인다",
      "texture_lh": "세 음 지속 화음(온마디). 왈츠 베이스를 멈추고 저음을 한 옥타브 내려 어둡게",
      "dynamic": "mf"
     },
     {
      "measures": [
       13,
       16
      ],
      "motif_treatment": "inversion",
      "texture_rh": "도약을 뒤집어 아래로 떨어뜨린 뒤 다시 걸어 올라온다",
      "texture_lh": "세 음 지속 화음(온마디)",
      "dynamic": "mp"
     }
    ]
   },
   {
    "label": "A'",
    "measures": [
     17,
     24
    ],
    "phrases": [
     {
      "measures": [
       17,
       20
      ],
      "motif_treatment": "statement",
      "texture_rh": "도약을 한 옥타브 위에서 되살린다. 곡 전체의 최고음 A6 이 17마디에 온다",
      "texture_lh": "왈츠 베이스",
      "dynamic": "f"
     },
     {
      "measures": [
       21,
       24
      ],
      "motif_treatment": "repeat",
      "texture_rh": "1~2마디를 음까지 그대로 되돌린 뒤 하행으로 종지",
      "texture_lh": "1~2마디와 동일. 마지막 마디는 옥타브 베이스 위에 세 음 화음",
      "dynamic": "p"
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
    "roman": "vi",
    "bass_note": null
   },
   {
    "measure": 14,
    "roman": "IV",
    "bass_note": null
   },
   {
    "measure": 15,
    "roman": "ii",
    "bass_note": null
   },
   {
    "measure": 16,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 17,
    "roman": "I",
    "bass_note": null
   },
   {
    "measure": 18,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 19,
    "roman": "IV",
    "bass_note": null
   },
   {
    "measure": 20,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 21,
    "roman": "I",
    "bass_note": null
   },
   {
    "measure": 22,
    "roman": "I",
    "bass_note": null
   },
   {
    "measure": 23,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 24,
    "roman": "I",
    "bass_note": null
   }
  ],
  "climax": {
   "measure": 17,
   "how": "6도 도약을 한 옥타브 위로 옮겨 곡 전체의 최고음 A6 을 길게 붙잡고, f 로 왈츠 베이스를 두껍게 받친다"
  },
  "showcase_measures": [
   {
    "range": [
     1,
     4
    ],
    "strength_used": "서정적 표현"
   },
   {
    "range": [
     17,
     20
    ],
    "strength_used": "서정적 표현"
   }
  ],
  "contrast_section": {
   "label": "B",
   "how": "나란한 단조로 색을 바꾸고, 왼손을 왈츠 베이스에서 세 음 지속 화음으로 멈춰 세워 저음을 한 옥타브 내린다. 오른손은 도약 폭을 6도에서 8도로 넓힌다"
  },
  "modulations": [],
  "ending": {
   "type": "완전종지 — V7 에서 I 로, 옥타브 베이스 위 세 음 화음",
   "measures": [
    21,
    24
   ]
  },
  "dynamics_curve": [
   {
    "measure": 1,
    "dyn": "p"
   },
   {
    "measure": 5,
    "dyn": "mp"
   },
   {
    "measure": 9,
    "dyn": "mf"
   },
   {
    "measure": 13,
    "dyn": "mp"
   },
   {
    "measure": 17,
    "dyn": "f"
   },
   {
    "measure": 21,
    "dyn": "p"
   }
  ],
  "pedal_plan": "마디마다 첫 박에 밟고 다음 마디 첫 박에서 바꾼다. 화성이 한 마디에 하나씩만 바뀌므로 흐리지 않는다",
  "difficulty_target": 5.0
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
         "F5"
        ],
        "tie": null,
        "artic": "none",
        "slur": "start"
       },
       {
        "dur": 2.0,
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
        "dur": 1.0,
        "pitches": [
         "F2",
         "F3"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 1.0,
        "pitches": [
         "A3",
         "C4"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 1.0,
        "pitches": [
         "A3",
         "C4"
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
    "number": 2,
    "rh": [
     {
      "voice": 1,
      "events": [
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
         "B-5"
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
        "dur": 1.0,
        "pitches": [
         "F2",
         "F3"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 1.0,
        "pitches": [
         "A3",
         "C4"
        ],
        "tie": null,
        "artic": "none",
        "slur": null
       },
       {
        "dur": 1.0,
        "pitches": [
         "A3",
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
   }
  ],
  "key": "F",
  "meter": "3/4",
  "tempo": 72,
  "character_label": "올려다보기",
  "why_it_works": "6도를 한 번에 뛰어올라 긴 음으로 머문 뒤 한 음씩 걸어 내려오는 모양이라, 뛰는 순간이 그대로 곡의 얼굴이 된다. 뛰는 폭을 좁히면 B 섹션의 잔잔한 노래가 되고, 뒤집어 내려꽂으면 대비 구간이 저절로 생긴다.",
  "source": "ai",
  "selected": false
 },
 "rule_based_musicality": {
  "score": 0.9626,
  "score_10": 9.63,
  "metrics": {
   "motif_consistency": {
    "value": 1.0,
    "target": 0.7,
    "met": true,
    "detail": "6/6 프레이즈에 등장 · 1-4:statement, 5-8:statement, 9-12:statement, 13-16:inversion, 17-20:statement, 21-24:statement"
   },
   "repetition_balance": {
    "value": 0.8333,
    "target": 0.6,
    "met": true,
    "detail": "정확 반복 17% (권장 20~45%)"
   },
   "melodic_contour": {
    "value": 1.0,
    "target": 0.6,
    "met": true,
    "detail": "도약 19% (권장 15~35%) · 최고음 17마디 / 클라이맥스 17마디"
   },
   "harmonic_consistency": {
    "value": 0.9045,
    "target": 0.85,
    "met": true,
    "detail": "코드톤 비율 90%"
   },
   "phrase_balance": {
    "value": 1.0,
    "target": 0.8,
    "met": true,
    "detail": "6/6 프레이즈가 호흡으로 끝난다"
   },
   "dynamic_curve": {
    "value": 1.0,
    "target": 0.7,
    "met": true,
    "detail": "Plan 대비 상관 1.00 (6개 지점)"
   },
   "texture_contrast": {
    "value": 1.0,
    "target": 0.5,
    "met": true,
    "detail": "A→B: 동시음·음역·리듬; B→A': 동시음·음역·리듬"
   },
   "playability": {
    "value": 0.95,
    "target": 0.7,
    "met": true,
    "detail": "스팬 초과 0회 · 평균 이동 3.8반음 · 연속 도약 최대 1회"
   }
  },
  "unmet": []
 },
 "validator_warnings": [],
 "total_measures": 24
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
