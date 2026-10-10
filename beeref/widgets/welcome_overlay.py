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

from datetime import datetime
import logging
import os.path

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref import constants
from beeref.assets import BeeAssets
from beeref.config import BeeSettings
from beeref.fileio.preview import board_preview, relative_date
from beeref.main_controls import MainControlsMixin


logger = logging.getLogger(__name__)

MAX_TILES = 6
COLUMNS = 3


def _highlight():
    return QtGui.QColor(*constants.COLORS['Active:Highlight'])


class BoardTile(QtWidgets.QWidget):
    """A recent board: preview mosaic, first palette, name and date."""

    THUMB = QtCore.QSize(184, 115)
    STRIP = 10

    def __init__(self, path, cache_dir, view, parent=None):
        super().__init__(parent)
        self.path = path
        self.view = view
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.preview, self.colors = board_preview(path, cache_dir)
        try:
            when = datetime.fromtimestamp(os.path.getmtime(path))
            self.date = relative_date(when)
        except OSError:
            self.date = ''
        self.hovered = False
        self.setToolTip(path)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        line = self.fontMetrics().height()
        self.setFixedSize(self.THUMB.width() + 8,
                          self.THUMB.height() + self.STRIP + 2 * line + 18)

    def enterEvent(self, event):
        self.hovered = True
        self.update()

    def leaveEvent(self, event):
        self.hovered = False
        self.update()

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self.view.open_from_file(self.path)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        thumb = QtCore.QRectF(4, 4, self.THUMB.width(), self.THUMB.height())

        # Preview, clipped to rounded top corners
        path = QtGui.QPainterPath()
        path.addRoundedRect(thumb.adjusted(0, 0, 0, self.STRIP), 6, 6)
        painter.save()
        painter.setClipPath(path)
        painter.fillRect(thumb, QtGui.QColor(30, 30, 30))
        if not self.preview.isNull():
            painter.drawImage(thumb, self.preview)
        else:
            painter.setPen(QtGui.QColor(120, 120, 120))
            painter.drawText(thumb, Qt.AlignmentFlag.AlignCenter,
                             'No preview')
        # First palette as a strip under the preview
        strip = QtCore.QRectF(thumb.left(), thumb.bottom(),
                              thumb.width(), self.STRIP)
        if self.colors:
            width = strip.width() / len(self.colors)
            for i, color in enumerate(self.colors):
                painter.fillRect(QtCore.QRectF(
                    strip.left() + i * width, strip.top(),
                    width + 0.5, strip.height()), color)
        else:
            painter.fillRect(strip, QtGui.QColor(45, 45, 45))
        painter.restore()

        border = _highlight() if self.hovered else QtGui.QColor(0, 0, 0, 90)
        painter.setPen(QtGui.QPen(border, 2 if self.hovered else 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        line = self.fontMetrics().height()
        text = QtCore.QRectF(thumb.left(), strip.bottom() + 6,
                             thumb.width(), line)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self.palette().color(QtGui.QPalette.ColorRole.Text))
        painter.drawText(text, Qt.AlignmentFlag.AlignLeft,
                         self.fontMetrics().elidedText(
                             self.name, Qt.TextElideMode.ElideRight,
                             int(text.width())))
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(150, 150, 150))
        painter.drawText(text.translated(0, line), Qt.AlignmentFlag.AlignLeft,
                         self.date)


class WelcomeOverlay(MainControlsMixin, QtWidgets.QWidget):
    """Shown while the board is empty: open or start a board."""

    HINT = ('Drop or paste images to start  ·  Right-click or M for the '
            'menu  ·  P palettes  ·  L lasso')

    def __init__(self, parent):
        super().__init__(parent)
        self.view = parent
        self.control_target = parent
        self.setAutoFillBackground(True)
        self.init_main_controls(main_window=parent.parent)
        self.cache_dir = os.path.join(
            os.path.dirname(BeeSettings().fileName()), 'previews')
        self.tiles = []

        self.card = QtWidgets.QWidget(self)
        card = QtWidgets.QVBoxLayout(self.card)
        card.setSpacing(18)

        # Logo and name
        title_row = QtWidgets.QHBoxLayout()
        title_row.addStretch(1)
        logo = QtWidgets.QLabel(self.card)
        logo.setPixmap(BeeAssets().logo.pixmap(48, 48))
        title_row.addWidget(logo)
        title = QtWidgets.QLabel(constants.APPNAME, self.card)
        font = title.font()
        font.setPointSizeF(font.pointSizeF() * 1.8)
        font.setBold(True)
        title.setFont(font)
        title_row.addWidget(title)
        title_row.addStretch(1)
        card.addLayout(title_row)

        # Actions
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        self.open_button = QtWidgets.QPushButton('Open board…', self.card)
        self.open_button.clicked.connect(lambda: self.view.on_action_open())
        self.add_images_button = QtWidgets.QPushButton(
            'Add images…', self.card)
        self.add_images_button.clicked.connect(
            lambda: self.view.on_action_insert_images())
        for button in (self.open_button, self.add_images_button):
            button.setMinimumWidth(140)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            buttons.addWidget(button)
        buttons.addStretch(1)
        card.addLayout(buttons)

        # Recent boards
        self.recent_widget = QtWidgets.QWidget(self.card)
        recent = QtWidgets.QVBoxLayout(self.recent_widget)
        recent.setContentsMargins(0, 12, 0, 0)
        heading = QtWidgets.QLabel('Recent boards', self.recent_widget)
        font = heading.font()
        font.setBold(True)
        heading.setFont(font)
        recent.addWidget(heading)
        self.tiles_layout = QtWidgets.QGridLayout()
        self.tiles_layout.setHorizontalSpacing(14)
        self.tiles_layout.setVerticalSpacing(10)
        recent.addLayout(self.tiles_layout)
        self.recent_widget.hide()
        card.addWidget(self.recent_widget, 0, Qt.AlignmentFlag.AlignHCenter)

        hint = QtWidgets.QLabel(self.HINT, self.card)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet('color: rgb(150, 150, 150);')
        card.addWidget(hint)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(self.card, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    def show(self):
        self.update_tiles(BeeSettings().get_recent_files(existing_only=True))
        super().show()

    def update_tiles(self, files):
        for tile in self.tiles:
            tile.setParent(None)
            tile.deleteLater()
        self.tiles = [BoardTile(path, self.cache_dir, self.view, self.card)
                      for path in files[:MAX_TILES]]
        for i, tile in enumerate(self.tiles):
            self.tiles_layout.addWidget(tile, i // COLUMNS, i % COLUMNS)
        self.recent_widget.setVisible(bool(self.tiles))

    def disable_mouse_events(self):
        self.card.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def enable_mouse_events(self):
        self.card.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, on=False)

    def mousePressEvent(self, event):
        if self.mousePressEventMainControls(event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.mouseMoveEventMainControls(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.mouseReleaseEventMainControls(event):
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self.keyPressEventMainControls(event):
            return
        super().keyPressEvent(event)
