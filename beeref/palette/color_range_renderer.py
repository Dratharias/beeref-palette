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
