# 피아노학원 자동 반주(MR) 엔진 — 1단계

.PHONY: help setup test bench fixtures demo seed serve clean

help:
	@echo "make setup     의존성 설치 (music21·mido·fluidsynth·ffmpeg·SoundFont)"
	@echo "make test      전체 테스트 (회귀 테스트 정확도 게이트 포함)"
	@echo "make bench     회귀 테스트 정확도 표"
	@echo "make fixtures  회귀 테스트용 오리지널 20곡 재생성"
	@echo "make demo      샘플 한 곡을 실제로 렌더 (out/)"
	@echo "make seed      카탈로그에 씨앗 곡 넣기 (2단계)"
	@echo "make serve     화성 확인 화면 띄우기 (2단계)"
	@echo "make clean     생성물 삭제"

setup:
	pip install -r requirements.txt
	apt-get install -y fluidsynth ffmpeg fluid-soundfont-gm

test:
	python3 -m pytest

bench:
	python3 bench.py --compare

fixtures:
	cd fixtures && python3 build_fixtures.py

demo:
	python3 mr.py fixtures/scores/p07_minuet_g.musicxml \
		--style chamber --level rich --bpm 108 \
		--all-formats --stems --keep-midi --out-dir out --tag demo

seed:
	python3 seed_catalog.py --catalog catalog

serve:
	python3 serve.py --catalog catalog

clean:
	rm -rf out catalog/cache __pycache__ server/__pycache__ piano_mr/__pycache__ tests/__pycache__ .pytest_cache
