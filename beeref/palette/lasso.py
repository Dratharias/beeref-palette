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

"""Polygonal lasso that limits a palette extraction to part of an image."""

from PyQt6 import QtCore


class Lasso:
    CLOSE_RADIUS = 8     # viewport px around the first vertex that close
    FREEHAND_STEP = 4    # viewport px between vertices while dragging

    def __init__(self):
        self.item = None
        self.vertices = []   # relative (x, y) on self.item
        self.hover = None    # scene position of the cursor
        self.dragging = False
        self.last_drag_pos = None

    @property
    def is_available(self):
        return self.item is not None and self.item.scene() is not None

    def scene_pos(self, vertex):
        size = self.item.pixmap().size()
        return self.item.mapToScene(QtCore.QPointF(
            vertex[0] * size.width(), vertex[1] * size.height()))

    def view_points(self, view):
        return [QtCore.QPointF(view.mapFromScene(self.scene_pos(v)))
                for v in self.vertices]

    def near_first(self, view, pos):
        if len(self.vertices) < 3:
            return False
        delta = self.view_points(view)[0] - QtCore.QPointF(pos)
        return delta.x() ** 2 + delta.y() ** 2 <= self.CLOSE_RADIUS ** 2

    def add(self, vertex):
        if not self.vertices or self.vertices[-1] != vertex:
            self.vertices.append(vertex)

    def pop(self):
        if self.vertices:
            self.vertices.pop()

    def polygon(self):
        """The closed region, or None if it has fewer than 3 vertices."""
        unique = list(dict.fromkeys(self.vertices))
        return list(self.vertices) if len(unique) >= 3 else None
