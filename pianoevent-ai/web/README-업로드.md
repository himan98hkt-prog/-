# accelssam.com 에 올리기 — **한 번에 끝납니다**

올릴 것은 **압축 파일 하나**입니다. 설치 파일(.exe)은 올리지 않으셔도 됩니다.

---

## 1단계 · 폴더 만들기 (30초)

1. WP 파일 관리자 → 왼쪽 **`public_html`** 클릭
2. 도구막대의 **새 폴더** → 이름 **`download`** → 확인

## 2단계 · 압축 하나 올리고 풀기 (1분)

1. 방금 만든 **`download` 폴더를 더블클릭해서 들어갑니다** ← 중요
2. 도구막대 **업로드** → **`recital-upload.zip`** (435KB)
3. 올라온 zip을 **오른쪽 클릭 → 압축 풀기(Extract)**
4. 파일 네 개가 그 자리에 나옵니다. **zip 과 `READ-ME-FIRST.txt` 는 지우세요**

압축 안에 **폴더가 없습니다.** 푸신 자리에 그대로 풀립니다.

```
public_html/download/
  index.html                    ← 받는 자리
  recital-manager-detail.html   ← 상품 상세페이지
  .htaccess
```

## 3단계 · 확인 (30초)

**https://accelssam.com/download/** 를 엽니다.
1.4초 뒤 내려받기가 시작되면 성공입니다.

> **설치 파일은 어디에 있나요?**
> 이 페이지는 **같은 폴더에 설치 파일이 있으면 그것을**, 없으면 **깃허브에 있는 것을** 자동으로 씁니다.
> 그래서 올리지 않으셔도 지금 바로 팔 수 있습니다.
>
> 나중에 홈페이지 안에 두고 싶으시면, 같은 `download` 폴더에 아래 두 파일을 올리시면 됩니다.
> 올리는 순간부터 저절로 그쪽을 씁니다. **고치실 것이 없습니다.**
> `RecitalManager-Setup-Windows.exe` · `RecitalManager-Mac.dmg`
> (받는 곳: https://github.com/himan98hkt-prog/-/releases/tag/installer-latest)

---

# 퍼널모아 상품에 넣을 코드

## ① 상품 설명 (상세페이지)

상품 편집 → **설명**란 → 오른쪽 위 **⋮ → 코드 편집기**(또는 텍스트/HTML 모드) → 아래를 붙여넣기

```html
<iframe id="recital-detail"
  src="https://accelssam.com/download/recital-manager-detail.html"
  style="display:block;border:0;width:100%;max-width:none;min-height:600px;position:relative;z-index:9;"
  scrolling="no" title="연주회 매니저 상세페이지"></iframe>
<script>
(function(){
  var f = document.getElementById('recital-detail');
  function fit(){
    f.style.maxWidth = 'none';
    f.style.width = document.documentElement.clientWidth + 'px';
    f.style.marginLeft = '0px';
    f.style.marginLeft = (-f.getBoundingClientRect().left) + 'px';
  }
  window.addEventListener('load', fit);
  window.addEventListener('resize', fit);
  fit();
  window.addEventListener('message', function(e){
    if(e.data && e.data.type === 'accel-recital-height'){
      f.style.height = e.data.height + 'px';
      fit();
    }
  });
})();
</script>
```

## ② 커리큘럼 탭

`커리큘럼-붙여넣기.html` 을 메모장으로 열어 **전체 선택(Ctrl+A) → 복사** 한 뒤,
상품 편집 → **커리큘럼** 탭 → **텍스트(HTML) 모드**에 붙여넣으세요.

## ③ 결제 후 안내 문구

우커머스 → **설정 → 결제 완료 안내**, 그리고 **주문 완료 메일** 본문에.

```
결제해 주셔서 감사합니다.

[1] 아래 주소를 누르시면 프로그램이 자동으로 내려받아집니다.
    https://accelssam.com/download/

[2] 받은 파일을 두 번 클릭 → 다음 · 다음 · 설치

[3] 바탕화면의 「연주회 매니저」 아이콘을 누르시고,
    아래 인증키를 붙여넣어 주세요.

    인증키: RM-XXXXX-XXXXX-XXXXX-XXXXX

한 번만 넣으시면 그 컴퓨터에서 계속 쓰십니다.
인터넷이 없어도 열리고, 아이 명단과 사진은 원장님 컴퓨터를 벗어나지 않습니다.

— 아첼쌤
```

인증키는 주문마다 따로 만드십니다 —
`RECITAL_LICENSE_SECRET='정하신값' npm run key:new -- --plan year --count 1`
(자세한 것은 `docs/SELLING-LICENSE.md`)

---

## 파일 이름에 대해

**올리는 파일은 전부 영문**입니다. 한글 이름은 서버에서 깨질 수 있습니다.

| 올리는 것 (영문) | 안 올리는 것 (한글 · 붙여넣기용) |
|---|---|
| `recital-upload.zip` → 풀면 세 파일 | `커리큘럼-붙여넣기.html` |
| (나중에) `RecitalManager-Setup-Windows.exe` | `다운로드-워드프레스-블록.html` |

## 안 될 때

| 증상 | 이렇게 |
|---|---|
| zip 이 안 올라감 | 플러그인 → **NinjaFirewall 잠시 비활성화** → 업로드 → 다시 활성화 |
| 압축 풀기가 없음 | zip 을 **선택한 뒤** 오른쪽 클릭하세요. 도구막대에 압축 아이콘이 따로 있기도 합니다 |
| 끌어다 놓기가 안 먹음 | 도구막대 **업로드 아이콘 → 파일 선택** |
| 상세페이지가 왼쪽에 좁게 나옴 | 위 iframe 코드의 `<script>` 부분까지 **전부** 붙여넣으셨는지 확인해 주세요 |

## 판올림할 때

설치 파일을 홈페이지에 두셨다면 `.exe` 만 같은 이름으로 덮어쓰시면 됩니다.
깃허브 쪽을 쓰신다면 **아무것도 하실 것이 없습니다** — 새 판이 자동으로 나갑니다.
