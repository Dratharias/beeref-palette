# BeeRef Palette — dev and install shortcuts (Python 3.12 via uv).
VENV := .venv
PY := $(VENV)/bin/python
APPS := $(HOME)/.local/share/applications

$(VENV): pyproject.toml requirements/test.txt
	uv venv --allow-existing --python 3.12 $(VENV)
	uv pip install --python $(PY) -e . -r requirements/test.txt
	touch $(VENV)

.PHONY: run test install uninstall
run: $(VENV)
	$(VENV)/bin/beeref-palette $(ARGS)

test: $(VENV)
	QT_QPA_PLATFORM=offscreen $(PY) -m pytest -q $(ARGS)

install:
	uv tool install --python 3.12 --force .
	install -Dm644 beeref/assets/logo.png $(HOME)/.local/share/icons/hicolor/256x256/apps/beeref-palette.png
	install -Dm644 packaging/beeref-palette.desktop $(APPS)/beeref-palette.desktop
	xdg-mime install --novendor packaging/beeref-palette-mime.xml
	update-desktop-database $(APPS) || true

uninstall:
	uv tool uninstall beeref-palette
	rm -f $(APPS)/beeref-palette.desktop
