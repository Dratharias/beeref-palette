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

"""Undoable palette operations."""

from PyQt6 import QtGui


class CreatePalette(QtGui.QUndoCommand):

    def __init__(self, store, palette):
        super().__init__('New palette')
        self.store = store
        self.palette = palette
        self.previous_active = store.active

    def redo(self):
        self.store.add(self.palette)
        self.store.set_active(self.palette)

    def undo(self):
        self.store.remove(self.palette)
        self.store.set_active(self.previous_active)


class DeletePalette(QtGui.QUndoCommand):

    def __init__(self, store, palette):
        super().__init__('Delete palette')
        self.store = store
        self.palette = palette
        self.index = None

    def redo(self):
        self.index = self.store.remove(self.palette)

    def undo(self):
        self.store.add(self.palette, self.index)
        self.store.set_active(self.palette)


class RenamePalette(QtGui.QUndoCommand):

    def __init__(self, store, palette, name):
        super().__init__('Rename palette')
        self.store = store
        self.palette = palette
        self.old_name = palette.name
        self.new_name = name

    def redo(self):
        self.palette.name = self.new_name
        self.store.notify()

    def undo(self):
        self.palette.name = self.old_name
        self.store.notify()


class ReplacePoints(QtGui.QUndoCommand):

    def __init__(self, store, palette, points, source_item):
        super().__init__('Extract palette')
        self.store = store
        self.palette = palette
        self.new = (list(points), source_item)
        self.old = (list(palette.points), palette.source_item)

    def _apply(self, state):
        self.palette.points = list(state[0])
        self.palette.source_item = state[1]
        self.store.selected_point = None
        self.store.notify()

    def redo(self):
        self._apply(self.new)

    def undo(self):
        self._apply(self.old)


class AddPoint(QtGui.QUndoCommand):

    def __init__(self, store, palette, point, index=None):
        super().__init__('Add color point')
        self.store = store
        self.palette = palette
        self.point = point
        self.index = len(palette.points) if index is None else index

    def redo(self):
        self.palette.points.insert(self.index, self.point)
        self.store.notify()

    def undo(self):
        self.palette.points.remove(self.point)
        if self.store.selected_point is self.point:
            self.store.selected_point = None
        self.store.notify()


class RemovePoint(QtGui.QUndoCommand):

    def __init__(self, store, palette, point):
        super().__init__('Remove color point')
        self.store = store
        self.palette = palette
        self.point = point
        self.index = palette.points.index(point)

    def redo(self):
        self.palette.points.pop(self.index)
        if self.store.selected_point is self.point:
            self.store.selected_point = None
        self.store.notify()

    def undo(self):
        self.palette.points.insert(self.index, self.point)
        self.store.notify()


class MovePoint(QtGui.QUndoCommand):

    def __init__(self, store, point, old, new, ignore_first_redo=False):
        super().__init__('Move color point')
        self.store = store
        self.point = point
        self.old = old
        self.new = new
        self.ignore_first_redo = ignore_first_redo

    def _apply(self, pos):
        self.point.x, self.point.y = pos
        self.point.refresh()
        self.store.notify()

    def redo(self):
        if self.ignore_first_redo:
            self.ignore_first_redo = False
            return
        self._apply(self.new)

    def undo(self):
        self._apply(self.old)


class ReorderPoint(QtGui.QUndoCommand):

    def __init__(self, store, palette, point, index):
        super().__init__('Reorder colors')
        self.store = store
        self.palette = palette
        self.point = point
        self.old_index = palette.points.index(point)
        self.new_index = index

    def _move(self, frm, to):
        self.palette.points.insert(to, self.palette.points.pop(frm))
        self.store.notify()

    def redo(self):
        self._move(self.old_index, self.new_index)

    def undo(self):
        self._move(self.new_index, self.old_index)
