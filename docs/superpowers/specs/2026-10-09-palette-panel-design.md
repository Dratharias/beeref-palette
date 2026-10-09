# BeeRef Palette — palette panel design

Date: 2026-10-09. Status: approved in conversation, pending written-spec review.

## Goal

A fork of BeeRef (GPL-3, upstream dormant since 2024-06) that turns reference boards into a
source of color palettes for painting in Clip Studio Paint (CSP, running under Wine on Bazzite /
KDE Wayland). The user picks palettes from references — automatically, then refined by hand —
and exports them as Photoshop `.aco` swatches, which CSP imports through
**Color Set > Import color set** (`.cls` or `.aco`, per the CSP Ver.5 guide).

Success: open a board, click a reference, get a sensible palette, nudge a few sample points,
export, import in CSP — without leaving the BeeRef look and feel.

### Already in BeeRef (not rebuilt)

Per-image grayscale view, flip, a color-gamut view (`widgets/color_gamut.py`) and **Sample
Color** (`S`), which copies the hex of the pixel under the cursor to the clipboard.

### Out of scope (later, if ever)

Screen-wide color picking (needs the Wayland color-picker portal), `.cls` export, editing a
swatch's color by hand, Flatpak packaging, upstreaming.

## User-facing behavior

### Palette panel

A right-hand side panel, shown/hidden with a keyboard shortcut or **View > Palettes**, and
**collapsible to a thin strip** with a chevron (`«` expand / `»` collapse). Expanded/collapsed
state persists across sessions (app settings).

- **Header**: *Auto-extract on click* toggle, color count spin box (3–12, default 6),
  **+ New palette** button.
- **Palette list**: every palette of the board, each with an editable name and a row of swatches.
  Exactly one palette is **active** (highlighted); clicking a palette makes it active.
- **Per-palette menu**: Rename, Regenerate, Export .aco…, Delete.
- **Swatches**: hover → tooltip with hex, RGB, HSV. Click → highlight its point on the canvas.
  Drag → reorder. Right-click → remove. A trailing **+** swatch enters pick mode: the next click
  on an image adds a point there.

A board can have zero, one or many palettes; none is created until the user asks for one or
auto-extract fires.

### Swatch inspector

Below the palette list, a read-only inspector in the spirit of Gcolor3 shows the selected swatch:
a hue ring with a saturation/value triangle marking the color, a large preview, HSV and RGB
values, the hex code, and a **Copy hex** button. Nothing is editable there: a swatch's color only
changes by moving its sample point, so every color stays tied to a real pixel.

### Composing palettes

A palette's points may sit on different images: auto-extract fills it from one image, and the
**+** swatch adds points from any image — e.g. an 8-color "Magma" palette pulled from a lava
photo, or a mood palette composed by hand across several references.

### Sample points on the canvas

- Only the active palette's points are drawn: a small disc filled with the sampled color, with a
  light and a dark ring so it reads on any background. Constant on-screen size at any zoom.
- Dragging a point moves the sample; its color updates live.
- Right-click removes the point (on the canvas or on its swatch).
- Points are drawn by the view as an overlay, not as scene items, so they never end up in
  scene exports (PNG/SVG), selections, or bounding boxes.

### Auto-extract

- When the toggle is on, a **plain click** (press + release without drag) on an image
  **replaces** the active palette's points with an extraction of that image (creating a palette
  if none exists). Dragging still moves images as usual.
- **Regenerate** re-runs extraction on the palette's source image (the image of its last
  auto-extract). Disabled when the palette has no source image.

### Undo

Every palette operation goes through BeeRef's undo stack (`Ctrl+Z`).

## Data model

- **Palette**: id, name, position in the list, source image (nullable), ordered points.
- **SamplePoint**: palette, image item, position **relative to the full image** (x, y in 0–1),
  order in the palette, cached color.
- The color is always re-read from the image at the point's position (3×3 average); the cached
  color is only used for export and for display when the image is missing.
- Board-level: active palette id and the auto-extract toggle. App-level setting: color count.

## Persistence (`.bee`, SQLite)

- `USER_VERSION` 2 → 3, with a migration adding:
  - `palettes (id, name, position, source_item_id → items.id ON DELETE SET NULL)`
  - `palette_points (id, palette_id → palettes.id ON DELETE CASCADE,
    item_id → items.id, x REAL, y REAL, position INT, color TEXT)`
  - On save, the palette tables are rewritten from scratch after the items; on load, points
    whose image no longer exists are dropped.
  - board settings (active palette, auto-extract) stored in a `palette_meta` key/value table.
