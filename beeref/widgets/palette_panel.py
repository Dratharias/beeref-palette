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

"""Collapsible side panel listing the board's palettes."""

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref import constants
from beeref.widgets.color_inspector import ColorInspector
from beeref.widgets.color_range import ColorRangeControls


def _highlight():
    return QtGui.QColor(*constants.COLORS['Active:Highlight'])


class SwatchStrip(QtWidgets.QWidget):
    """Swatches of one palette plus a trailing "+" cell; wraps rows."""

    SIZE = 24
    GAP = 4

    def __init__(self, controller, palette, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.palette = palette
        self._drag_from = None
        self.setMouseTracking(True)
        policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def _columns(self, width=None):
        width = self.width() if width is None else width
        return max(1, (width + self.GAP) // (self.SIZE + self.GAP))

    def cell_count(self):
        return len(self.palette.points) + 1

    def cell_rect(self, index):
        cols = self._columns()
        step = self.SIZE + self.GAP
        return QtCore.QRect((index % cols) * step, (index // cols) * step,
                            self.SIZE, self.SIZE)

    def heightForWidth(self, width):
        rows = -(-self.cell_count() // self._columns(width))
        return rows * (self.SIZE + self.GAP)

    def sizeHint(self):
        return QtCore.QSize(240, self.heightForWidth(240))

    def index_at(self, pos):
        for i in range(self.cell_count()):
            if self.cell_rect(i).contains(pos):
                return i
        return None

    def is_picking(self):
        """Whether the view waits for a click to add a point here."""
        view = self.controller.view
        return (view.active_mode == view.PICK_POINT_MODE
                and self.controller.store.active is self.palette)

    def tooltip_at(self, pos):
        index = self.index_at(pos)
        if index is None:
            return None
        if index == len(self.palette.points):
            return ('Add a color point: click here, then click on an image\n'
                    '(Esc cancels)')
        c = self.palette.points[index].color
        return (f'{c.name().upper()}\n'
                f'RGB {c.red()}, {c.green()}, {c.blue()}\n'
                f'HSV {max(c.hsvHue(), 0)}°, '
                f'{round(c.hsvSaturationF() * 100)}%, '
                f'{round(c.valueF() * 100)}%')

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        store = self.controller.store
        for i, point in enumerate(self.palette.points):
            rect = QtCore.QRectF(self.cell_rect(i)).adjusted(1, 1, -1, -1)
            available = point.is_available and point.in_crop()
            painter.setBrush(point.color if available
                             else QtGui.QBrush(point.color,
                                               Qt.BrushStyle.Dense4Pattern))
            selected = point is store.selected_point
            painter.setPen(QtGui.QPen(_highlight() if selected
                                      else QtGui.QColor(0, 0, 0, 120),
                                      2.5 if selected else 1))
            painter.drawRoundedRect(rect, 4, 4)
        plus = QtCore.QRectF(self.cell_rect(len(self.palette.points)))
        plus = plus.adjusted(1, 1, -1, -1)
        if self.is_picking():
            fill = _highlight()
            fill.setAlpha(90)
            painter.setBrush(fill)
            painter.setPen(QtGui.QPen(_highlight(), 2))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor(160, 160, 160), 1,
                                      Qt.PenStyle.DashLine))
        painter.drawRoundedRect(plus, 4, 4)
        painter.drawText(plus, Qt.AlignmentFlag.AlignCenter, '+')

    def event(self, event):
        if event.type() == QtCore.QEvent.Type.ToolTip:
            text = self.tooltip_at(event.pos())
            if text:
                QtWidgets.QToolTip.showText(event.globalPos(), text, self)
            else:
                QtWidgets.QToolTip.hideText()
            return True
        return super().event(event)

    def mousePressEvent(self, event):
        index = self.index_at(event.position().toPoint())
        if index is None:
            return
        self.controller.set_active(self.palette)
        if index == len(self.palette.points):
            self.controller.view.enter_pick_point_mode()
            return
        point = self.palette.points[index]
        if event.button() == Qt.MouseButton.RightButton:
            self.controller.remove_point(point)
            return
        self.controller.store.select_point(point)
        self._drag_from = index

    def mouseMoveEvent(self, event):
        if self.index_at(event.position().toPoint()) == len(
                self.palette.points):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_from is None:
            return
        target = self.index_at(event.position().toPoint())
        point = self.palette.points[self._drag_from]
        self._drag_from = None
        if target is not None and target < len(self.palette.points):
            self.controller.reorder_point(self.palette, point, target)


class PaletteRow(QtWidgets.QFrame):

    def __init__(self, controller, palette, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.palette = palette
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)

        self.name_edit = QtWidgets.QLineEdit(palette.name)
        self.name_edit.editingFinished.connect(self.on_name_edited)
        self.menu_button = QtWidgets.QToolButton()
        # Buttons never keep focus: Space must reach the canvas to pan.
        self.menu_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.menu_button.setText('⋯')
        self.menu_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QtWidgets.QMenu(self.menu_button)
        menu.addAction('Rename', self.start_rename)
        self.regenerate_action = menu.addAction(
            'Regenerate', lambda: controller.regenerate(self.palette))
        self.clear_region_action = menu.addAction(
            'Clear region', lambda: controller.clear_region(self.palette))
        menu.addAction('Export .aco…', self.export)
        menu.addSeparator()
        self.merge_menu = menu.addMenu('Merge with')
        self.export_merged_menu = menu.addMenu('Export merged .aco')
        menu.addSeparator()
        menu.addAction('Delete', lambda: controller.delete(self.palette))
        menu.aboutToShow.connect(self.on_menu_about_to_show)
        self.menu_button.setMenu(menu)
        self.strip = SwatchStrip(controller, palette)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(self.name_edit, 1)
        header.addWidget(self.menu_button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(header)
        layout.addWidget(self.strip)
        self.refresh()

    def on_menu_about_to_show(self):
        self.regenerate_action.setEnabled(
            self.controller.can_regenerate(self.palette))
        self.clear_region_action.setEnabled(
            self.controller.can_clear_region(self.palette))
        self.fill_merge_menu(self.merge_menu, self.controller.merge)
        self.fill_merge_menu(self.export_merged_menu, self.export_merged)

    def fill_merge_menu(self, menu, callback):
        """One entry per other palette, plus All palettes if 3 or more."""
        menu.clear()
        palettes = self.controller.store.palettes
        others = [p for p in palettes if p is not self.palette]
        menu.setEnabled(bool(others))
        for other in others:
            menu.addAction(other.name,
                           lambda o=other: callback([self.palette, o]))
        if len(others) > 1:
            menu.addSeparator()
            menu.addAction('All palettes', lambda: callback(list(palettes)))

    def start_rename(self):
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def on_name_edited(self):
        self.name_edit.setModified(False)
        self.controller.rename(self.palette, self.name_edit.text())
        if not self.name_edit.text().strip():
            self.name_edit.setText(self.palette.name)

    def export(self):
        self.export_dialog(
            self.palette,
            lambda path: self.controller.export(self.palette, path))

    def export_merged(self, palettes):
        self.export_dialog(
            palettes,
            lambda path: self.controller.export_merged(palettes, path))

    def export_dialog(self, palettes, write):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Export palette',
            self.controller.default_export_path(palettes),
            'Photoshop swatches (*.aco)')
        if not path:
            return
        if not path.lower().endswith('.aco'):
            path += '.aco'
        try:
            write(path)
        except OSError as e:
            QtWidgets.QMessageBox.warning(
                self, 'Problem exporting palette',
                f'<p>Could not write {path}</p><p>{e}</p>')

    def mousePressEvent(self, event):
        self.controller.set_active(self.palette)
        super().mousePressEvent(event)

    def refresh(self):
        editing = self.name_edit.hasFocus() or self.name_edit.isModified()
        if not editing:
            self.name_edit.setText(self.palette.name)
        active = self.palette is self.controller.store.active
        color = _highlight().name() if active else 'transparent'
        self.setStyleSheet(
            f'PaletteRow {{ border: 2px solid {color}; border-radius: 6px; }}')
        self.strip.updateGeometry()
        self.strip.update()


class PalettePanel(QtWidgets.QWidget):

    WIDTH = 280

    def __init__(self, controller, settings, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings = settings
        self.rows = []
        self.setFixedWidth(self.WIDTH)

        self.auto_checkbox = QtWidgets.QCheckBox('Auto-extract on click')
        self.auto_checkbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.auto_checkbox.toggled.connect(controller.set_auto_extract)
        self.count_spinbox = QtWidgets.QSpinBox()
        self.count_spinbox.setRange(3, 12)
        self.count_spinbox.setValue(controller.color_count())
        self.count_spinbox.setToolTip('Colors per extraction')
        self.count_spinbox.valueChanged.connect(
            lambda v: settings.setValue('Palette/color_count', v))
        self.new_button = QtWidgets.QPushButton('+ New palette')
        self.new_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.new_button.clicked.connect(controller.new_palette)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(self.auto_checkbox, 1)
        header.addWidget(self.count_spinbox)

        self.color_range_controls = ColorRangeControls(controller)
        self.color_range_controls.hide()

        self.list_widget = QtWidgets.QWidget()
        self.list_layout = QtWidgets.QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.addStretch(1)
        scroll = QtWidgets.QScrollArea()
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(self.list_widget)

        self.layout_ = QtWidgets.QVBoxLayout(self)
        self.layout_.addLayout(header)
        self.layout_.addWidget(self.color_range_controls)
        self.layout_.addWidget(self.new_button)
        self.layout_.addWidget(scroll, 1)

        self.inspector = ColorInspector()
        self.layout_.addWidget(self.inspector)

        controller.store.changed.connect(self.on_store_changed)
        self.on_store_changed()

    def on_store_changed(self):
        store = self.controller.store
        if [row.palette for row in self.rows] != store.palettes:
            for row in self.rows:
                row.setParent(None)
                row.deleteLater()
            self.rows = [PaletteRow(self.controller, p)
                         for p in store.palettes]
            for i, row in enumerate(self.rows):
                self.list_layout.insertWidget(i, row)
        for row in self.rows:
            row.refresh()
        if self.auto_checkbox.isChecked() != store.auto_extract:
            self.auto_checkbox.blockSignals(True)
            self.auto_checkbox.setChecked(store.auto_extract)
            self.auto_checkbox.blockSignals(False)
        point = store.selected_point
        self.inspector.set_color(point.color if point is not None else None)


class PaletteSidebar(QtWidgets.QWidget):
    """The palette panel plus a thin chevron strip that collapses it."""

    visibility_changed = QtCore.pyqtSignal()

    def refresh_swatches(self):
        for strip in self.findChildren(SwatchStrip):
            strip.update()

    def __init__(self, controller, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.chevron = QtWidgets.QToolButton()
        self.chevron.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chevron.setFixedWidth(14)
        self.chevron.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed,
                                   QtWidgets.QSizePolicy.Policy.Expanding)
        self.chevron.setAutoRaise(True)
        self.chevron.clicked.connect(
            lambda: self.set_collapsed(not self.is_collapsed()))
        self.panel = PalettePanel(controller, settings)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.chevron)
        layout.addWidget(self.panel)
        self.set_collapsed(
            settings.value('PalettePanel/collapsed', False, type=bool))
        # Hidden on the welcome screen; on a board, shown if the user left
        # it open last time (off by default).
        self.board_open = False
        self.apply_visibility()

    def is_collapsed(self):
        return self.panel.isHidden()

    def set_collapsed(self, collapsed):
        self.panel.setHidden(collapsed)
        self.chevron.setText('«' if collapsed else '»')
        self.chevron.setToolTip('Show palettes' if collapsed
                                else 'Hide palettes')
        self.settings.setValue('PalettePanel/collapsed', collapsed)
        self.visibility_changed.emit()

    def panel_shown(self):
        """Whether the expanded panel is on screen (logically)."""
        return (self.board_open and self.wanted()
                and not self.is_collapsed())

    def wanted(self):
        return self.settings.value('PalettePanel/visible', False, type=bool)

    def apply_visibility(self):
        self.setVisible(self.board_open and self.wanted())
        self.visibility_changed.emit()

    def set_board_open(self, board_open):
        self.board_open = board_open
        self.apply_visibility()

    def toggle_visible(self):
        self.settings.setValue('PalettePanel/visible', not self.wanted())
        self.apply_visibility()
