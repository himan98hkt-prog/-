# 피아노 자동 반주 — 4단계 작업 보고 (PDF 업로드)

개발지시서 **9장 4단계** 구현 결과. 체크리스트는 세 줄이다.

> - [ ] OMR API 연동
> - [ ] 화성 확인 화면 재사용
> - [ ] 월 업로드 제한

코드는 [`mr/piano_mr/pdf.py`](../mr/piano_mr/pdf.py) ·
[`omr.py`](../mr/piano_mr/omr.py) · [`uploads.py`](../mr/piano_mr/uploads.py),
앞 단계 보고는 [MR-ENGINE.md](MR-ENGINE.md) · [MR-CATALOG.md](MR-CATALOG.md) ·
[MR-PLAYER.md](MR-PLAYER.md).

```bash
cd mr
python3 serve.py --catalog catalog
#   PDF 올리기      http://127.0.0.1:8765/static/upload.html
#   화성 확인 화면   http://127.0.0.1:8765/
```

---

## 1. 체크리스트 대조

| 지시서 9장 4단계 | 상태 |
|---|---|
| **OMR API 연동** | 구조 완성 · **공급사 실서비스로는 못 돌려 봤다** (아래 2장) |
| **화성 확인 화면 재사용** | 완료 — 인식이 끝나면 그 곡의 확인 화면으로 바로 간다 |
| **월 업로드 제한** | 완료 — 쪽 단위, 계정별, 매달 리셋 |

그리고 지시서가 4단계에 붙여 둔 제약 둘.

| 제약 | 어디에 |
|---|---|
| 7장 "서버 영구 저장·재배포 금지" | PDF 는 격리 폴더에만, MusicXML 이 오면 즉시 삭제 (4장) |
| 3장 "'PDF 넣으면 바로 완성'을 약속하지 말 것" | 업로드 화면이 인식률을 먼저 말하고, 확인 없이는 완료가 안 된다 (5장) |

---

## 2. OMR 공급사 API 는 확인하지 못했다

지시서는 Klangio Scan2Notes / Soundslice 를 "유일한 외부 유료 요소"로 지목한다.
그런데 이 작업을 한 컨테이너에서 **`klang.io` 와 `api-docs.klang.io` 가 둘 다 조직
egress 정책에 막혀 있었다** (프록시가 차단). 공식 API 문서를 볼 수 없었다.

여기서 고를 수 있는 길이 둘이었다.

1. 기억으로 엔드포인트 이름을 지어내 하드코딩한다
2. 모양만 잡고 값은 설정으로 뺀다

**2번을 골랐다.** 1번은 그럴듯한데 틀린 코드를 남기고, 그건 나중에 키를 받은
사람이 "왜 안 되지"로 반나절을 쓰게 만든다. 지금 코드는 주소를 하나도 지어내지
않는다 — 설정이 비어 있으면 이렇게 말한다:

```
OMR 서비스 설정이 비어 있습니다 (MR_OMR_BASE, MR_OMR_SUBMIT, MR_OMR_RESULT).
신청제(manual)로 두거나 환경변수를 채우세요 — piano_mr/omr.py 참고.
```

키와 문서가 손에 들어오면 **환경변수만 채우면 된다. 코드는 안 고친다.**

```bash
export MR_OMR_PROVIDER=http
export MR_OMR_BASE=https://api.공급사.com
export MR_OMR_KEY=발급받은키
export MR_OMR_KEY_HEADER=kl-api-key      # 비우면 Authorization: Bearer
export MR_OMR_SUBMIT=/transcription
export MR_OMR_STATUS=/transcription/{job}
export MR_OMR_RESULT=/transcription/{job}/musicxml
export MR_OMR_JOB_FIELD=job_id
export MR_OMR_STATE_FIELD=status
```

### 확인할 수 있는 것은 확인했다

공급사 필드 이름은 못 맞춰 봤지만, **전선(wire) 위의 동작은 진짜 HTTP 서버를 띄워
확인했다** (`tests/test_omr.py`). 멀티파트를 제대로 싸는지, 키 헤더가 붙는지,
폴링이 상태를 옳게 옮기는지, 402(크레딧 소진) 같은 실패를 삼키지 않는지.

