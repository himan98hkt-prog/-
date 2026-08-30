# accelssam.com 에 올리는 법 (전부 홈페이지 안에 두는 판)

올리고 나면 이렇게 됩니다.

```
public_html/
  download/
    index.html                          ← 받는 자리  accelssam.com/download/
    .htaccess
    RecitalManager-Setup-Windows.exe    ← 92MB
    RecitalManager-Mac.dmg              ← 110MB (맥 손님이 계실 때만)
  pages/
    recital-manager-detail.html         ← 상품 상세페이지
```

**올리는 파일 이름은 전부 영문입니다.** 한글 이름은 서버에서 깨질 수 있어 쓰지 않습니다.
(제가 드린 것 중 `커리큘럼-붙여넣기.html` · `다운로드-워드프레스-블록.html` 은 **올리는 파일이 아니라
붙여넣기용**이니 컴퓨터에만 두세요.)

---

## 1단계 · 묶음 올리고 풀기 (2분)

1. WP 파일 관리자 → 왼쪽 **public_html** 클릭
2. 위 도구막대 **업로드** → `accelssam-upload.zip` 올리기 (235KB, 금방 끝납니다)
3. 올라온 `accelssam-upload.zip` 을 **오른쪽 클릭 → 압축 풀기(Extract)**
4. `download` 폴더와 `pages` 폴더가 생겼는지 확인하고, **zip 파일은 지웁니다**

> 압축 풀기를 눌렀을 때 「어디에 풀까요」를 물으면 **현재 폴더(public_html)** 를 고르세요.

## 2단계 · 설치 파일 올리기 (5~10분)

1. 아래 주소에서 설치본을 받습니다
   **https://github.com/himan98hkt-prog/-/releases/tag/installer-latest**
   - 윈도우: `RecitalManager-Setup-Windows.exe` (92MB)
   - 맥: `RecitalManager-Mac.dmg` (110MB) — 맥 손님이 계실 때만
2. 파일 관리자에서 **download 폴더로 들어갑니다** (더블클릭)
3. **업로드** → 받은 `.exe` 를 올립니다 (2~5분 걸립니다. 창을 닫지 마세요)

**`.exe` 업로드가 막히면** — 같은 릴리스에 있는 `RecitalManager-Setup-Windows.zip` 을 올리시고
**오른쪽 클릭 → 압축 풀기** 하시면 `.exe` 가 나옵니다. 그다음 zip 은 지우세요.

> 파일 이름을 바꾸지 마세요. 받는 자리의 단추가 이 이름을 찾습니다.

## 3단계 · 확인 (30초)

브라우저에서 **https://accelssam.com/download/** 를 엽니다.
1.4초 뒤 내려받기가 저절로 시작되면 성공입니다.

파일이 제대로 올라갔는지만 보시려면 주소창에 이렇게 쳐 보세요 —
`https://accelssam.com/download/RecitalManager-Setup-Windows.exe`
바로 내려받기가 시작되면 된 것입니다.

## 4단계 · 상품 상세페이지 붙이기 (2분)

상품 편집 → 설명란을 **텍스트(HTML) 모드**로 바꾸고 아래를 붙여넣습니다.

```html
<iframe id="recital-detail"
  src="https://accelssam.com/pages/recital-manager-detail.html"
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

**커리큘럼 탭**에는 `커리큘럼-붙여넣기.html` 의 내용을 그대로 붙여넣습니다.

## 5단계 · 결제 후 안내 문구

우커머스 → **설정 → 결제 완료 안내**, 그리고 **주문 완료 메일**에 넣으세요.

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

인증키는 주문마다 따로 만드셔야 합니다 —
`RECITAL_LICENSE_SECRET='정하신값' npm run key:new -- --plan year --count 1`
(자세한 것은 `docs/SELLING-LICENSE.md`)

---

## 판올림할 때

새 설치본이 나오면 **`download` 폴더의 `.exe` 만 같은 이름으로 덮어쓰시면** 됩니다.
받는 자리도, 상세페이지도 고치실 것이 없습니다.

## 파일이 안 올라갈 때

| 증상 | 이렇게 해 보세요 |
|---|---|
| `.html` · `.exe` 가 안 올라감 | 플러그인 → **NinjaFirewall 잠시 비활성화** → 업로드 → 다시 활성화 |
| 그래도 안 됨 | **zip 으로 올리고 파일 관리자에서 압축 풀기** (확장자 검사를 피해 갑니다) |
| 끌어다 놓기가 안 먹음 | 도구막대의 **업로드 아이콘 → 파일 선택** 으로 |
| 큰 파일에서 멈춤 | 호스팅의 업로드 한도 문제입니다. FTP(파일질라)로 올리시거나, 받는 자리를 깃허브 주소로 두세요 |
