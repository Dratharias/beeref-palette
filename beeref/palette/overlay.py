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

    def region_polygon(self, view):
        """Viewport polygon of the active palette's region, or None."""
        palette = self.store.active
        if palette is None or not palette.source_region:
            return None
        item = palette.source_item
        if item is None or item.scene() is None:
            return None
        size = item.pixmap().size()
        return QtGui.QPolygonF([
            QtCore.QPointF(view.mapFromScene(item.mapToScene(QtCore.QPointF(
                x * size.width(), y * size.height()))))
            for x, y in palette.source_region])

    @staticmethod
    def _contrast_pens(dashed):
        dark = QtGui.QPen(QtGui.QColor(0, 0, 0, 200), 3)
        light = QtGui.QPen(QtGui.QColor(255, 255, 255, 230), 1.5)
        if dashed:
            light.setStyle(Qt.PenStyle.DashLine)
        return dark, light

    def paint_region(self, painter, view):
        polygon = self.region_polygon(view)
        if polygon is None:
            return
        for pen in self._contrast_pens(dashed=True):
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(polygon)

    def paint_lasso(self, painter, view):
        lasso = getattr(view, 'lasso', None)
        if lasso is None or not lasso.is_available or not lasso.vertices:
            return
        points = lasso.view_points(view)
        if lasso.hover is not None:
            points.append(QtCore.QPointF(view.mapFromScene(lasso.hover)))
        for pen in self._contrast_pens(dashed=False):
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolyline(QtGui.QPolygonF(points))
        # The first vertex closes the lasso when clicked
        painter.setBrush(QtGui.QColor(255, 255, 255, 230))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 200), 1.5))
        painter.drawEllipse(points[0], 4, 4)

    def paint(self, painter, view):
        painter.save()
        painter.resetTransform()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.paint_region(painter, view)
        self.paint_points(painter, view)
        self.paint_lasso(painter, view)
        painter.restore()

    def paint_points(self, painter, view):
        for point in self.visible_points():
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
