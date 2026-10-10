from PyQt6 import QtGui

from beeref.items import BeePixmapItem
from beeref.palette.commands import (
    AddPoint, CreatePalette, DeletePalette, MovePoint, RemovePoint,
    RenamePalette, ReorderPoint, ReplacePoints, SetRegion)
from beeref.palette.model import Palette, PaletteStore, SamplePoint
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def setup(view):
    item = BeePixmapItem(stripes([RED, BLUE]))
    view.scene.addItem(item)
    return PaletteStore(), QtGui.QUndoStack(), item


def test_create_and_delete_palette(view):
    store, stack, _ = setup(view)
    palette = Palette('A')
    stack.push(CreatePalette(store, palette))
    assert store.palettes == [palette] and store.active is palette
    stack.push(DeletePalette(store, palette))
    assert store.palettes == [] and store.active is None
    stack.undo()
    assert store.palettes == [palette] and store.active is palette
    stack.undo()
    assert store.palettes == []


def test_rename(view):
    store, stack, _ = setup(view)
    palette = Palette('A')
    store.add(palette)
    stack.push(RenamePalette(store, palette, 'Magma'))
    assert palette.name == 'Magma'
    stack.undo()
    assert palette.name == 'A'


def test_replace_points(view):
    store, stack, item = setup(view)
    old = SamplePoint(item, 0.1, 0.5)
    palette = Palette('A', [old])
    store.add(palette)
    new = [SamplePoint(item, 0.9, 0.5)]
    stack.push(ReplacePoints(store, palette, new, item))
    assert palette.points == new and palette.source_item is item
    stack.undo()
    assert palette.points == [old] and palette.source_item is None


def test_add_remove_point(view):
    store, stack, item = setup(view)
    palette = Palette('A')
    store.add(palette)
    point = SamplePoint(item, 0.1, 0.5)
    stack.push(AddPoint(store, palette, point))
    assert palette.points == [point]
    store.select_point(point)
    stack.push(RemovePoint(store, palette, point))
    assert palette.points == [] and store.selected_point is None
    stack.undo()
    assert palette.points == [point]


def test_move_point_refreshes_color(view):
    store, stack, item = setup(view)
    point = SamplePoint(item, 0.1, 0.5)
    store.add(Palette('A', [point]))
    point.x = 0.9                        # live drag already moved it
    stack.push(MovePoint(store, point, (0.1, 0.5), (0.9, 0.5),
                         ignore_first_redo=True))
    stack.undo()
    assert (point.x, point.color) == (0.1, QtGui.QColor(*RED))
    stack.redo()
    assert (point.x, point.color) == (0.9, QtGui.QColor(*BLUE))


def test_reorder_point(view):
    store, stack, item = setup(view)
    a, b, c = (SamplePoint(item, x, 0.5) for x in (0.1, 0.2, 0.3))
    palette = Palette('A', [a, b, c])
    store.add(palette)
    stack.push(ReorderPoint(store, palette, a, 2))
    assert palette.points == [b, c, a]
    stack.undo()
    assert palette.points == [a, b, c]


def test_replace_points_sets_and_restores_region(view):
    store, stack, item = setup(view)
    palette = Palette('A')
    palette.source_region = [(0, 0), (1, 0), (1, 1)]
    store.add(palette)
    region = [(0, 0), (0.5, 0), (0.5, 1)]
    stack.push(ReplacePoints(store, palette, [], item, region))
    assert palette.source_region == region
    stack.undo()
    assert palette.source_region == [(0, 0), (1, 0), (1, 1)]


def test_replace_points_without_region_clears_it(view):
    store, stack, item = setup(view)
    palette = Palette('A')
    palette.source_region = [(0, 0), (1, 0), (1, 1)]
    store.add(palette)
    stack.push(ReplacePoints(store, palette, [], item))
    assert palette.source_region is None


def test_set_region(view):
    store, stack, _ = setup(view)
    palette = Palette('A')
    palette.source_region = [(0, 0), (1, 0), (1, 1)]
    store.add(palette)
    stack.push(SetRegion(store, palette, None))
    assert palette.source_region is None
    stack.undo()
    assert palette.source_region == [(0, 0), (1, 0), (1, 1)]
