# Color Range Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show an image item as flat zones painted with one palette's colors (paint-by-numbers
look), with a Simplify slider, as a non-destructive per-image view.

**Architecture:** A pure numpy module (`beeref/palette/color_range.py`) quantizes an image to a
palette in OKLab and removes small zones with a majority filter. A `ColorRangeRenderer` runs
that work on a thread pool and hands results to `BeePixmapItem`, whose display pipeline becomes
original → Color Range → Grayscale while `pixmap()` stays the original. Undo commands, a
checkable action and a slider widget (in the palette panel or a floating bar) drive it.

**Tech Stack:** Python 3.12, PyQt6 6.7, numpy, pytest + pytest-qt (offscreen).

**Spec:** `docs/superpowers/specs/2026-10-13-color-range-design.md`

## Global Constraints

- No new dependencies: numpy and PyQt6 only (no scipy).
- All code, comments and docs in English.
- Working resolution: **2048 px** longer side for final renders, **512 px** while dragging.
- Simplify range 0–100, default **26**; radius = `round(level / 100 * 0.0126 * long_side)`.
- Color distance: Euclidean in **OKLab**.
- `BeePixmapItem.pixmap()` must always stay the original image; palette sampling, auto-extract,
  lasso, Sample Color (`S`) and SVG export never see Color Range output.
- Save data key `color_range: {"palette": <position>, "level": <0-100>}`; no SQL schema change.
- Shortcut `F`; menu entry **Images → Color Range**, right after Grayscale.
- Run tests with `make test ARGS="<pytest args>"` (offscreen Qt). Two failures pre-exist and are
  unrelated: `tests/test_view.py::test_mouse_press_move_window` and
  `tests/test_view.py::test_mouse_move_movewin`.
- The working tree holds the user's uncommitted work in `beeref/palette/commands.py`,
  `beeref/palette/model.py`, `beeref/palette/overlay.py`, `beeref/scene.py` and
  `tests/palette/test_overlay.py`. Never stage those files; never `git add -A` / `git add .`;
  stage only the files listed in each task. No task modifies them.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Fully transparent or null (0×0) image put through Color Range: no crash, image stays as-is
   (Task 1 tests `prepare`/`render` on both).
2. Very large or very thin images (e.g. 3000×30): working copy capped at 2048 on the longer side,
   output has the source size (Task 1 test).
3. Slider dragged fast, results arriving out of order or after the filter was turned off: stale
   results dropped (Task 3 tests).
4. A render that raises: logged, previous rendering kept, app keeps running (Task 3 test).
5. Selection changes syncing the checkable action must not push undo steps (checkable actions
   call their callback on `toggled`, including programmatic `setChecked`) (Task 4 test).

---

### Task 1: Pure Color Range processing

**Files:**
- Create: `beeref/palette/color_range.py`
- Test: `tests/palette/test_color_range.py`

**Interfaces:**
- Consumes: `beeref.palette.extract._rgba_array(image: QImage) -> uint8[h,w,4]` (existing).
- Produces (module `beeref.palette.color_range`):
  - constants `DEFAULT_LEVEL = 26`, `FINAL_SIDE = 2048`, `PREVIEW_SIDE = 512`
  - `@dataclass(frozen=True) ColorRangeState(palette, level: int = DEFAULT_LEVEL)`
  - `@dataclass Prepared(source: QImage, lab: float32[h,w,3], mask: bool[h,w])`
  - `to_oklab(rgb: uint8[...,3]) -> float32[...,3]`
  - `quantize(lab, palette_lab: float32[k,3]) -> uint16[h,w]`
  - `simplify(labels, k: int, radius: int, mask) -> uint16[h,w]`
  - `radius_for(level: int, long_side: int) -> int`
  - `prepare(image: QImage, max_side: int) -> Prepared`
  - `render(prepared: Prepared, colors: list[QColor], level: int) -> QImage` (Format_RGBA8888,
    same size as `prepared.source`)

- [ ] **Step 1: Write the failing tests**

`tests/palette/test_color_range.py`:

```python
import numpy as np
from PyQt6 import QtCore, QtGui

from beeref.palette import color_range as cr
from tests.palette.helpers import stripes

RED, MAUVE, BLUE = (220, 30, 30), (200, 40, 60), (40, 60, 210)


def qcolors(*colors):
    return [QtGui.QColor(*c) for c in colors]


def pixel(image, x, y):
    return image.pixelColor(x, y).getRgb()


def test_to_oklab_reference_values():
    rgb = np.array([[255, 255, 255], [0, 0, 0], [255, 0, 0]], np.uint8)
    lab = cr.to_oklab(rgb)
    np.testing.assert_allclose(lab[0], [1, 0, 0], atol=1e-3)
    np.testing.assert_allclose(lab[1], [0, 0, 0], atol=1e-6)
    np.testing.assert_allclose(lab[2], [0.62796, 0.22486, 0.12585], atol=1e-3)


def test_quantize_picks_nearest_palette_color():
    lab = cr.to_oklab(np.array([[RED, MAUVE, BLUE]], np.uint8))
    palette = cr.to_oklab(np.array([RED, BLUE], np.uint8))
    assert cr.quantize(lab, palette).tolist() == [[0, 0, 1]]


def test_quantize_tie_goes_to_first_color():
    lab = cr.to_oklab(np.array([[RED]], np.uint8))
    palette = cr.to_oklab(np.array([RED, RED], np.uint8))
    assert cr.quantize(lab, palette).tolist() == [[0]]


def test_simplify_radius_zero_is_identity():
    labels = np.array([[0, 1], [1, 0]], np.uint16)
    out = cr.simplify(labels, 2, 0, np.ones((2, 2), bool))
    assert out.tolist() == labels.tolist()


def test_simplify_absorbs_small_island():
    labels = np.zeros((21, 21), np.uint16)
    labels[10, 10] = 1
    out = cr.simplify(labels, 2, 1, np.ones((21, 21), bool))
    assert not out.any()


def test_simplify_keeps_large_zones():
    labels = np.zeros((21, 21), np.uint16)
    labels[:, 10:] = 1
    out = cr.simplify(labels, 2, 1, np.ones((21, 21), bool))
    assert out.tolist() == labels.tolist()


def test_simplify_transparent_pixels_do_not_vote():
    labels = np.ones((3, 3), np.uint16)
    labels[1, 1] = 0
    mask = np.zeros((3, 3), bool)
    mask[1, 1] = True
    out = cr.simplify(labels, 2, 1, mask)
    assert out.tolist() == labels.tolist()


def test_radius_for():
    assert cr.radius_for(0, 2048) == 0
    assert cr.radius_for(100, 1000) == 30
    assert cr.radius_for(50, 2048) == 31


def test_render_maps_to_palette_colors_and_keeps_size():
    image = stripes([RED, MAUVE, BLUE])
    result = cr.render(cr.prepare(image, cr.FINAL_SIDE), qcolors(RED, BLUE), 0)
    assert result.size() == image.size()
    assert pixel(result, 5, 5) == (*RED, 255)
    assert pixel(result, 30, 5) == (*RED, 255)
    assert pixel(result, 50, 5) == (*BLUE, 255)


def test_render_one_color_palette_is_flat():
    image = stripes([RED, BLUE])
    result = cr.render(cr.prepare(image, cr.FINAL_SIDE), qcolors(BLUE), 50)
    assert {pixel(result, x, 5) for x in range(40)} == {(*BLUE, 255)}


def test_render_preserves_alpha():
    image = QtGui.QImage(10, 10, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.fillRect(0, 0, 5, 10, QtGui.QColor(*RED))
    painter.end()
    result = cr.render(cr.prepare(image, cr.FINAL_SIDE), qcolors(BLUE), 0)
    assert pixel(result, 2, 5) == (*BLUE, 255)
    assert result.pixelColor(7, 5).alpha() == 0


def test_render_fully_transparent_image():
    image = QtGui.QImage(8, 8, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    result = cr.render(cr.prepare(image, cr.FINAL_SIDE), qcolors(RED), 50)
    assert result.size() == image.size()
    assert result.pixelColor(4, 4).alpha() == 0


def test_null_image_renders_as_is():
    prepared = cr.prepare(QtGui.QImage(), cr.PREVIEW_SIDE)
    assert cr.render(prepared, qcolors(RED), 50).isNull()


def test_prepare_caps_working_size():
    image = stripes([RED, BLUE], widths=[1500, 1500], height=30)
    prepared = cr.prepare(image, cr.FINAL_SIDE)
    assert prepared.lab.shape[1] == 2048
    result = cr.render(prepared, qcolors(RED, BLUE), 30)
    assert result.size() == image.size()


def test_preview_and_final_agree_on_large_zones():
    image = stripes([RED, BLUE], widths=[400, 400], height=100)
    preview = cr.render(cr.prepare(image, cr.PREVIEW_SIDE), qcolors(RED, BLUE), 50)
    final = cr.render(cr.prepare(image, cr.FINAL_SIDE), qcolors(RED, BLUE), 50)
    for x in (100, 700):
        assert pixel(preview, x, 50) == pixel(final, x, 50)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS="tests/palette/test_color_range.py"`