```
test_http_submit_sends_a_real_multipart_with_the_key
test_http_polls_until_ready_then_fetches
test_http_surfaces_an_http_error_body          # 402 + "out of credits"
test_http_says_what_is_missing_rather_than_guessing_a_url
```

### 기본값은 신청제다

지시서 8.3 ③ 이 그냥 대안으로 적어 둔 게 아니다:

> **③ PDF 업로드는 신청제도 좋다.** 원장님이 악보를 보내면 1~2일 내 납품. 품질
> 보장이 되고 기대치 관리가 된다. **경험상 "무한 자동생성"보다 잘 팔린다.**

그래서 키가 없어도 4단계 전체가 **오늘 당장 돈 한 푼 없이 돌아간다.** 그리고 이게
2.2 의 사실과도 맞는다 — 어차피 사람이 화성 확인 화면을 봐야 한다면, 악보 인식
단계에서 사람이 한 번 보는 편이 전체 품질에 낫다.

운영자 쪽은 CLI 한 줄이다.

```
$ python3 catalog_cli.py uploads
2026-09  3/10쪽 사용 · 남은 몫 7쪽 · 이번 달 1,200원 · 인식 manual

★ 567f04de5b1e  악보 인식 중  3쪽  체르니 100번 5번

★ 1건이 인식을 기다립니다. PDF 는 /tmp/cli-up/incoming 에 있습니다.
   MusicXML 을 만들어 넣으세요:
   python3 catalog_cli.py --catalog /tmp/cli-up deliver 567f04de5b1e 결과.musicxml
```

```
$ python3 catalog_cli.py deliver 567f04de5b1e out.musicxml --id czerny100_05
567f04de5b1e → 화성 확인 대기 · 곡 czerny100_05
화성 확인 화면: /static/verify.html?id=czerny100_05
OMR 은 90~95% 입니다 — 32마디에 2~6마디가 틀립니다 (지시서 2.2). 확인 화면을 꼭 거치세요.
```

---

## 3. 월 업로드 제한 — 단위는 "쪽"이다

지시서 8.2 를 그대로 옮기면 이렇게 된다.

| | |
|---|---|
| Klangio Scan2Notes Pro | 월 50 스캔 |
| 스캔 1장 | 약 300~400원 |
| 8.3 ①의 권고 | "월 5~10장 제한을 걸면 변동비가 월 2~4천원으로 묶인다" |

**과금 단위가 스캔(=쪽)이므로 제한 단위도 쪽이어야 한다.** 작업(문서) 수로 세면
40쪽짜리 한 편으로 한 달 예산이 통째로 날아간다. 그래서 `UploadLedger` 는 쪽으로
세고, 화면도 쪽과 원으로 보여 준다.

```
남은 이번 달 몫  7쪽      이번 달 쓴 양  3 / 10쪽
이번 달 비용   1,200원    한 번에       20쪽까지
```

두 가지를 더 정해 뒀다.

- **한 번에 20쪽까지.** 한 방에 예산을 다 태우지 못하게.
- **취소는 돌려주고, 실패는 안 돌려준다.** 취소는 OMR 을 돌리기 전에만 되므로 돈이
  안 나갔다. 실패는 서비스가 이미 스캔했고 과금도 됐다. 실패를 환불해 주면 장부와
  카드 명세서가 안 맞는다.

```bash
python3 catalog_cli.py limit 6
# 월 6쪽 (쪽당 400원 → 최대 월 2,400원)
```

---

## 4. 올린 PDF 를 들고 있지 않는다 (지시서 7장)

> 약관으로 **생성 책임을 사용자에게 귀속**. **서버 영구 저장·재배포 금지.**
> 업로드본은 해당 계정에서만 사용.

세 문장이 코드에서 각각 이렇게 된다.

### ① 격리 폴더 + 즉시 삭제

PDF 는 카탈로그가 아니라 `catalog/incoming/` 에 들어간다. 그리고 **MusicXML 이
들어오는 그 순간 지운다.** 실패해도 지우고, 취소해도 지운다.

