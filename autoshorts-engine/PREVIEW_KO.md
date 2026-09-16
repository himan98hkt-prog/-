# 분석 쇼츠 로컬 미리보기

이 버전은 분석 쇼츠 SaaS 기반의 개발용 미리보기입니다. shorts-factory 신규 생성
엔진과의 통합, 결제, YouTube 발행까지 완료한 제품이 아닙니다.
기존 shorts-factory 예약 작업 및 Google 인증정보를 사용하지 않습니다.

## 실행

Windows에서는 Docker Desktop(Linux containers)을 설치·실행한 뒤 이 저장소의
codex/shorts-studio-integration 브랜치를 다운로드하세요. 압축을 풀고
autoshorts-engine 폴더에서 터미널을 열어 실행합니다.

```sh
docker compose -f compose.preview.yml up --build -d
docker compose -f compose.preview.yml ps
```

브라우저에서 http://localhost:8765 를 엽니다. 가입 → 프로젝트 만들기 → 본인 소유
MP4 업로드 → 권리 확인 → 작업 제출 순서로 사용합니다. 최초에는 1~3분 정도의
짧고 음성이 또렷한 영상을 권장합니다. 테스트용 이메일과 별도 비밀번호를 사용하세요.

외부 유료 AI 키는 필요 없습니다. CPU Whisper 전사와 휴리스틱 구간 선정을 사용합니다.
최초 모델 다운로드에 인터넷이 필요하며 모델 서버에 연결하지 못하면 작업이 실패합니다.
PC 성능에 따라 전사·렌더가 오래 걸립니다. 대량/장시간 영상은 이 미리보기 범위 밖입니다.

화면의 결과 다운로드 버튼으로 렌더된 MP4를 저장합니다. 업로드는 자동으로
YouTube에 게시되지 않습니다. 이 패키지는 로컬 호스트에만 포트를 엽니다.
인터넷 공개 서버로 배포하지 마세요. 고정 개발용 DB 비밀번호를 사용합니다.

## 상태 및 중지

```sh
docker compose -f compose.preview.yml logs --tail 100 worker
docker compose -f compose.preview.yml logs --tail 100 api
docker compose -f compose.preview.yml stop
```

stop은 데이터와 결과 영상을 보존합니다. 다시 up -d로 시작할 수 있습니다.
기존 프로그램의 .env나 OAuth 토큰을 이 폴더로 복사하지 마세요.

## 검증의 범위

CI는 일회용 PostgreSQL에서 SaaS 회귀 테스트와 별도 API/워커 프로세스의 실제 FFmpeg
렌더를 검증합니다. 렌더 테스트는 합성 소스 및 미리 넣은 전사 캐시를 사용하므로
실제 음성인식 품질이나 유료 AI의 품질 검증은 아닙니다. Docker Desktop 자체의
빌드·실행 결과는 별도 검증 상태를 확인해야 합니다.
