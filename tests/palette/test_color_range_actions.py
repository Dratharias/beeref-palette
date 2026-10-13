from beeref import commands
from beeref.actions import actions
from beeref.items import BeePixmapItem, BeeTextItem
from beeref.palette.color_range import DEFAULT_LEVEL, ColorRangeState
from beeref.palette.model import Palette, SamplePoint
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def board(view, with_palette=True):
    view.palette_controller.color_range.synchronous = True
    item = BeePixmapItem(stripes([RED, BLUE]))
    view.scene.addItem(item)
    palette = None
    if with_palette:
        palette = Palette('P', [SamplePoint(item, 0.25, 0.5)])
        view.scene.palettes.add(palette)
        view.scene.palettes.set_active(palette)
    return item, palette


def qaction():
    return actions.actions['color_range'].qaction


def test_toggle_command_redo_undo(view):
    item, palette = board(view)
    renderer = view.palette_controller.color_range
    command = commands.ToggleColorRange(renderer, [item], palette, True)
    command.redo()
    assert item.color_range == ColorRangeState(palette, DEFAULT_LEVEL)
    command.undo()
    assert item.color_range is None


def test_toggle_on_rebinds_and_keeps_level(view):
    item, palette = board(view)
    other = Palette('O', [SamplePoint(item, 0.75, 0.5)])
    view.scene.palettes.add(other)
    renderer = view.palette_controller.color_range
    renderer.apply(item, ColorRangeState(palette, 70))
    commands.ToggleColorRange(renderer, [item], other, True).redo()
    assert item.color_range == ColorRangeState(other, 70)


def test_toggle_command_skips_text_items(view):
    item, palette = board(view)
    text = BeeTextItem('t')
    command = commands.ToggleColorRange(
        view.palette_controller.color_range, [item, text], palette, True)
    assert command.items == [item]


def test_level_command_redo_undo(view):
    item, palette = board(view)
    renderer = view.palette_controller.color_range
    renderer.apply(item, ColorRangeState(palette, 30))
    command = commands.SetColorRangeLevel(renderer, [item], [30], 80)
    command.redo()
    assert item.color_range.level == 80
    command.undo()
    assert item.color_range.level == 30


def test_action_toggles_selected_images_with_undo(view):
    item, palette = board(view)
    item.setSelected(True)
    view.on_action_color_range(True)
    assert item.color_range.palette is palette
    view.undo_stack.undo()
    assert item.color_range is None


def test_action_needs_a_palette(view):
    item, _ = board(view, with_palette=False)
    item.setSelected(True)
    view.update_color_range_controls()
    assert not qaction().isEnabled()
    view.on_action_color_range(True)
    assert item.color_range is None


def test_action_enabled_with_image_and_palette(view):
    item, _ = board(view)
    view.update_color_range_controls()
    assert not qaction().isEnabled()
    item.setSelected(True)
    assert qaction().isEnabled()


def test_action_checked_follows_first_selected_item(view):
    item, palette = board(view)
    view.palette_controller.color_range.apply(
        item, ColorRangeState(palette))
    item.setSelected(True)
    assert qaction().isChecked()
    item.setSelected(False)
    assert not qaction().isChecked()


def test_syncing_checked_state_pushes_no_undo(view):
    item, palette = board(view)
    view.palette_controller.color_range.apply(
        item, ColorRangeState(palette))
    count = view.undo_stack.count()
    item.setSelected(True)
    item.setSelected(False)
    assert view.undo_stack.count() == count
    assert item.color_range is not None


def test_preview_pushes_no_undo_commit_pushes_one(view):
    item, palette = board(view)
    controller = view.palette_controller
    controller.color_range.apply(item, ColorRangeState(palette, 30))
    count = view.undo_stack.count()
    controller.preview_color_range_level([item], 55)
    assert item.color_range.level == 55
    assert view.undo_stack.count() == count
    controller.commit_color_range_level([item], [30], 60)
    assert view.undo_stack.count() == count + 1
    view.undo_stack.undo()
    assert item.color_range.level == 30