```
인식 중        incoming/ab12cd34.pdf
MusicXML 도착  incoming/  (비었음)
```

CI 가 매번 확인한다 — "올린 PDF 를 서버가 들고 있지 않는지".

### ② 보관 시계를 `updated_at` 으로 재지 않는다

처음엔 `stale()` 이 `updated_at`(마지막으로 손댄 시각)으로 오래된 작업을 찾았다.
그런데 폴러가 1분마다 `detail` 을 갱신하면 그때마다 시계가 되감긴다. **오래 도는
작업일수록 PDF 가 더 오래 남는** 거꾸로 된 일이 벌어진다.

지금은 `pdf_at`(PDF 가 격리 폴더에 들어온 시각)으로 잰다. 테스트가 이걸 지킨다:

```python
def test_polling_a_job_does_not_reset_its_retention_clock(ledger):
    ...
    for _ in range(3):                    # 폴러가 계속 건드린다
        ledger.update(j.id, detail='인식 중…')
    assert ledger.get(j.id).updated_at > '2020'        # 손댄 시각은 새로워졌지만
    assert [x.id for x in ledger.stale(older_than_hours=1)] == [j.id]
```

`sweep()` 이 방치된 작업과 **주인 없는 파일**을 같이 쓸어낸다. 프로세스가 인식
도중에 죽어도 재시작 후 정리된다 (실제로 죽여 보고 확인).

```bash
python3 catalog_cli.py sweep --hours 72
```

### ③ 업로드본은 카탈로그 곡이 아니다

곡 레코드에 `owner`(계정)와 `source='upload'` 가 붙는다. 카탈로그 곡은
`public_domain=True` 를 요구받지만 업로드본은 요구받지 않는다 — 약관으로 책임이
사용자에게 있기 때문이다. 대신 **카탈로그로 팔 수 없다.**

**블랙리스트는 어느 경로든 예외가 없다.** 업로드라고 봐 주지 않는다. 바스티앙,
피아노 어드벤처(Faber), 지브리, 디즈니는 약관으로도 면책되지 않는 쪽이다.
검사는 **파일이 디스크에 닿기 전에** 한다.

```python
def test_a_blacklisted_title_never_touches_the_disk(st, prov):
    with pytest.raises(cat.CopyrightError):
        submit(st, prov, title='피아노 어드벤처 1급')
    assert os.listdir(st.incoming_dir) == []
    assert st.ledger.rows() == []            # 쿼터도 안 깎였다
```

---

## 5. "바로 완성"이라고 말하지 않는다

지시서 3장이 세 번째 주의사항으로 적어 둔 것이다.

> **"PDF 넣으면 바로 완성"을 약속하지 말 것.** 2.2 표를 보면 확인 화면 없이는
> 32마디에 2~6마디가 틀린다.

업로드 화면이 제일 위에 이걸 쓴다.

> **올리면 바로 완성되지는 않습니다.** 악보 인식은 90~95% 입니다. 32마디 기준
> 2~6마디가 틀리므로 화성 확인 화면을 꼭 거쳐야 합니다.
> 인식이 끝나면 **화성 확인 화면**에서 한 번 보셔야 반주가 만들어집니다. 곡당 3~5분입니다.

말로만 그러는 게 아니라 **상태기계가 막는다.** 인식이 끝난 작업은 "완료"가 아니라
**"화성 확인 대기"** 로 간다. 확인 전에 완료로 넘기려 하면 거절한다.

```python
def test_review_cannot_be_skipped(st, prov):
    job = st.poll_upload(submit(st, prov)['id'], provider=prov)
    with pytest.raises(ValueError) as e:
        st.finish_upload(job['id'])
    assert '화성 확인' in str(e.value)
```

그리고 "화성 확인하러 가기"는 **그 곡의 확인 화면**으로 바로 간다
(`/static/verify.html?id=<곡>`). 처음엔 목록 페이지로 보냈다가 브라우저로 돌려
보고 잡았다 — 원장님이 26곡 중에서 방금 올린 곡을 다시 찾게 만들 뻔했다.

