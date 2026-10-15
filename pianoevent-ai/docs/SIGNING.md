# 서명서 넣기 — 「Windows의 PC 보호」 창 없애기

설치 파일에 **코드 서명**이 없으면, 원장님이 두 번 클릭하셨을 때 파란 창이 뜹니다.

> **Windows의 PC 보호**
> Microsoft Defender SmartScreen에서 인식할 수 없는 앱의 시작을 차단했습니다.

프로그램에 문제가 있어서가 아니라 **「누가 만들었는지 확인할 수 없다」**는 뜻입니다.
설명서에 「추가 정보 → 실행」이라고 적어 두었지만, 돈을 내고 받으신 물건에서
이 창을 보시면 그 순간 손이 멈춥니다. 환불 문의가 여기서 가장 많이 나옵니다.

서명서를 넣으면 창이 사라지고, 설치 화면에 **만든 사람 이름**이 뜹니다.

---

## 프로그램 쪽은 이미 준비돼 있습니다

깃허브 저장소에 **비밀(Secrets)** 두 개만 넣으시면 그다음부터 자동으로 서명해서 나옵니다.
코드는 하나도 고치실 것이 없습니다.

| 비밀 이름 | 무엇을 넣나 |
|---|---|
| `WINDOWS_CERT_BASE64` | 서명서 파일(`.pfx`)을 base64 로 바꾼 글자 |
| `WINDOWS_CERT_PASSWORD` | 그 서명서의 비밀번호 |

넣는 자리: 저장소 → **Settings → Secrets and variables → Actions → New repository secret**

`.pfx` 를 base64 로 바꾸는 법:

```powershell
# 윈도우 (PowerShell)
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\경로\내서명서.pfx")) | Set-Clipboard
```

```bash
# 맥 · 리눅스
base64 -w0 내서명서.pfx | pbcopy      # 맥은 -w0 대신 그냥 base64
```

비밀을 넣지 않으셔도 설치본은 **지금처럼 계속 나옵니다.** 서명만 안 될 뿐입니다.

---

## 어떤 서명서를 사야 하나

2023년 6월부터 규칙이 바뀌었습니다. **일반(OV) 서명서도 하드웨어 토큰(USB)** 에 담겨 옵니다.
USB 를 깃허브에 꽂을 수는 없으므로, 실제로 쓸 수 있는 길은 셋입니다.

| 길 | 값 (연) | 자동 빌드에서 쓸 수 있나 | 파란 창이 바로 사라지나 |
|---|---|---|---|
| **① Azure Trusted Signing** | 월 $9.99 (약 1.4만 원) | ✅ 됩니다 | ✅ 바로 |
| **② 클라우드 서명(EV)** — DigiCert KeyLocker · SSL.com eSigner | 40~70만 원 | ✅ 됩니다 | ✅ 바로 |
| **③ 일반(OV) + USB 토큰** — 세티고 · 글로벌사인 | 25~40만 원 | ❌ 손으로 서명 | ⚠️ 평판이 쌓일 때까지 며칠~몇 주 |

**처음이시면 ①** 을 권합니다. 가장 싸고, 자동 빌드에 바로 붙고, EV 와 같은 효과가 납니다.
다만 **사업자 등록 3년 이상**이어야 신청이 받아들여집니다(아첼쌤은 해당되실 겁니다).

②③ 은 개인사업자도 됩니다. ③ 은 값이 싸 보이지만 **평판이 쌓이기 전까지는 파란 창이
계속 뜹니다** — 그러면 산 보람이 없습니다. 살 거면 ① 또는 ② 입니다.

### ③ 을 고르셨다면 (USB 토큰) — 손으로 서명하는 법

깃허브에서 뽑은 `RecitalManager-Setup-Windows.exe` 를 받아, 토큰을 꽂은 윈도우에서:

```powershell
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a RecitalManager-Setup-Windows.exe
signtool verify /pa /v RecitalManager-Setup-Windows.exe
```

`signtool` 은 Windows SDK 에 들어 있습니다. 서명한 파일을 릴리스에 다시 올리시면 됩니다.

> **시간 도장(`/tr`)을 꼭 붙이세요.** 없으면 서명서가 만료되는 날 이미 팔린 설치본까지
> 다 같이 「확인할 수 없음」으로 바뀝니다.

---

## 맥은 하나 더 필요합니다

맥은 서명만으로는 부족하고 **애플 공증(notarization)** 까지 받아야 경고가 사라집니다.
Apple Developer Program (연 $99) 에 가입하신 뒤 비밀 다섯 개를 넣으시면 됩니다.

| 비밀 이름 | 무엇을 넣나 |
|---|---|
| `MAC_CERT_BASE64` | Developer ID Application 인증서(`.p12`)를 base64 로 |
| `MAC_CERT_PASSWORD` | 그 인증서의 비밀번호 |
| `APPLE_ID` | 애플 계정 이메일 |
| `APPLE_APP_SPECIFIC_PASSWORD` | appleid.apple.com 에서 만드는 **앱 암호** (계정 비밀번호가 아닙니다) |
| `APPLE_TEAM_ID` | 개발자 계정의 팀 ID (10자리) |

맥 손님이 없으시면 서두르실 것 없습니다. 윈도우가 먼저입니다.

---

## 넣고 나서 확인하기

1. 저장소 → **Actions → PianoEvent 설치본 만들기 → Run workflow**
2. 로그의 **「서명서 준비」** 칸에 `서명서가 있습니다 — 서명해서 뽑습니다` 가 보이면 된 것입니다
3. 나온 `.exe` 를 받아 **오른쪽 클릭 → 속성 → 디지털 서명** 에 이름이 보이는지 보세요
4. 다른 컴퓨터에서 두 번 클릭해 파란 창이 안 뜨는지 보세요

---

## 값어치가 있나

- 서명 없음 → 파란 창 → **「이거 바이러스 아니에요?」 문의**가 옵니다. 한 건 대응에 10분씩 듭니다
- 상세페이지에 「정품 서명된 설치 프로그램」이라고 적을 수 있습니다
- 백신 프로그램의 오탐(false positive)도 크게 줄어듭니다

월 1.4만 원(①)이면 **한 달에 한 건만 덜 물어보셔도 남습니다.**
