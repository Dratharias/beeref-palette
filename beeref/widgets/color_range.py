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
        if start is None:
            return
        if all(level == value for level in start):
            # Nothing to undo, but previews may be on screen
            self.controller.finish_color_range_preview(self.items)
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
