from PyQt6 import QtCore, QtGui

from beeref.items import BeePixmapItem
from beeref.palette.color_range import ColorRangeState
from beeref.palette.model import Palette
from tests.palette.helpers import stripes

RED, GREEN, BLUE = (220, 30, 30), (30, 180, 60), (40, 60, 210)


def filled(size, color):
    pixmap = QtGui.QPixmap(size)
    pixmap.fill(QtGui.QColor(*color))
    return pixmap


def bound_item(palette=None):
    item = BeePixmapItem(stripes([RED, BLUE]))
    item.set_color_range(ColorRangeState(palette or Palette('P')))
    return item


def color_at(pixmap, x=5, y=5):
    return pixmap.toImage().pixelColor(x, y)


def test_display_is_original_until_result_arrives(qapp):
    item = bound_item()
    assert not item.color_range_shown()
    assert item.display_pixmap().cacheKey() == item.pixmap().cacheKey()


def test_display_shows_result(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    assert color_at(item.display_pixmap()) == QtGui.QColor(*GREEN)
    assert color_at(item.pixmap()) == QtGui.QColor(*RED)


def test_turning_off_drops_result(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    item.set_color_range(None)
    assert item._color_range_pixmap is None
    assert not item.color_range_shown()
    assert item.display_pixmap().cacheKey() == item.pixmap().cacheKey()


def test_grayscale_applies_on_top_of_result(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    item.grayscale = True
    expected = BeePixmapItem._grayscale_of(item.color_pixmap())
    assert color_at(item.display_pixmap()) == color_at(expected)
    original_gray = BeePixmapItem._grayscale_of(item.pixmap())
    assert color_at(item.display_pixmap()) != color_at(original_gray)


def test_result_arriving_rebuilds_grayscale(qapp):
    item = bound_item()
    item.grayscale = True
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    expected = BeePixmapItem._grayscale_of(item.color_pixmap())
    assert color_at(item.display_pixmap()) == color_at(expected)


def test_sample_color_reads_original(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    assert item.sample_color_at(QtCore.QPointF(5, 5)) == QtGui.QColor(*RED)


def test_sample_color_grayscale_reads_original_gray(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    item.grayscale = True
    expected = color_at(BeePixmapItem._grayscale_of(item.pixmap()))
    assert item.sample_color_at(QtCore.QPointF(5, 5)) == expected


def test_export_grayscale_ignores_color_range(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    item.grayscale = True
    data, _ = item.pixmap_to_bytes(apply_grayscale=True)
    exported = QtGui.QImage.fromData(data)
    expected = color_at(BeePixmapItem._grayscale_of(item.pixmap()))
    assert exported.pixelColor(5, 5).getRgb()[:3] == expected.getRgb()[:3]


def test_save_data_records_palette_position(view):
    first, second = Palette('A'), Palette('B')
    view.scene.palettes.add(first)
    view.scene.palettes.add(second)
    item = bound_item(second)
    item.set_color_range(ColorRangeState(second, 45))
    view.scene.addItem(item)
    data = item.get_extra_save_data()
    assert data['color_range'] == {'palette': 1, 'level': 45}


def test_save_data_omits_color_range_when_off_or_unbound(view):
    item = BeePixmapItem(stripes([RED]))
    view.scene.addItem(item)
    assert 'color_range' not in item.get_extra_save_data()
    item.set_color_range(ColorRangeState(Palette('Not in store')))
    assert 'color_range' not in item.get_extra_save_data()


def test_create_from_data_keeps_color_range_pending(qapp):
    item = BeePixmapItem(stripes([RED]))
    BeePixmapItem.create_from_data(
        item=item, data={'color_range': {'palette': 0, 'level': 10}})
    assert item._color_range_pending == {'palette': 0, 'level': 10}
    assert item.color_range is None


def test_create_copy_carries_color_range(qapp):
    item = bound_item()
    item.set_color_range_result(filled(item.pixmap().size(), GREEN))
    copy = item.create_copy()
    assert copy.color_range == item.color_range
    assert color_at(copy.display_pixmap()) == QtGui.QColor(*GREEN)