Expected: FAIL — `ImportError: cannot import name 'color_range'`.

- [ ] **Step 3: Implement `beeref/palette/color_range.py`**

Start with the same GPL header comment block as `beeref/palette/extract.py`, then:

```python
"""Color Range: an image shown as flat zones of a palette's colors."""

from dataclasses import dataclass

import numpy as np
from PyQt6 import QtGui
from PyQt6.QtCore import Qt

from beeref.palette.extract import _rgba_array


DEFAULT_LEVEL = 26
FINAL_SIDE = 2048
PREVIEW_SIDE = 512
# Neighborhood radius at level 100, as a fraction of the longer side
MAX_RADIUS = 0.03
PASSES = 2

_RGB_TO_LMS = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                        [0.2119034982, 0.6806995451, 0.1073969566],
                        [0.0883024619, 0.2817188376, 0.6299787005]],
                       np.float32)
_LMS_TO_LAB = np.array([[0.2104542553, 0.7936177850, -0.0040720123],
                        [1.9779984951, -2.4285922050, 0.4505937099],
                        [0.0259040371, 0.7827717662, -0.8086757660]],
                       np.float32)


@dataclass(frozen=True)
class ColorRangeState:
    """An image's Color Range binding: which palette, how simplified."""
    palette: object
    level: int = DEFAULT_LEVEL


@dataclass
class Prepared:
    """An image's OKLab pixels at working resolution."""
    source: QtGui.QImage
    lab: np.ndarray
    mask: np.ndarray


def to_oklab(rgb):
    """Convert an (..., 3) uint8 sRGB array to OKLab."""
    c = rgb.astype(np.float32) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return np.cbrt(c @ _RGB_TO_LMS.T) @ _LMS_TO_LAB.T


def quantize(lab, palette_lab):
    """Index of the nearest palette color for every pixel."""
    best = np.zeros(lab.shape[:2], np.uint16)
    best_dist = np.full(lab.shape[:2], np.inf, np.float32)
    for index, color in enumerate(palette_lab):
        dist = ((lab - color) ** 2).sum(axis=-1)
        closer = dist < best_dist
        best[closer] = index
        best_dist[closer] = dist[closer]
    return best


def _box_sum(values, radius):
    """Sum of ``values`` over the (2r+1)² square around each pixel."""
    size = 2 * radius + 1
    padded = np.pad(values, ((radius + 1, radius), (radius + 1, radius)))
    total = padded.cumsum(axis=0).cumsum(axis=1)
    return (total[size:, size:] - total[:-size, size:]
            - total[size:, :-size] + total[:-size, :-size])


def simplify(labels, k, radius, mask):
    """Majority filter: each opaque pixel takes its neighborhood's most
    frequent label. Transparent pixels do not vote; ties keep the pixel's
    own label."""
    if radius <= 0:
        return labels
    out = labels
    for _ in range(PASSES):
        best = out.copy()
        best_count = np.full(out.shape, -1, np.int32)
        for index in range(k):
            own = out == index
            counts = _box_sum((own & mask).astype(np.int32), radius)
            better = (counts > best_count) | ((counts == best_count) & own)
            best[better] = index
            best_count[better] = counts[better]
        out = np.where(mask, best, out)
    return out


def radius_for(level, long_side):
    return round(level / 100 * MAX_RADIUS * long_side)


def _qimage(rgba):
    rgba = np.ascontiguousarray(rgba)
    h, w = rgba.shape[:2]
    data = rgba.tobytes()  # must outlive the QImage until it is copied
    image = QtGui.QImage(data, w, h, 4 * w,
                         QtGui.QImage.Format.Format_RGBA8888)
    return image.copy()


def prepare(image, max_side):
    """Working-resolution OKLab copy of ``image``."""
    if image.isNull():
        return Prepared(image, np.zeros((0, 0, 3), np.float32),
                        np.zeros((0, 0), bool))
    work = image
    if max(image.width(), image.height()) > max_side:
        work = image.scaled(max_side, max_side,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
    rgba = _rgba_array(work)
    return Prepared(image, to_oklab(rgba[..., :3]), rgba[..., 3] > 0)


def render(prepared, colors, level):
    """The source image as flat zones of ``colors`` (at least one)."""
    if prepared.mask.size == 0:
        return QtGui.QImage(prepared.source)
    h, w = prepared.mask.shape
    palette_rgb = np.array([c.getRgb()[:3] for c in colors], np.uint8)
    labels = quantize(prepared.lab, to_oklab(palette_rgb))
    labels = simplify(labels, len(colors), radius_for(level, max(w, h)),
                      prepared.mask)
    rgba = np.empty((h, w, 4), np.uint8)
    rgba[..., :3] = palette_rgb[labels]
    rgba[..., 3] = 255
    image = _qimage(rgba)
    source = prepared.source
    if image.size() != source.size():
        image = image.scaled(source.size(),
                             Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.FastTransformation)
    full = _rgba_array(image).copy()
    full[..., 3] = _rgba_array(source)[..., 3]
    return _qimage(full)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test ARGS="tests/palette/test_color_range.py"`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add beeref/palette/color_range.py tests/palette/test_color_range.py
