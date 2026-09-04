FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    QT_QPA_PLATFORM=offscreen

# 시스템 도구: ffmpeg, fluidsynth, xvfb(MuseScore headless), java(Audiveris)
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg fluidsynth fluid-soundfont-gm \
      xvfb libegl1 libgl1 libnss3 libasound2 libxcb-xinerama0 fuse libfuse2 \
      openjdk-17-jre-headless \
      curl ca-certificates unzip git build-essential \
    && rm -rf /var/lib/apt/lists/*

# MuseScore 4 AppImage — headless 변환기(mscore)로 사용. AppImage는 컨테이너에서
# FUSE 없이 --appimage-extract 로 풀어서 쓴다.
ARG MSCORE_URL=https://github.com/musescore/MuseScore/releases/download/v4.4.4/MuseScore-Studio-4.4.4.243461245-x86_64.AppImage
RUN curl -fsSL "$MSCORE_URL" -o /tmp/mscore.AppImage \
    && chmod +x /tmp/mscore.AppImage \
    && cd /opt && /tmp/mscore.AppImage --appimage-extract >/dev/null \
    && mv /opt/squashfs-root /opt/musescore \
    && printf '#!/bin/sh\nexec xvfb-run -a /opt/musescore/AppRun "$@"\n' > /usr/local/bin/mscore \
    && chmod +x /usr/local/bin/mscore \
    && rm /tmp/mscore.AppImage \
    || echo "WARN: MuseScore 설치 실패 — FluidSynth 폴백으로 동작한다"

# Audiveris 5.x (OMR)
ARG AUDIVERIS_URL=https://github.com/Audiveris/audiveris/releases/download/5.3.1/Audiveris-5.3.1-linux-x86_64.zip
RUN curl -fsSL "$AUDIVERIS_URL" -o /tmp/audiveris.zip \
    && unzip -q /tmp/audiveris.zip -d /opt/audiveris \
    && ln -sf "$(find /opt/audiveris -type f -name 'Audiveris' | head -1)" /usr/local/bin/audiveris \
    && rm /tmp/audiveris.zip \
    || echo "WARN: Audiveris 설치 실패 — OMR 비활성"

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir -r requirements-transcribe.txt \
 && pip install --no-cache-dir -r requirements-dev.txt

COPY . /app

ENV SOUNDFONT_PATH=/usr/share/sounds/sf2/FluidR3_GM.sf2

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