- Palettes are written after items, so points can reference the items' `save_id`s.
- Compatibility: upstream BeeRef opens version-3 files (it only migrates when the file version
  is lower) and in-place saves leave the new tables intact; **Save As** from upstream drops
  palettes. Documented in the README.

### Edge cases

- Image deleted → its points are hidden and not saved (they come back on undo).
- Image cropped → points outside the crop are drawn greyed out and come back if uncropped.
- Image flipped → the point follows the pixel, not the screen position.
- Image with fewer distinct colors than requested, or tiny image → fewer points, no error.
- Export failure (permissions, disk) → BeeRef's usual error dialog.

## Extraction algorithm

`extract(image: QImage, n: int) -> list[(x, y, color)]`, pure function:

1. Downscale to ~64 px on the long side; skip pixels with alpha < 128.
2. Convert sRGB → CIE Lab.
3. k-means over-segmentation: k = min(3·n, distinct colors), deterministic k-means++ seeding
   (fixed seed), at most 20 iterations — the same image always yields the same palette.
4. **Distinct colors**: walk the clusters from largest to smallest and keep a cluster only if
   its centroid is at least `MIN_DELTA_E = 15` (CIE76 ΔE) away from every cluster already kept;
   stop at n. Near-duplicate shades are dropped, and small but distinct accents survive thanks
   to the over-segmentation. Images with few distinct colors yield fewer than n points.
5. For each kept cluster, pick the **real pixel** closest to the centroid (so every color and
   point exists in the image); map it back to relative full-image coordinates.

NumPy does the clustering (pure Python would take about a second per extraction).

## `.aco` export

`write_aco(path, colors)`: version-1 block followed by a version-2 block (names), RGB color
space, each color named `#RRGGBB`. Default filename `<board> - <palette>.aco`.

## Architecture

New modules, each with one job:

| Module | Responsibility |
|---|---|
| `beeref/palette/model.py` | `Palette`, `SamplePoint`; sampling a color from an image. No UI. |
| `beeref/palette/extract.py` | `extract()` — pure function. |
| `beeref/palette/aco.py` | `write_aco()` — pure function. |
| `beeref/palette/commands.py` | Undoable commands: add/move/remove/reorder point, extract, create/rename/delete palette. |
| `beeref/palette/overlay.py` | Draws the active palette's points over the view; hit-testing. |
| `beeref/palette/controller.py` | User-level operations (new, extract, regenerate, pick, export) wired to the undo stack. |
| `beeref/widgets/palette_panel.py` | Side panel, swatches, collapse chevron. |
| `beeref/widgets/color_inspector.py` | Read-only hue ring/triangle, values, Copy hex. |

Minimal changes to existing code: `scene.py` / `view.py` (click-to-extract and pick mode),
`fileio/schema.py` + `fileio/sql.py` (tables, migration, read/write), `actions/actions.py` +
`actions/menu_structure.py` (commands, shortcuts), `config/settings.py` (color count, panel
state).

## Testing

pytest + pytest-qt, like the existing suite:

- `extract`: synthetic images with 2, 3 and 6 flat colors; determinism; transparency ignored;
  fewer distinct colors than `n`; near-duplicate shades are never both returned.
- `write_aco`: byte-level check and round trip through a small test-only reader.
- Persistence: save → reload keeps palettes and points; a version-2 file migrates; deleting an
  image cascades its points.
- Commands: undo/redo for each.
- Panel: smoke test (create palette, active switch, collapse).
- Manual: import an exported `.aco` in CSP under Wine.

## Project and distribution

- **Private, unpublished work.** Private GitHub repo `Dratharias/beeref-palette`, created as a
  plain repo, not a GitHub fork, so it does not appear on upstream's fork list (forks of public
  repos cannot be private anyway). Local clone at `~/Projects/github/beeref-palette`; upstream
  kept as remote `upstream` for fetching only — its push URL is set to `DISABLED`. No pull
  requests or issues upstream.
- GPL-3 kept, original headers and copyright preserved; `CHANGELOG` notes the fork. The GPL
  only requires sharing source with people the program is distributed to, so private personal
  use creates no obligation to publish.
- Name: **BeeRef Palette**, command `beeref-palette`.
- Run with `uv` on a uv-managed Python 3.12 (system Python is 3.14; BeeRef requires < 3.13).
  `Makefile`: `run`, `test`, `install` (installs the uv tool + a `.desktop` launcher that opens
  `.bee` files). The Flathub BeeRef may stay installed alongside.
