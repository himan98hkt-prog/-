<!-- 단계: phrase_25_28 · 응답 파일: phrase_25_28_response.json -->
# 작업

아래 시스템 지시를 따르고, **맨 아래 JSON 스키마에 맞는 JSON 하나만** 다음 파일에 써라.

    /home/user/-/concours-composer/runs/golden/g05/phrase_25_28_response.json

25~28마디만 만든다. 각 성부의 dur 합계는 정확히 한 마디여야 하고, 동시 타건 폭은 14반음 이하, 음역은 36~96 안이어야 한다. 왼손 최고음이 오른손 최저음을 넘으면 안 된다.

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
   25,
   28
  ],
  "motif_treatment": "transpose_to_dominant",
  "texture_rh": "팡파르를 딸림화음 위로 옮겨 한 번 더 세운다",
  "texture_lh": "옥타브 베이스 + 화음",
  "dynamic": "mf"
 },
 "measure_range": [
  25,
  28
 ],
 "harmony": [
  {
   "measure": 25,
   "roman": "V7"
  },
  {
   "measure": 26,
   "roman": "V7"
  },
  {
   "measure": 27,
   "roman": "ii"
  },
  {
   "measure": 28,
   "roman": "V7"
  }
 ],
 "next_harmony": "I",
 "key": "G",
 "meter": "4/4",
 "tempo": 120,
 "previous_measures": [
  {
   "number": 17,
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
   "number": 18,
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
  },
  {
   "number": 19,
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
       "dur": 2.0,
       "pitches": [
        "C3",
        "C4"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "G3",
        "E4"
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
   "number": 20,
   "rh": [
    {
     "voice": 1,
     "events": [
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
        "C6"
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
        "A5"
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
        "D5"
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
   "number": 21,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.75,
       "pitches": [
        "G4",
        "D5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "G4",
        "D5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "D5",
        "G5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "G5",
        "B5"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "D5",
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
   "dynamics": "ff",
   "text": null,
   "pedal": true
  },
  {
   "number": 22,
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
        "F#6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.5,
       "pitches": [
        "G6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
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
   "number": 23,
   "rh": [
    {
     "voice": 1,
     "events": [
      {
       "dur": 0.75,
       "pitches": [
        "C6",
        "E6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 0.25,
       "pitches": [
        "C6",
        "E6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "G5",
        "C6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "E5",
        "C6"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 1.0,
       "pitches": [
        "G5",
        "C6"
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
        "C3",
        "C4"
       ],
       "tie": null,
       "artic": "none",
       "slur": null
      },
      {
       "dur": 2.0,
       "pitches": [
        "G3",
        "E4"
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
   "number": 24,
   "rh": [
    {
     "voice": 1,
     "events": [
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
        "C6"
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
        "A5"
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
