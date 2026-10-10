from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

from beeref.items import BeePixmapItem
from beeref.palette.model import Palette, SamplePoint
from tests.palette.aco_reader import read_aco
from tests.palette.helpers import stripes

RED, GREEN, BLUE = (220, 30, 30), (30, 180, 60), (40, 60, 210)


def add_image(view, colors=(RED, GREEN, BLUE)):
    item = BeePixmapItem(stripes(list(colors), height=60))
    view.scene.addItem(item)
    return item


def click(qtbot, view, scene_pos, button=Qt.MouseButton.LeftButton, jitter=0):
    pos = view.mapFromScene(scene_pos)
    qtbot.mousePress(view.viewport(), button, pos=pos)
    qtbot.mouseRelease(view.viewport(), button,
                       pos=pos + QtCore.QPoint(jitter, 0))


def test_new_palette_is_undoable(view):
    c = view.palette_controller
    palette = c.new_palette()
    assert c.store.palettes == [palette] and c.store.active is palette
    view.undo_stack.undo()
    assert c.store.palettes == []


def test_extract_into_active_creates_palette_in_one_undo_step(view):
    c = view.palette_controller
    item = add_image(view)
    c.extract_into_active(item)
    palette = c.store.active
    assert len(palette.points) == 3 and palette.source_item is item
    view.undo_stack.undo()
    assert c.store.palettes == []


def test_color_count_setting(view, settings):
    settings.setValue('Palette/color_count', 3)
    c = view.palette_controller
    c.extract_into_active(
        add_image(view, (RED, GREEN, BLUE, (240, 220, 40), (10, 10, 10))))
    assert len(c.store.active.points) == 3


def test_click_extracts_only_when_auto_on(qtbot, view):
    view.show()
    c = view.palette_controller
    item = add_image(view)
    view.fitInView(item)
    click(qtbot, view, item.sceneBoundingRect().center())
    assert c.store.palettes == []
    c.set_auto_extract(True)
    click(qtbot, view, item.sceneBoundingRect().center(), jitter=2)
    assert len(c.store.active.points) == 3


def test_drag_does_not_extract(qtbot, view):
    view.show()
    c = view.palette_controller
    c.set_auto_extract(True)
    item = add_image(view)
    view.fitInView(item)
    start = view.mapFromScene(item.sceneBoundingRect().center())
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), pos=start + QtCore.QPoint(40, 0))
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton,
                       pos=start + QtCore.QPoint(40, 0))
    assert c.store.palettes == []


def test_regenerate(view):
    c = view.palette_controller
    item = add_image(view)
    c.extract_into_active(item)
    palette = c.store.active
    palette.points.pop()
    assert c.regenerate(palette)
    assert len(palette.points) == 3
    assert not c.regenerate(Palette('empty'))


def test_pick_mode_adds_point(qtbot, view):
    view.show()
    c = view.palette_controller
    item = add_image(view)
    view.fitInView(item)
    view.enter_pick_point_mode()
    assert view.active_mode == view.PICK_POINT_MODE
    rect = item.sceneBoundingRect()
    click(qtbot, view, QtCore.QPointF(rect.left() + rect.width() * 5 / 6,
                                      rect.center().y()))
    point = c.store.active.points[0]
    assert point.color == QtGui.QColor(*BLUE)
    assert view.active_mode is None


def test_pick_mode_on_empty_canvas_adds_nothing(qtbot, view):
    view.show()
    add_image(view)
    view.enter_pick_point_mode()
    click(qtbot, view, QtCore.QPointF(-5000, -5000))
    assert all(not p.points for p in view.palette_controller.store.palettes)


def test_escape_cancels_pick_mode(qtbot, view):
    view.enter_pick_point_mode()
    qtbot.keyClick(view, Qt.Key.Key_Escape)
    assert view.active_mode is None


def test_drag_point_then_undo(view):
    c = view.palette_controller
    item = add_image(view)
    point = SamplePoint(item, 0.1, 0.5)
    c.store.add(Palette('A', [point]))
    rect = item.sceneBoundingRect()
    c.drag_point_to(point, QtCore.QPointF(rect.right() - 1, rect.center().y()))
    assert point.color == QtGui.QColor(*BLUE)
    c.finish_point_drag(point, (0.1, 0.5))
    view.undo_stack.undo()
    assert (point.x, point.color) == (0.1, QtGui.QColor(*RED))


def test_rename_delete_reorder_remove(view):
    c = view.palette_controller
    item = add_image(view)
    c.extract_into_active(item)
    palette = c.store.active
    first = palette.points[0]
    c.rename(palette, 'Magma')
    c.reorder_point(palette, first, 2)
    c.remove_point(first)
    assert palette.name == 'Magma' and first not in palette.points
    c.delete(palette)
    assert c.store.palettes == []
    for _ in range(3):       # undo delete, remove, reorder — not rename
        view.undo_stack.undo()
    assert palette.name == 'Magma' and palette.points[0] is first


def test_export(view, tmpfile):
    c = view.palette_controller
    c.extract_into_active(add_image(view))
    c.export(c.store.active, tmpfile)
    assert len(read_aco(tmpfile)) == 3
    view.filename = '/tmp/Volcano.bee'
    c.store.active.name = 'Magma'
    assert c.default_export_name(c.store.active) == 'Volcano - Magma.aco'


