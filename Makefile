DRAWBOT_SCRIPTS=$(shell ls documentation/*.py)
DRAWBOT_OUTPUT=$(shell ls documentation/*.py | sed 's/\.py/.png/g')

help:
	@echo "###"
	@echo "# Build targets for UD Gothic"
	@echo "###"
	@echo
	@echo "  make build:  Builds the fonts and places them in the fonts/ directory"
	@echo "  make test:   Tests the fonts with fontbakery"
	@echo "  make proof:  Creates HTML proof documents in the proof/ directory"
	@echo "  make images: Creates PNG specimen images in the documentation/ directory"
	@echo

build: build.stamp

venv: venv/touchfile

build.stamp: venv .init.stamp sources/build.py
	. venv/bin/activate; rm -rf fonts/; python3 sources/build.py && touch build.stamp

.init.stamp: venv
	. venv/bin/activate; python3 scripts/first-run.py

venv/touchfile: requirements.txt
	test -d venv || python3 -m venv venv
	. venv/bin/activate; pip install -Ur requirements.txt
	touch venv/touchfile

test: venv build.stamp
	. venv/bin/activate; mkdir -p out/ out/fontbakery; fontbakery check-googlefonts -l WARN --succinct --badges out/badges --html out/fontbakery/fontbakery-report.html --ghmarkdown out/fontbakery/fontbakery-report.md $(shell find fonts/ttf -type f)

proof: venv build.stamp
	. venv/bin/activate; mkdir -p out/ out/proof; gftools gen-html proof $(shell find fonts/ttf -type f) -o out/proof

images: venv build.stamp $(DRAWBOT_OUTPUT)
	git add documentation/*.png && git commit -m "Rebuild images" documentation/*.png

%.png: %.py build.stamp
	python3 $< --output $@

clean:
	rm -rf venv
	find . -name "*.pyc" | xargs rm delete

update-ufr:
	npx update-template https://github.com/googlefonts/Unified-Font-Repository/

update:
	pip install --upgrade $(dependency); pip freeze > requirements.txt
