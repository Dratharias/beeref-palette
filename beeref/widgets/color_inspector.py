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