def test_restore_loaded(view, tmpfile):
    from beeref.fileio import save_bee
    c = view.palette_controller
    c.extract_into_active(add_image(view))
    save_bee(tmpfile, view.scene, create_new=True)
    view.open_from_file(tmpfile)
    view.worker.wait()
    QtCore.QCoreApplication.processEvents()
    assert len(c.store.palettes) == 1 and len(c.store.active.points) == 3


def press_wobble_release(qtbot, view, item, wobble):
    start = view.mapFromScene(item.sceneBoundingRect().center())
    end = start + wobble
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), pos=end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)


def test_diagonal_pen_wobble_is_a_click(qtbot, view):
    view.show()
    c = view.palette_controller
    c.set_auto_extract(True)
    item = add_image(view)
    view.fitInView(item)
    press_wobble_release(qtbot, view, item, QtCore.QPoint(2, 2))
    assert c.store.active is not None


def test_wobbly_click_extraction_is_the_only_undo_step(qtbot, view):
    view.show()
    c = view.palette_controller
    c.set_auto_extract(True)
    item = add_image(view)
    view.fitInView(item)
    item.setSelected(True)
    press_wobble_release(qtbot, view, item, QtCore.QPoint(1, 1))
    stack = view.undo_stack
    assert [stack.text(i) for i in range(stack.count())] == ['Extract palette']
    assert item.pos() == QtCore.QPointF(0, 0)
    item.setSelected(False)


LEFT_THIRD = [(0, 0), (0.33, 0), (0.33, 1), (0, 1)]


def rgbs(palette):
    return sorted((c.red(), c.green(), c.blue()) for c in palette.colors())


def test_extract_into_active_with_region(view):
    c = view.palette_controller
    item = add_image(view)
    c.extract_into_active(item, LEFT_THIRD)
    palette = c.store.active
    assert rgbs(palette) == [RED]
    assert palette.source_region == LEFT_THIRD


def test_regenerate_reuses_region(view):
    c = view.palette_controller
    item = add_image(view)
    c.extract_into_active(item, LEFT_THIRD)
    palette = c.store.active
    palette.points = []
    assert c.regenerate(palette)
    assert rgbs(palette) == [RED]
    assert palette.source_region == LEFT_THIRD


def test_plain_extraction_respects_crop(view):
    c = view.palette_controller
    item = add_image(view)
    # Keep only the right third (blue)
    item.crop = QtCore.QRectF(40, 0, 20, 60)
    c.extract_into_active(item)
    palette = c.store.active
    assert rgbs(palette) == [BLUE]
    assert palette.source_region is None


def test_regenerate_follows_new_crop(view):
    c = view.palette_controller
    item = add_image(view)
    c.extract_into_active(item)
    item.crop = QtCore.QRectF(0, 0, 20, 60)
    c.regenerate(c.store.active)
    assert rgbs(c.store.active) == [RED]


def test_clear_region_is_undoable(view):
    c = view.palette_controller
    item = add_image(view)
    c.extract_into_active(item, LEFT_THIRD)
    palette = c.store.active
    assert c.can_clear_region(palette)
    c.clear_region(palette)
    assert palette.source_region is None
    assert not c.can_clear_region(palette)
    view.undo_stack.undo()
    assert palette.source_region == LEFT_THIRD


# Merging

def two_palettes(view):
    c = view.palette_controller
    item = add_image(view)
    billet = c.new_palette()
    c.extract_into_active(item)
    c.rename(billet, 'Billet')
    other = c.new_palette()
    c.extract_into_active(item, LEFT_THIRD)
    return c, item, billet, other


def test_merged_name_prefers_user_named_palettes(view):
    c, _, billet, other = two_palettes(view)
    assert other.name == 'Palette 2'
    assert c.merged_name([billet, other]) == 'Billet'
    c.rename(other, 'Mood')
    assert c.merged_name([billet, other]) == 'Billet + Mood'


def test_merged_name_without_user_names_joins_defaults(view):
    c, _, billet, other = two_palettes(view)
    c.rename(billet, 'Palette 1')
    assert c.merged_name([billet, other]) == 'Palette 1 + Palette 2'


def test_merge_creates_palette_with_all_points(view):
    c, item, billet, other = two_palettes(view)
    merged = c.merge([billet, other])
    assert merged.name == 'Billet'
    assert c.store.palettes == [billet, merged, other]
    assert c.store.active is merged
    assert merged.colors() == billet.colors() + other.colors()
    assert merged.source_item is None and merged.source_region is None
    assert not c.can_regenerate(merged)


def test_merged_points_are_copies(view):
    c, item, billet, other = two_palettes(view)
    merged = c.merge([billet, other])
    assert all(p not in billet.points + other.points
               for p in merged.points)
    merged.points[0].x = 0.99
    assert billet.points[0].x != 0.99


def test_merge_is_one_undo_step(view):
    c, item, billet, other = two_palettes(view)
    c.merge([billet, other])
    view.undo_stack.undo()
    assert c.store.palettes == [billet, other]
    assert c.store.active is other


def test_export_merged_writes_all_colors(view, tmpdir):
    c, item, billet, other = two_palettes(view)
    path = str(tmpdir.join('both.aco'))
    c.export_merged([billet, other], path)
    colors = read_aco(path)
    assert len(colors) == len(billet.points) + len(other.points)
    assert c.store.palettes == [billet, other]


def test_default_export_path_of_merge(view, settings, tmpdir):
    settings.setValue('Save/palette_dir', str(tmpdir))
    c, item, billet, other = two_palettes(view)
    view.filename = '/x/Magma.bee'
    assert c.default_export_path([billet, other]) == str(
        tmpdir.join('Magma - Billet.aco'))