---

## 6. PDF 검사기를 직접 썼다

페이지 수가 과금 단위라 **틀리면 돈이 틀어진다.** 그런데 이 컨테이너에는 PDF 도구가
하나도 없었고(`pdftoppm`·`pdfinfo`·`qpdf`·`mutool` 전부 없음), `pypdf` 는 설치는
되지만 시스템 `cryptography` 가 깨져 있어 **import 조차 안 된다.** 그 한 줄을 위해
무거운 의존성을 `requirements.txt` 에 넣고 싶지도 않았다.

그래서 `piano_mr/pdf.py` 를 의존성 없이 썼다. 페이지 수를 세 가지로 본다.

1. 페이지 트리 뿌리의 `/Count` — 명세가 전체 쪽수를 여기 적게 되어 있다
2. `/Type /Page` 객체 세기 — 단 `/Type /Pages`(중간 노드)와 헷갈리면 안 된다
3. 압축 객체 스트림(`/Type /ObjStm`)을 풀어서 다시 1·2 — **PDF 1.5+ 는 페이지
   객체를 압축해 넣어서 겉만 보면 0쪽으로 보인다**

**못 세면 추측하지 않는다.** `pages` 가 `None` 이면 업로드를 거절한다. "아마 1쪽
이겠지"로 넘기면 과금이 조용히 틀어진다.

우리가 만든 fixture 만 통과하는 검사기는 의미가 없어서, **이 기계에 굴러다니는 남의
PDF** 로도 확인한다 — 10쪽짜리 문서는 `/Count`·`/Type /Page`·`/Kids` 셋이 모두 10을
가리켰다.

함정 하나도 막아 뒀다. 암호 판정을 본문에서 `/Encrypt` 글자를 찾는 식으로 하면,
본문에 우연히 그 글자가 든 멀쩡한 악보가 거절된다. 암호화는 **트레일러 사전**에
선언되므로 거기만 본다 (`test_does_not_confuse_the_word_encrypt_in_the_body`).

---

## 7. 브라우저로 한 바퀴

```
[1] 남은 몫: 10쪽
[2] 안내 문구: 악보 인식은 90~95% 입니다. 32마디 기준 2~6마디가 틀리므로 화성 …
[3] 고른 파일: three_pages.pdf · 1 KB
[4] 접수했습니다 — 3쪽. 악보 인식이 끝나면 화성 확인 화면에 나타납니다.
[5] 작업: 3쪽 · 1,200원 · three_pages.pdf · 악보 인식 중
[6] 쿼터 카드: ['7쪽', '3 / 10쪽', '1,200원', '20쪽까지']
[7] 사람이 MusicXML 투입 → {"id":"34b1243b8a07", …
[8] 상태: 화성 확인 대기
[9] 화성 확인 링크: /static/verify.html?id=upload_34b1243b8a07
[10] 화성 확인 화면이 열렸다 — 8마디
```

---

## 8. 아직 안 된 것

| 항목 | 상태 |
|---|---|
| 공급사 OMR 실호출 | **못 해 봤다** — 키가 없고 문서 호스트가 egress 차단 (2장) |
| 실제 스캔본의 인식 품질 | 못 쟀다. 위와 같은 이유 |
| 로그인·다계정 | 계정은 문자열 하나로만 다룬다. 한 학원 한 대 전제 |
| 약관 화면 | 지시서 7장이 "약관으로 책임 귀속"이라고 했는데, 약관 문구 자체는 법률 자문 영역이라 만들지 않았다 |

> 지시서 7장의 마지막 줄을 그대로 옮겨 둔다 —
> **"유료 판매 착수 전 저작권 전문 변호사 1회 상담은 필수 비용으로 잡을 것."**
> 이 단계가 사용자 업로드를 받기 시작하는 지점이라 특히 그렇다.

---

## 9. 검사

```bash
cd mr
python3 -m pytest              # 339개
python3 catalog_cli.py uploads # 신청제 운영자 화면
```

CI 가 도는 것: 전체 테스트, 그리고 "올린 PDF 를 서버가 들고 있지 않는지" 한 단계.
