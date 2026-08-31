<!-- 단계: critic · 응답 파일: critic_response.json -->
# 작업

아래 시스템 지시를 따르고, **맨 아래 JSON 스키마에 맞는 JSON 하나만** 다음 파일에 써라.

    /home/user/-/concours-composer/runs/golden/g05/critic_response.json

당신은 이 곡을 쓰지 않았다. 후하게 주지 마라. 마디 참조는 1~32 안이어야 한다.

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
 "score_text": "m1 | [I] | (f) | RH D5/0.75 D5/0.25 G5/1 B5/1 G5/1 | LH G2+G3/2 D3+B3/2 | ped\nm2 | [I] | RH A5/0.25 B5/0.25 C6/0.25 D6/0.25 B5/1 G5/2 | LH G2+G3/2 D3+B3/2 | ped\nm3 | [V7] | RH A5/0.75 A5/0.25 D6/1 F#6/1 D6/1 | LH D2+D3/2 A2+F#3/2 | ped\nm4 | [V7] | RH E6/0.25 D6/0.25 C6/0.25 B5/0.25 A5/1 D5/2 | LH D2+D3/2 A2+F#3/2 | ped\nm5 | [ii] | (mf) | RH E5/0.75 E5/0.25 A5/1 C6/1 A5/1 | LH A2+A3/2 E3+C4/2 | ped\nm6 | [ii] | RH B5/0.25 C6/0.25 D6/0.25 E6/0.25 C6/1 A5/2 | LH A2+A3/2 E3+C4/2 | ped\nm7 | [V7] | RH A5/0.75 A5/0.25 D6/1 F#6/1 D6/1 | LH D2+D3/2 A2+F#3/2 | ped\nm8 | [I] | RH E6/0.25 D6/0.25 B5/0.25 G5/0.25 D5/1 G5/2 | LH G2+G3/2 D3+B3/2 | ped\nm9 | [vi] | (p) | RH B4/0.75 B4/0.25 E5/1 G5/1 E5/1 | LH E2+B2+E3/4 | ped\nm10 | [vi] | RH F#5/0.25 G5/0.25 A5/0.25 B5/0.25 G5/1 E5/2 | LH E2+B2+E3/4 | ped\nm11 | [IV] | RH C6/0.75 C6/0.25 G5/1 E5/1 C5/1 | LH C3+G3+C4/4 | ped\nm12 | [V7] | RH D5/0.5 E5/0.5 F#5/1 A5/2 | LH A2+D3+F#3/4 | ped\nm13 | [I] | (mp) | RH G5/0.75 G5/0.25 D5/1 A4/1 D5/1 | LH G2+D3+G3/4 | ped\nm14 | [IV] | RH C5/0.25 D5/0.25 E5/0.25 G5/0.25 B5/1 G5/2 | LH C3+G3+C4/4 | ped\nm15 | [ii] | RH C6/0.75 C6/0.25 A5/1 E5/1 A5/1 | LH A2+E3+A3/4 | ped\nm16 | [V7] | RH D6/0.5 C6/0.5 A5/1 F#5/2 | LH D2+A2+D3/4 | ped\nm17 | [I] | (f) | RH D5/0.75 D5/0.25 G5/1 B5/1 G5/1 | LH G2+G3/2 D3+B3/2 | ped\nm18 | [I] | RH A5/0.25 B5/0.25 C6/0.25 D6/0.25 B5/1 G5/2 | LH G2+G3/2 D3+B3/2 | ped\nm19 | [IV] | RH C6/0.75 C6/0.25 G5/1 E5/1 C5/1 | LH C3+C4/2 G3+E4/2 | ped\nm20 | [V7] | RH D6/0.25 C6/0.25 B5/0.25 A5/0.25 F#5/1 D5/2 | LH D2+D3/2 A2+F#3/2 | ped\nm21 | [I] | (ff) | RH G4+D5/0.75 G4+D5/0.25 D5+G5/1 G5+B5/1 D5+G5/1 | LH G2+G3/2 D3+B3/2 | ped\nm22 | [I] | RH A5/0.25 B5/0.25 C6/0.25 D6/0.25 E6/0.25 F#6/0.25 G6/0.5 D6/2 | LH G2+G3/2 D3+B3/2 | ped\nm23 | [IV] | RH C6+E6/0.75 C6+E6/0.25 G5+C6/1 E5+C6/1 G5+C6/1 | LH C3+C4/2 G3+E4/2 | ped\nm24 | [V7] | RH D6/0.25 C6/0.25 B5/0.25 A5/0.25 F#5/1 A5/2 | LH D2+D3/2 A2+F#3/2 | ped\nm25 | [V7] | (mf) | RH A5/0.75 A5/0.25 D6/1 F#6/1 D6/1 | LH D2+D3/2 A2+F#3/2 | ped\nm26 | [V7] | RH E6/0.25 D6/0.25 C6/0.25 B5/0.25 A5/1 D5/2 | LH D2+D3/2 A2+F#3/2 | ped\nm27 | [ii] | RH E5/0.75 E5/0.25 A5/1 C6/1 A5/1 | LH A2+A3/2 E3+C4/2 | ped\nm28 | [V7] | RH B5/0.25 C6/0.25 D6/0.25 E6/0.25 C6/1 A5/2 | LH D2+D3/2 A2+F#3/2 | ped\nm29 | [I] | (f) | RH D5/0.75 D5/0.25 G5/1 B5/1 G5/1 | LH G2+G3/2 D3+B3/2 | ped\nm30 | [I] | RH A5/0.25 B5/0.25 C6/0.25 D6/0.25 B5/1 G5/2 | LH G2+G3/2 D3+B3/2 | ped\nm31 | [V7] | RH D6/0.5 C6/0.5 B5/0.5 A5/0.5 F#5/2 | LH D2+D3/2 A2+F#3/2 | ped\nm32 | [I] | RH G4+B4+D5+G5/4 | LH G2+G3/4 | ped",
 "plan": {
  "title_candidates": [
   "개선 행진",
   "높은 탑",
   "빛나는 길"
  ],
  "key": "G",
  "meter": "4/4",
  "tempo": 120,
  "total_measures": 32,
  "duration_est": 64.0,
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
      "texture_rh": "붙점 팡파르 + 16분음표 하행 스케일. 4마디 끝은 2박 긴 음",
      "texture_lh": "옥타브 베이스 2분음표 + 화음 2분음표",
      "dynamic": "f"
     },
     {
      "measures": [
       5,
       8
      ],
      "motif_treatment": "sequence_up_2nd",
      "texture_rh": "같은 팡파르를 2도 위에서. 8마디는 하행 스케일로 종지",
      "texture_lh": "옥타브 베이스 + 화음",
      "dynamic": "mf"
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
      "texture_rh": "나란한 단조(e단조) 색. 팡파르를 낮은 자리로 옮기고 스케일을 짧게 자른다",
      "texture_lh": "세 음 지속 화음(온마디). 옥타브 걸음을 멈춰 세운다",
      "dynamic": "p"
     },
     {
      "measures": [
       13,
       16
      ],
      "motif_treatment": "inversion",
      "texture_rh": "팡파르의 도약을 뒤집어 아래로. 스케일은 상행으로 되돌린다",
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
      "texture_rh": "1~2마디를 그대로 되돌린 뒤 버금딸림으로 넓힌다",
      "texture_lh": "옥타브 베이스 + 화음",
      "dynamic": "f"
     },
     {
      "measures": [
       21,
       24
      ],
      "motif_treatment": "fragment_head",
      "texture_rh": "팡파르를 3도·5도 겹친 화음으로 두껍게. 22마디에서 한 옥타브 반 스케일로 곡 최고음 G6 까지 올라간다",
      "texture_lh": "옥타브 베이스 + 화음",
      "dynamic": "ff"
     }
    ]
   },
   {
    "label": "C",
    "measures": [
     25,
     32
    ],
    "phrases": [
     {
      "measures": [
       25,
       28
      ],
      "motif_treatment": "transpose_to_dominant",
      "texture_rh": "팡파르를 딸림화음 위로 옮겨 한 번 더 세운다",
      "texture_lh": "옥타브 베이스 + 화음",
      "dynamic": "mf"
     },
     {
      "measures": [
       29,
       32
      ],
      "motif_treatment": "repeat",
      "texture_rh": "1~2마디를 음까지 그대로 재현한 뒤 네 음 화음으로 마무리",
      "texture_lh": "1~2마디와 동일. 마지막 마디는 옥타브를 온음표로",
      "dynamic": "f"
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
    "roman": "I",
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
    "roman": "IV",
    "bass_note": null
   },
   {
    "measure": 24,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 25,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 26,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 27,
    "roman": "ii",
    "bass_note": null
   },
   {
    "measure": 28,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 29,
    "roman": "I",
    "bass_note": null
   },
   {
    "measure": 30,
    "roman": "I",
    "bass_note": null
   },
   {
    "measure": 31,
    "roman": "V7",
    "bass_note": null
   },
   {
    "measure": 32,
    "roman": "I",
    "bass_note": null
   }
  ],
  "climax": {
   "measure": 22,
   "how": "한 옥타브 반 상행 스케일로 곡 전체의 최고음 G6 에 도달하고, ff 로 왼손 옥타브 베이스가 받친다"
  },
  "showcase_measures": [
   {
    "range": [
     1,
     4
    ],
    "strength_used": "화려한 스케일"
   },
   {
    "range": [
     21,
     24
    ],
    "strength_used": "화려한 스케일"
   }
  ],
  "contrast_section": {
   "label": "B",
   "how": "나란한 단조로 색을 바꾸고, 왼손을 옥타브 걸음에서 세 음 지속 화음으로 멈춰 세우며, 오른손 팡파르를 한 옥타브 낮은 자리로 옮긴다"
  },
  "modulations": [],
  "ending": {
   "type": "완전종지 — V7 에서 I 로, 네 음 화음을 온음표로",
   "measures": [
    29,
    32
   ]
  },
  "dynamics_curve": [
   {
    "measure": 1,
    "dyn": "f"
   },
   {
    "measure": 5,
    "dyn": "mf"
   },
   {
    "measure": 9,
    "dyn": "p"
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
    "dyn": "ff"
   },
   {
    "measure": 25,
    "dyn": "mf"
   },
   {
    "measure": 29,
    "dyn": "f"
   }
  ],
  "pedal_plan": "화성이 바뀌는 마디마다 밟아 바꾼다. 16분음표 스케일 구간은 얕게 밟아 음이 뭉치지 않게 한다",
  "difficulty_target": 6.0
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
 "rule_based_musicality": {
  "score": 0.9221,
  "score_10": 9.22,
  "metrics": {
   "motif_consistency": {
    "value": 0.875,
    "target": 0.7,
    "met": true,
    "detail": "7/8 프레이즈에 등장 · 1-4:statement, 5-8:statement, 9-12:statement, 17-20:statement, 21-24:fragment_head, 25-28:statement"
   },
   "repetition_balance": {
    "value": 1.0,
    "target": 0.6,
    "met": true,
    "detail": "정확 반복 25% (권장 20~45%)"
   },
   "melodic_contour": {
    "value": 1.0,
    "target": 0.6,
    "met": true,
    "detail": "도약 18% (권장 15~35%) · 최고음 22마디 / 클라이맥스 22마디"
   },
   "harmonic_consistency": {
    "value": 0.9067,
    "target": 0.85,
    "met": true,
    "detail": "코드톤 비율 91%"
   },
   "phrase_balance": {
    "value": 1.0,
    "target": 0.8,
    "met": true,
    "detail": "8/8 프레이즈가 호흡으로 끝난다"
   },
   "dynamic_curve": {
    "value": 1.0,
    "target": 0.7,
    "met": true,
    "detail": "Plan 대비 상관 1.00 (8개 지점)"
   },
   "texture_contrast": {
    "value": 0.6667,
    "target": 0.5,
    "met": true,
    "detail": "A→B: 동시음·리듬; B→A': 동시음·리듬"
   },
   "playability": {
    "value": 0.95,
    "target": 0.7,
    "met": true,
    "detail": "스팬 초과 0회 · 평균 이동 3.2반음 · 연속 도약 최대 1회"
   }
  },
  "unmet": []
 },
 "validator_warnings": [],
 "total_measures": 32
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
