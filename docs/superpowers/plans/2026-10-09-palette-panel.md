# BeeRef Palette — Palette Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn BeeRef into BeeRef Palette: build color palettes from reference images (auto-extracted distinct colors, refined by draggable sample points), inspect them, and export them as `.aco` for Clip Studio Paint.

**Architecture:** A new `beeref/palette/` package holds pure logic (extraction, `.aco` writer, data model, undo commands) and a controller that wires user operations to BeeRef's undo stack. The view draws sample points as an overlay (never scene items) and routes mouse events to the controller. A collapsible side panel (`beeref/widgets/palette_panel.py`, `color_inspector.py`) sits right of the view. Palettes persist in three new SQLite tables of the `.bee` file (schema v3).

**Tech Stack:** Python 3.12 (uv-managed), PyQt6 6.7, NumPy, pytest 8 + pytest-qt.

**Spec:** `docs/superpowers/specs/2026-10-09-palette-panel-design.md`

## Global Constraints

- Python `>=3.9,<3.13` (pyproject); run everything on **Python 3.12 via uv** — system Python is 3.14.
- PyQt6 pinned `>=6.7.0,<=6.7.0`; add only `numpy>=1.26,<3` as a new runtime dependency.
- App name **BeeRef Palette**, command `beeref-palette`.
- `.bee` schema `USER_VERSION` 2 → 3; new tables `palettes`, `palette_points`, `palette_meta`.
- Color count setting: 3–12, default 6. Extraction: `MAX_SIDE = 64`, `MIN_DELTA_E = 15` (CIE76), k = min(3·n, distinct colors), ≤ 20 iterations, fixed seed.
- `.aco`: version-1 block then version-2 block, RGB space, names `#RRGGBB` (uppercase). Default file name `<board> - <palette>.aco`.
- Keep every upstream GPL header; new files get the same header. Code, comments and docs in English.
- **Private work**: never push to `upstream` (its push URL is `DISABLED`); GitHub repo `Dratharias/beeref-palette` is created **private**, as a plain repo, only in Task 11 and only after asking the user.
- Each commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Clicking a sample point while images are selected** — must drag the point only; images must not move and no "Move items" undo entry may appear. (Test in Task 8.)
2. **Exporting the scene (PNG/SVG) with an active palette** — exported files must not contain sample points, and SVG export must not crash. (Test in Task 8.)
3. **Opening a board saved by upstream BeeRef after it deleted an image that had points** — orphan rows must be ignored, not crash, and remaining points must load. (Test in Task 6.)
4. **Tiny pointer jitter on click with auto-extract on** (tablet pens move 1–2 px) — still counts as a click and extracts. (Test in Task 7.)
5. **Renaming a palette while the store emits changes** — the name field must keep focus and text while typing. (Test in Task 9.)

---

## File Structure

| File | Responsibility |
|---|---|
| `beeref/palette/__init__.py` | Package marker. |
| `beeref/palette/extract.py` | `extract(image, n)` → distinct dominant colors with positions. Pure. |
| `beeref/palette/aco.py` | `write_aco(path, colors, names=None)`. Pure. |
| `beeref/palette/model.py` | `SamplePoint`, `Palette`, `PaletteStore`, `sample_color`, `item_image`. No widgets. |
| `beeref/palette/commands.py` | `QUndoCommand`s for palette edits. |
| `beeref/palette/controller.py` | `PaletteController`: user operations, undo macros, load restore, export. |
| `beeref/palette/overlay.py` | `PaletteOverlay`: paints points over the view, hit-testing. |
| `beeref/widgets/palette_panel.py` | `PaletteSidebar` (chevron + panel), `PalettePanel`, `PaletteRow`, `SwatchStrip`. |
| `beeref/widgets/color_inspector.py` | `ColorInspector`: read-only hue ring/triangle, values, Copy hex. |
| Modified: `beeref/fileio/schema.py`, `beeref/fileio/sql.py` | Schema v3, palette read/write. |
| Modified: `beeref/scene.py` | Owns `PaletteStore`; emits `image_clicked`. |
| Modified: `beeref/view.py` | Overlay paint, point drag, pick mode, actions, load restore. |
| Modified: `beeref/__main__.py` | Lays out view + sidebar. |
| Modified: `beeref/actions/actions.py`, `menu_structure.py` | New actions/menus. |
| Modified: `beeref/config/settings.py` | `Palette/color_count` field. |
| Tests: `tests/palette/…`, `tests/widgets/test_palette_panel.py`, `tests/widgets/test_color_inspector.py` | |

---

### Task 1: Tooling, rename, baseline

**Files:**
- Create: `.python-version`, `Makefile`, `packaging/beeref-palette.desktop`, `packaging/beeref-palette-mime.xml`, `beeref/palette/__init__.py`, `tests/palette/__init__.py`, `tests/palette/helpers.py`
- Modify: `pyproject.toml`, `beeref/constants.py`, `tests/test_main.py:13`, `tests/test_view.py:32,96,1103,1110,1117,1124`

**Interfaces:**
- Produces: `make test`, `make run`, `make install`; `tests/palette/helpers.py::stripes(colors, widths=None, height=20) -> QtGui.QImage`.

- [ ] **Step 1: Create the venv and run the upstream suite as a baseline**

```bash
cd ~/Projects/github/beeref-palette
echo 3.12 > .python-version
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e . -r requirements/test.txt
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x
```
Expected: all tests pass (≈940). If some fail before any change, note them in the task report and continue — they are upstream failures, not ours.

- [ ] **Step 2: Rename the app and add NumPy**

In `pyproject.toml`, change:
```toml
name = "BeeRef"
version = "0.3.4-dev"
```
to
```toml
name = "beeref-palette"
version = "0.3.4+palette.1"
```
add `"numpy>=1.26,<3",` to `dependencies`, and replace the scripts block with:
```toml
[project.gui-scripts]
beeref-palette = "beeref.__main__:main"
```
In `beeref/constants.py`:
```python
APPNAME = 'BeeRef Palette'
APPNAME_FULL = f'{APPNAME} Reference Image Viewer'
VERSION = '0.3.4+palette.1'
```

- [ ] **Step 3: Update the window-title assertions**

```bash
sed -i "s/== 'BeeRef'$/== 'BeeRef Palette'/; s/- BeeRef'$/- BeeRef Palette'/" tests/test_main.py tests/test_view.py
grep -n "BeeRef'" tests/test_main.py tests/test_view.py
```
Expected: every printed line ends in `BeeRef Palette'`.

- [ ] **Step 4: Add the Makefile**

`Makefile`:
```make
# BeeRef Palette — dev and install shortcuts (Python 3.12 via uv).
VENV := .venv
PY := $(VENV)/bin/python
APPS := $(HOME)/.local/share/applications

$(VENV): pyproject.toml requirements/test.txt
	uv venv --python 3.12 $(VENV)
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
```
`packaging/beeref-palette.desktop`:
```ini
[Desktop Entry]
Name=BeeRef Palette
GenericName=Reference Board
Comment=Reference image viewer with color palettes
Exec=beeref-palette %f
Icon=beeref-palette
Terminal=false
Type=Application
MimeType=application/x-beeref;
Categories=Qt;KDE;Graphics;
```
`packaging/beeref-palette-mime.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-beeref">
    <comment>BeeRef board</comment>
    <glob pattern="*.bee"/>
  </mime-type>
</mime-info>
```
Add `.venv/` to `.gitignore` if absent.

- [ ] **Step 5: Add the palette package and test helper**

`beeref/palette/__init__.py` — the GPL header (copy lines 1–14 of `beeref/commands.py`) followed by:
```python
"""Color palettes built from reference images."""
```
`tests/palette/__init__.py` — empty. `tests/palette/helpers.py`:
```python
from PyQt6 import QtCore, QtGui


def stripes(colors, widths=None, height=20):
    """Image made of vertical stripes, one per color (RGB tuples or QColors)."""
    widths = widths or [20] * len(colors)
    image = QtGui.QImage(sum(widths), height,
                         QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    x = 0
    for color, width in zip(colors, widths):
        painter.fillRect(x, 0, width, height, QtGui.QColor(*color)
                         if isinstance(color, tuple) else color)
        x += width
    painter.end()
    return image
```

- [ ] **Step 6: Run the suite**

Run: `make test`
Expected: same pass count as Step 1. If a test still fails only because it expects the old name `BeeRef` (e.g. an About dialog text), update that literal to `BeeRef Palette`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Rename to BeeRef Palette, add uv Makefile and packaging

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Distinct-color extraction

**Files:**
- Create: `beeref/palette/extract.py`
- Test: `tests/palette/test_extract.py`

**Interfaces:**
- Consumes: `tests/palette/helpers.py::stripes`.
- Produces: `extract(image: QtGui.QImage, n: int, min_delta_e: float = MIN_DELTA_E) -> list[tuple[float, float, QtGui.QColor]]` (x, y relative 0–1, largest cluster first); `srgb_to_lab(rgb: np.ndarray) -> np.ndarray`; constants `MAX_SIDE`, `MIN_DELTA_E`, `MAX_ITERATIONS`.

- [ ] **Step 1: Write the failing tests**

`tests/palette/test_extract.py`:
```python
import itertools

import numpy as np
from PyQt6 import QtGui

from beeref.palette.extract import MIN_DELTA_E, extract, srgb_to_lab
from tests.palette.helpers import stripes

RED, GREEN, BLUE = (220, 30, 30), (30, 180, 60), (40, 60, 210)
YELLOW, BLACK, WHITE = (240, 220, 40), (10, 10, 10), (250, 250, 250)


def rgb(color):
    return (color.red(), color.green(), color.blue())


def test_two_colors_requested_six():
    result = extract(stripes([RED, BLUE]), 6)
    assert sorted(rgb(c) for _, _, c in result) == sorted([RED, BLUE])


def test_six_colors():
    colors = [RED, GREEN, BLUE, YELLOW, BLACK, WHITE]
    result = extract(stripes(colors), 6)
    assert sorted(rgb(c) for _, _, c in result) == sorted(colors)


def test_n_smaller_than_distinct_colors():
    colors = [RED, GREEN, BLUE, YELLOW, BLACK, WHITE]
    result = extract(stripes(colors), 3)
    found = [rgb(c) for _, _, c in result]
    assert len(found) == 3
    assert len(set(found)) == 3
    assert set(found) <= set(colors)


def test_largest_cluster_first():
    result = extract(stripes([BLUE, RED], widths=[10, 50]), 2)
    assert rgb(result[0][2]) == RED


def test_deterministic():
    image = stripes([RED, GREEN, BLUE, YELLOW], widths=[13, 29, 7, 41])
    first = [(x, y, rgb(c)) for x, y, c in extract(image, 4)]
    second = [(x, y, rgb(c)) for x, y, c in extract(image, 4)]
    assert first == second


def test_transparent_pixels_ignored():
    image = stripes([RED, (0, 0, 0, 0)])
    result = extract(image, 6)
    assert [rgb(c) for _, _, c in result] == [RED]


def test_near_duplicate_shades_are_not_both_returned():
    near_red = (226, 34, 30)
    result = extract(stripes([RED, near_red, GREEN, BLUE]), 6)
    labs = srgb_to_lab(np.array([rgb(c) for _, _, c in result], np.uint8))
    for a, b in itertools.combinations(labs, 2):
        assert np.linalg.norm(a - b) >= MIN_DELTA_E
    assert len(result) == 3


def test_positions_point_at_pixels_of_that_color():
    image = stripes([RED, GREEN, BLUE], widths=[30, 20, 10])
    for x, y, color in extract(image, 3):
        px = image.pixelColor(int(x * image.width()), int(y * image.height()))
        assert rgb(px) == rgb(color)
        assert 0 <= x <= 1 and 0 <= y <= 1


def test_null_and_fully_transparent_images():
    assert extract(QtGui.QImage(), 6) == []
    assert extract(stripes([(0, 0, 0, 0)]), 6) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS=tests/palette/test_extract.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'beeref.palette.extract'`.

- [ ] **Step 3: Implement**