git commit -m "Color Range: OKLab quantization and majority-filter simplification

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Item display pipeline and save data

**Files:**
- Modify: `beeref/items.py` (`BeePixmapItem`: `__init__`, `create_from_data`, `grayscale`
  setter, `sample_color_at`, `get_extra_save_data`, `pixmap_to_bytes`, `create_copy`, `paint`)
- Test: `tests/palette/test_color_range_item.py`

**Interfaces:**
- Consumes: `ColorRangeState` (Task 1).
- Produces on `BeePixmapItem`:
  - attributes `color_range` (`ColorRangeState | None`), `_color_range_pixmap`
    (`QPixmap | None`), `_color_range_pending` (`dict | None`, raw save data awaiting palette
    resolution), `_color_range_colors` (`list[str] | None`, hex names used for the last
    request), `_color_range_generation` (`int`), `_color_range_prepared`
    (`dict[int, tuple[int, Prepared]]`, keyed by working side)
  - `set_color_range(state)` — sets state; `None` also drops the result
  - `set_color_range_result(pixmap | None)` — stores the result, rebuilds grayscale, repaints
  - `color_pixmap() -> QPixmap` — result if on and ready, else `pixmap()`
  - `display_pixmap() -> QPixmap` — what `paint` draws
  - `original_display_pixmap() -> QPixmap` — what the item would show without Color Range
  - `_grayscale_of(pixmap) -> QPixmap` (staticmethod)

- [ ] **Step 1: Write the failing tests**

`tests/palette/test_color_range_item.py`:

```python
from PyQt6 import QtCore, QtGui

from beeref.items import BeePixmapItem
from beeref.palette.color_range import ColorRangeState
from beeref.palette.model import Palette
from tests.palette.helpers import stripes

RED, GREEN, BLUE = (220, 30, 30), (30, 180, 60), (40, 60, 210)


def filled(size, color):
    pixmap = QtGui.QPixmap(size)
    pixmap.fill(QtGui.QColor(*color))
    return pixmap


def bound_item(palette=None):
    item = BeePixmapItem(stripes([RED, BLUE]))
    item.set_color_range(ColorRangeState(palette or Palette('P')))
    return item


def color_at(pixmap, x=5, y=5):
    return pixmap.toImage().pixelColor(x, y)


def test_display_is_original_until_result_arrives(qapp):
    item = bound_item()
    assert item.display_pixmap() is item.pixmap()


def test_display_shows_result(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    assert color_at(item.display_pixmap()) == QtGui.QColor(*GREEN)
    assert color_at(item.pixmap()) == QtGui.QColor(*RED)


def test_turning_off_drops_result(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    item.set_color_range(None)
    assert item._color_range_pixmap is None
    assert item.display_pixmap() is item.pixmap()


def test_grayscale_applies_on_top_of_result(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    item.grayscale = True
    expected = BeePixmapItem._grayscale_of(item.color_pixmap())
    assert color_at(item.display_pixmap()) == color_at(expected)
    original_gray = BeePixmapItem._grayscale_of(item.pixmap())
    assert color_at(item.display_pixmap()) != color_at(original_gray)


def test_result_arriving_rebuilds_grayscale(qapp):
    item = bound_item()
    item.grayscale = True
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    expected = BeePixmapItem._grayscale_of(item.color_pixmap())
    assert color_at(item.display_pixmap()) == color_at(expected)


def test_sample_color_reads_original(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    assert item.sample_color_at(QtCore.QPointF(5, 5)) == QtGui.QColor(*RED)


def test_sample_color_grayscale_reads_original_gray(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    item.grayscale = True
    expected = color_at(BeePixmapItem._grayscale_of(item.pixmap()))
    assert item.sample_color_at(QtCore.QPointF(5, 5)) == expected


def test_export_grayscale_ignores_color_range(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    item.grayscale = True
    data, _ = item.pixmap_to_bytes(apply_grayscale=True)
    exported = QtGui.QImage.fromData(data)
    expected = color_at(BeePixmapItem._grayscale_of(item.pixmap()))
    assert exported.pixelColor(5, 5).getRgb()[:3] == expected.getRgb()[:3]


def test_save_data_records_palette_position(view):
    first, second = Palette('A'), Palette('B')
    view.scene.palettes.add(first)
    view.scene.palettes.add(second)
    item = bound_item(second)
    item.set_color_range(ColorRangeState(second, 45))
    view.scene.addItem(item)
    data = item.get_extra_save_data()
    assert data['color_range'] == {'palette': 1, 'level': 45}


def test_save_data_omits_color_range_when_off_or_unbound(view):
    item = BeePixmapItem(stripes([RED]))
    view.scene.addItem(item)
    assert 'color_range' not in item.get_extra_save_data()
    item.set_color_range(ColorRangeState(Palette('Not in store')))
    assert 'color_range' not in item.get_extra_save_data()


def test_create_from_data_keeps_color_range_pending(qapp):
    item = BeePixmapItem(stripes([RED]))
    BeePixmapItem.create_from_data(
        item=item, data={'color_range': {'palette': 0, 'level': 10}})
    assert item._color_range_pending == {'palette': 0, 'level': 10}
    assert item.color_range is None


def test_create_copy_carries_color_range(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    copy = item.create_copy()
    assert copy.color_range == item.color_range
    assert color_at(copy.display_pixmap()) == QtGui.QColor(*GREEN)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS="tests/palette/test_color_range_item.py"`
Expected: FAIL — `AttributeError: 'BeePixmapItem' object has no attribute 'set_color_range'`.

- [ ] **Step 3: Implement in `beeref/items.py`**

In `BeePixmapItem.__init__`, insert **before** `self.grayscale = False` (the grayscale setter
reads `color_pixmap()`):

```python
        # Color Range view (see beeref/palette/color_range.py); the
        # renderer fills the result, pixmap() always stays the original.
        self.color_range = None
        self._color_range_pixmap = None
        self._color_range_pending = None
        self._color_range_colors = None
        self._color_range_generation = 0
        self._color_range_prepared = {}
```

In `create_from_data`, after the `item.grayscale = ...` line:

```python
        item._color_range_pending = data.get('color_range')
```

