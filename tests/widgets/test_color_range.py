from beeref.items import BeePixmapItem
from beeref.palette.color_range import ColorRangeState
from beeref.palette.model import Palette, SamplePoint
from beeref.widgets.color_range import ColorRangeControls
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def board(view, level=30):
    controller = view.palette_controller
    controller.color_range.synchronous = True
    item = BeePixmapItem(stripes([RED, BLUE]))
    view.scene.addItem(item)
    palette = Palette('Lava', [SamplePoint(item, 0.25, 0.5)])
    view.scene.palettes.add(palette)
    controller.color_range.apply(item, ColorRangeState(palette, level))
    return item


def controls_for(view, item):
    controls = ColorRangeControls(view.palette_controller)
    controls.set_items([item])
    return controls


def test_set_items_shows_palette_and_level(view):
    item = board(view, level=42)
    controls = controls_for(view, item)
    assert controls.palette_label.text() == 'Lava'
    assert controls.slider.value() == 42


def test_drag_previews_then_commits_one_step(view):
    item = board(view)
    controls = controls_for(view, item)
    count = view.undo_stack.count()
    controls.slider.setSliderDown(True)
    controls.slider.setValue(60)
    assert item.color_range.level == 60
    assert view.undo_stack.count() == count
    controls.slider.setSliderDown(False)
    assert view.undo_stack.count() == count + 1
    view.undo_stack.undo()
    assert item.color_range.level == 30


def test_release_without_change_pushes_nothing(view):
    item = board(view)
    controls = controls_for(view, item)
    count = view.undo_stack.count()
    controls.slider.setSliderDown(True)
    controls.slider.setSliderDown(False)
    assert view.undo_stack.count() == count


def test_keyboard_step_commits(view):
    item = board(view)
    controls = controls_for(view, item)
    count = view.undo_stack.count()
    controls.slider.setValue(31)
    assert item.color_range.level == 31
    assert view.undo_stack.count() == count + 1


def open_sidebar(main_window):
    sidebar = main_window.palette_sidebar
    sidebar.set_board_open(True)
    if not sidebar.wanted():
        sidebar.toggle_visible()
    sidebar.set_collapsed(False)
    return sidebar


def test_controls_in_panel_when_visible(main_window):
    view = main_window.view
    item = board(view)
    sidebar = open_sidebar(main_window)
    item.setSelected(True)
    assert not sidebar.panel.color_range_controls.isHidden()
    assert view.color_range_bar.isHidden()


def test_controls_in_floating_bar_when_panel_collapsed(main_window):
    view = main_window.view
    item = board(view)
    sidebar = open_sidebar(main_window)
    item.setSelected(True)
    sidebar.set_collapsed(True)
    assert sidebar.panel.color_range_controls.isHidden()
    assert not view.color_range_bar.isHidden()


def test_controls_hidden_without_filtered_selection(main_window):
    view = main_window.view
    item = board(view)
    sidebar = open_sidebar(main_window)
    plain = BeePixmapItem(stripes([BLUE]))
    view.scene.addItem(plain)
    plain.setSelected(True)
    assert sidebar.panel.color_range_controls.isHidden()
    assert view.color_range_bar.isHidden()
    plain.setSelected(False)
    item.setSelected(True)
    view.palette_controller.toggle_color_range([item], False)
    assert sidebar.panel.color_range_controls.isHidden()
    assert view.color_range_bar.isHidden()


def test_drag_back_to_start_ends_with_full_size_render(view):
    from unittest.mock import call, patch
    item = board(view)
    controls = controls_for(view, item)
    renderer = view.palette_controller.color_range
    with patch.object(renderer, 'request',
                      wraps=renderer.request) as request:
        controls.slider.setSliderDown(True)
        controls.slider.setValue(60)
        controls.slider.setValue(30)
        controls.slider.setSliderDown(False)
    assert request.call_args_list[-1] == call(item)