`beeref/palette/extract.py` (GPL header first):
```python
"""Dominant, visually distinct colors of an image."""

import numpy as np
from PyQt6 import QtGui
from PyQt6.QtCore import Qt


MAX_SIDE = 64
MIN_DELTA_E = 15.0
MAX_ITERATIONS = 20

_SRGB_TO_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                         [0.2126729, 0.7151522, 0.0721750],
                         [0.0193339, 0.1191920, 0.9503041]])
_WHITE_D65 = np.array([0.95047, 1.0, 1.08883])


def srgb_to_lab(rgb):
    """Convert an (..., 3) uint8 sRGB array to CIE Lab (D65)."""
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = c @ _SRGB_TO_XYZ.T / _WHITE_D65
    eps, kappa = 216 / 24389, 24389 / 27
    f = np.where(xyz > eps, np.cbrt(xyz), (kappa * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], axis=-1)


def _rgba_array(image):
    img = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    w, h = img.width(), img.height()
    raw = img.constBits().asstring(img.sizeInBytes())
    arr = np.frombuffer(raw, np.uint8).reshape(h, img.bytesPerLine())
    return arr[:, :w * 4].reshape(h, w, 4)


def _nearest(points, centroids):
    d2 = ((points[:, None, :] - centroids[None, :, :]) ** 2).sum(-1)
    return np.argmin(d2, axis=1), d2


def _kmeans(points, k, rng):
    """k-means with k-means++ seeding; returns (centroids, labels)."""
    centroids = [points[rng.integers(len(points))]]
    while len(centroids) < k:
        _, d2 = _nearest(points, np.array(centroids))
        weights = d2.min(axis=1)
        total = weights.sum()
        if total == 0:
            break
        centroids.append(points[rng.choice(len(points), p=weights / total)])
    centroids = np.array(centroids)
    for _ in range(MAX_ITERATIONS):
        labels, _ = _nearest(points, centroids)
        updated = np.array([
            points[labels == i].mean(axis=0) if np.any(labels == i)
            else centroids[i]
            for i in range(len(centroids))])
        if np.allclose(updated, centroids):
            break
        centroids = updated
    labels, _ = _nearest(points, centroids)
    return centroids, labels


def extract(image, n, min_delta_e=MIN_DELTA_E):
    """Return up to ``n`` distinct dominant colors of ``image``.

    Each entry is ``(x, y, color)`` with x/y relative to the image (0–1)
    and pointing at a real pixel of that color; largest cluster first.
    """
    if image.isNull() or n < 1:
        return []
    small = image
    if max(image.width(), image.height()) > MAX_SIDE:
        small = image.scaled(MAX_SIDE, MAX_SIDE,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.FastTransformation)
    rgba = _rgba_array(small)
    h, w = rgba.shape[:2]
    ys, xs = np.nonzero(rgba[..., 3] >= 128)
    if len(xs) == 0:
        return []
    rgb = rgba[ys, xs, :3]
    lab = srgb_to_lab(rgb)
    k = min(3 * n, len(np.unique(rgb, axis=0)))
    centroids, labels = _kmeans(lab, k, np.random.default_rng(0))
    sizes = np.bincount(labels, minlength=len(centroids))

    kept = []
    for i in np.argsort(-sizes, kind='stable'):
        if sizes[i] == 0:
            continue
        if all(np.linalg.norm(centroids[i] - centroids[j]) >= min_delta_e
               for j in kept):
            kept.append(i)
            if len(kept) == n:
                break

    result = []
    for i in kept:
        members = np.nonzero(labels == i)[0]
        best = members[np.argmin(((lab[members] - centroids[i]) ** 2).sum(-1))]
        r, g, b = (int(v) for v in rgb[best])
        result.append(((xs[best] + 0.5) / w, (ys[best] + 0.5) / h,
                       QtGui.QColor(r, g, b)))
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test ARGS=tests/palette/test_extract.py`
Expected: 9 passed.

- [ ] **Step 5: Check speed on a photo-sized image**

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "
import time; from PyQt6 import QtGui, QtWidgets; app=QtWidgets.QApplication([])
from beeref.palette.extract import extract
img=QtGui.QImage(4000,3000,QtGui.QImage.Format.Format_RGB32)
import random; p=QtGui.QPainter(img)
for i in range(400): p.fillRect(random.randrange(4000),random.randrange(3000),300,300,QtGui.QColor(random.randrange(256),random.randrange(256),random.randrange(256)))
p.end(); t=time.perf_counter(); extract(img,12); print(round((time.perf_counter()-t)*1000),'ms')"
```
Expected: well under 300 ms. If slower, report the number; do not optimize speculatively.

- [ ] **Step 6: Commit**

```bash
git add beeref/palette/extract.py tests/palette/test_extract.py
git commit -m "Add distinct dominant-color extraction

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `.aco` writer

**Files:**
- Create: `beeref/palette/aco.py`, `tests/palette/aco_reader.py`
- Test: `tests/palette/test_aco.py`

**Interfaces:**
- Produces: `write_aco(path: str, colors: list[QtGui.QColor], names: list[str] | None = None) -> None`; test-only `read_aco(path) -> list[tuple[str, tuple[int, int, int]]]`.

- [ ] **Step 1: Write the test reader and failing tests**

`tests/palette/aco_reader.py`:
```python
import struct


def read_aco(path):
    """Parse an .aco file; return [(name, (r, g, b))] from its v2 block."""
    with open(path, 'rb') as f:
        data = f.read()
    version, count = struct.unpack_from('>HH', data, 0)
    assert version == 1
    offset = 4 + count * 10
    version, count = struct.unpack_from('>HH', data, offset)
    assert version == 2
    offset += 4
    result = []
    for _ in range(count):
        space, r, g, b, _z = struct.unpack_from('>5H', data, offset)
        assert space == 0
        offset += 10
        (length,) = struct.unpack_from('>I', data, offset)
        offset += 4
        name = data[offset:offset + 2 * (length - 1)].decode('utf-16-be')
        assert data[offset + 2 * (length - 1):offset + 2 * length] == b'\0\0'
        offset += 2 * length
        result.append((name, (r // 257, g // 257, b // 257)))
    assert offset == len(data)
    return result
```
`tests/palette/test_aco.py`:
```python
import struct

from PyQt6 import QtGui

from beeref.palette.aco import write_aco
from tests.palette.aco_reader import read_aco


def test_round_trip_default_names(tmpfile):
    write_aco(tmpfile, [QtGui.QColor(211, 28, 28), QtGui.QColor(0, 0, 255)])
    assert read_aco(tmpfile) == [('#D31C1C', (211, 28, 28)),
                                 ('#0000FF', (0, 0, 255))]


def test_custom_names(tmpfile):
    write_aco(tmpfile, [QtGui.QColor(1, 2, 3)], names=['Magma é'])
    assert read_aco(tmpfile) == [('Magma é', (1, 2, 3))]


def test_v1_block_bytes(tmpfile):
    write_aco(tmpfile, [QtGui.QColor(255, 0, 1)])
    with open(tmpfile, 'rb') as f:
        head = f.read(14)
    assert head == struct.pack('>HH5H', 1, 1, 0, 65535, 0, 257, 0)


def test_empty_palette(tmpfile):
    write_aco(tmpfile, [])
    assert read_aco(tmpfile) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS=tests/palette/test_aco.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'beeref.palette.aco'`.

- [ ] **Step 3: Implement**

`beeref/palette/aco.py` (GPL header first):
```python
"""Adobe Photoshop swatch (.aco) writer — CSP imports these as color sets."""

import struct


def _color_record(color):
    return struct.pack('>5H', 0, color.red() * 257, color.green() * 257,
                       color.blue() * 257, 0)


def write_aco(path, colors, names=None):
    """Write ``colors`` (QColors) as a v1 + v2 .aco file at ``path``."""
    if names is None:
        names = [color.name().upper() for color in colors]
    data = bytearray(struct.pack('>HH', 1, len(colors)))
    for color in colors:
        data += _color_record(color)
    data += struct.pack('>HH', 2, len(colors))
    for color, name in zip(colors, names):
        encoded = name.encode('utf-16-be')
        data += _color_record(color)
        data += struct.pack('>I', len(encoded) // 2 + 1)
        data += encoded + b'\0\0'
    with open(path, 'wb') as f:
        f.write(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test ARGS=tests/palette/test_aco.py`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add beeref/palette/aco.py tests/palette/aco_reader.py tests/palette/test_aco.py
git commit -m "Add .aco swatch writer

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Data model

**Files:**
- Create: `beeref/palette/model.py`
- Test: `tests/palette/test_model.py`

**Interfaces:**
- Consumes: `beeref.items.BeePixmapItem` (`pixmap()`, `crop`, `scene()`, `save_id`).
- Produces:
  - `sample_color(image: QImage, x: float, y: float) -> QColor` (3×3 average, transparent pixels skipped; invalid `QColor()` if none).
  - `item_image(item) -> QImage` (cached per pixmap `cacheKey()`).
  - `SamplePoint(item, x, y, color=None)`: attrs `item, x, y, color`; `is_available` (property), `pixel_pos() -> QPointF`, `in_crop() -> bool`, `refresh() -> QColor`.
  - `Palette(name, points=None, source_item=None)`: attrs `name, points, source_item`; `colors() -> list[QColor]`.
  - `PaletteStore(QObject)`: signal `changed`; attrs `palettes, active, selected_point, auto_extract, pending`; methods `add(palette, index=None)`, `remove(palette) -> int`, `set_active(palette)`, `select_point(point)`, `set_auto_extract(value)`, `notify()`, `clear()`, `next_name() -> str`, `palette_of(point) -> Palette | None`, `restore(data, items_by_save_id)`.
  - `restore` data format (also produced by Task 6): `{'palettes': [{'name': str, 'source_save_id': int | None, 'points': [{'save_id': int, 'x': float, 'y': float, 'color': '#rrggbb'}]}], 'active': int | None, 'auto_extract': bool}`.

- [ ] **Step 1: Write the failing tests**

`tests/palette/test_model.py`:
```python
from PyQt6 import QtCore, QtGui

from beeref.items import BeePixmapItem
from beeref.palette.model import (
    Palette, PaletteStore, SamplePoint, item_image, sample_color)
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def image_item(view, colors=(RED, BLUE), widths=None):
    item = BeePixmapItem(stripes(list(colors), widths))
    view.scene.addItem(item)
    return item


def test_sample_color_averages_3x3():
    image = stripes([(0, 0, 0), (90, 90, 90)], widths=[1, 2], height=3)
    color = sample_color(image, 0.5, 0.5)   # centre pixel x=1: 3 black, 6 grey
    assert (color.red(), color.green(), color.blue()) == (60, 60, 60)


def test_sample_color_clamps_and_skips_transparent():
    image = stripes([(0, 0, 0, 0), RED], widths=[2, 2], height=2)
    color = sample_color(image, 1.5, -3)
    assert (color.red(), color.green(), color.blue()) == RED
    assert not sample_color(stripes([(0, 0, 0, 0)]), 0.5, 0.5).isValid()


def test_item_image_is_cached(view):
    item = image_item(view)
    assert item_image(item) is item_image(item)


def test_sample_point_refresh_and_geometry(view):
    item = image_item(view, widths=[20, 20])
    point = SamplePoint(item, 0.75, 0.5)
    assert (point.color.red(), point.color.green(), point.color.blue()) == BLUE
    assert point.pixel_pos() == QtCore.QPointF(30, 10)
    assert point.is_available
    item.crop = QtCore.QRectF(0, 0, 20, 20)
    assert not point.in_crop()
    view.scene.removeItem(item)
    assert not point.is_available


def test_store_add_remove_active(qtbot):
    store = PaletteStore()
    a, b = Palette('A'), Palette('B')
    with qtbot.waitSignal(store.changed):
        store.add(a)
    store.add(b)
    store.set_active(b)
    assert store.remove(b) == 1
    assert store.active is a
    assert store.remove(a) == 0
    assert store.active is None


def test_store_next_name_and_palette_of(view):
    store = PaletteStore()
    assert store.next_name() == 'Palette 1'
    p = Palette('Palette 1', [SamplePoint(image_item(view), 0.1, 0.1)])
    store.add(p)
    assert store.next_name() == 'Palette 2'
    assert store.palette_of(p.points[0]) is p


def test_store_restore_drops_missing_images(view):
    item = image_item(view)
    item.save_id = 7
    store = PaletteStore()
    store.restore({
        'palettes': [{'name': 'Lava', 'source_save_id': 7, 'points': [
            {'save_id': 7, 'x': 0.25, 'y': 0.5, 'color': '#000000'},
            {'save_id': 99, 'x': 0.5, 'y': 0.5, 'color': '#ffffff'}]}],
        'active': 0, 'auto_extract': True}, {7: item})
    palette = store.palettes[0]
    assert palette.name == 'Lava' and palette.source_item is item
    assert len(palette.points) == 1
    assert palette.points[0].color == QtGui.QColor(*RED)   # refreshed
    assert store.active is palette and store.auto_extract


def test_store_clear(qtbot):
    store = PaletteStore()
    store.add(Palette('A'))
    store.pending = {'palettes': []}
    store.auto_extract = True
    store.clear()
    assert store.palettes == [] and store.active is None
    assert store.pending is None and not store.auto_extract
```
- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS=tests/palette/test_model.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'beeref.palette.model'`.

- [ ] **Step 3: Implement**

`beeref/palette/model.py` (GPL header first):
```python
"""Palettes, sample points and the per-board palette store."""

