# This file is part of BeeRef.
#
# BeeRef is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BeeRef is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BeeRef.  If not, see <https://www.gnu.org/licenses/>.

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
