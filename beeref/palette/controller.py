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

"""User-level palette operations, wired to the undo stack."""

import os.path

from beeref.items import BeeErrorItem
from beeref.palette import commands
from beeref.palette.aco import write_aco
from beeref.palette.extract import extract
from beeref.palette.model import Palette, SamplePoint, item_image


class PaletteController:

    def __init__(self, view):
        self.view = view
        self.scene = view.scene
        self.store = view.scene.palettes
        self.undo_stack = view.undo_stack
        self.settings = view.settings
        self.scene.image_clicked.connect(self.on_image_clicked)

    def color_count(self):
        return self.settings.valueOrDefault('Palette/color_count')

    # Palettes

    def new_palette(self):
        palette = Palette(self.store.next_name())
        self.undo_stack.push(commands.CreatePalette(self.store, palette))
        return palette

    def rename(self, palette, name):
        name = name.strip()
        if name and name != palette.name:
            self.undo_stack.push(
                commands.RenamePalette(self.store, palette, name))

    def delete(self, palette):
        self.undo_stack.push(commands.DeletePalette(self.store, palette))

    def set_active(self, palette):
        if palette is not self.store.active:
            self.store.set_active(palette)

    def set_auto_extract(self, value):
        self.store.set_auto_extract(value)

    # Extraction

    def extract_points(self, item):
        return [SamplePoint(item, x, y)
                for x, y, _ in extract(item_image(item), self.color_count())]

    def extract_into_active(self, item):
        points = self.extract_points(item)
        self.undo_stack.beginMacro('Extract palette')
        if self.store.active is None:
            self.new_palette()
        self.undo_stack.push(commands.ReplacePoints(
            self.store, self.store.active, points, item))
        self.undo_stack.endMacro()

    def on_image_clicked(self, item):
        if self.store.auto_extract:
            self.extract_into_active(item)

    def can_regenerate(self, palette):
        item = palette.source_item
        return item is not None and item.scene() is not None

    def regenerate(self, palette):
        if not self.can_regenerate(palette):
            return False
        self.undo_stack.push(commands.ReplacePoints(
            self.store, palette, self.extract_points(palette.source_item),
            palette.source_item))
        return True

    # Points

    def image_at(self, scene_pos):
        for item in self.scene.items(scene_pos):
            if getattr(item, 'is_image', False):
                return item
        return None

    @staticmethod
    def relative_pos(item, scene_pos):
        local = item.mapFromScene(scene_pos)
        size = item.pixmap().size()
        return (min(max(local.x() / size.width(), 0.0), 1.0),
                min(max(local.y() / size.height(), 0.0), 1.0))

    def add_point_at(self, scene_pos):
        item = self.image_at(scene_pos)
        if item is None:
            return None
        if self.store.active is None:
            self.new_palette()
        point = SamplePoint(item, *self.relative_pos(item, scene_pos))
        self.undo_stack.push(
            commands.AddPoint(self.store, self.store.active, point))
        return point

    def drag_point_to(self, point, scene_pos):
        point.x, point.y = self.relative_pos(point.item, scene_pos)
        point.refresh()
        self.store.notify()

    def finish_point_drag(self, point, start):
        if (point.x, point.y) != tuple(start):
            self.undo_stack.push(commands.MovePoint(
                self.store, point, tuple(start), (point.x, point.y),
                ignore_first_redo=True))

    def remove_point(self, point):
        palette = self.store.palette_of(point)
        if palette is not None:
            self.undo_stack.push(
                commands.RemovePoint(self.store, palette, point))

    def reorder_point(self, palette, point, index):
        if palette.points.index(point) != index:
            self.undo_stack.push(
                commands.ReorderPoint(self.store, palette, point, index))

    # Files

    def default_export_name(self, palette):
        board = self.view.filename
        board = (os.path.splitext(os.path.basename(board))[0]
                 if board else 'Untitled')
        return f'{board} - {palette.name}.aco'

    def export(self, palette, path):
        write_aco(path, palette.colors())

    def restore_loaded(self):
        data = self.store.pending
        if data is None:
            return
        items = {item.save_id: item
                 for item in self.scene.items_for_save()
                 if getattr(item, 'is_image', False)}
        unloaded = {item.original_save_id
                    for item in self.scene.items_by_type(BeeErrorItem.TYPE)}
        self.store.restore(data, items, unloaded)