from PyQt6 import QtCore, QtGui


def sample_color(image, x, y):
    """Average of the opaque pixels in the 3×3 square at relative x/y."""
    w, h = image.width(), image.height()
    if w == 0 or h == 0:
        return QtGui.QColor()
    cx = min(max(int(x * w), 0), w - 1)
    cy = min(max(int(y * h), 0), h - 1)
    total = [0, 0, 0]
    count = 0
    for py in range(max(cy - 1, 0), min(cy + 2, h)):
        for px in range(max(cx - 1, 0), min(cx + 2, w)):
            color = image.pixelColor(px, py)
            if color.alpha() == 0:
                continue
            total[0] += color.red()
            total[1] += color.green()
            total[2] += color.blue()
            count += 1
    if count == 0:
        return QtGui.QColor()
    return QtGui.QColor(*(round(v / count) for v in total))


def item_image(item):
    """QImage of an image item's full pixmap, cached until it changes."""
    pixmap = item.pixmap()
    cached = getattr(item, '_palette_image', None)
    if cached is None or cached[0] != pixmap.cacheKey():
        cached = (pixmap.cacheKey(), pixmap.toImage())
        item._palette_image = cached
    return cached[1]


class SamplePoint:
    """A color sampled at a relative position (0–1) of an image item."""

    def __init__(self, item, x, y, color=None):
        self.item = item
        self.x = x
        self.y = y
        self.color = QtGui.QColor(color) if color else QtGui.QColor()
        if color is None:
            self.refresh()

    @property
    def is_available(self):
        return self.item is not None and self.item.scene() is not None

    def pixel_pos(self):
        size = self.item.pixmap().size()
        return QtCore.QPointF(self.x * size.width(), self.y * size.height())

    def in_crop(self):
        return self.item.crop.contains(self.pixel_pos())

    def refresh(self):
        color = sample_color(item_image(self.item), self.x, self.y)
        if color.isValid():
            self.color = color
        return self.color


class Palette:

    def __init__(self, name, points=None, source_item=None):
        self.name = name
        self.points = list(points or [])
        self.source_item = source_item

    def colors(self):
        return [QtGui.QColor(point.color) for point in self.points]


class PaletteStore(QtCore.QObject):
    """All palettes of a board, plus the board's palette state."""

    changed = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.palettes = []
        self.active = None
        self.selected_point = None
        self.auto_extract = False
        self.pending = None

    def notify(self):
        self.changed.emit()

    def add(self, palette, index=None):
        if index is None:
            index = len(self.palettes)
        self.palettes.insert(index, palette)
        self.notify()

    def remove(self, palette):
        index = self.palettes.index(palette)
        self.palettes.pop(index)
        if self.active is palette:
            neighbours = self.palettes[max(index - 1, 0):index + 1]
            self.active = neighbours[0] if neighbours else None
        if self.palette_of(self.selected_point) is None:
            self.selected_point = None
        self.notify()
        return index

    def set_active(self, palette):
        self.active = palette
        if palette is None or self.selected_point not in palette.points:
            self.selected_point = None
        self.notify()

    def select_point(self, point):
        self.selected_point = point
        self.notify()

    def set_auto_extract(self, value):
        self.auto_extract = bool(value)
        self.notify()

    def palette_of(self, point):
        for palette in self.palettes:
            if any(p is point for p in palette.points):
                return palette
        return None

    def next_name(self):
        names = {palette.name for palette in self.palettes}
        number = len(self.palettes) + 1
        while f'Palette {number}' in names:
            number += 1
        return f'Palette {number}'

    def clear(self):
        self.palettes = []
        self.active = None
        self.selected_point = None
        self.auto_extract = False
        self.pending = None
        self.notify()

    def restore(self, data, items_by_save_id):
        """Rebuild palettes from saved data; drop points of missing images."""
        self.palettes = []
        for pdata in data.get('palettes', []):
            points = [SamplePoint(items_by_save_id[d['save_id']],
                                  d['x'], d['y'])
                      for d in pdata['points']
                      if d['save_id'] in items_by_save_id]
            self.palettes.append(Palette(
                pdata['name'], points,
                items_by_save_id.get(pdata.get('source_save_id'))))
        active = data.get('active')
        if active is not None and 0 <= active < len(self.palettes):
            self.active = self.palettes[active]
        else:
            self.active = self.palettes[0] if self.palettes else None
        self.selected_point = None
        self.auto_extract = bool(data.get('auto_extract', False))
        self.pending = None
        self.notify()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test ARGS=tests/palette/test_model.py`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add beeref/palette/model.py tests/palette/test_model.py
git commit -m "Add palette data model and store

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Undo commands

**Files:**
- Create: `beeref/palette/commands.py`
- Test: `tests/palette/test_commands.py`

**Interfaces:**
- Consumes: `PaletteStore`, `Palette`, `SamplePoint` (Task 4).
- Produces (all `QtGui.QUndoCommand`): `CreatePalette(store, palette)`, `DeletePalette(store, palette)`, `RenamePalette(store, palette, name)`, `ReplacePoints(store, palette, points, source_item)`, `AddPoint(store, palette, point, index=None)`, `RemovePoint(store, palette, point)`, `MovePoint(store, point, old, new, ignore_first_redo=False)` (old/new are `(x, y)`), `ReorderPoint(store, palette, point, index)`.

- [ ] **Step 1: Write the failing tests**

`tests/palette/test_commands.py`:
```python
from PyQt6 import QtGui

from beeref.items import BeePixmapItem
from beeref.palette.commands import (
    AddPoint, CreatePalette, DeletePalette, MovePoint, RemovePoint,
    RenamePalette, ReorderPoint, ReplacePoints)
from beeref.palette.model import Palette, PaletteStore, SamplePoint
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def setup(view):
    item = BeePixmapItem(stripes([RED, BLUE]))
    view.scene.addItem(item)
    return PaletteStore(), QtGui.QUndoStack(), item


def test_create_and_delete_palette(view):
    store, stack, _ = setup(view)
    palette = Palette('A')
    stack.push(CreatePalette(store, palette))
    assert store.palettes == [palette] and store.active is palette
    stack.push(DeletePalette(store, palette))
    assert store.palettes == [] and store.active is None
    stack.undo()
    assert store.palettes == [palette] and store.active is palette
    stack.undo()
    assert store.palettes == []


def test_rename(view):
    store, stack, _ = setup(view)
    palette = Palette('A')
    store.add(palette)
    stack.push(RenamePalette(store, palette, 'Magma'))
    assert palette.name == 'Magma'
    stack.undo()
    assert palette.name == 'A'


def test_replace_points(view):
    store, stack, item = setup(view)
    old = SamplePoint(item, 0.1, 0.5)
    palette = Palette('A', [old])
    store.add(palette)
    new = [SamplePoint(item, 0.9, 0.5)]
    stack.push(ReplacePoints(store, palette, new, item))
    assert palette.points == new and palette.source_item is item
    stack.undo()
    assert palette.points == [old] and palette.source_item is None


def test_add_remove_point(view):
    store, stack, item = setup(view)
    palette = Palette('A')
    store.add(palette)
    point = SamplePoint(item, 0.1, 0.5)
    stack.push(AddPoint(store, palette, point))
    assert palette.points == [point]
    store.select_point(point)
    stack.push(RemovePoint(store, palette, point))
    assert palette.points == [] and store.selected_point is None
    stack.undo()
    assert palette.points == [point]


def test_move_point_refreshes_color(view):
    store, stack, item = setup(view)
    point = SamplePoint(item, 0.1, 0.5)
    store.add(Palette('A', [point]))
    point.x = 0.9                        # live drag already moved it
    stack.push(MovePoint(store, point, (0.1, 0.5), (0.9, 0.5),
                         ignore_first_redo=True))
    stack.undo()
    assert (point.x, point.color) == (0.1, QtGui.QColor(*RED))
    stack.redo()
    assert (point.x, point.color) == (0.9, QtGui.QColor(*BLUE))


def test_reorder_point(view):
    store, stack, item = setup(view)
    a, b, c = (SamplePoint(item, x, 0.5) for x in (0.1, 0.2, 0.3))
    palette = Palette('A', [a, b, c])
    store.add(palette)
    stack.push(ReorderPoint(store, palette, a, 2))
    assert palette.points == [b, c, a]
    stack.undo()
    assert palette.points == [a, b, c]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS=tests/palette/test_commands.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'beeref.palette.commands'`.

- [ ] **Step 3: Implement**

`beeref/palette/commands.py` (GPL header first):
```python
"""Undoable palette operations."""

from PyQt6 import QtGui


class CreatePalette(QtGui.QUndoCommand):

    def __init__(self, store, palette):
        super().__init__('New palette')
        self.store = store
        self.palette = palette
        self.previous_active = store.active

    def redo(self):
        self.store.add(self.palette)
        self.store.set_active(self.palette)

    def undo(self):
        self.store.remove(self.palette)
        self.store.set_active(self.previous_active)


class DeletePalette(QtGui.QUndoCommand):

    def __init__(self, store, palette):
        super().__init__('Delete palette')
        self.store = store
        self.palette = palette
        self.index = None

    def redo(self):
        self.index = self.store.remove(self.palette)

    def undo(self):
        self.store.add(self.palette, self.index)
        self.store.set_active(self.palette)


class RenamePalette(QtGui.QUndoCommand):

    def __init__(self, store, palette, name):
        super().__init__('Rename palette')
        self.store = store
        self.palette = palette
        self.old_name = palette.name
        self.new_name = name

    def redo(self):
        self.palette.name = self.new_name
        self.store.notify()

    def undo(self):
        self.palette.name = self.old_name
        self.store.notify()


class ReplacePoints(QtGui.QUndoCommand):

    def __init__(self, store, palette, points, source_item):
        super().__init__('Extract palette')
        self.store = store
        self.palette = palette
        self.new = (list(points), source_item)
        self.old = (list(palette.points), palette.source_item)

    def _apply(self, state):
        self.palette.points, self.palette.source_item = list(state[0]), state[1]
        self.store.selected_point = None
        self.store.notify()

    def redo(self):
        self._apply(self.new)

    def undo(self):
        self._apply(self.old)


class AddPoint(QtGui.QUndoCommand):

    def __init__(self, store, palette, point, index=None):
        super().__init__('Add color point')
        self.store = store
        self.palette = palette
        self.point = point
        self.index = len(palette.points) if index is None else index

    def redo(self):
        self.palette.points.insert(self.index, self.point)
        self.store.notify()

    def undo(self):
        self.palette.points.remove(self.point)
        if self.store.selected_point is self.point:
            self.store.selected_point = None
        self.store.notify()


