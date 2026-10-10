from PyQt6 import QtCore
from PyQt6.QtCore import Qt

from beeref.items import BeePixmapItem
from tests.palette.helpers import stripes

RED, GREEN, BLUE = (220, 30, 30), (30, 180, 60), (40, 60, 210)


def add_image(view):
    item = BeePixmapItem(stripes([RED, GREEN, BLUE], height=60))
    view.scene.addItem(item)
    view.resize(400, 300)
    view.fitInView(item, Qt.AspectRatioMode.KeepAspectRatio)
    return item


def vpos(view, item, x, y):
    """Viewport position of relative image position x/y."""
    return view.mapFromScene(item.mapToScene(QtCore.QPointF(x * 60, y * 60)))


def press(qtbot, view, pos):
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=pos)


def draw(qtbot, view, item, vertices):
    for x, y in vertices:
        press(qtbot, view, vpos(view, item, x, y))


LEFT = [(0.02, 0.05), (0.3, 0.05), (0.3, 0.95), (0.02, 0.95)]


def rgbs(palette):
    return sorted((c.red(), c.green(), c.blue()) for c in palette.colors())


def test_lasso_action_enters_lasso_mode(view):
    add_image(view)
    view.on_action_palette_lasso()
    assert view.active_mode == view.LASSO_MODE


def test_lasso_closed_with_enter_extracts_region(qtbot, view):
    item = add_image(view)
    view.on_action_palette_lasso()
    draw(qtbot, view, item, LEFT)
    qtbot.keyClick(view, Qt.Key.Key_Return)
    palette = view.scene.palettes.active
    assert rgbs(palette) == [RED]
    assert palette.source_item is item
    assert len(palette.source_region) == 4
    assert view.active_mode is None


def test_lasso_closed_by_clicking_first_vertex(qtbot, view):
    item = add_image(view)
    view.on_action_palette_lasso()
    draw(qtbot, view, item, LEFT + [LEFT[0]])
    assert view.active_mode is None
    assert rgbs(view.scene.palettes.active) == [RED]
    assert len(view.scene.palettes.active.source_region) == 4


def test_lasso_closed_by_double_click(qtbot, view):
    item = add_image(view)
    view.on_action_palette_lasso()
    draw(qtbot, view, item, LEFT[:3])
    qtbot.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton,
                      pos=vpos(view, item, *LEFT[3]))
    assert view.active_mode is None
    assert rgbs(view.scene.palettes.active) == [RED]


def test_lasso_extraction_is_one_undo_step(qtbot, view):
    item = add_image(view)
    view.on_action_palette_lasso()
    draw(qtbot, view, item, LEFT)
    qtbot.keyClick(view, Qt.Key.Key_Return)
    view.undo_stack.undo()
    assert view.scene.palettes.palettes == []


def test_backspace_removes_last_vertex(qtbot, view):
    item = add_image(view)
    view.on_action_palette_lasso()
    draw(qtbot, view, item, LEFT + [(0.9, 0.5)])
    qtbot.keyClick(view, Qt.Key.Key_Backspace)
    qtbot.keyClick(view, Qt.Key.Key_Return)
    assert rgbs(view.scene.palettes.active) == [RED]


def test_escape_cancels_lasso(qtbot, view):
    item = add_image(view)
    view.on_action_palette_lasso()
    draw(qtbot, view, item, LEFT)
    qtbot.keyClick(view, Qt.Key.Key_Escape)
    assert view.active_mode is None
    assert view.scene.palettes.palettes == []


def test_closing_with_fewer_than_three_vertices_cancels(qtbot, view):
    item = add_image(view)
    view.on_action_palette_lasso()
    draw(qtbot, view, item, LEFT[:2])
    qtbot.keyClick(view, Qt.Key.Key_Return)
    assert view.active_mode is None
    assert view.scene.palettes.palettes == []


def test_first_click_outside_images_is_ignored(qtbot, view):
    item = add_image(view)
    view.on_action_palette_lasso()
    press(qtbot, view, vpos(view, item, 1.5, 0.5))
    assert view.active_mode == view.LASSO_MODE
    assert view.lasso.item is None


def test_vertices_outside_the_image_are_clamped(qtbot, view):
    item = add_image(view)
    view.on_action_palette_lasso()
    draw(qtbot, view, item, [(0.1, 0.1), (1.5, 0.1), (1.5, 0.9)])
    xs = [x for x, _ in view.lasso.vertices]
    assert max(xs) == 1.0


def test_drag_draws_freehand(qtbot, view):
    item = add_image(view)
    view.on_action_palette_lasso()
    start = vpos(view, item, 0.05, 0.1)
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    for x, y in [(0.3, 0.1), (0.3, 0.5), (0.3, 0.9), (0.05, 0.9)]:
        qtbot.mouseMove(view.viewport(), vpos(view, item, x, y))
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton,
                       pos=vpos(view, item, 0.05, 0.9))
    assert len(view.lasso.vertices) >= 4
    qtbot.keyClick(view, Qt.Key.Key_Return)
    assert rgbs(view.scene.palettes.active) == [RED]


def test_lasso_and_region_are_painted(qtbot, view):
    from PyQt6 import QtGui
    item = add_image(view)
    view.on_action_palette_lasso()
    draw(qtbot, view, item, LEFT[:2])
    image = QtGui.QImage(400, 300, QtGui.QImage.Format.Format_ARGB32)
    painter = QtGui.QPainter(image)
    view.palette_overlay.paint(painter, view)   # in-progress lasso
    qtbot.keyClick(view, Qt.Key.Key_Escape)
    view.on_action_palette_lasso()
    draw(qtbot, view, item, LEFT)
    qtbot.keyClick(view, Qt.Key.Key_Return)
    view.palette_overlay.paint(painter, view)   # saved region outline
    painter.end()
    assert view.palette_overlay.region_polygon(view) is not None


def test_space_pan_keeps_lasso(qtbot, view):
    item = add_image(view)
    view.on_action_palette_lasso()
    draw(qtbot, view, item, LEFT[:2])
    view.space_held = True
    press(qtbot, view, vpos(view, item, 0.5, 0.5))
    view.space_held = False
    assert view.active_mode == view.LASSO_MODE
    assert len(view.lasso.vertices) == 2
