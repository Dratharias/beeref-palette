# BeeRef Palette — Color Range design

Date: 2026-10-13. Status: approved in conversation, pending written-spec review.

## Goal

Read a reference through a palette: show an image as flat zones painted only with the colors of
one palette, like a filled-in paint-by-numbers page. Gradients and noise disappear; what remains
is how the palette carves up the image. A **Simplify** slider goes from a raw per-pixel
quantization to a few large flat areas.

It is a pure viewing tool: the source image is never modified, nothing is exported.

Success: select a reference, toggle Color Range, drag Simplify, and see clean flat zones in the
palette's colors update smoothly — then toggle it off and get the untouched image back.

### Out of scope (later, if ever)

Zone outlines, a numbered blank template, baking the result into a new image (copy/paste or
duplicate), a membership "heatmap", lightness/chroma weighting of the color distance, a
lightness-band ("value study") variant.

## User-facing behavior

### Activation

A checkable action **Images → Color Range** (shortcut `F`, currently free), in the same group as
**Grayscale**: it applies to the selected image items, is undoable, and is disabled when there
is no selection or the board has no palette. Non-image items are ignored.

Turning it on binds each selected image to the **palette that is active at that moment**. The
binding is per image and does not follow later changes of the active palette, so several images
can be read through different palettes, and one image's palette can be applied to another.

### What is shown

Every opaque pixel is assigned the palette color nearest to it in **OKLab** (Euclidean
distance). Then a majority filter removes small zones: each pixel takes the color that is most
frequent in a square neighborhood whose radius grows with the slider.

- **Simplify 0**: raw quantization, no filtering.
- **Simplify 100**: neighborhood radius ≈ 3 % of the image's longer side; only large zones
  survive.

Transparent pixels keep their alpha and do not vote. The result is fully opaque palette colors
wherever the source was opaque.

### The Simplify control

A `ColorRangeControls` widget: a horizontal slider (0–100, default 30) and the name of the bound
palette. It is visible only while at least one selected image has Color Range on.

- **Palette panel visible**: shown as a "Color Range" section right under the panel header.
- **Palette panel hidden or collapsed**: shown in a small floating bar centered at the top of
  the canvas view.

With several filtered images selected, the slider shows the first one's value and sets all of
them. One drag (press → release) is one undo step.

### Combinations

- **Grayscale on top**: the pipeline is original → Color Range → Grayscale; both can be on.
- **Crop**: applies to the displayed result as usual.
- **Sampling**: palette sample points, auto-extract, the lasso and **Sample Color** (`S`) all
  keep reading the original pixels — the filter never feeds back into palette colors.

### Reacting to palette changes

- When the bound palette's colors change (point added, removed, moved, resampled, regenerated),
  its images recompute. Changes that leave the color list identical (rename, reorder of
  palettes) do not trigger a recompute.
- When the bound palette is deleted, Color Range turns off on its images.
- A palette with no colors leaves the image shown as-is while the filter stays on; it resumes as
  soon as the palette gets a color.
- A palette with one color makes the image a single flat area of that color.

### Persistence

Saved in the item's extra save data, no SQL schema change:

```json
"color_range": {"palette": <palette position>, "level": <0-100>}
```

Absent key (older files) means off. On load, the palette is resolved by position after palettes
are restored; an unresolvable position means off.

## Architecture

### `beeref/palette/color_range.py` — pure processing (numpy, no Qt widgets)

- `to_oklab(rgb: uint8[h,w,3]) -> float32[h,w,3]` — sRGB → linear → OKLab.
- `quantize(lab, palette_lab: float32[k,3]) -> uint8[h,w]` — index of the nearest palette color.
- `simplify(labels, k, radius, mask) -> uint8[h,w]` — majority filter. For each label, count its
  pixels in the `(2r+1)²` box with an integral image (cumulative sums), keeping a running best
  count and best label so only one count array lives at a time. Masked-out (transparent) pixels
  do not vote. Two passes. `radius == 0` returns the input.
- `radius_for(level, long_side) -> int` — `round(level / 100 * 0.03 * long_side)`.
- `render(image: QImage, colors: list[QColor], level, max_side) -> QImage` — orchestration:
  downscale to `max_side` on the longer side if larger, convert, quantize, simplify, paint
  palette colors, restore source alpha, scale back up to the source size without smoothing.

The OKLab array of an image's working-resolution copy is cached per item, keyed by the pixmap's
`cacheKey()` and the working size, so moving the slider only re-runs quantize + simplify.

### Working resolution

Flat zones carry no fine detail, so processing is capped: **2048 px** on the longer side for the
final result, **512 px** while the slider is being dragged. The radius is derived from the
working size, so preview and final result match. On very large images, strong zoom shows slightly
stepped zone edges; accepted.

### Background computation

A `QThread` worker in the style of `GamutPainterThread` computes `render()`. Each request carries
a generation number; results older than the latest request for that item are dropped. Until a
result arrives, the item keeps showing its previous rendering. An exception in the worker is
logged and the previous rendering stays.

### `BeePixmapItem` changes (`beeref/items.py`)

- New state `color_range` (`None` or bound palette + level) and the cached result pixmap.
- A display pipeline replaces the direct `self._grayscale_pixmap if self.grayscale else
  self.pixmap()` choice: original → Color Range result (if on and ready) → grayscale (if on).
  The grayscale conversion starts from the Color Range output instead of `self.pixmap()`.
- `pixmap()` stays the original; `sample_color_at` and `item_image` are unaffected.
- `get_extra_save_data` / `create_from_data` carry the `color_range` entry.

### Undo commands (`beeref/commands.py`)

- `ToggleColorRange(items, checked, palette)` — stores each item's previous state for undo.
- `SetColorRangeLevel(items, old_levels, new_level)` — pushed once on slider release.

### UI (`beeref/widgets/color_range.py`)

`ColorRangeControls` (slider + palette name). Two instances: one inserted in `PalettePanel`
under its header, one in a floating bar parented to the view and kept centered at its top. A
small controller listens to selection changes and the sidebar's visibility/collapse state, and
shows exactly one of them (or neither). The slider shows live previews at 512 px while dragging
and requests the 2048 px result on release.

### Palette reactivity

The controller listens to `PaletteStore` change notifications. For each filtered item it
compares the bound palette's current color list with the one used for its last render and
recomputes only on a difference; items whose palette left the store turn Color Range off
(outside the undo stack, like other consequences of deleting a palette).

## Testing (pytest, TDD)

`tests/palette/test_color_range.py` — processing:

- `to_oklab` matches reference values (white, black, pure sRGB primaries).
- `quantize` picks the nearest palette color, including near-ties resolved consistently.
- `simplify` with radius 0 is the identity; a small island inside a large zone is absorbed; a
  zone larger than the neighborhood survives; transparent pixels do not vote.
- `render` preserves alpha and output size; a one-color palette gives a single flat color;
  `radius_for` scales with the longer side so a 512 px and a 2048 px render agree on large zones.

Item, commands and persistence:

- Toggle and level change with undo/redo restore the previous state.
- Save/load round-trip resolves the palette by position; a missing key or position means off.
- Deleting the bound palette turns the filter off.
- Grayscale on top of Color Range yields gray output; `pixmap()` stays the original and palette
  sampling reads original pixels.

UI:

- Controls appear in the palette panel when it is visible, in the floating bar otherwise, and
  are hidden when no selected image has Color Range on.
- One slider drag pushes one undo step.