class RemovePoint(QtGui.QUndoCommand):

    def __init__(self, store, palette, point):
        super().__init__('Remove color point')
        self.store = store
        self.palette = palette
        self.point = point
        self.index = palette.points.index(point)

    def redo(self):
        self.palette.points.pop(self.index)
        if self.store.selected_point is self.point:
            self.store.selected_point = None
        self.store.notify()

    def undo(self):
        self.palette.points.insert(self.index, self.point)
        self.store.notify()


class MovePoint(QtGui.QUndoCommand):

    def __init__(self, store, point, old, new, ignore_first_redo=False):
        super().__init__('Move color point')
        self.store = store
        self.point = point
        self.old = old
        self.new = new
        self.ignore_first_redo = ignore_first_redo

    def _apply(self, pos):
        self.point.x, self.point.y = pos
        self.point.refresh()
        self.store.notify()

    def redo(self):
        if self.ignore_first_redo:
            self.ignore_first_redo = False
            return
        self._apply(self.new)

    def undo(self):
        self._apply(self.old)


class ReorderPoint(QtGui.QUndoCommand):

    def __init__(self, store, palette, point, index):
        super().__init__('Reorder colors')
        self.store = store
        self.palette = palette
        self.point = point
        self.old_index = palette.points.index(point)
        self.new_index = index

    def _move(self, frm, to):
        self.palette.points.insert(to, self.palette.points.pop(frm))
        self.store.notify()

    def redo(self):
        self._move(self.old_index, self.new_index)

    def undo(self):
        self._move(self.new_index, self.old_index)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test ARGS=tests/palette/test_commands.py`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add beeref/palette/commands.py tests/palette/test_commands.py
git commit -m "Add undoable palette commands

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Persistence in `.bee` (schema v3) and scene ownership

**Files:**
- Modify: `beeref/fileio/schema.py`, `beeref/fileio/sql.py` (`read`, `write_data`, new `read_palettes`, `write_palettes`), `beeref/scene.py:42-57` (`__init__`) and `:58-64` (`clear`)
- Test: `tests/palette/test_persistence.py`

**Interfaces:**
- Consumes: `PaletteStore.restore` data format (Task 4).
- Produces: `scene.palettes: PaletteStore`; `SQLiteIO.read_palettes() -> dict | None`; `SQLiteIO.write_palettes() -> None`; after `load_bee`, `scene.palettes.pending` holds the restore data (applied in Task 7 by `PaletteController.restore_loaded()`).

- [ ] **Step 1: Write the failing tests**

`tests/palette/test_persistence.py`:
```python
import sqlite3

from beeref.fileio import load_bee, save_bee, schema
from beeref.items import BeePixmapItem
from beeref.palette.model import Palette, SamplePoint
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def board(view):
    a = BeePixmapItem(stripes([RED, BLUE]))
    b = BeePixmapItem(stripes([BLUE]))
    view.scene.addItem(a)
    view.scene.addItem(b)
    store = view.scene.palettes
    lava = Palette('Lava', [SamplePoint(a, 0.1, 0.5), SamplePoint(b, 0.5, 0.5)],
                   source_item=a)
    mood = Palette('Mood', [SamplePoint(a, 0.9, 0.5)])
    store.add(lava)
    store.add(mood)
    store.set_active(mood)
    store.auto_extract = True
    return a, b


def reload(view, filename):
    view.scene.clear()
    load_bee(filename, view.scene)
    view.scene.add_queued_items()
    data = view.scene.palettes.pending
    items = {i.save_id: i for i in view.scene.items_for_save()}
    view.scene.palettes.restore(data, items)
    return view.scene.palettes


def test_schema_version_is_3():
    assert schema.USER_VERSION == 3


def test_round_trip(view, tmpfile):
    board(view)
    save_bee(tmpfile, view.scene, create_new=True)
    store = reload(view, tmpfile)
    assert [p.name for p in store.palettes] == ['Lava', 'Mood']
    lava, mood = store.palettes
    assert [(p.x, p.y) for p in lava.points] == [(0.1, 0.5), (0.5, 0.5)]
    assert lava.points[0].item is lava.source_item
    assert lava.points[1].item is not lava.points[0].item
    assert store.active is mood and store.auto_extract


def test_resave_in_place_rewrites_palettes(view, tmpfile):
    board(view)
    save_bee(tmpfile, view.scene, create_new=True)
    view.scene.palettes.remove(view.scene.palettes.palettes[0])
    save_bee(tmpfile, view.scene)
    assert [p.name for p in reload(view, tmpfile).palettes] == ['Mood']


def test_deleted_image_points_not_saved(view, tmpfile):
    a, b = board(view)
    view.scene.removeItem(b)
    save_bee(tmpfile, view.scene, create_new=True)
    lava = reload(view, tmpfile).palettes[0]
    assert len(lava.points) == 1


def test_orphan_rows_from_upstream_are_ignored(view, tmpfile):
    a, b = board(view)
    save_bee(tmpfile, view.scene, create_new=True)
    con = sqlite3.connect(tmpfile)      # upstream deletes items with FKs off
    con.execute('DELETE FROM items WHERE id = ?', (b.save_id,))
    con.commit()
    con.close()
    lava = reload(view, tmpfile).palettes[0]
    assert len(lava.points) == 1


def test_version_2_file_migrates(view, tmpfile):
    con = sqlite3.connect(tmpfile)
    for statement in schema.SCHEMA[:2]:
        con.execute(statement)
    con.execute('PRAGMA user_version=2')
    con.commit()
    con.close()
    store = reload(view, tmpfile)
    assert store.palettes == []


def test_scene_clear_clears_palettes(view):
    board(view)
    view.scene.clear()
    assert view.scene.palettes.palettes == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS=tests/palette/test_persistence.py`
Expected: FAIL — `AttributeError: 'BeeGraphicsScene' object has no attribute 'palettes'` and `assert 2 == 3`.

- [ ] **Step 3: Implement schema v3**

In `beeref/fileio/schema.py`, set `USER_VERSION = 3`, and add above `SCHEMA`:
```python
PALETTE_SCHEMA = [
    """
    CREATE TABLE palettes (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        position INTEGER NOT NULL,
        source_item_id INTEGER
          REFERENCES items (id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE palette_points (
        id INTEGER PRIMARY KEY,
        palette_id INTEGER NOT NULL
          REFERENCES palettes (id) ON DELETE CASCADE,
        item_id INTEGER NOT NULL
          REFERENCES items (id) ON DELETE CASCADE,
        x REAL NOT NULL,
        y REAL NOT NULL,
        position INTEGER NOT NULL,
        color TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE palette_meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """,
]
```
After the `SCHEMA = [...]` list add `SCHEMA = SCHEMA + PALETTE_SCHEMA`, and add `3: PALETTE_SCHEMA,` to `MIGRATIONS`.

- [ ] **Step 4: Implement read/write in `beeref/fileio/sql.py`**

Add the import `from beeref.palette.model import PaletteStore`. Add methods to `SQLiteIO`:
```python
    def _palette_store(self):
        store = getattr(self.scene, 'palettes', None)
        return store if isinstance(store, PaletteStore) else None

    def read_palettes(self):
        """Palette data in PaletteStore.restore format, or None."""
        try:
            palettes = self.fetchall(
                'SELECT id, name, source_item_id FROM palettes '
                'ORDER BY position')
            points = self.fetchall(
                'SELECT palette_id, item_id, x, y, color FROM palette_points '
                'ORDER BY palette_id, position')
            meta = dict(self.fetchall('SELECT key, value FROM palette_meta'))
        except sqlite3.OperationalError:
            logger.debug('No palette tables found')
            return None
        by_palette = {}
        for palette_id, item_id, x, y, color in points:
            by_palette.setdefault(palette_id, []).append(
                {'save_id': item_id, 'x': x, 'y': y, 'color': color})
        active = meta.get('active') or ''
        return {
            'palettes': [{'name': name,
                          'source_save_id': source,
                          'points': by_palette.get(pid, [])}
                         for pid, name, source in palettes],
            'active': int(active) if active.isdigit() else None,
            'auto_extract': meta.get('auto_extract') == '1',
        }

    def write_palettes(self):
        store = self._palette_store()
        if store is None:
            return
        self.ex('DELETE FROM palette_points')
        self.ex('DELETE FROM palettes')
        self.ex('DELETE FROM palette_meta')
        for position, palette in enumerate(store.palettes):
            source = palette.source_item
            source_id = (source.save_id
                         if source is not None and source.scene() is not None
                         else None)
            self.ex('INSERT INTO palettes (name, position, source_item_id) '
                    'VALUES (?, ?, ?)', (palette.name, position, source_id))
            palette_id = self.cursor.lastrowid
            points = [p for p in palette.points
                      if p.is_available and p.item.save_id]
            self.exmany(
                'INSERT INTO palette_points '
                '(palette_id, item_id, x, y, position, color) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                [(palette_id, p.item.save_id, p.x, p.y, i, p.color.name())
                 for i, p in enumerate(points)])
        active = next((i for i, p in enumerate(store.palettes)
                       if p is store.active), None)
        self.exmany('INSERT INTO palette_meta (key, value) VALUES (?, ?)',
                    [('active', '' if active is None else str(active)),
                     ('auto_extract', '1' if store.auto_extract else '0')])
```
In `write_data`, insert `self.write_palettes()` right after `self.delete_items(to_delete)` (before `VACUUM`).
In `read`, right before the final `if self.worker: self.worker.finished.emit(self.filename, [])`, add:
```python
        store = self._palette_store()
        if store is not None:
            store.pending = self.read_palettes()
```

- [ ] **Step 5: Give the scene its store**

In `beeref/scene.py` add `from beeref.palette.model import PaletteStore`. In `__init__`, insert `self.palettes = PaletteStore()` **before** the existing `self.clear()` call. In `clear()`, add `self.palettes.clear()` after `super().clear()`.

- [ ] **Step 6: Run the new and the existing file-IO tests**

Run: `make test ARGS="tests/palette/test_persistence.py tests/fileio tests/test_scene.py"`
Expected: all pass. If an upstream test asserts the exact `SCHEMA` length or `USER_VERSION == 2`, update that assertion to the new value and mention it in the commit message.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Persist palettes in .bee files (schema v3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Controller, click-to-extract, pick mode, load restore

**Files:**
- Create: `beeref/palette/controller.py`
- Modify: `beeref/scene.py` (`image_clicked` signal, `mousePressEvent`, `mouseReleaseEvent`), `beeref/view.py` (`__init__`, `cancel_active_modes`, `on_loading_finished`, `mousePressEvent`, `keyPressEvent`, new `enter_pick_point_mode`), `beeref/config/settings.py` (`FIELDS`)
- Test: `tests/palette/test_controller.py`

**Interfaces:**
- Consumes: Tasks 2–6.
- Produces: `PaletteController(view)` with `store`, `color_count() -> int`, `new_palette() -> Palette`, `extract_into_active(item)`, `on_image_clicked(item)`, `regenerate(palette) -> bool`, `can_regenerate(palette) -> bool`, `add_point_at(scene_pos) -> SamplePoint | None`, `image_at(scene_pos)`, `relative_pos(item, scene_pos) -> (x, y)`, `drag_point_to(point, scene_pos)`, `finish_point_drag(point, start)`, `remove_point(point)`, `rename(palette, name)`, `delete(palette)`, `reorder_point(palette, point, index)`, `set_active(palette)`, `set_auto_extract(value)`, `default_export_name(palette) -> str`, `export(palette, path)`, `restore_loaded()`. View: `palette_controller`, `PICK_POINT_MODE = 4`, `enter_pick_point_mode()`. Scene: `image_clicked = pyqtSignal(object)`. Setting `'Palette/color_count'`.

- [ ] **Step 1: Write the failing tests**

`tests/palette/test_controller.py`:
```python
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

from beeref.items import BeePixmapItem
from beeref.palette.model import Palette, SamplePoint
from tests.palette.aco_reader import read_aco
from tests.palette.helpers import stripes

RED, GREEN, BLUE = (220, 30, 30), (30, 180, 60), (40, 60, 210)


def add_image(view, colors=(RED, GREEN, BLUE)):
    item = BeePixmapItem(stripes(list(colors), height=60))
    view.scene.addItem(item)
    return item


