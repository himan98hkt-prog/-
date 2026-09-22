# 피아노학원 자동 반주(MR) 엔진 — 1단계

.PHONY: help setup test bench fixtures demo seed serve player uploads roster clean

help:
	@echo "make setup     의존성 설치 (music21·mido·fluidsynth·ffmpeg·SoundFont)"
	@echo "make test      전체 테스트 (회귀 테스트 정확도 게이트 포함)"
	@echo "make bench     회귀 테스트 정확도 표"
	@echo "make fixtures  회귀 테스트용 오리지널 20곡 재생성"
	@echo "make demo      샘플 한 곡을 실제로 렌더 (out/)"
	@echo "make seed      카탈로그에 씨앗 곡 넣기 (2단계)"
	@echo "make serve     화성 확인 화면 띄우기 (2단계)"
	@echo "make player    플레이어 PWA 를 브라우저에서 검사 (3단계)"
	@echo "make uploads   올라온 PDF 악보와 이번 달 몫 (4단계)"
	@echo "make roster    관리노트에서 받은 학생 명단 (5단계)"
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

# 브라우저가 필요하다: pip install playwright && python3 -m playwright install chromium
player:
	python3 tools/player_check.py --catalog catalog

uploads:
	python3 catalog_cli.py --catalog catalog uploads

roster:
	python3 catalog_cli.py --catalog catalog roster

clean:
	rm -rf out catalog/cache __pycache__ server/__pycache__ piano_mr/__pycache__ tests/__pycache__ .pytest_cache
