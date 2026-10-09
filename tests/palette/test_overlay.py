from unittest.mock import patch

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

from beeref.fileio.export import SceneToPixmapExporter, SceneToSVGExporter
from beeref.items import BeePixmapItem
from beeref.palette.model import Palette, SamplePoint
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def setup(view):
    view.show()
    item = BeePixmapItem(stripes([RED, BLUE], height=40))
    view.scene.addItem(item)
    view.fitInView(item)
    point = SamplePoint(item, 0.25, 0.5)
    palette = Palette('A', [point])
    view.scene.palettes.add(palette)
    view.scene.palettes.set_active(palette)
    return item, point


def test_hit_test(view):
    _, point = setup(view)
    overlay = view.palette_overlay
    pos = overlay.view_pos(view, point)
    assert overlay.hit_test(view, pos) is point
    assert overlay.hit_test(view, pos + QtCore.QPointF(30, 0)) is None


def test_only_active_and_available_points(view):
    item, point = setup(view)
    assert view.palette_overlay.visible_points() == [point]
    view.scene.removeItem(item)
    assert view.palette_overlay.visible_points() == []
    view.scene.palettes.set_active(None)
    assert view.palette_overlay.visible_points() == []


def test_point_is_drawn(view):
    _, point = setup(view)
    pos = view.palette_overlay.view_pos(view, point).toPoint()
    image = view.viewport().grab().toImage()
    ring = image.pixelColor(pos + QtCore.QPoint(view.palette_overlay.RADIUS, 0))
    assert ring != QtGui.QColor(*RED)


def test_drag_point_moves_point_not_images(qtbot, view):
    item, point = setup(view)
    item.setSelected(True)
    start = view.palette_overlay.view_pos(view, point).toPoint()
    end = view.mapFromScene(item.mapToScene(QtCore.QPointF(30, 20)))
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), pos=end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert item.pos() == QtCore.QPointF(0, 0)
    assert point.color == QtGui.QColor(*BLUE)
    assert view.undo_stack.count() == 1
    assert view.undo_stack.command(0).text() == 'Move color point'


def test_right_click_removes_point(view):
    _, point = setup(view)
    pos = view.palette_overlay.view_pos(view, point).toPoint()
    view.on_context_menu(pos)
    assert view.scene.palettes.active.points == []


def test_pixmap_export_has_no_points(view):
    item, point = setup(view)
    exporter = SceneToPixmapExporter(view.scene)
    exporter.size = exporter.default_size
    image = exporter.render_to_image()
    center = QtCore.QPoint(int(exporter.margin) + 10,
                           int(exporter.margin) + 20)
    assert image.pixelColor(center) == QtGui.QColor(*RED)


def test_svg_export_does_not_crash(view):
    setup(view)
    exporter = SceneToSVGExporter(view.scene)
    exporter.size = exporter.default_size
    assert exporter.render_to_svg() is not None
