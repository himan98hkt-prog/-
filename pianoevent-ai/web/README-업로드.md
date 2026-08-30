# accelssam.com 에 올리는 법 (WP 파일 관리자)

이 폴더의 것을 그대로 올리시면 **결제 → 링크 클릭 → 자동 내려받기 → 설치 → 인증키** 가 됩니다.

```
public_html/
  download/
    index.html                          ← 이 폴더의 web/download/index.html
    .htaccess                           ← 이 폴더의 web/download/.htaccess
    RecitalManager-Setup-Windows.exe    ← 깃허브 Releases 에서 받아 올리기
    RecitalManager-Mac.dmg              ← (맥 손님이 있으실 때만)
  pages/
    recital-manager-detail.html         ← 이 폴더의 web/pages/…
```

---

## 1. 설치 파일 올리기

1. 깃허브 → **Releases → installer-latest** 에서 `RecitalManager-Setup-Windows.exe` 를 받습니다
2. WP 파일 관리자 → `public_html` → **새 폴더** → 이름 `download`
3. 그 안으로 들어가 **업로드** → 받은 `.exe` 를 끌어다 놓습니다 (80MB 안팎이라 1~2분 걸립니다)

> **`.exe` 업로드가 막히면** — 보안 플러그인(NinjaFirewall 등)이 실행 파일을 막을 수 있습니다.
> 그때는 `.exe` 를 **압축(zip)** 해서 `RecitalManager-Setup-Windows.zip` 으로 올리시고,
> `download/index.html` 안의 `RecitalManager-Setup-Windows.exe` 를 `.zip` 으로 두 군데 고치시면 됩니다.
> (원장님은 압축을 푼 뒤 두 번 클릭하시면 됩니다 — 안내 문구도 한 줄 늘려 주세요.)

## 2. 안내 페이지 — 두 가지 길 중 하나

### (가) 파일을 못 올리실 때 &mdash; **워드프레스 페이지로 만들기** (권장)

파일 관리자가 `.html` 업로드를 막는 경우가 많습니다(보안 플러그인 &middot; 허용 확장자 제한).
그럴 때는 **파일을 아예 올리지 않고** 워드프레스 페이지 하나로 만드시면 됩니다.

1. 알림판 → **페이지 → 새로 추가**
2. 제목: `프로그램 받기` (주소가 `/프로그램-받기/` 가 됩니다. 영문으로 하시려면 슬러그를 `download` 로)
3. 본문에서 **+ → 「사용자 정의 HTML」** 블록을 넣고, `web/다운로드-워드프레스-블록.html` 의 내용을 **통째로** 붙여넣기
4. **공개** 를 누르면 끝입니다

### (나) 파일로 올리실 때

## 2-1. 안내 페이지 파일 올리기

같은 `download` 폴더에 `index.html` 과 `.htaccess` 를 올립니다.
`.htaccess` 는 **브라우저에서 열리지 않고 내려받아지게** 하고, 폴더 목록이 보이지 않게 막습니다.

주소: **https://accelssam.com/download/**

이 주소를 열면 1.4초 뒤 자동으로 내려받기가 시작되고, 아래에 설치 3단계와 인증키 넣는 법이 나옵니다.

## 3. 상세페이지 올리기

`public_html/pages/` 에 `recital-manager-detail.html` 을 올린 뒤,
상품 편집 → **설명란을 텍스트(HTML) 모드**로 바꾸고 아래를 붙여넣습니다.

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

**커리큘럼 탭**에는 `web/커리큘럼-붙여넣기.html` 의 내용을 그대로 붙여넣으시면 됩니다.

## 4. 결제 후 안내 붙이기 (가장 중요)

원장님이 결제하시면 **받는 주소**와 **인증키**가 함께 가야 합니다.

- **주문 완료 화면** (우커머스 → 설정 → 결제 완료 안내) 에 넣을 문구
- **자동 발송 메일** (주문 완료 메일 본문) 에도 같은 내용

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

> 인증키는 **주문마다 다릅니다.** 결제가 들어오면
> `RECITAL_LICENSE_SECRET='정하신값' npm run key:new -- --plan year --count 1`
> 로 한 개 만들어 문자·메일로 보내 주세요. 자세한 것은 `docs/SELLING-LICENSE.md`.

## 5. 판올림할 때

새 설치본이 나오면 `download` 폴더의 `.exe` 만 **같은 이름으로 덮어쓰시면** 됩니다.
안내 페이지도, 상세페이지도 고치실 것이 없습니다.
