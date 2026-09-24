# -*- coding: utf-8 -*-
"""회귀 테스트용 원곡 20곡의 사양 (지시서 9장 1단계).

전부 **자사 오리지널** 이다 — 지시서 7장 화이트리스트의 마지막 항목.
저작권 걱정이 없고, 무엇보다 **정답 화성을 우리가 정해서 만들기 때문에
정답지가 추정이 아니라 사실이다.** 남의 악보를 받아 적은 정답지는
사람이 틀릴 수 있지만 이 20곡은 그럴 수 없다.

지시서가 지목한 취약 케이스를 일부러 덮는다:
  * 3박자 곡        (waltz_*, minuet_*, 3/4·3/8·6/8)
  * 단조 곡         (key 가 소문자인 것들 — 화성단음계 V, vii° 포함)
  * 화성이 자주 바뀌는 곡  (harmonic rhythm = 박마다)
  * 못갖춘마디, 반복기호, 자리바꿈, 부속화음, 딸림7화음

bars 형식: 한 마디 = [(화음이름, 박수), ...]. 박수의 합 = 그 마디 길이.
"""

# id, title, key, ts, lh(왼손 텍스처), rh(오른손 패턴), bars, 기타
PIECES = [

    # ---- 4박자 · 장조 · 기본 ------------------------------------------------
    dict(id='p01_block_c', title='첫 화음 연습 (C장조)', key='C', ts='4/4',
         lh='block', rh='quarter', level=1, style='strings',
         bars=[[('C', 4)], [('F', 4)], [('G', 4)], [('C', 4)],
               [('C', 4)], [('Am', 4)], [('G7', 4)], [('C', 4)]]),

    dict(id='p02_alberti_c', title='알베르티 베이스 연습 (C장조)', key='C', ts='4/4',
         lh='alberti', rh='eighth', level=3, style='chamber',
         bars=[[('C', 4)], [('G7', 2), ('C', 2)], [('F', 2), ('C', 2)], [('G7', 4)],
               [('C', 4)], [('F', 2), ('G', 2)], [('C', 2), ('G7', 2)], [('C', 4)]]),

    dict(id='p03_scale_g', title='음계 연습곡 (G장조)', key='G', ts='4/4',
         lh='octave', rh='sixteenth', level=4, style='march',
         bars=[[('G', 4)], [('C', 4)], [('D7', 4)], [('G', 4)],
               [('Em', 4)], [('Am', 4)], [('D7', 4)], [('G', 4)]]),

    dict(id='p04_f_major_arp', title='분산화음 연습 (F장조)', key='F', ts='4/4',
         lh='arp', rh='quarter', level=3, style='warm',
         bars=[[('F', 4)], [('Bb', 4)], [('C7', 4)], [('F', 4)],
               [('Dm', 4)], [('Bb', 4)], [('C7', 4)], [('F', 4)]]),

    # ---- 3박자 (지시서가 지목한 취약 케이스) ---------------------------------
    dict(id='p05_waltz_c', title='작은 왈츠 (C장조)', key='C', ts='3/4',
         lh='waltz', rh='waltz_melody', level=2, style='fairytale',
         bars=[[('C', 3)], [('G7', 3)], [('C', 3)], [('F', 3)],
               [('C', 3)], [('G7', 3)], [('C', 3)], [('C', 3)]]),

    dict(id='p06_waltz_fast_d', title='화성이 빠른 왈츠 (D장조)', key='D', ts='3/4',
         lh='waltz', rh='waltz_melody', level=5, style='chamber',
         bars=[[('D', 1), ('A', 1), ('D', 1)], [('G', 1), ('D', 1), ('A7', 1)],
               [('Bm', 1), ('Em', 1), ('A7', 1)], [('D', 3)],
               [('G', 1), ('A7', 1), ('D', 1)], [('Em', 1), ('A7', 1), ('D', 1)],
               [('A7', 3)], [('D', 3)]]),

    dict(id='p07_minuet_g', title='미뉴에트풍 소품 (G장조)', key='G', ts='3/4',
         lh='two_voice', rh='minuet', level=4, style='chamber',
         bars=[[('G', 3)], [('D7', 3)], [('G', 3)], [('C', 2), ('D7', 1)],
               [('G', 3)], [('Em', 3)], [('A7', 3)], [('D', 3)],
               [('G', 3)], [('C', 3)], [('D7', 3)], [('G', 3)]]),

    dict(id='p08_three_eight', title='3/8박 작은 노래 (F장조)', key='F', ts='3/8',
         lh='block', rh='eighth', level=2, style='fairytale',
         bars=[[('F', 1.5)], [('C7', 1.5)], [('F', 1.5)], [('Bb', 1.5)],
               [('F', 1.5)], [('C7', 1.5)], [('F', 1.5)], [('F', 1.5)]]),

    # ---- 6/8 (겹박자) -------------------------------------------------------
    dict(id='p09_six_eight', title='뱃노래 (G장조 6/8)', key='G', ts='6/8',
         lh='arp', rh='compound', level=4, style='warm',
         bars=[[('G', 3)], [('C', 1.5), ('G', 1.5)], [('D7', 3)], [('G', 3)],
               [('Em', 1.5), ('Am', 1.5)], [('D7', 3)], [('G', 1.5), ('D7', 1.5)],
               [('G', 3)]]),

    # ---- 단조 (지시서가 지목한 취약 케이스) ----------------------------------
    dict(id='p10_minor_am', title='가단조 소품', key='a', ts='4/4',
         lh='block', rh='quarter', level=3, style='strings',
         bars=[[('Am', 4)], [('Dm', 4)], [('E7', 4)], [('Am', 4)],
               [('F', 4)], [('Dm', 4)], [('E7', 4)], [('Am', 4)]]),

    dict(id='p11_minor_em_alberti', title='마단조 알베르티', key='e', ts='4/4',
         lh='alberti', rh='eighth', level=5, style='chamber',
         bars=[[('Em', 4)], [('Am', 2), ('B7', 2)], [('Em', 4)], [('C', 2), ('B7', 2)],
               [('Em', 4)], [('Am', 4)], [('B7', 4)], [('Em', 4)]]),

    dict(id='p12_minor_dm_waltz', title='라단조 왈츠', key='d', ts='3/4',
         lh='waltz', rh='waltz_melody', level=4, style='warm',
         bars=[[('Dm', 3)], [('Gm', 3)], [('A7', 3)], [('Dm', 3)],
               [('Bb', 3)], [('Gm', 3)], [('A7', 3)], [('Dm', 3)]]),

    dict(id='p13_minor_gm_dim', title='사단조 — 이끔음 감삼화음', key='g', ts='4/4',
         lh='two_voice', rh='eighth', level=6, style='orchestra',
         bars=[[('Gm', 4)], [('F#dim', 4)], [('Gm', 4)], [('Cm', 4)],
               [('D7', 4)], [('Gm', 2), ('Cm', 2)], [('D7', 4)], [('Gm', 4)]]),

    dict(id='p14_minor_bm_fast', title='나단조 — 화성이 잦은 곡', key='b', ts='4/4',
         lh='block', rh='eighth', level=6, style='orchestra',
         bars=[[('Bm', 2), ('Em', 2)], [('F#7', 2), ('Bm', 2)],
               [('G', 2), ('Em', 2)], [('F#7', 4)],
               [('Bm', 2), ('G', 2)], [('Em', 2), ('F#7', 2)],
               [('Bm', 2), ('F#7', 2)], [('Bm', 4)]]),

    # ---- 화성이 자주 바뀌는 곡 (박마다) --------------------------------------
    dict(id='p15_fast_harmony_c', title='박마다 바뀌는 화성 (C장조)', key='C', ts='4/4',
         lh='block', rh='eighth', level=7, style='chamber',
         bars=[[('C', 1), ('Am', 1), ('F', 1), ('G', 1)],
               [('C', 1), ('Em', 1), ('Dm', 1), ('G7', 1)],
               [('C', 1), ('F', 1), ('C', 1), ('G', 1)],
               [('Am', 1), ('Dm', 1), ('G7', 1), ('C', 1)],
               [('F', 2), ('G', 2)], [('Em', 2), ('Am', 2)],
               [('Dm', 1), ('G7', 1), ('C', 1), ('G7', 1)], [('C', 4)]]),

    dict(id='p16_fast_harmony_bb', title='박마다 바뀌는 화성 (Bb장조)', key='Bb', ts='4/4',
         lh='alberti', rh='sixteenth', level=8, style='orchestra',
         bars=[[('Bb', 1), ('Gm', 1), ('Eb', 1), ('F', 1)],
               [('Bb', 1), ('Dm', 1), ('Cm', 1), ('F7', 1)],
               [('Bb', 2), ('Eb', 2)], [('F7', 2), ('Bb', 2)],
               [('Gm', 1), ('Cm', 1), ('F7', 1), ('Bb', 1)],
               [('Eb', 2), ('Cm', 2)], [('F7', 4)], [('Bb', 4)]]),

    # ---- 2박자 · 못갖춘마디 · 반복 -------------------------------------------
    dict(id='p17_two_four_pickup', title='2/4박 행진 (못갖춘마디)', key='C', ts='2/4',
         lh='octave', rh='eighth', level=3, style='march', pickup=[('G', 1)],
         bars=[[('C', 2)], [('G7', 2)], [('C', 2)], [('F', 2)],
               [('C', 2)], [('G7', 2)], [('C', 2)], [('C', 2)]]),

    dict(id='p18_repeat_g', title='반복기호가 있는 소품 (G장조)', key='G', ts='4/4',
         lh='block', rh='quarter', level=2, style='strings', repeat=True,
         bars=[[('G', 4)], [('C', 4)], [('D7', 4)], [('G', 4)],
               [('C', 4)], [('G', 4)], [('D7', 4)], [('G', 4)]]),

    # ---- 자리바꿈 · 부속화음 -------------------------------------------------
    dict(id='p19_inversions_c', title='자리바꿈 연습 (C장조)', key='C', ts='4/4',
         lh='inversion', rh='quarter', level=5, style='warm',
         bars=[[('C', 4)], [('C', 2), ('F', 2)], [('G', 4)], [('C', 4)],
               [('Am', 4)], [('F', 2), ('C', 2)], [('G7', 4)], [('C', 4)]]),

    dict(id='p20_secondary_f', title='부속화음 연습 (F장조)', key='F', ts='4/4',
         lh='arp', rh='eighth', level=7, style='orchestra',
         bars=[[('F', 4)], [('D7', 4)], [('Gm', 4)], [('C7', 4)],
               [('F', 4)], [('A7', 4)], [('Dm', 4)], [('C7', 2), ('F', 2)]]),
]

assert len({p['id'] for p in PIECES}) == len(PIECES) == 20
