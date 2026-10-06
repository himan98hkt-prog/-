# 연동 설정 안내

앱의 **설정·연동** 탭에서 연동마다 켜고 끄고, **보낼 명함(고객/거래처/기타)** 을 고를 수 있습니다.
예) 고객 명함 → HubSpot, 거래처 명함 → 사내 ERP 웹훅, 전부 → 구글 시트.

명함을 저장하거나 수정하면 켜진 연동으로 바로 보냅니다. 실패한 연동(네트워크 끊김 등)은
앱을 다시 열 때 자동으로 재전송되며, 명함 상세 화면에서 **재시도** 할 수도 있습니다.

## 1. 휴대폰 연락처

- 처음 저장할 때 연락처 권한을 묻습니다.
- 이름이 같고 휴대폰 번호가 같은 연락처가 이미 있으면 새로 만들지 않고 **회사·부서·직책을 고치고 빠진 번호·이메일만 추가**합니다(생일 등 기존 정보는 지우지 않음).
- 앱에서 수정한 명함은 앱이 만든 연락처에 그대로 반영됩니다.

## 2. 구글 시트

1. 시트에서 *확장 프로그램 > Apps Script* 를 열고 [`google-sheets.gs`](google-sheets.gs) 를 붙여 넣습니다.
2. `SECRET` 값을 바꾸고 *배포 > 새 배포 > 웹 앱* (실행: 나 / 액세스: 모든 사용자) 으로 배포합니다.
3. 웹 앱 URL(`https://script.google.com/macros/s/…/exec`)과 SECRET 을 앱에 넣고 **테스트 전송** 을 누릅니다.

열: `id, 구분, 이름, 영문이름, 회사, 부서, 직책, 휴대폰, 전화, 팩스, 이메일, 웹사이트, 주소, 메모, 등록일, 수정일`
같은 명함(id)은 같은 줄을 갱신합니다.

## 3. HubSpot CRM

1. HubSpot *설정 > 연동 > 비공개 앱(Private Apps)* 에서 앱을 만들고 범위 `crm.objects.contacts.write`, `crm.objects.contacts.read` 를 줍니다.
2. 액세스 토큰(`pat-…`)을 앱에 넣습니다.

- 같은 이메일의 연락처가 이미 있으면 그 연락처를 갱신합니다.
- 빈 칸은 보내지 않으므로 HubSpot 에 있던 값이 지워지지 않습니다.
- 고객 명함은 `lifecyclestage=customer` 로 들어갑니다.

## 4. 웹훅 (ERP·그룹웨어·Zapier·Make·n8n 등)

`POST <웹훅 주소>` / `Content-Type: application/json` / (설정 시) `X-CardScan-Secret: <비밀값>`

```json
{
  "event": "card.created",          // 수정 후 재전송이면 "card.updated"
  "source": "cardscan",
  "card": {
    "id": "8d0c…",                   // 앱 내 고유 id — 받는 쪽에서 upsert 키로 사용
    "kind": "partner", "kindLabel": "거래처",
    "name": "홍길동", "nameEn": "Gildong Hong",
    "company": "(주)한빛상사", "department": "영업1팀", "title": "팀장",
    "mobile": "010-1234-5678", "mobileE164": "+821012345678",
    "phone": "02-123-4567", "fax": "02-123-4568",
    "email": "gd.hong@hanbit.co.kr", "website": "https://hanbit.co.kr",
    "address": "서울특별시 중구 세종대로 110", "memo": "",
    "extra": ["@hanbit_official"],
    "createdAt": "2026-10-06T01:00:00.000Z", "updatedAt": "2026-10-06T01:00:00.000Z"
  }
}
```

2xx 응답이면 성공으로 기록합니다. 받는 쪽은 `X-CardScan-Secret` 을 반드시 확인하세요.

- **Zapier**: *Webhooks by Zapier → Catch Hook* 주소를 넣으면 이후 아무 앱(더존·세일즈포스·노션 등)으로 연결할 수 있습니다.
- **Make / n8n**: *Custom webhook* / *Webhook* 노드 주소를 넣습니다.

## 5. 슬랙 알림

슬랙 앱의 *Incoming Webhooks* 를 켜고 채널용 주소(`https://hooks.slack.com/services/…`)를 넣습니다.
새 명함이 처음 저장될 때 한 번만 알립니다.