def click(qtbot, view, scene_pos, button=Qt.MouseButton.LeftButton, jitter=0):
    pos = view.mapFromScene(scene_pos)
    qtbot.mousePress(view.viewport(), button, pos=pos)
    qtbot.mouseRelease(view.viewport(), button,
                       pos=pos + QtCore.QPoint(jitter, 0))


def test_new_palette_is_undoable(view):
    c = view.palette_controller
    palette = c.new_palette()
    assert c.store.palettes == [palette] and c.store.active is palette
    view.undo_stack.undo()
    assert c.store.palettes == []


def test_extract_into_active_creates_palette_in_one_undo_step(view):
    c = view.palette_controller
    item = add_image(view)
    c.extract_into_active(item)
    palette = c.store.active
    assert len(palette.points) == 3 and palette.source_item is item
    view.undo_stack.undo()
    assert c.store.palettes == []


def test_color_count_setting(view, settings):
    settings.setValue('Palette/color_count', 3)
    c = view.palette_controller
    c.extract_into_active(
        add_image(view, (RED, GREEN, BLUE, (240, 220, 40), (10, 10, 10))))
    assert len(c.store.active.points) == 3


def test_click_extracts_only_when_auto_on(qtbot, view):
    view.show()
    c = view.palette_controller
    item = add_image(view)
    view.fitInView(item)
    click(qtbot, view, item.sceneBoundingRect().center())
    assert c.store.palettes == []
    c.set_auto_extract(True)
    click(qtbot, view, item.sceneBoundingRect().center(), jitter=2)
    assert len(c.store.active.points) == 3


def test_drag_does_not_extract(qtbot, view):
    view.show()
    c = view.palette_controller
    c.set_auto_extract(True)
    item = add_image(view)
    view.fitInView(item)
    start = view.mapFromScene(item.sceneBoundingRect().center())
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), pos=start + QtCore.QPoint(40, 0))
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton,
                       pos=start + QtCore.QPoint(40, 0))
    assert c.store.palettes == []


def test_regenerate(view):
    c = view.palette_controller
    item = add_image(view)
    c.extract_into_active(item)
    palette = c.store.active
    palette.points.pop()
    assert c.regenerate(palette)
    assert len(palette.points) == 3
    assert not c.regenerate(Palette('empty'))


def test_pick_mode_adds_point(qtbot, view):
    view.show()
    c = view.palette_controller
    item = add_image(view)
    view.fitInView(item)
    view.enter_pick_point_mode()
    assert view.active_mode == view.PICK_POINT_MODE
    rect = item.sceneBoundingRect()
    click(qtbot, view, QtCore.QPointF(rect.left() + rect.width() * 5 / 6,
                                      rect.center().y()))
    point = c.store.active.points[0]
    assert point.color == QtGui.QColor(*BLUE)
    assert view.active_mode is None


def test_pick_mode_on_empty_canvas_adds_nothing(qtbot, view):
    view.show()
    add_image(view)
    view.enter_pick_point_mode()
    click(qtbot, view, QtCore.QPointF(-5000, -5000))
    assert all(not p.points for p in view.palette_controller.store.palettes)


def test_escape_cancels_pick_mode(qtbot, view):
    view.enter_pick_point_mode()
    qtbot.keyClick(view, Qt.Key.Key_Escape)
    assert view.active_mode is None


def test_drag_point_then_undo(view):
    c = view.palette_controller
    item = add_image(view)
    point = SamplePoint(item, 0.1, 0.5)
    c.store.add(Palette('A', [point]))
    rect = item.sceneBoundingRect()
    c.drag_point_to(point, QtCore.QPointF(rect.right() - 1, rect.center().y()))
    assert point.color == QtGui.QColor(*BLUE)
    c.finish_point_drag(point, (0.1, 0.5))
    view.undo_stack.undo()
    assert (point.x, point.color) == (0.1, QtGui.QColor(*RED))


def test_rename_delete_reorder_remove(view):
    c = view.palette_controller
    item = add_image(view)
    c.extract_into_active(item)
    palette = c.store.active
    first = palette.points[0]
    c.rename(palette, 'Magma')
    c.reorder_point(palette, first, 2)
    c.remove_point(first)
    assert palette.name == 'Magma' and first not in palette.points
    c.delete(palette)
    assert c.store.palettes == []
    for _ in range(3):       # undo delete, remove, reorder — not rename
        view.undo_stack.undo()
    assert palette.name == 'Magma' and palette.points[0] is first


def test_export(view, tmpfile):
    c = view.palette_controller
    c.extract_into_active(add_image(view))
    c.export(c.store.active, tmpfile)
    assert len(read_aco(tmpfile)) == 3
    view.filename = '/tmp/Volcano.bee'
    c.store.active.name = 'Magma'
    assert c.default_export_name(c.store.active) == 'Volcano - Magma.aco'


def test_restore_loaded(view, tmpfile):
    from beeref.fileio import save_bee
    c = view.palette_controller
    c.extract_into_active(add_image(view))
    save_bee(tmpfile, view.scene, create_new=True)
    view.open_from_file(tmpfile)
    view.worker.wait()
    QtCore.QCoreApplication.processEvents()
    assert len(c.store.palettes) == 1 and len(c.store.active.points) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS=tests/palette/test_controller.py`
Expected: FAIL with `AttributeError: 'BeeGraphicsView' object has no attribute 'palette_controller'`.

- [ ] **Step 3: Add the setting**

In `beeref/config/settings.py`, add to `BeeSettings.FIELDS`:
```python
        'Palette/color_count': {
            'default': 6,
            'cast': int,
            'validate': lambda x: 3 <= x <= 12,
        },
```

- [ ] **Step 4: Implement the controller**

`beeref/palette/controller.py` (GPL header first):
```python
"""User-level palette operations, wired to the undo stack."""

import os.path

from beeref.palette import commands
from beeref.palette.aco import write_aco
from beeref.palette.extract import extract
from beeref.palette.model import Palette, SamplePoint, item_image


class PaletteController:

    def __init__(self, view):
        self.view = view
        self.scene = view.scene
        self.store = view.scene.palettes
        self.undo_stack = view.undo_stack
        self.settings = view.settings
        self.scene.image_clicked.connect(self.on_image_clicked)

    def color_count(self):
        return self.settings.valueOrDefault('Palette/color_count')

    # Palettes

    def new_palette(self):
        palette = Palette(self.store.next_name())
        self.undo_stack.push(commands.CreatePalette(self.store, palette))
        return palette

    def rename(self, palette, name):
        name = name.strip()
        if name and name != palette.name:
            self.undo_stack.push(
                commands.RenamePalette(self.store, palette, name))

    def delete(self, palette):
        self.undo_stack.push(commands.DeletePalette(self.store, palette))

    def set_active(self, palette):
        if palette is not self.store.active:
            self.store.set_active(palette)

    def set_auto_extract(self, value):
        self.store.set_auto_extract(value)

    # Extraction

    def extract_points(self, item):
        return [SamplePoint(item, x, y)
                for x, y, _ in extract(item_image(item), self.color_count())]

    def extract_into_active(self, item):
        points = self.extract_points(item)
        self.undo_stack.beginMacro('Extract palette')
        if self.store.active is None:
            self.new_palette()
        self.undo_stack.push(commands.ReplacePoints(
            self.store, self.store.active, points, item))
        self.undo_stack.endMacro()

    def on_image_clicked(self, item):
        if self.store.auto_extract:
            self.extract_into_active(item)

    def can_regenerate(self, palette):
        item = palette.source_item
        return item is not None and item.scene() is not None

    def regenerate(self, palette):
        if not self.can_regenerate(palette):
            return False
        self.undo_stack.push(commands.ReplacePoints(
            self.store, palette, self.extract_points(palette.source_item),
            palette.source_item))
        return True

    # Points

    def image_at(self, scene_pos):
        for item in self.scene.items(scene_pos):
            if getattr(item, 'is_image', False):
                return item
        return None

    @staticmethod
    def relative_pos(item, scene_pos):
        local = item.mapFromScene(scene_pos)
        size = item.pixmap().size()
        return (min(max(local.x() / size.width(), 0.0), 1.0),
                min(max(local.y() / size.height(), 0.0), 1.0))

    def add_point_at(self, scene_pos):
        item = self.image_at(scene_pos)
        if item is None:
            return None
        if self.store.active is None:
            self.new_palette()
        point = SamplePoint(item, *self.relative_pos(item, scene_pos))
        self.undo_stack.push(
            commands.AddPoint(self.store, self.store.active, point))
        return point

    def drag_point_to(self, point, scene_pos):
        point.x, point.y = self.relative_pos(point.item, scene_pos)
        point.refresh()
        self.store.notify()

    def finish_point_drag(self, point, start):
        if (point.x, point.y) != tuple(start):
            self.undo_stack.push(commands.MovePoint(
                self.store, point, tuple(start), (point.x, point.y),
                ignore_first_redo=True))

    def remove_point(self, point):
        palette = self.store.palette_of(point)
        if palette is not None:
            self.undo_stack.push(
                commands.RemovePoint(self.store, palette, point))

    def reorder_point(self, palette, point, index):
        if palette.points.index(point) != index:
            self.undo_stack.push(
                commands.ReorderPoint(self.store, palette, point, index))

    # Files

    def default_export_name(self, palette):
        board = self.view.filename
        board = (os.path.splitext(os.path.basename(board))[0]
                 if board else 'Untitled')
        return f'{board} - {palette.name}.aco'

    def export(self, palette, path):
        write_aco(path, palette.colors())

    def restore_loaded(self):
        data = self.store.pending
        if data is None:
            return
        items = {item.save_id: item
                 for item in self.scene.items_for_save()
                 if getattr(item, 'is_image', False)}
        self.store.restore(data, items)
```

- [ ] **Step 5: Emit `image_clicked` from the scene**

In `beeref/scene.py`: add `image_clicked = QtCore.pyqtSignal(object)` next to the other signals; in `__init__` add `self.press_item = None`. In `mousePressEvent`, inside `if event.button() == Qt.MouseButton.LeftButton:` right after `item_at_pos = ...`, add `self.press_item = item_at_pos`. At the start of `mouseReleaseEvent` add:
```python
        if (self.active_mode == self.MOVE_MODE
                and event.button() == Qt.MouseButton.LeftButton
                and getattr(self.press_item, 'is_image', False)):
            scale = self.views()[0].transform().m11() or 1
            moved = (event.scenePos() - self.event_start).manhattanLength()
            if moved * scale <= 3:
                self.image_clicked.emit(self.press_item)
```

- [ ] **Step 6: Wire the view**

In `beeref/view.py`: import `from beeref.palette.controller import PaletteController`; add `PICK_POINT_MODE = 4` beside `SAMPLE_COLOR_MODE`. In `__init__`, right after `self.setScene(self.scene)`:
```python
        self.palette_controller = PaletteController(self)
        self.palette_sidebar = None
```
In `on_loading_finished`'s `else:` branch, after `self.scene.add_queued_items()` add `self.palette_controller.restore_loaded()`. Add the method:
```python
    def enter_pick_point_mode(self):
        self.cancel_active_modes()
        logger.debug('Entering pick color point mode')
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.active_mode = self.PICK_POINT_MODE
```
In `mousePressEvent`, right after the `SAMPLE_COLOR_MODE` block:
```python
        if self.active_mode == self.PICK_POINT_MODE:
            if event.button() == Qt.MouseButton.LeftButton:
                self.palette_controller.add_point_at(
                    self.mapToScene(event.pos()))
            self.cancel_sample_color_mode()
            event.accept()
            return
