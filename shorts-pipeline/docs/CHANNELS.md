# 채널 여러 개 돌리기 — 그리고 원리한입

한 설치에서 채널을 둘 이상 돌린다. 채널마다 **설정 파일 하나**가 전부다.

```
config.yaml           기존 채널 (AI DEOKHU)  runs/       seeds/       매일 21:00
config.wonri.yaml     원리한입               runs-wonri/ seeds-wonri/ 매일 09:00
```

## 왜 갈라야 했나

예전에는 산출물 폴더도 예약 이름도 하나뿐이었다. 두 번째 채널을 그냥 얹으면
세 군데가 부딪힌다.

| 부딪히는 곳 | 그냥 뒀을 때 생기는 일 |
|---|---|
| 윈도우 작업 이름 | 원리한입 예약을 켜면 **기존 채널 예약이 사라진다** (같은 이름을 덮어쓴다) |
| `daily.bat` | 나중에 켠 채널의 설정으로 덮여, 한 채널이 두 번 올라간다 |
| `runs/` | `latest_run()` 이 가장 최근 영상을 집으므로 **남의 채널 영상을 올린다** |
| 이번 달 누적 비용 | 두 채널 비용이 한 통에 쌓여 한쪽 상한이 다른 쪽을 멈춘다 |

`channel` 블록이 이 넷을 전부 가른다.

```yaml
channel:
  slug: wonri            # 폴더·작업 이름에 쓰는 영문 이름
  name: 원리한입          # 사람이 읽는 이름
  publish_at: "09:00"    # 게시 시각
  runs_dir: runs-wonri   # 생략하면 runs-<slug>
  seeds_dir: seeds-wonri # 생략하면 seeds-<slug>
```

`channel` 블록이 **없는 설정은 예전 그대로** `runs/` · `seeds/` 를 쓰고 예약
이름도 바뀌지 않는다. 이미 돌고 있는 채널은 아무것도 건드릴 필요가 없다.

> `slug` 를 적어 놓고 비워 두면 오류가 난다. 조용히 `default` 로 떨어지면
> 그 채널이 기본 채널의 폴더와 예약을 말없이 가로챈다.

## 원리한입 켜기

```bash
# 1) 무엇이 준비됐는지 본다 (시드 폴더도 이 채널 것으로 본다)
python main.py doctor --config config.wonri.yaml

# 2) seeds-wonri/ 에 9:16 세로 이미지를 넣는다

# 3) 비용부터 — API 를 부르지 않는다
python main.py estimate --config config.wonri.yaml

# 4) 한 편 만들어 눈으로 본다
python main.py generate --image seeds-wonri/<파일> --config config.wonri.yaml

# 5) 매일 아침 9시 예약 (윈도우)
python main.py schedule on --config config.wonri.yaml
python main.py schedule status --config config.wonri.yaml
python main.py schedule off --config config.wonri.yaml
```

리눅스·맥은 `schedule status` 가 그대로 쓸 cron 한 줄을 찍어 준다.

```
30 8 * * *  cd /path/to/shorts-pipeline && \
  python -m publish.scheduler --config config.wonri.yaml --at 09:00 --youtube
```

### 8시 30분에 시작해 9시에 올린다

생성에 5~10분이 걸리므로 예약은 게시 시각 **30분 전**에 시작한다
(`win_schedule.LEAD_MINUTES`). 만들어 두고 09:00 까지 기다렸다 올린다.

내 PC 엔진(LTX-2.5)으로 만들면 그래픽카드에 따라 한 시간을 넘길 수 있어
**두 시간 전**에 시작한다 (`LEAD_MINUTES_LOCAL`). `schedule on` 이 설정의
provider 를 보고 알아서 고른다.

예약은 `Register-ScheduledTask` 로 걸린다 — 창 없이(pythonw) 돌고, 그 시각에
PC 가 꺼져 있었으면 켜지는 대로 따라잡고(`StartWhenAvailable`), 절전에서
깨우기를 시도하고(`WakeToRun`), 배터리로도 돈다. PowerShell 이 막힌 PC 는
`schtasks` 로 물러서는데, 그때는 놓친 회차를 따라잡지 못하므로 그 사실을
메시지로 알린다.

## 업로드는 처음에 비공개로

## 업로드는 처음에 비공개로

`config.wonri.yaml` 의 `publish.youtube.enabled` 는 `false`, `privacy` 는
`private` 이다. 무인 실행이 바로 공개로 나가면 잘못 만들어진 편을 되돌릴 수
없다. 며칠 비공개로 쌓아 눈으로 확인한 뒤 바꾸는 편이 안전하다.

## 실패하면 그날은 안 올린다

생성이 실패했을 때 **예전 영상으로 대체하지 않는다.** 예전에는
`latest_run()` 이 `runs/` 에서 가장 최근 영상을 집었기 때문에, 생성이
실패한 날 어제 영상이 다시 올라갈 수 있었다. 지금은 이번 실행에서 만들어진
것만 후보로 본다. 중복 업로드는 되돌릴 수 없고, 하루 거르는 편이 낫다.

실행 이력은 채널 폴더에 쌓인다.

```
runs-wonri/schedule.log   성공·실패 한 줄씩
runs-wonri/cron.log       예약이 찍은 출력 전부
```

## 성적표도 채널별로

```bash
python main.py stats --config config.wonri.yaml
```
