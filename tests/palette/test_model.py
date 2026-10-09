from PyQt6 import QtCore, QtGui

from beeref.items import BeePixmapItem
from beeref.palette.model import (
    Palette, PaletteStore, SamplePoint, item_image, sample_color)
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def image_item(view, colors=(RED, BLUE), widths=None):
    item = BeePixmapItem(stripes(list(colors), widths))
    view.scene.addItem(item)
    return item


def test_sample_color_averages_3x3():
    image = stripes([(0, 0, 0), (90, 90, 90)], widths=[1, 2], height=3)
    color = sample_color(image, 0.5, 0.5)   # centre pixel x=1: 3 black, 6 grey
    assert (color.red(), color.green(), color.blue()) == (60, 60, 60)


def test_sample_color_clamps_and_skips_transparent():
    image = stripes([(0, 0, 0, 0), RED], widths=[2, 2], height=2)
    color = sample_color(image, 1.5, -3)
    assert (color.red(), color.green(), color.blue()) == RED
    assert not sample_color(stripes([(0, 0, 0, 0)]), 0.5, 0.5).isValid()


def test_item_image_is_cached(view):
    item = image_item(view)
    assert item_image(item) is item_image(item)


def test_sample_point_refresh_and_geometry(view):
    item = image_item(view, widths=[20, 20])
    point = SamplePoint(item, 0.75, 0.5)
    assert (point.color.red(), point.color.green(), point.color.blue()) == BLUE
    assert point.pixel_pos() == QtCore.QPointF(30, 10)
    assert point.is_available
    item.crop = QtCore.QRectF(0, 0, 20, 20)
    assert not point.in_crop()
    view.scene.removeItem(item)
    assert not point.is_available


def test_store_add_remove_active(qtbot):
    store = PaletteStore()
    a, b = Palette('A'), Palette('B')
    with qtbot.waitSignal(store.changed):
        store.add(a)
    store.add(b)
    store.set_active(b)
    assert store.remove(b) == 1
    assert store.active is a
    assert store.remove(a) == 0
    assert store.active is None


def test_store_next_name_and_palette_of(view):
    store = PaletteStore()
    assert store.next_name() == 'Palette 1'
    p = Palette('Palette 1', [SamplePoint(image_item(view), 0.1, 0.1)])
    store.add(p)
    assert store.next_name() == 'Palette 2'
    assert store.palette_of(p.points[0]) is p


def test_store_restore_drops_missing_images(view):
    item = image_item(view)
    item.save_id = 7
    store = PaletteStore()
    store.restore({
        'palettes': [{'name': 'Lava', 'source_save_id': 7, 'points': [
            {'save_id': 7, 'x': 0.25, 'y': 0.5, 'color': '#000000'},
            {'save_id': 99, 'x': 0.5, 'y': 0.5, 'color': '#ffffff'}]}],
        'active': 0, 'auto_extract': True}, {7: item})
    palette = store.palettes[0]
    assert palette.name == 'Lava' and palette.source_item is item
    assert len(palette.points) == 1
    assert palette.points[0].color == QtGui.QColor(*RED)   # refreshed
    assert store.active is palette and store.auto_extract


def test_store_clear(qtbot):
    store = PaletteStore()
    store.add(Palette('A'))
    store.pending = {'palettes': []}
    store.auto_extract = True
    store.clear()
    assert store.palettes == [] and store.active is None
    assert store.pending is None and not store.auto_extract


def test_point_on_deleted_item_is_not_available(view):
    from PyQt6 import sip
    item = image_item(view)
    point = SamplePoint(item, 0.5, 0.5)
    view.scene.removeItem(item)
    sip.delete(item)
    assert not point.is_available