```
In `keyPressEvent`, change `if self.active_mode == self.SAMPLE_COLOR_MODE:` to `if self.active_mode in (self.SAMPLE_COLOR_MODE, self.PICK_POINT_MODE):`. (`cancel_sample_color_mode` already resets `active_mode` and the cursor.)

- [ ] **Step 7: Run tests**

Run: `make test ARGS="tests/palette tests/test_view.py tests/test_scene.py"`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Add palette controller, click-to-extract and pick mode

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Point overlay — drawing, dragging, right-click removal

**Files:**
- Create: `beeref/palette/overlay.py`
- Modify: `beeref/view.py` (`__init__`, `drawForeground`, `on_scene_changed`, `on_context_menu`, `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`)
- Test: `tests/palette/test_overlay.py`

**Interfaces:**
- Consumes: `PaletteStore`, `PaletteController` (Task 7).
- Produces: `PaletteOverlay(store)` with `RADIUS = 7`, `visible_points() -> list[SamplePoint]`, `view_pos(view, point) -> QPointF`, `hit_test(view, pos: QPointF) -> SamplePoint | None`, `paint(painter, view)`. View: `palette_overlay`, `DRAG_POINT_MODE = 5`.

- [ ] **Step 1: Write the failing tests**

`tests/palette/test_overlay.py`:
```python
from unittest.mock import patch

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

from beeref.fileio.export import SceneToPixmapExporter, SceneToSVGExporter
from beeref.items import BeePixmapItem
from beeref.palette.model import Palette, SamplePoint
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def setup(view):
    view.show()
    item = BeePixmapItem(stripes([RED, BLUE], height=40))
    view.scene.addItem(item)
    view.fitInView(item)
    point = SamplePoint(item, 0.25, 0.5)
    palette = Palette('A', [point])
    view.scene.palettes.add(palette)
    view.scene.palettes.set_active(palette)
    return item, point


def test_hit_test(view):
    _, point = setup(view)
    overlay = view.palette_overlay
    pos = overlay.view_pos(view, point)
    assert overlay.hit_test(view, pos) is point
    assert overlay.hit_test(view, pos + QtCore.QPointF(30, 0)) is None


def test_only_active_and_available_points(view):
    item, point = setup(view)
    assert view.palette_overlay.visible_points() == [point]
    view.scene.removeItem(item)
    assert view.palette_overlay.visible_points() == []
    view.scene.palettes.set_active(None)
    assert view.palette_overlay.visible_points() == []


def test_point_is_drawn(view):
    _, point = setup(view)
    pos = view.palette_overlay.view_pos(view, point).toPoint()
    image = view.viewport().grab().toImage()
    ring = image.pixelColor(pos + QtCore.QPoint(view.palette_overlay.RADIUS, 0))
    assert ring != QtGui.QColor(*RED)


def test_drag_point_moves_point_not_images(qtbot, view):
    item, point = setup(view)
    item.setSelected(True)
    start = view.palette_overlay.view_pos(view, point).toPoint()
    end = view.mapFromScene(item.mapToScene(QtCore.QPointF(30, 20)))
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), pos=end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert item.pos() == QtCore.QPointF(0, 0)
    assert point.color == QtGui.QColor(*BLUE)
    assert view.undo_stack.count() == 1
    assert view.undo_stack.command(0).text() == 'Move color point'


def test_right_click_removes_point(view):
    _, point = setup(view)
    pos = view.palette_overlay.view_pos(view, point).toPoint()
    view.on_context_menu(pos)
    assert view.scene.palettes.active.points == []


def test_pixmap_export_has_no_points(view):
    item, point = setup(view)
    exporter = SceneToPixmapExporter(view.scene)
    exporter.size = exporter.default_size
    image = exporter.render_to_image()
    center = QtCore.QPoint(int(exporter.margin) + 10,
                           int(exporter.margin) + 20)
    assert image.pixelColor(center) == QtGui.QColor(*RED)


def test_svg_export_does_not_crash(view):
    setup(view)
    exporter = SceneToSVGExporter(view.scene)
    exporter.size = exporter.default_size
    assert exporter.render_to_svg() is not None
```
If `SceneToSVGExporter` has another name in `beeref/fileio/export.py`, use the class whose `TYPE` is `'svg'` (check with `grep -n "class .*Exporter" beeref/fileio/export.py`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS=tests/palette/test_overlay.py`
Expected: FAIL with `AttributeError: 'BeeGraphicsView' object has no attribute 'palette_overlay'`.

- [ ] **Step 3: Implement the overlay**

`beeref/palette/overlay.py` (GPL header first):
```python
"""Draws the active palette's sample points on top of the view.

Points are painted in viewport coordinates from ``drawForeground`` and
are never scene items, so exports, selections and bounding boxes ignore
them.
"""

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt


class PaletteOverlay:
    RADIUS = 7
    HIT_MARGIN = 2

    def __init__(self, store):
        self.store = store

    def visible_points(self):
        palette = self.store.active
        if palette is None:
            return []
        return [p for p in palette.points if p.is_available]

    def view_pos(self, view, point):
        scene_pos = point.item.mapToScene(point.pixel_pos())
        return QtCore.QPointF(view.mapFromScene(scene_pos))

    def hit_test(self, view, pos):
        limit = (self.RADIUS + self.HIT_MARGIN) ** 2
        for point in reversed(self.visible_points()):
            delta = self.view_pos(view, point) - QtCore.QPointF(pos)
            if delta.x() ** 2 + delta.y() ** 2 <= limit:
                return point
        return None

    def paint(self, painter, view):
        points = self.visible_points()
        if not points:
            return
        painter.save()
        painter.resetTransform()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        for point in points:
            center = self.view_pos(view, point)
            radius = self.RADIUS + (3 if point is self.store.selected_point
                                    else 0)
            fill = (QtGui.QColor(point.color) if point.in_crop()
                    else QtGui.QColor(128, 128, 128, 90))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 200), 3))
            painter.drawEllipse(center, radius, radius)
            painter.setBrush(fill)
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 230), 1.5))
            painter.drawEllipse(center, radius, radius)
        painter.restore()
```

- [ ] **Step 4: Wire the view**

In `beeref/view.py`: import `from beeref.palette.overlay import PaletteOverlay`; add `DRAG_POINT_MODE = 5`. In `__init__` after the controller lines:
```python
        self.palette_overlay = PaletteOverlay(self.scene.palettes)
        self.scene.palettes.changed.connect(self.viewport().update)
```
Add:
```python
    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        self.palette_overlay.paint(painter, self)
```
At the top of `on_scene_changed` add:
```python
        if self.scene.palettes.active is not None:
            self.viewport().update()
```
At the top of `on_context_menu`:
```python
        hit = self.palette_overlay.hit_test(self, QtCore.QPointF(point))
        if hit is not None:
            self.palette_controller.remove_point(hit)
            return
```
In `mousePressEvent`, after the `PICK_POINT_MODE` block (Task 7):
```python
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self.palette_overlay.hit_test(self, event.position())
            if hit is not None:
                self.scene.palettes.select_point(hit)
                self.active_mode = self.DRAG_POINT_MODE
                self.drag_point = hit
                self.drag_point_start = (hit.x, hit.y)
                event.accept()
                return
            if self.scene.palettes.selected_point is not None:
                self.scene.palettes.select_point(None)
```
At the top of `mouseMoveEvent`:
```python
        if self.active_mode == self.DRAG_POINT_MODE:
            self.palette_controller.drag_point_to(
                self.drag_point, self.mapToScene(event.pos()))
            event.accept()
            return
```
At the top of `mouseReleaseEvent`:
```python
        if self.active_mode == self.DRAG_POINT_MODE:
            self.palette_controller.finish_point_drag(
                self.drag_point, self.drag_point_start)
            self.active_mode = None
            event.accept()
            return
```
Because the view consumes the press, the scene never sees it: images stay put and no `MoveItemsBy` is pushed.

- [ ] **Step 5: Run tests**

Run: `make test ARGS="tests/palette tests/test_view.py tests/fileio"`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Draw and drag palette sample points over the view

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Side panel, chevron, actions and menus

**Files:**
- Create: `beeref/widgets/palette_panel.py`
- Modify: `beeref/widgets/__init__.py` (import list), `beeref/__main__.py` (`BeeRefMainWindow.__init__`), `beeref/view.py` (action callbacks), `beeref/actions/actions.py`, `beeref/actions/menu_structure.py`
- Test: `tests/widgets/test_palette_panel.py`

**Interfaces:**
- Consumes: `PaletteController` (Task 7). (Task 10 later adds `PalettePanel.inspector` and extends `on_store_changed`.)
- Produces: `PaletteSidebar(controller, settings)` with `panel`, `chevron`, `set_collapsed(bool)`, `is_collapsed() -> bool`, `toggle_visible()`; `PalettePanel(controller, settings)` with `auto_checkbox`, `count_spinbox`, `new_button`, `rows: list[PaletteRow]`, `on_store_changed()`; `PaletteRow(controller, palette)` with `name_edit`, `strip`, `menu_button`, `refresh()`; `SwatchStrip(controller, palette)` with `index_at(pos) -> int | None`, `cell_rect(i) -> QRect`. Main window: `palette_sidebar`. View callbacks: `on_action_toggle_palette_panel`, `on_action_palette_new`, `on_action_palette_add_point`. Settings keys: `PalettePanel/visible`, `PalettePanel/collapsed`.

- [ ] **Step 1: Write the failing tests**

`tests/widgets/test_palette_panel.py`:
```python
from unittest.mock import patch

from PyQt6 import QtCore
from PyQt6.QtCore import Qt

from beeref.items import BeePixmapItem
from tests.palette.helpers import stripes

RED, GREEN, BLUE = (220, 30, 30), (30, 180, 60), (40, 60, 210)


def sidebar(main_window):
    return main_window.palette_sidebar


def extracted(main_window):
    view = main_window.view
    item = BeePixmapItem(stripes([RED, GREEN, BLUE]))
    view.scene.addItem(item)
    view.palette_controller.extract_into_active(item)
    return view.palette_controller.store.active


def test_sidebar_is_right_of_view(main_window):
    layout = main_window.centralWidget().layout()
    assert layout.itemAt(0).widget() is main_window.view
    assert layout.itemAt(1).widget() is sidebar(main_window)


def test_collapse_persists(main_window, settings):
    side = sidebar(main_window)
    side.chevron.click()
    assert side.is_collapsed() and not side.panel.isVisibleTo(side)
    assert settings.value('PalettePanel/collapsed', type=bool) is True
    side.chevron.click()
    assert not side.is_collapsed()


def test_toggle_action(main_window, settings):
    side = sidebar(main_window)
    visible = side.isVisibleTo(main_window)
    main_window.view.on_action_toggle_palette_panel()
    assert side.isVisibleTo(main_window) is not visible
    assert settings.value('PalettePanel/visible', type=bool) is not visible


def test_new_palette_button_adds_row(main_window):
    panel = sidebar(main_window).panel
    panel.new_button.click()
    assert len(panel.rows) == 1
    assert panel.rows[0].name_edit.text() == 'Palette 1'


def test_auto_and_count_controls(main_window, settings):
    panel = sidebar(main_window).panel
    panel.auto_checkbox.setChecked(True)
    assert main_window.view.palette_controller.store.auto_extract
    panel.count_spinbox.setValue(9)
    assert settings.valueOrDefault('Palette/color_count') == 9


def test_rename_keeps_focus_while_store_changes(qtbot, main_window):
    main_window.show()
    panel = sidebar(main_window).panel
    panel.new_button.click()
    edit = panel.rows[0].name_edit
    edit.setFocus()
    edit.setText('Mag')
    main_window.view.palette_controller.store.notify()
    assert panel.rows[0].name_edit is edit and edit.text() == 'Mag'
    edit.setText('Magma')
    edit.editingFinished.emit()
    assert main_window.view.palette_controller.store.active.name == 'Magma'


def test_swatch_click_selects_and_right_click_removes(qtbot, main_window):
    palette = extracted(main_window)
    strip = sidebar(main_window).panel.rows[0].strip
    first = palette.points[0]
    qtbot.mouseClick(strip, Qt.MouseButton.LeftButton,
                     pos=strip.cell_rect(0).center())
    store = main_window.view.palette_controller.store
    assert store.selected_point is first
    qtbot.mouseClick(strip, Qt.MouseButton.RightButton,
                     pos=strip.cell_rect(0).center())
    assert first not in palette.points


def test_swatch_drag_reorders(qtbot, main_window):
    palette = extracted(main_window)
    strip = sidebar(main_window).panel.rows[0].strip
    first = palette.points[0]
    qtbot.mousePress(strip, Qt.MouseButton.LeftButton,
                     pos=strip.cell_rect(0).center())
    qtbot.mouseRelease(strip, Qt.MouseButton.LeftButton,
                       pos=strip.cell_rect(2).center())
    assert palette.points[2] is first


def test_plus_cell_enters_pick_mode(qtbot, main_window):
    palette = extracted(main_window)
    strip = sidebar(main_window).panel.rows[0].strip
    qtbot.mouseClick(strip, Qt.MouseButton.LeftButton,
                     pos=strip.cell_rect(len(palette.points)).center())
    assert main_window.view.active_mode == main_window.view.PICK_POINT_MODE


def test_export_menu(main_window, tmpdir):
    extracted(main_window)
    row = sidebar(main_window).panel.rows[0]
    target = str(tmpdir.join('out.aco'))
    with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName',
               return_value=(target, '')):
        row.export()
    assert tmpdir.join('out.aco').check()


def test_export_error_shows_dialog(main_window):
    extracted(main_window)
    row = sidebar(main_window).panel.rows[0]
    with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName',
               return_value=('/nonexistent/dir/x.aco', '')), \
            patch('PyQt6.QtWidgets.QMessageBox.warning') as warning:
        row.export()
    warning.assert_called_once()


def test_regenerate_disabled_without_source(main_window):
    sidebar(main_window).panel.new_button.click()
    row = sidebar(main_window).panel.rows[0]
    row.menu_button.menu().aboutToShow.emit()
    assert not row.regenerate_action.isEnabled()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS=tests/widgets/test_palette_panel.py`