Replace the `grayscale` setter body so it builds from `color_pixmap()`, moving the existing
long comment block (from "Using the grayscale image format..." through "3. Going through every
pixel and doing it manually — bad performance.") unchanged into the new staticmethod:

```python
    @grayscale.setter
    def grayscale(self, value):
        logger.debug('Setting grayscale for {self} to {value}')
        self._grayscale = value
        if value is True:
            self._grayscale_pixmap = self._grayscale_of(self.color_pixmap())
        else:
            self._grayscale_pixmap = None

        self.update()

    @staticmethod
    def _grayscale_of(pixmap):
        # <existing comment block, moved here verbatim>
        img = QtGui.QImage(
            pixmap.size(), QtGui.QImage.Format.Format_Grayscale8)
        img.fill(QtGui.QColor(*COLORS['Scene:Canvas']))
        painter = QtGui.QPainter(img)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        return QtGui.QPixmap.fromImage(img)

    def set_color_range(self, state):
        """Bind a ColorRangeState, or None to turn Color Range off."""
        self.color_range = state
        if state is None:
            self.set_color_range_result(None)

    def set_color_range_result(self, pixmap):
        self._color_range_pixmap = pixmap
        self.grayscale = self.grayscale  # rebuilds the gray version
        self.update()

    def color_pixmap(self):
        """The original pixmap, or its Color Range rendering once ready."""
        if (self.color_range is not None
                and self._color_range_pixmap is not None):
            return self._color_range_pixmap
        return self.pixmap()

    def display_pixmap(self):
        if self.grayscale:
            return self._grayscale_pixmap
        return self.color_pixmap()

    def original_display_pixmap(self):
        """What the item shows without Color Range (sampling, export)."""
        if not self.grayscale:
            return self.pixmap()
        if self.color_pixmap() is self.pixmap():
            return self._grayscale_pixmap
        return self._grayscale_of(self.pixmap())
```

In `sample_color_at`, replace the `if self.grayscale: ... else: ...` choice with:

```python
        pm = self.original_display_pixmap()
```

In `pixmap_to_bytes`, replace the `if apply_grayscale and self.grayscale:` branch body:

```python
        if apply_grayscale and self.grayscale:
            pm = self.original_display_pixmap()
        else:
            pm = self.pixmap()
```

Replace `get_extra_save_data` with:

```python
    def get_extra_save_data(self):
        data = {'filename': self.filename,
                'opacity': self.opacity(),
                'grayscale': self.grayscale,
                'crop': [self.crop.topLeft().x(),
                         self.crop.topLeft().y(),
                         self.crop.width(),
                         self.crop.height()]}
        color_range = self._color_range_save_data()
        if color_range is not None:
            data['color_range'] = color_range
        return data

    def _color_range_save_data(self):
        if self.color_range is None or self.scene() is None:
            return None
        palettes = self.scene().palettes.palettes
        for position, palette in enumerate(palettes):
            if palette is self.color_range.palette:
                return {'palette': position, 'level': self.color_range.level}
        return None
```

In `create_copy`, insert **before** `item.grayscale = self.grayscale`:

```python
        item.color_range = self.color_range
        item._color_range_pixmap = self._color_range_pixmap
        item._color_range_colors = self._color_range_colors
```

In `paint`, replace
`pm = self._grayscale_pixmap if self.grayscale else self.pixmap()` with:

```python
            pm = self.display_pixmap()
```

- [ ] **Step 4: Run the new tests and the existing item tests**

Run: `make test ARGS="tests/palette/test_color_range_item.py tests/items tests/fileio tests/palette"`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add beeref/items.py tests/palette/test_color_range_item.py
git commit -m "Image items: display pipeline with a Color Range stage under grayscale

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Background renderer, palette reactivity and loading

**Files:**
- Create: `beeref/palette/color_range_renderer.py`
- Modify: `beeref/palette/controller.py` (`__init__`, `restore_loaded`, new
  `restore_color_ranges`)
- Test: `tests/palette/test_color_range_renderer.py`

**Interfaces:**
- Consumes: Task 1 (`prepare`, `render`, `ColorRangeState`, `FINAL_SIDE`, `PREVIEW_SIDE`,
  `DEFAULT_LEVEL`), Task 2 item API, `beeref.palette.model.item_image(item) -> QImage`.
- Produces:
  - `ColorRangeRenderer(scene, synchronous=False)` (QObject) with
    `apply(item, state, preview=False)`, `request(item, preview=False)`,
    `on_done(item, generation, side, cache_entry, result)`, `on_store_changed()`, `wait()`,
    attribute `synchronous: bool`
  - `PaletteController.color_range: ColorRangeRenderer`
  - `PaletteController.restore_color_ranges(items)`

- [ ] **Step 1: Write the failing tests**

`tests/palette/test_color_range_renderer.py`:

```python
from unittest.mock import patch

from PyQt6 import QtGui

from beeref.fileio import load_bee, save_bee
from beeref.items import BeePixmapItem
from beeref.palette import color_range
from beeref.palette.color_range import ColorRangeState
from beeref.palette.model import Palette, SamplePoint
from tests.palette.helpers import stripes

RED, MAUVE, BLUE = (220, 30, 30), (200, 40, 60), (40, 60, 210)


def setup(view):
    renderer = view.palette_controller.color_range
    renderer.synchronous = True
    item = BeePixmapItem(stripes([RED, MAUVE, BLUE]))
    view.scene.addItem(item)
    palette = Palette('P', [SamplePoint(item, 10 / 60, 0.5),
                            SamplePoint(item, 50 / 60, 0.5)])
    view.scene.palettes.add(palette)
    return renderer, item, palette


def shown(item, x):
    return item.color_pixmap().toImage().pixelColor(x, 5)


def test_apply_renders_palette_colors(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    assert item.color_pixmap() is not item.pixmap()
    assert shown(item, 30) == QtGui.QColor(*RED)
    assert shown(item, 50) == QtGui.QColor(*BLUE)


def test_apply_none_turns_off(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    renderer.apply(item, None)
    assert item.color_range is None
    assert item.color_pixmap() is item.pixmap()


def test_deleting_palette_turns_off(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    view.scene.palettes.remove(palette)
    assert item.color_range is None
    assert item.color_pixmap() is item.pixmap()


def test_palette_color_change_recomputes(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    palette.points.pop()
    view.scene.palettes.notify()
    assert shown(item, 50) == QtGui.QColor(*RED)


def test_unchanged_colors_do_not_recompute(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    with patch.object(renderer, 'request') as request:
        palette.name = 'Renamed'
        view.scene.palettes.notify()
    request.assert_not_called()


def test_empty_palette_shows_original_but_stays_on(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    palette.points.clear()
    view.scene.palettes.notify()
    assert item.color_range is not None
    assert item.color_pixmap() is item.pixmap()


def test_stale_result_is_dropped(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    current = item.color_pixmap()
    stale = QtGui.QImage(item.pixmap().size(),
                         QtGui.QImage.Format.Format_RGBA8888)
    renderer.on_done(item, item._color_range_generation - 1,
                     color_range.FINAL_SIDE, (0, None), stale)
    assert item.color_pixmap() is current


def test_result_after_turning_off_is_dropped(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    renderer.apply(item, None)
    late = QtGui.QImage(item.pixmap().size(),
                        QtGui.QImage.Format.Format_RGBA8888)
    renderer.on_done(item, item._color_range_generation,
                     color_range.FINAL_SIDE, (0, None), late)
    assert item.color_pixmap() is item.pixmap()


def test_prepared_image_is_cached(view):
    renderer, item, palette = setup(view)
    with patch('beeref.palette.color_range.prepare',
               wraps=color_range.prepare) as prepare:
        renderer.apply(item, ColorRangeState(palette, 0))
        renderer.apply(item, ColorRangeState(palette, 40))
    assert prepare.call_count == 1


def test_preview_uses_preview_side(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0), preview=True)
    assert color_range.PREVIEW_SIDE in item._color_range_prepared


def test_render_failure_keeps_previous_result(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    previous = item.color_pixmap()
    with patch('beeref.palette.color_range.render',
               side_effect=ValueError('boom')):
        renderer.apply(item, ColorRangeState(palette, 40))
    assert item.color_pixmap() is previous


def test_threaded_render_arrives(view, qtbot):
    renderer, item, palette = setup(view)
    renderer.synchronous = False
    renderer.apply(item, ColorRangeState(palette, 0))
    qtbot.waitUntil(lambda: item.color_pixmap() is not item.pixmap())


def test_result_for_removed_item_is_harmless(view, qtbot):
    renderer, item, palette = setup(view)
    renderer.synchronous = False
    renderer.apply(item, ColorRangeState(palette, 0))
    view.scene.removeItem(item)
    renderer.wait()
    qtbot.wait(10)


def reload(view, filename):
    view.scene.clear()
    load_bee(filename, view.scene)
    view.scene.add_queued_items()
    view.palette_controller.restore_loaded()


def images(view):
    return [i for i in view.scene.items() if getattr(i, 'is_image', False)]


def test_save_load_round_trip(view, tmpfile):
    renderer, item, palette = setup(view)
    other = Palette('Other', [SamplePoint(item, 0.5, 0.5)])
    view.scene.palettes.add(other)
    renderer.apply(item, ColorRangeState(other, 45))
    save_bee(tmpfile, view.scene, create_new=True)
    reload(view, tmpfile)
    [loaded] = images(view)
    assert loaded.color_range.palette is view.scene.palettes.palettes[1]
    assert loaded.color_range.level == 45
    assert loaded.color_pixmap() is not loaded.pixmap()


def test_unresolvable_palette_position_means_off(view):
    renderer, item, palette = setup(view)
    item._color_range_pending = {'palette': 7, 'level': 10}
    view.palette_controller.restore_color_ranges([item])
    assert item.color_range is None
    assert item._color_range_pending is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS="tests/palette/test_color_range_renderer.py"`
Expected: FAIL — `AttributeError: 'PaletteController' object has no attribute 'color_range'`.

- [ ] **Step 3: Implement `beeref/palette/color_range_renderer.py`**

GPL header block as in the other modules, then:

```python
"""Runs Color Range renders off the GUI thread and applies the results."""

import logging

from PyQt6 import QtCore, QtGui

from beeref.palette import color_range
from beeref.palette.model import item_image


logger = logging.getLogger(__name__)


class _Signals(QtCore.QObject):
    # item, generation, working side, (cache key, Prepared), result QImage
    done = QtCore.pyqtSignal(object, int, int, object, object)


class _Job(QtCore.QRunnable):

    def __init__(self, signals, item, generation, image, side, cache_key,
                 prepared, colors, level):
        super().__init__()
        self.signals = signals
        self.item = item
        self.generation = generation
        self.image = image
        self.side = side
        self.cache_key = cache_key
        self.prepared = prepared
        self.colors = colors
        self.level = level

    def run(self):
        try:
            prepared = (self.prepared
                        or color_range.prepare(self.image, self.side))
            result = color_range.render(prepared, self.colors, self.level)
        except Exception:
            logger.exception('Color Range render failed')
            return
        self.signals.done.emit(self.item, self.generation, self.side,
                               (self.cache_key, prepared), result)


class ColorRangeRenderer(QtCore.QObject):
    """Keeps Color Range items rendered with their palette's colors."""

    def __init__(self, scene, synchronous=False):
        super().__init__()
        self.scene = scene
        self.store = scene.palettes
        # Render on the calling thread (tests)
        self.synchronous = synchronous
        self.pool = QtCore.QThreadPool()
        self.pool.setMaxThreadCount(2)
        self.signals = _Signals()
        self.signals.done.connect(self.on_done)
        self.store.changed.connect(self.on_store_changed)

    def apply(self, item, state, preview=False):
        """Set an item's Color Range state (None = off) and render it."""
        item._color_range_generation += 1
        item.set_color_range(state)
        if state is not None:
            self.request(item, preview)

    def request(self, item, preview=False):
        state = item.color_range
        colors = state.palette.colors()
        item._color_range_colors = [c.name() for c in colors]
        item._color_range_generation += 1
        if not colors or item.pixmap().isNull():
            item.set_color_range_result(None)
            return
        side = (color_range.PREVIEW_SIDE if preview
                else color_range.FINAL_SIDE)
        key = item.pixmap().cacheKey()
        cached = item._color_range_prepared.get(side)
        prepared = cached[1] if cached and cached[0] == key else None
        job = _Job(self.signals, item, item._color_range_generation,
                   item_image(item), side, key, prepared, colors, state.level)
        if self.synchronous:
            job.run()
        else:
            self.pool.start(job)

    def on_done(self, item, generation, side, cache_entry, result):
        item._color_range_prepared[side] = cache_entry
        if (generation != item._color_range_generation
                or item.color_range is None):
            return
        item.set_color_range_result(QtGui.QPixmap.fromImage(result))

    def on_store_changed(self):
        palettes = self.store.palettes
        for item in self.scene.items():
            state = getattr(item, 'color_range', None)
            if state is None:
                continue
            if not any(p is state.palette for p in palettes):
                self.apply(item, None)
            elif ([c.name() for c in state.palette.colors()]
                    != item._color_range_colors):
                self.request(item)

    def wait(self):
        """Block until queued renders are finished."""
        self.pool.waitForDone()
```

- [ ] **Step 4: Wire it into `beeref/palette/controller.py`**

Add imports:

```python
from beeref.palette.color_range import DEFAULT_LEVEL, ColorRangeState
from beeref.palette.color_range_renderer import ColorRangeRenderer
```

At the end of `PaletteController.__init__`:

```python
        self.color_range = ColorRangeRenderer(self.scene)
```

At the end of `restore_loaded` (after `self.store.restore(data, items, unloaded)`):

```python
        self.restore_color_ranges(items.values())

    def restore_color_ranges(self, items):
        """Bind loaded images to their saved palette (by position)."""
        palettes = self.store.palettes
        for item in items:
            pending = item._color_range_pending
            item._color_range_pending = None
            if not pending:
                continue
            position = pending.get('palette')
            if isinstance(position, int) and 0 <= position < len(palettes):
                level = int(pending.get('level', DEFAULT_LEVEL))
                self.color_range.apply(
                    item, ColorRangeState(palettes[position], level))
```

(Place `restore_color_ranges` as its own method right after `restore_loaded`; the call line is
the last statement inside `restore_loaded`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `make test ARGS="tests/palette"`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add beeref/palette/color_range_renderer.py beeref/palette/controller.py tests/palette/test_color_range_renderer.py
git commit -m "Color Range renderer: threaded renders, palette reactivity, loading

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Undo commands, controller operations and the Images → Color Range action

**Files:**
- Modify: `beeref/commands.py` (append two commands)
- Modify: `beeref/palette/controller.py` (three methods)
- Modify: `beeref/actions/actions.py` (new action after `grayscale`)
- Modify: `beeref/actions/menu_structure.py` (`&Images` menu)
- Modify: `beeref/view.py` (`__init__`, `on_selection_changed`, new `on_action_color_range`,
  new `update_color_range_controls`)
- Test: `tests/palette/test_color_range_actions.py`

**Interfaces:**
- Consumes: `ColorRangeRenderer.apply`, `ColorRangeState`, `DEFAULT_LEVEL`.
- Produces:
  - `beeref.commands.ToggleColorRange(renderer, items, palette, checked)`
  - `beeref.commands.SetColorRangeLevel(renderer, items, old_levels, level)`
  - `PaletteController.toggle_color_range(items, checked)`,
    `PaletteController.preview_color_range_level(items, level)`,
    `PaletteController.commit_color_range_level(items, old_levels, level)`
  - `BeeGraphicsView.on_action_color_range(checked)`,
    `BeeGraphicsView.update_color_range_controls()` (Task 5 replaces its body)

- [ ] **Step 1: Write the failing tests**

`tests/palette/test_color_range_actions.py`:

```python
from beeref import commands
from beeref.actions import actions
from beeref.items import BeePixmapItem, BeeTextItem
from beeref.palette.color_range import DEFAULT_LEVEL, ColorRangeState
from beeref.palette.model import Palette, SamplePoint
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def board(view, with_palette=True):
    view.palette_controller.color_range.synchronous = True
    item = BeePixmapItem(stripes([RED, BLUE]))
    view.scene.addItem(item)
    palette = None
    if with_palette:
        palette = Palette('P', [SamplePoint(item, 0.25, 0.5)])
        view.scene.palettes.add(palette)
        view.scene.palettes.set_active(palette)
    return item, palette


def qaction():
    return actions.actions['color_range'].qaction


def test_toggle_command_redo_undo(view):
    item, palette = board(view)
    renderer = view.palette_controller.color_range
    command = commands.ToggleColorRange(renderer, [item], palette, True)
    command.redo()
    assert item.color_range == ColorRangeState(palette, DEFAULT_LEVEL)
    command.undo()
    assert item.color_range is None


def test_toggle_on_rebinds_and_keeps_level(view):
    item, palette = board(view)
    other = Palette('O', [SamplePoint(item, 0.75, 0.5)])
    view.scene.palettes.add(other)
    renderer = view.palette_controller.color_range
    renderer.apply(item, ColorRangeState(palette, 70))
    commands.ToggleColorRange(renderer, [item], other, True).redo()
    assert item.color_range == ColorRangeState(other, 70)


def test_toggle_command_skips_text_items(view):
    item, palette = board(view)
    text = BeeTextItem('t')
    command = commands.ToggleColorRange(
        view.palette_controller.color_range, [item, text], palette, True)
    assert command.items == [item]


def test_level_command_redo_undo(view):
    item, palette = board(view)
    renderer = view.palette_controller.color_range
    renderer.apply(item, ColorRangeState(palette, 30))
    command = commands.SetColorRangeLevel(renderer, [item], [30], 80)
    command.redo()
    assert item.color_range.level == 80
    command.undo()
    assert item.color_range.level == 30


def test_action_toggles_selected_images_with_undo(view):
    item, palette = board(view)
    item.setSelected(True)
    view.on_action_color_range(True)
    assert item.color_range.palette is palette
    view.undo_stack.undo()
    assert item.color_range is None


def test_action_needs_a_palette(view):
    item, _ = board(view, with_palette=False)
    item.setSelected(True)
    view.update_color_range_controls()
    assert not qaction().isEnabled()
    view.on_action_color_range(True)
    assert item.color_range is None


def test_action_enabled_with_image_and_palette(view):
    item, _ = board(view)
    view.update_color_range_controls()
    assert not qaction().isEnabled()
    item.setSelected(True)
    assert qaction().isEnabled()


def test_action_checked_follows_first_selected_item(view):
    item, palette = board(view)
    view.palette_controller.color_range.apply(
        item, ColorRangeState(palette))
    item.setSelected(True)
    assert qaction().isChecked()
    item.setSelected(False)
    assert not qaction().isChecked()


def test_syncing_checked_state_pushes_no_undo(view):
    item, palette = board(view)
    view.palette_controller.color_range.apply(
        item, ColorRangeState(palette))
    count = view.undo_stack.count()
    item.setSelected(True)
    item.setSelected(False)
    assert view.undo_stack.count() == count
    assert item.color_range is not None


def test_preview_pushes_no_undo_commit_pushes_one(view):
    item, palette = board(view)
    controller = view.palette_controller
    controller.color_range.apply(item, ColorRangeState(palette, 30))
    count = view.undo_stack.count()
    controller.preview_color_range_level([item], 55)
    assert item.color_range.level == 55
    assert view.undo_stack.count() == count
    controller.commit_color_range_level([item], [30], 60)
    assert view.undo_stack.count() == count + 1
    view.undo_stack.undo()
    assert item.color_range.level == 30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS="tests/palette/test_color_range_actions.py"`
Expected: FAIL — `AttributeError: module 'beeref.commands' has no attribute 'ToggleColorRange'`.

- [ ] **Step 3: Add the commands to `beeref/commands.py`**

Add imports at the top:

```python
import dataclasses

from beeref.palette.color_range import DEFAULT_LEVEL, ColorRangeState
```

Append after `ToggleGrayscale`:

```python
class ToggleColorRange(QtGui.QUndoCommand):
    """Turn Color Range on (bound to a palette) or off on images."""

    def __init__(self, renderer, items, palette, checked):
        super().__init__('Toggle Color Range')
        self.renderer = renderer
        self.items = [item for item in items if item.is_image]
        self.old_states = [item.color_range for item in self.items]
        self.new_states = [
            ColorRangeState(palette, old.level if old else DEFAULT_LEVEL)
            if checked else None
            for old in self.old_states]

    def redo(self):
        for item, state in zip(self.items, self.new_states):
            self.renderer.apply(item, state)

    def undo(self):
        for item, state in zip(self.items, self.old_states):
            self.renderer.apply(item, state)


class SetColorRangeLevel(QtGui.QUndoCommand):
    """Change the Simplify level of Color Range images."""

    def __init__(self, renderer, items, old_levels, level):
        super().__init__('Change Color Range')
        self.renderer = renderer
        self.items = list(items)
        self.old_levels = list(old_levels)
        self.level = level

    def set_level(self, item, level):
        if item.color_range is not None:
            self.renderer.apply(
                item, dataclasses.replace(item.color_range, level=level))

    def redo(self):
        for item in self.items:
            self.set_level(item, self.level)

    def undo(self):
        for item, level in zip(self.items, self.old_levels):
            self.set_level(item, level)
```

- [ ] **Step 4: Add the controller operations to `beeref/palette/controller.py`**

Add imports:

```python
import dataclasses

from beeref.commands import SetColorRangeLevel, ToggleColorRange
```

Add a section after the `# Palettes` methods:

```python
    # Color Range

    def toggle_color_range(self, items, checked):
        palette = self.store.active or (
            self.store.palettes[0] if self.store.palettes else None)
        if checked and palette is None:
            return
        self.undo_stack.push(
            ToggleColorRange(self.color_range, items, palette, checked))

    def preview_color_range_level(self, items, level):
        """Fast low-resolution render while the slider is dragged."""
        for item in items:
            if item.color_range is not None:
                self.color_range.apply(
                    item, dataclasses.replace(item.color_range, level=level),
                    preview=True)

    def commit_color_range_level(self, items, old_levels, level):
        self.undo_stack.push(
            SetColorRangeLevel(self.color_range, items, old_levels, level))
```

If importing `beeref.commands` from the controller causes a circular import at startup, move
the import inside the two methods that use it and note it in the commit message.

- [ ] **Step 5: Add the action and menu entry**

In `beeref/actions/actions.py`, right after the `grayscale` `Action(...)`:

```python
    Action(
        id='color_range',
        text='Colo&r Range',
        shortcuts=['F'],
        checkable=True,
        callback='on_action_color_range',
    ),
```

(No `group`: the view manages its enabled state.)

In `beeref/actions/menu_structure.py`, `&Images` items become:

```python
            'change_opacity',
            'grayscale',
            'color_range',
            MENU_SEPARATOR,
            'show_color_gamut',
            'sample_color',
```

- [ ] **Step 6: Wire the view (`beeref/view.py`)**

Right after `self.build_menu_and_actions()` in `__init__`:

```python
        self.scene.palettes.changed.connect(self.update_color_range_controls)
        self.undo_stack.indexChanged.connect(
            lambda _: self.update_color_range_controls())
        self.update_color_range_controls()
```

At the end of `on_selection_changed` (before `self.viewport().repaint()`):

```python
        self.update_color_range_controls()
```

New methods (next to `on_action_grayscale`):

```python
    def on_action_color_range(self, checked):
        images = [item for item in self.scene.selectedItems(user_only=True)
                  if item.is_image]
        if images:
            self.palette_controller.toggle_color_range(images, checked)
        self.update_color_range_controls()

    def selected_images(self):
        return [item for item in self.scene.selectedItems(user_only=True)
                if getattr(item, 'is_image', False)]

    def update_color_range_controls(self):
        images = self.selected_images()
        action = actions.actions['color_range'].qaction
        action.setEnabled(bool(images) and bool(self.scene.palettes.palettes))
        # Checkable actions fire their callback on toggled, so syncing the
        # checkmark must not go through it.
        action.blockSignals(True)
        action.setChecked(bool(images) and images[0].color_range is not None)
        action.blockSignals(False)
```

- [ ] **Step 7: Run tests**

Run: `make test ARGS="tests/palette tests/test_view.py tests/test_commands.py tests/actions tests/config"`
Expected: all PASS except the two pre-existing failures listed in Global Constraints.

- [ ] **Step 8: Commit**

```bash
git add beeref/commands.py beeref/palette/controller.py beeref/actions/actions.py beeref/actions/menu_structure.py beeref/view.py tests/palette/test_color_range_actions.py
git commit -m "Images > Color Range action with undoable toggle and level commands

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Simplify slider in the palette panel or a floating bar

**Files:**
- Create: `beeref/widgets/color_range.py`
- Modify: `beeref/widgets/palette_panel.py` (`PalettePanel.__init__`; `PaletteSidebar`:
  signal, `set_collapsed`, `apply_visibility`, new `panel_shown`)
- Modify: `beeref/view.py` (`__init__`, `resizeEvent`, `update_color_range_controls`)
- Modify: `beeref/__main__.py` (connect the sidebar signal)
- Modify: `beeref/widgets/__init__.py` only if it lists submodules explicitly (it imports
  `color_gamut` etc.; add `color_range` to that import list)
- Test: `tests/widgets/test_color_range.py`

**Interfaces:**
- Consumes: `PaletteController.preview_color_range_level`, `commit_color_range_level`.
- Produces:
  - `ColorRangeControls(controller, parent=None)`: `set_items(items)`, `items`, `slider`,
    `palette_label`
  - `ColorRangeBar(controller, parent)`: `controls`, `reposition()`
  - `PalettePanel.color_range_controls`
  - `PaletteSidebar.visibility_changed` (signal), `PaletteSidebar.panel_shown() -> bool`
  - `BeeGraphicsView.color_range_bar`

- [ ] **Step 1: Write the failing tests**

`tests/widgets/test_color_range.py`:

```python
from beeref.items import BeePixmapItem
from beeref.palette.color_range import ColorRangeState
from beeref.palette.model import Palette, SamplePoint
from beeref.widgets.color_range import ColorRangeControls
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def board(view, level=30):
    controller = view.palette_controller
    controller.color_range.synchronous = True
    item = BeePixmapItem(stripes([RED, BLUE]))
    view.scene.addItem(item)
    palette = Palette('Lava', [SamplePoint(item, 0.25, 0.5)])
    view.scene.palettes.add(palette)
    controller.color_range.apply(item, ColorRangeState(palette, level))
    return item


def controls_for(view, item):
    controls = ColorRangeControls(view.palette_controller)
    controls.set_items([item])
    return controls


def test_set_items_shows_palette_and_level(view):
    item = board(view, level=42)
    controls = controls_for(view, item)
    assert controls.palette_label.text() == 'Lava'
    assert controls.slider.value() == 42


def test_drag_previews_then_commits_one_step(view):
    item = board(view)
    controls = controls_for(view, item)
    count = view.undo_stack.count()
    controls.slider.setSliderDown(True)
    controls.slider.setValue(60)
    assert item.color_range.level == 60
    assert view.undo_stack.count() == count
    controls.slider.setSliderDown(False)
    assert view.undo_stack.count() == count + 1
    view.undo_stack.undo()
    assert item.color_range.level == 30


def test_release_without_change_pushes_nothing(view):
    item = board(view)
    controls = controls_for(view, item)
    count = view.undo_stack.count()
    controls.slider.setSliderDown(True)
    controls.slider.setSliderDown(False)
    assert view.undo_stack.count() == count


def test_keyboard_step_commits(view):
    item = board(view)
    controls = controls_for(view, item)
    count = view.undo_stack.count()
    controls.slider.setValue(31)
    assert item.color_range.level == 31
    assert view.undo_stack.count() == count + 1


def open_sidebar(main_window):
    sidebar = main_window.palette_sidebar
    sidebar.set_board_open(True)
    if not sidebar.wanted():
        sidebar.toggle_visible()
    sidebar.set_collapsed(False)
    return sidebar


def test_controls_in_panel_when_visible(main_window):
    view = main_window.view
    item = board(view)
    sidebar = open_sidebar(main_window)
    item.setSelected(True)
    assert not sidebar.panel.color_range_controls.isHidden()
    assert view.color_range_bar.isHidden()


def test_controls_in_floating_bar_when_panel_collapsed(main_window):
    view = main_window.view
    item = board(view)
    sidebar = open_sidebar(main_window)
    item.setSelected(True)
    sidebar.set_collapsed(True)
    assert sidebar.panel.color_range_controls.isHidden()
    assert not view.color_range_bar.isHidden()


def test_controls_hidden_without_filtered_selection(main_window):
    view = main_window.view
    item = board(view)
    sidebar = open_sidebar(main_window)
    plain = BeePixmapItem(stripes([BLUE]))
    view.scene.addItem(plain)
    plain.setSelected(True)
    assert sidebar.panel.color_range_controls.isHidden()
    assert view.color_range_bar.isHidden()
    plain.setSelected(False)
    item.setSelected(True)
    view.palette_controller.toggle_color_range([item], False)
    assert sidebar.panel.color_range_controls.isHidden()
    assert view.color_range_bar.isHidden()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test ARGS="tests/widgets/test_color_range.py"`
Expected: FAIL — `ModuleNotFoundError: No module named 'beeref.widgets.color_range'`.

- [ ] **Step 3: Implement `beeref/widgets/color_range.py`**

GPL header block, then:

```python
"""Simplify slider for images shown through Color Range."""

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt


class ColorRangeControls(QtWidgets.QFrame):
    """Color Range title, bound palette name and Simplify slider."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.items = []
        self.start_levels = None

        title = QtWidgets.QLabel('Color Range')
        self.palette_label = QtWidgets.QLabel()
        self.slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider.setToolTip('Simplify')
        self.slider.sliderPressed.connect(self.on_pressed)
        self.slider.valueChanged.connect(self.on_value_changed)
        self.slider.sliderReleased.connect(self.on_released)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.palette_label)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self.slider)

    def set_items(self, items):
        self.items = list(items)
        if not self.items:
            return
        state = self.items[0].color_range
        self.palette_label.setText(state.palette.name)
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(state.level)
            self.slider.blockSignals(False)

    def levels(self):
        return [item.color_range.level for item in self.items]

    def on_pressed(self):
        self.start_levels = self.levels()

    def on_value_changed(self, value):
        if self.slider.isSliderDown():
            self.controller.preview_color_range_level(self.items, value)
        elif self.items:
            self.controller.commit_color_range_level(
                self.items, self.levels(), value)

    def on_released(self):
        start, self.start_levels = self.start_levels, None
        value = self.slider.value()
        if start is None or all(level == value for level in start):
            return
        self.controller.commit_color_range_level(self.items, start, value)


class ColorRangeBar(QtWidgets.QFrame):
    """Color Range controls floating at the top of the canvas view."""

    WIDTH = 260
    MARGIN = 8

    def __init__(self, controller, parent):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        self.setFixedWidth(self.WIDTH)
        self.controls = ColorRangeControls(controller, self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 6)
        layout.addWidget(self.controls)
        self.hide()

    def reposition(self):
        self.adjustSize()
        parent = self.parentWidget()
        self.move((parent.width() - self.width()) // 2, self.MARGIN)
        self.raise_()
```

- [ ] **Step 4: Panel and sidebar (`beeref/widgets/palette_panel.py`)**

Import: `from beeref.widgets.color_range import ColorRangeControls`.

In `PalettePanel.__init__`, after the `header` layout is built:

```python
        self.color_range_controls = ColorRangeControls(controller)
        self.color_range_controls.hide()
```

and make the layout order:

```python
        self.layout_.addLayout(header)
        self.layout_.addWidget(self.color_range_controls)
        self.layout_.addWidget(self.new_button)
```

In `PaletteSidebar`, add the class attribute and method:

```python
    visibility_changed = QtCore.pyqtSignal()

    def panel_shown(self):
        """Whether the expanded panel is on screen (logically)."""
        return (self.board_open and self.wanted()
                and not self.is_collapsed())
```

Emit `self.visibility_changed.emit()` as the last line of `set_collapsed` and of
`apply_visibility`. (`set_collapsed` runs in `__init__` before `board_open` exists; that is
fine because nothing is connected yet and `panel_shown` is not called there.)

- [ ] **Step 5: View and main window**

`beeref/view.py`: import `from beeref.widgets.color_range import ColorRangeBar`. In
`__init__`, right after `self.palette_overlay = ...`:

```python
        self.color_range_bar = ColorRangeBar(self.palette_controller, self)
```

In `resizeEvent`, append:

```python
        self.color_range_bar.reposition()
```

Replace `update_color_range_controls` with:

```python
    def update_color_range_controls(self):
        images = self.selected_images()
        action = actions.actions['color_range'].qaction
        action.setEnabled(bool(images) and bool(self.scene.palettes.palettes))
        # Checkable actions fire their callback on toggled, so syncing the
        # checkmark must not go through it.
        action.blockSignals(True)
        action.setChecked(bool(images) and images[0].color_range is not None)
        action.blockSignals(False)

        filtered = [item for item in images if item.color_range is not None]
        sidebar = self.palette_sidebar
        in_panel = sidebar is not None and sidebar.panel_shown()
        if sidebar is not None:
            sidebar.panel.color_range_controls.set_items(filtered)
            sidebar.panel.color_range_controls.setVisible(
                bool(filtered) and in_panel)
        self.color_range_bar.controls.set_items(filtered)
        self.color_range_bar.setVisible(bool(filtered) and not in_panel)
        if not self.color_range_bar.isHidden():
            self.color_range_bar.reposition()
```

`beeref/__main__.py`, right after `self.view.palette_sidebar = self.palette_sidebar`:

```python
        self.palette_sidebar.visibility_changed.connect(
            self.view.update_color_range_controls)
```

- [ ] **Step 6: Run tests**

Run: `make test ARGS="tests/widgets tests/palette tests/test_view.py tests/test_main.py"`
Expected: all PASS except the two pre-existing failures.

- [ ] **Step 7: Commit**

```bash
git add beeref/widgets/color_range.py beeref/widgets/palette_panel.py beeref/view.py beeref/__main__.py tests/widgets/test_color_range.py
git commit -m "Color Range: Simplify slider in the palette panel or a floating bar

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(Add `beeref/widgets/__init__.py` to `git add` if Step 3 required editing it.)

---

### Task 6: Docs, full suite and a manual check

**Files:**
- Modify: `README.rst` (fork feature list and shortcut table)

- [ ] **Step 1: Document the feature**

In `README.rst`, add after the "Read-only inspector with Copy hex." bullet:

```rst
- Color Range (``F``, Images > Color Range): shows the selected images as
  flat zones of the active palette's colors (nearest color in OKLab), like
  a filled paint-by-numbers page. The Simplify slider (palette panel, or a
  bar at the top of the board when the panel is hidden) merges small zones.
  View only: the image itself, sampling and exports are unchanged; Grayscale
  applies on top.
```

and a row in the "Shortcuts added by this fork" table, after the ``L`` row:

```rst
   * - ``F``
     - Color Range: show selected images in the palette's flat colors
```

- [ ] **Step 2: Run the full suite**

Run: `make test`
Expected: only the two pre-existing `tests/test_view.py` failures.

- [ ] **Step 3: Manual check (user)**

Ask the user to run `make run`, open a board, select a photo, press `F`, drag Simplify, toggle
`G`, collapse the panel (bar appears at the top), save, reopen. Do not claim the UI works until
they confirm.

- [ ] **Step 4: Commit**

```bash
git add README.rst
git commit -m "Docs: Color Range

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
