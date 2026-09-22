# 무대 배경 이미지·영상

발표회 운영 화면(`program.html`)의 무대는 **CSS·SVG 로 그린다.** 이 폴더가 비어
있어도 화면은 그대로 뜬다 — 연주홀 와이파이는 믿을 수 없다는 것이 지시서 모듈
⑤-1 의 전제다.

여기에 파일을 넣으면 서버(`/api/stage`)가 알아서 찾아 무대 위에 얹는다.

| 파일 | 쓰임 |
|---|---|
| `hall.mp4` | 무대 배경 영상 (있으면 이게 우선) |
| `hall.jpg` | 무대 배경 이미지 |
| `keys.jpg` | 예비 — 건반 클로즈업 |
| `curtain.jpg` | 예비 — 벨벳 커튼 텍스처 |

## 이미 만들어 둔 것

Higgsfield 로 생성해 뒀다. **이 세션의 컨테이너는 조직 egress 정책상 해당 CDN 에
접근할 수 없어서 파일을 받아 커밋하지 못했다.** 네트워크가 되는 곳에서 받아
이 폴더에 넣으면 바로 붙는다.

```bash
# 무대 배경 영상 (kling3_0_turbo · 1080p · 5초)
curl -o hall.mp4 "https://d8j0ntlcm91z4.cloudfront.net/user_3GQvWIPUy5cSGTXYMKA9lfLrTXy/hf_20260922_032317_136d7d52-d9f4-4335-aa10-f223c779aad0.mp4"

# 무대 배경 이미지 (gpt_image_2_5 · 1344×752)
curl -o hall.png "https://d8j0ntlcm91z4.cloudfront.net/user_3GQvWIPUy5cSGTXYMKA9lfLrTXy/hf_20260922_032103_87ca9469-2d3e-4867-96e3-8705d307ef66.png"

# 건반 클로즈업
curl -o keys.png "https://d8j0ntlcm91z4.cloudfront.net/user_3GQvWIPUy5cSGTXYMKA9lfLrTXy/hf_20260922_032103_a23af0bd-16cf-4413-a5f1-aca5c958b4d1.png"

# 벨벳 커튼 텍스처
curl -o curtain.png "https://d8j0ntlcm91z4.cloudfront.net/user_3GQvWIPUy5cSGTXYMKA9lfLrTXy/hf_20260922_032103_e0875405-8534-474f-a9bf-6fe0c85f99d6.png"

# 웹용으로 줄인다 (원본 PNG 는 무겁다)
for n in hall keys curtain; do
  ffmpeg -y -i $n.png -vf scale=1600:-2 -q:v 4 $n.jpg && rm $n.png
done
```

CDN 링크는 언제까지 살아 있을지 모른다. 오래 쓸 것이면 받아서 이 폴더에 커밋할 것.

## 다시 만들려면

`docs/MR-DASHBOARD.md` 에 프롬프트가 그대로 적혀 있다.

## 주의

이 폴더의 이미지는 **배경 장식**이다. 화면이 동작하는 데 필요하지 않다.
없다고 기능이 빠지지 않는다.