Expected: FAIL with `AttributeError: 'BeeRefMainWindow' object has no attribute 'palette_sidebar'`.

- [ ] **Step 3: Implement the panel**

`beeref/widgets/palette_panel.py` (GPL header first):
```python
"""Collapsible side panel listing the board's palettes."""

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref import constants


def _highlight():
    return QtGui.QColor(*constants.COLORS['Active:Highlight'])


class SwatchStrip(QtWidgets.QWidget):
    """Swatches of one palette plus a trailing "+" cell; wraps rows."""

    SIZE = 24
    GAP = 4

    def __init__(self, controller, palette, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.palette = palette
        self._drag_from = None
        self.setMouseTracking(True)
        policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def _columns(self, width=None):
        width = self.width() if width is None else width
        return max(1, (width + self.GAP) // (self.SIZE + self.GAP))

    def cell_count(self):
        return len(self.palette.points) + 1

    def cell_rect(self, index):
        cols = self._columns()
        step = self.SIZE + self.GAP
        return QtCore.QRect((index % cols) * step, (index // cols) * step,
                            self.SIZE, self.SIZE)

    def heightForWidth(self, width):
        rows = -(-self.cell_count() // self._columns(width))
        return rows * (self.SIZE + self.GAP)

    def sizeHint(self):
        return QtCore.QSize(240, self.heightForWidth(240))

    def index_at(self, pos):
        for i in range(self.cell_count()):
            if self.cell_rect(i).contains(pos):
                return i
        return None

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        store = self.controller.store
        for i, point in enumerate(self.palette.points):
            rect = QtCore.QRectF(self.cell_rect(i)).adjusted(1, 1, -1, -1)
            available = point.is_available and point.in_crop()
            painter.setBrush(point.color if available
                             else QtGui.QBrush(point.color,
                                               Qt.BrushStyle.Dense4Pattern))
            selected = point is store.selected_point
            painter.setPen(QtGui.QPen(_highlight() if selected
                                      else QtGui.QColor(0, 0, 0, 120),
                                      2.5 if selected else 1))
            painter.drawRoundedRect(rect, 4, 4)
        plus = QtCore.QRectF(self.cell_rect(len(self.palette.points)))
        plus = plus.adjusted(1, 1, -1, -1)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(QtGui.QColor(160, 160, 160), 1,
                                  Qt.PenStyle.DashLine))
        painter.drawRoundedRect(plus, 4, 4)
        painter.drawText(plus, Qt.AlignmentFlag.AlignCenter, '+')

    def event(self, event):
        if event.type() == QtCore.QEvent.Type.ToolTip:
            index = self.index_at(event.pos())
            if index is not None and index < len(self.palette.points):
                c = self.palette.points[index].color
                QtWidgets.QToolTip.showText(
                    event.globalPos(),
                    f'{c.name().upper()}\n'
                    f'RGB {c.red()}, {c.green()}, {c.blue()}\n'
                    f'HSV {max(c.hsvHue(), 0)}°, '
                    f'{round(c.hsvSaturationF() * 100)}%, '
                    f'{round(c.valueF() * 100)}%', self)
            else:
                QtWidgets.QToolTip.hideText()
            return True
        return super().event(event)

    def mousePressEvent(self, event):
        index = self.index_at(event.position().toPoint())
        if index is None:
            return
        self.controller.set_active(self.palette)
        if index == len(self.palette.points):
            self.controller.view.enter_pick_point_mode()
            return
        point = self.palette.points[index]
        if event.button() == Qt.MouseButton.RightButton:
            self.controller.remove_point(point)
            return
        self.controller.store.select_point(point)
        self._drag_from = index

    def mouseReleaseEvent(self, event):
        if self._drag_from is None:
            return
        target = self.index_at(event.position().toPoint())
        point = self.palette.points[self._drag_from]
        self._drag_from = None
        if target is not None and target < len(self.palette.points):
            self.controller.reorder_point(self.palette, point, target)


class PaletteRow(QtWidgets.QFrame):

    def __init__(self, controller, palette, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.palette = palette
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)

        self.name_edit = QtWidgets.QLineEdit(palette.name)
        self.name_edit.editingFinished.connect(self.on_name_edited)
        self.menu_button = QtWidgets.QToolButton()
        self.menu_button.setText('⋯')
        self.menu_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QtWidgets.QMenu(self.menu_button)
        menu.addAction('Rename', self.start_rename)
        self.regenerate_action = menu.addAction(
            'Regenerate', lambda: controller.regenerate(self.palette))
        menu.addAction('Export .aco…', self.export)
        menu.addSeparator()
        menu.addAction('Delete', lambda: controller.delete(self.palette))
        menu.aboutToShow.connect(self.on_menu_about_to_show)
        self.menu_button.setMenu(menu)
        self.strip = SwatchStrip(controller, palette)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(self.name_edit, 1)
        header.addWidget(self.menu_button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(header)
        layout.addWidget(self.strip)
        self.refresh()

    def on_menu_about_to_show(self):
        self.regenerate_action.setEnabled(
            self.controller.can_regenerate(self.palette))

    def start_rename(self):
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def on_name_edited(self):
        self.controller.rename(self.palette, self.name_edit.text())
        if not self.name_edit.text().strip():
            self.name_edit.setText(self.palette.name)

    def export(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Export palette',
            self.controller.default_export_name(self.palette),
            'Photoshop swatches (*.aco)')
        if not path:
            return
        if not path.lower().endswith('.aco'):
            path += '.aco'
        try:
            self.controller.export(self.palette, path)
        except OSError as e:
            QtWidgets.QMessageBox.warning(
                self, 'Problem exporting palette',
                f'<p>Could not write {path}</p><p>{e}</p>')

    def mousePressEvent(self, event):
        self.controller.set_active(self.palette)
        super().mousePressEvent(event)

    def refresh(self):
        if not self.name_edit.hasFocus():
            self.name_edit.setText(self.palette.name)
        active = self.palette is self.controller.store.active
        color = _highlight().name() if active else 'transparent'
        self.setStyleSheet(
            f'PaletteRow {{ border: 2px solid {color}; border-radius: 6px; }}')
        self.strip.updateGeometry()
        self.strip.update()


class PalettePanel(QtWidgets.QWidget):

    WIDTH = 280

    def __init__(self, controller, settings, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings = settings
        self.rows = []
        self.setFixedWidth(self.WIDTH)

        self.auto_checkbox = QtWidgets.QCheckBox('Auto-extract on click')
        self.auto_checkbox.toggled.connect(controller.set_auto_extract)
        self.count_spinbox = QtWidgets.QSpinBox()
        self.count_spinbox.setRange(3, 12)
        self.count_spinbox.setValue(controller.color_count())
        self.count_spinbox.setToolTip('Colors per extraction')
        self.count_spinbox.valueChanged.connect(
            lambda v: settings.setValue('Palette/color_count', v))
        self.new_button = QtWidgets.QPushButton('+ New palette')
        self.new_button.clicked.connect(controller.new_palette)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(self.auto_checkbox, 1)
        header.addWidget(self.count_spinbox)

        self.list_widget = QtWidgets.QWidget()
        self.list_layout = QtWidgets.QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.addStretch(1)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(self.list_widget)

        self.layout_ = QtWidgets.QVBoxLayout(self)
        self.layout_.addLayout(header)
        self.layout_.addWidget(self.new_button)
        self.layout_.addWidget(scroll, 1)

        controller.store.changed.connect(self.on_store_changed)
        self.on_store_changed()

    def on_store_changed(self):
        store = self.controller.store
        if [row.palette for row in self.rows] != store.palettes:
            for row in self.rows:
                row.setParent(None)
                row.deleteLater()
            self.rows = [PaletteRow(self.controller, p)
                         for p in store.palettes]
            for i, row in enumerate(self.rows):
                self.list_layout.insertWidget(i, row)
        for row in self.rows:
            row.refresh()
        if self.auto_checkbox.isChecked() != store.auto_extract:
            self.auto_checkbox.blockSignals(True)
            self.auto_checkbox.setChecked(store.auto_extract)
            self.auto_checkbox.blockSignals(False)


class PaletteSidebar(QtWidgets.QWidget):
    """The palette panel plus a thin chevron strip that collapses it."""

    def __init__(self, controller, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.chevron = QtWidgets.QToolButton()
        self.chevron.setFixedWidth(14)
        self.chevron.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed,
                                   QtWidgets.QSizePolicy.Policy.Expanding)
        self.chevron.setAutoRaise(True)
        self.chevron.clicked.connect(
            lambda: self.set_collapsed(not self.is_collapsed()))
        self.panel = PalettePanel(controller, settings)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.chevron)
        layout.addWidget(self.panel)
        self.set_collapsed(
            settings.value('PalettePanel/collapsed', False, type=bool))
        self.setVisible(
            settings.value('PalettePanel/visible', True, type=bool))

    def is_collapsed(self):
        return self.panel.isHidden()

    def set_collapsed(self, collapsed):
        self.panel.setHidden(collapsed)
        self.chevron.setText('«' if collapsed else '»')
        self.chevron.setToolTip('Show palettes' if collapsed
                                else 'Hide palettes')
        self.settings.setValue('PalettePanel/collapsed', collapsed)

    def toggle_visible(self):
        visible = self.isHidden()
        self.setVisible(visible)
        self.settings.setValue('PalettePanel/visible', visible)
```
Add `palette_panel,` to the `from beeref.widgets import (...)` list in `beeref/widgets/__init__.py`.

- [ ] **Step 4: Lay out the main window**

In `beeref/__main__.py`, import `from beeref.widgets.palette_panel import PaletteSidebar` and replace `self.setCentralWidget(self.view)` with:
```python
        self.palette_sidebar = PaletteSidebar(
            self.view.palette_controller, self.view.settings)
        self.view.palette_sidebar = self.palette_sidebar
        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.palette_sidebar)
        self.setCentralWidget(central)
```

- [ ] **Step 5: Add actions, menus and view callbacks**

In `beeref/actions/actions.py`, append to the `ActionList([...])`, before the closing `])`:
```python
    Action(
        id='toggle_palette_panel',
        text='&Palette Panel',
        shortcuts=['P'],
        callback='on_action_toggle_palette_panel',
    ),
    Action(
        id='palette_new',
        text='&New Palette',
        shortcuts=['Shift+P'],
        callback='on_action_palette_new',
    ),
    Action(
        id='palette_add_point',
        text='&Add Color Point',
        shortcuts=['A'],
        callback='on_action_palette_add_point',
        group='active_when_items_in_scene',
    ),
```
In `beeref/actions/menu_structure.py`, add `MENU_SEPARATOR, 'toggle_palette_panel',` at the end of the `&View` items, and insert after the `&Images` menu dict:
```python
    {
        'menu': '&Palette',
        'items': [
            'palette_new',
            'palette_add_point',
        ],
    },
```
In `beeref/view.py` add:
```python
    def on_action_toggle_palette_panel(self):
        if self.palette_sidebar is not None:
            self.palette_sidebar.toggle_visible()

    def on_action_palette_new(self):
        self.palette_controller.new_palette()

    def on_action_palette_add_point(self):
        self.enter_pick_point_mode()
```

