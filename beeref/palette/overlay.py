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