- [ ] **Step 6: Run the panel tests and the whole suite**

Run: `make test`
Expected: all pass. If an upstream test counts menus or actions exactly (e.g. in `tests/actions`), update its expected number and say so in the commit message.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Add collapsible palette side panel and palette actions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Read-only color inspector

**Files:**
- Create: `beeref/widgets/color_inspector.py`
- Modify: `beeref/widgets/palette_panel.py` (`PalettePanel.__init__`, `on_store_changed`), `beeref/widgets/__init__.py`
- Test: `tests/widgets/test_color_inspector.py`

**Interfaces:**
- Consumes: `PalettePanel` (Task 9), `PaletteStore.selected_point`.
- Produces: `ColorInspector()` with `set_color(color: QColor | None)`, `copy_hex()`, `value_labels: dict[str, QLabel]` keyed `'Hue', 'Saturation', 'Value', 'Red', 'Green', 'Blue', 'Hex'`, `copy_button`; `HueTriangle` with `set_color(color)`; `PalettePanel.inspector`.

- [ ] **Step 1: Write the failing tests**

`tests/widgets/test_color_inspector.py`:
```python
from PyQt6 import QtGui, QtWidgets

from beeref.items import BeePixmapItem
from beeref.widgets.color_inspector import ColorInspector
from tests.palette.helpers import stripes


def test_values(qtbot):
    inspector = ColorInspector()
    qtbot.addWidget(inspector)
    inspector.set_color(QtGui.QColor(211, 28, 28))
    labels = {k: v.text() for k, v in inspector.value_labels.items()}
    assert labels == {'Hue': '0', 'Saturation': '87', 'Value': '83',
                      'Red': '211', 'Green': '28', 'Blue': '28',
                      'Hex': '#D31C1C'}
    assert inspector.copy_button.isEnabled()


def test_copy_hex(qtbot):
    inspector = ColorInspector()
    qtbot.addWidget(inspector)
    inspector.set_color(QtGui.QColor(211, 28, 28))
    inspector.copy_button.click()
    assert QtWidgets.QApplication.clipboard().text() == '#D31C1C'


def test_empty_state_and_paint(qtbot):
    inspector = ColorInspector()
    qtbot.addWidget(inspector)
    inspector.set_color(None)
    assert not inspector.copy_button.isEnabled()
    assert inspector.value_labels['Hex'].text() == '–'
    inspector.set_color(QtGui.QColor(128, 128, 128))
    assert not inspector.grab().isNull()


def test_panel_follows_selected_point(main_window):
    view = main_window.view
    item = BeePixmapItem(stripes([(211, 28, 28)]))
    view.scene.addItem(item)
    view.palette_controller.extract_into_active(item)
    store = view.palette_controller.store
    store.select_point(store.active.points[0])
    inspector = main_window.palette_sidebar.panel.inspector
    assert inspector.value_labels['Hex'].text() == '#D31C1C'
    store.select_point(None)
    assert inspector.value_labels['Hex'].text() == '–'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS=tests/widgets/test_color_inspector.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'beeref.widgets.color_inspector'`.

- [ ] **Step 3: Implement**

`beeref/widgets/color_inspector.py` (GPL header first):
```python
"""Read-only view of a swatch: hue ring, S/V triangle and values."""

import math

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt


class HueTriangle(QtWidgets.QWidget):
    """Hue ring with a saturation/value triangle, marking one color."""

    RING = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = None
        self.setFixedSize(120, 120)

    def set_color(self, color):
        self.color = color
        self.update()

    def _geometry(self):
        center = QtCore.QPointF(self.width() / 2, self.height() / 2)
        outer = min(self.width(), self.height()) / 2 - 1
        inner = outer - self.RING
        return center, outer, inner

    def _vertices(self, hue, center, radius):
        def at(angle):
            rad = math.radians(angle)
            return center + QtCore.QPointF(radius * math.cos(rad),
                                           -radius * math.sin(rad))
        return at(hue), at(hue + 120), at(hue + 240)  # hue, white, black

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        center, outer, inner = self._geometry()
        ring = QtGui.QConicalGradient(center, 0)
        for i in range(7):
            ring.setColorAt(i / 6, QtGui.QColor.fromHsv((i * 60) % 360, 255,
                                                        255))
        path = QtGui.QPainterPath()
        path.addEllipse(center, outer, outer)
        path.addEllipse(center, inner, inner)
        painter.fillPath(path, QtGui.QBrush(ring))
        if self.color is None:
            return
        hue = max(self.color.hsvHue(), 0)
        h, w, b = self._vertices(hue, center, inner - 3)
        triangle = QtGui.QPolygonF([h, w, b])
        base = QtGui.QLinearGradient(w, h)
        base.setColorAt(0, Qt.GlobalColor.white)
        base.setColorAt(1, QtGui.QColor.fromHsv(hue, 255, 255))
        shade = QtGui.QLinearGradient((h + w) / 2, b)
        shade.setColorAt(0, QtGui.QColor(0, 0, 0, 0))
        shade.setColorAt(1, QtGui.QColor(0, 0, 0, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QBrush(base))
        painter.drawPolygon(triangle)
        painter.setBrush(QtGui.QBrush(shade))
        painter.drawPolygon(triangle)
        s, v = self.color.hsvSaturationF(), self.color.valueF()
        marker = b + (w + (h - w) * s - b) * v
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(Qt.GlobalColor.white, 2))
        painter.drawEllipse(marker, 4, 4)
        angle = math.radians(hue)
        tick = (inner + outer) / 2
        painter.drawLine(
            center + QtCore.QPointF((tick - 6) * math.cos(angle),
                                    -(tick - 6) * math.sin(angle)),
            center + QtCore.QPointF((tick + 6) * math.cos(angle),
                                    -(tick + 6) * math.sin(angle)))


class ColorInspector(QtWidgets.QWidget):

    NAMES = ('Hue', 'Saturation', 'Value', 'Red', 'Green', 'Blue', 'Hex')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = None
        self.triangle = HueTriangle()
        self.preview = QtWidgets.QFrame()
        self.preview.setFixedHeight(24)
        self.value_labels = {}
        grid = QtWidgets.QGridLayout()
        for i, name in enumerate(self.NAMES):
            label = QtWidgets.QLabel()
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            self.value_labels[name] = label
            grid.addWidget(QtWidgets.QLabel(f'{name}:'), i, 0)
            grid.addWidget(label, i, 1)
        self.copy_button = QtWidgets.QPushButton('Copy hex')
        self.copy_button.clicked.connect(self.copy_hex)

        left = QtWidgets.QVBoxLayout()
        left.addWidget(self.triangle)
        left.addWidget(self.preview)
        right = QtWidgets.QVBoxLayout()
        right.addLayout(grid)
        right.addWidget(self.copy_button)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.addLayout(left)
        layout.addLayout(right, 1)
        self.set_color(None)

    def set_color(self, color):
        self.color = QtGui.QColor(color) if color is not None else None
        self.triangle.set_color(self.color)
        c = self.color
        if c is None:
            values = ['–'] * len(self.NAMES)
            self.preview.setStyleSheet('background: transparent;')
        else:
            values = [max(c.hsvHue(), 0), round(c.hsvSaturationF() * 100),
                      round(c.valueF() * 100), c.red(), c.green(), c.blue(),
                      c.name().upper()]
            self.preview.setStyleSheet(
                f'background: {c.name()}; border-radius: 4px;')
        for name, value in zip(self.NAMES, values):
            self.value_labels[name].setText(str(value))
        self.copy_button.setEnabled(c is not None)

    def copy_hex(self):
        if self.color is not None:
            QtWidgets.QApplication.clipboard().setText(
                self.color.name().upper())
```
In `PalettePanel.__init__` (Task 9 code), before `controller.store.changed.connect(...)`, add:
```python
        self.inspector = ColorInspector()
        self.layout_.addWidget(self.inspector)
```
with `from beeref.widgets.color_inspector import ColorInspector` at the top of `palette_panel.py`. At the end of `on_store_changed` add:
```python
        point = store.selected_point
        self.inspector.set_color(point.color if point is not None else None)
```
Add `color_inspector,` to the import list in `beeref/widgets/__init__.py`.

- [ ] **Step 4: Run tests**

Run: `make test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Add read-only swatch inspector

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Docs, manual check in CSP, private GitHub repo

**Files:**
- Create: `CLAUDE.md`
- Modify: `README.rst` (top section), `CHANGELOG.rst` (new top entry)

**Interfaces:**
- Consumes: everything above.
- Produces: installed `beeref-palette` launcher; private repo `Dratharias/beeref-palette` with remote `origin`.

- [ ] **Step 1: Write the docs**

Prepend to `README.rst`:
```rst
BeeRef Palette
==============

A private fork of `BeeRef <https://github.com/rbreu/beeref>`_ that builds
color palettes from reference images for painting in Clip Studio Paint.

- Palette panel (``P``), collapsible with its chevron.
- Auto-extract on click: distinct dominant colors (3–12) as draggable
  sample points; Regenerate re-extracts from the source image.
- Add points by hand (``A`` or the ``+`` swatch), right-click to remove.
- Read-only inspector with Copy hex.
- Export ``.aco``; in CSP: Color Set palette > Import color set.

Compatibility: boards are saved as ``.bee`` schema v3. Upstream BeeRef
opens them and keeps palettes on a normal save, but drops them on Save As.

Run with ``make run``, test with ``make test``, install with
``make install`` (Python 3.12 via uv).

----
```
Add to the top of `CHANGELOG.rst`:
```rst
0.3.4+palette.1
---------------

* Fork: BeeRef Palette — palette panel, distinct-color extraction,
  sample points, color inspector, .aco export, .bee schema v3.
```
`CLAUDE.md`:
```markdown
# BeeRef Palette

Private fork of BeeRef (GPL-3). Palette feature lives in `beeref/palette/`
and `beeref/widgets/palette_panel.py` / `color_inspector.py`.

- Python 3.12 via uv: `make test`, `make run`, `make install`.
- Spec and plan: `docs/superpowers/`.
- Remote `upstream` is fetch-only (push URL `DISABLED`); never push there
  or open issues/PRs upstream. `origin` is the private GitHub repo.
```

- [ ] **Step 2: Full suite and lint**

Run: `make test && .venv/bin/python -m pip install flake8==7.0.0 -q && .venv/bin/flake8 beeref tests/palette tests/widgets/test_palette_panel.py tests/widgets/test_color_inspector.py`
Expected: tests pass; flake8 prints nothing.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "Document BeeRef Palette

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Install and check by hand**

Run `make install`, launch **BeeRef Palette** from the menu, then:
1. Drop two photos on the board, turn on *Auto-extract on click*, click one photo → palette with distinct colors.
2. Drag a point → swatch and inspector update; `Ctrl+Z` undoes the move.
3. `A`, click the second photo → a point from it joins the palette.
4. Save, close, reopen → palettes, points and active palette are back.
5. Export .aco → in CSP (Wine): Color Set palette menu > Import color set → colors appear with `#RRGGBB` names.
6. Collapse with the chevron, restart → still collapsed.
Report any failure with the step number.

- [ ] **Step 5: Create the private GitHub repo — ask the user first**

This publishes to an external service. Ask the user to confirm, then:
```bash
gh repo create Dratharias/beeref-palette --private --source . --remote origin --push
git remote -v
```
Expected: `origin` → `github.com/Dratharias/beeref-palette`; `upstream` push URL still `DISABLED`. Verify privacy: `gh repo view Dratharias/beeref-palette --json visibility` → `"PRIVATE"`.
