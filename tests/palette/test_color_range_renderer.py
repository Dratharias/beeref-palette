from unittest.mock import patch

from PyQt6 import QtGui

from beeref.fileio import load_bee, save_bee
from beeref.items import BeePixmapItem
from beeref.palette import color_range
from beeref.palette.color_range import ColorRangeState
from beeref.palette.model import Palette, SamplePoint
from tests.palette.helpers import stripes

RED, MAUVE, BLUE = (220, 30, 30), (200, 40, 60), (40, 60, 210)


def setup(view):
    renderer = view.palette_controller.color_range
    renderer.synchronous = True
    item = BeePixmapItem(stripes([RED, MAUVE, BLUE]))
    view.scene.addItem(item)
    palette = Palette('P', [SamplePoint(item, 10 / 60, 0.5),
                            SamplePoint(item, 50 / 60, 0.5)])
    view.scene.palettes.add(palette)
    return renderer, item, palette


def shown(item, x):
    return item.color_pixmap().toImage().pixelColor(x, 5)


def test_apply_renders_palette_colors(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    assert item.color_range_shown()
    assert shown(item, 30) == QtGui.QColor(*RED)
    assert shown(item, 50) == QtGui.QColor(*BLUE)


def test_apply_none_turns_off(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    renderer.apply(item, None)
    assert item.color_range is None
    assert not item.color_range_shown()


def test_deleting_palette_turns_off(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    view.scene.palettes.remove(palette)
    assert item.color_range is None
    assert not item.color_range_shown()


def test_palette_color_change_recomputes(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    palette.points.pop()
    view.scene.palettes.notify()
    assert shown(item, 50) == QtGui.QColor(*RED)


def test_unchanged_colors_do_not_recompute(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    with patch.object(renderer, 'request') as request:
        palette.name = 'Renamed'
        view.scene.palettes.notify()
    request.assert_not_called()


def test_empty_palette_shows_original_but_stays_on(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    palette.points.clear()
    view.scene.palettes.notify()
    assert item.color_range is not None
    assert not item.color_range_shown()


def test_stale_result_is_dropped(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    current = item.color_pixmap()
    stale = QtGui.QImage(item.pixmap().size(),
                         QtGui.QImage.Format.Format_RGBA8888)
    renderer.on_done(item, item._color_range_generation - 1,
                     color_range.FINAL_SIDE, (0, None), stale)
    assert item.color_pixmap() is current


def test_result_after_turning_off_is_dropped(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    renderer.apply(item, None)
    late = QtGui.QImage(item.pixmap().size(),
                        QtGui.QImage.Format.Format_RGBA8888)
    renderer.on_done(item, item._color_range_generation,
                     color_range.FINAL_SIDE, (0, None), late)
    assert not item.color_range_shown()


def test_prepared_image_is_cached(view):
    renderer, item, palette = setup(view)
    with patch('beeref.palette.color_range.prepare',
               wraps=color_range.prepare) as prepare:
        renderer.apply(item, ColorRangeState(palette, 0))
        renderer.apply(item, ColorRangeState(palette, 40))
    assert prepare.call_count == 1


def test_preview_uses_preview_side(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0), preview=True)
    assert color_range.PREVIEW_SIDE in item._color_range_prepared


def test_render_failure_keeps_previous_result(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    previous = item.color_pixmap()
    with patch('beeref.palette.color_range.render',
               side_effect=ValueError('boom')):
        renderer.apply(item, ColorRangeState(palette, 40))
    assert item.color_pixmap() is previous


def test_threaded_render_arrives(view, qtbot):
    renderer, item, palette = setup(view)
    renderer.synchronous = False
    renderer.apply(item, ColorRangeState(palette, 0))
    qtbot.waitUntil(lambda: item.color_range_shown())


def test_result_for_removed_item_is_harmless(view, qtbot):
    renderer, item, palette = setup(view)
    renderer.synchronous = False
    renderer.apply(item, ColorRangeState(palette, 0))
    view.scene.removeItem(item)
    renderer.wait()
    qtbot.wait(10)


def reload(view, filename):
    view.scene.clear()
    load_bee(filename, view.scene)
    view.scene.add_queued_items()
    view.palette_controller.restore_loaded()


def images(view):
    return [i for i in view.scene.items() if getattr(i, 'is_image', False)]


def test_save_load_round_trip(view, tmpfile):
    renderer, item, palette = setup(view)
    other = Palette('Other', [SamplePoint(item, 0.5, 0.5)])
    view.scene.palettes.add(other)
    renderer.apply(item, ColorRangeState(other, 45))
    save_bee(tmpfile, view.scene, create_new=True)
    reload(view, tmpfile)
    [loaded] = images(view)
    assert loaded.color_range.palette is view.scene.palettes.palettes[1]
    assert loaded.color_range.level == 45
    assert loaded.color_range_shown()


def test_unresolvable_palette_position_means_off(view):
    renderer, item, palette = setup(view)
    item._color_range_pending = {'palette': 7, 'level': 10}
    view.palette_controller.restore_color_ranges([item])
    assert item.color_range is None
    assert item._color_range_pending is None


def test_result_for_deleted_item_is_ignored(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    generation = item._color_range_generation
    entry = item._color_range_prepared[color_range.FINAL_SIDE]
    late = QtGui.QImage(item.pixmap().size(),
                        QtGui.QImage.Format.Format_RGBA8888)
    view.clear_scene()
    renderer.on_done(item, generation, color_range.FINAL_SIDE, entry, late)


def test_stale_job_skips_rendering(view):
    renderer, item, palette = setup(view)
    renderer.synchronous = False
    with patch.object(renderer.pool, 'start') as start:
        renderer.apply(item, ColorRangeState(palette, 10))
        renderer.apply(item, ColorRangeState(palette, 20))
    stale_job = start.call_args_list[0].args[0]
    with patch('beeref.palette.color_range.render') as render:
        stale_job.run()
    render.assert_not_called()


def test_turning_off_frees_working_copies(view):
    renderer, item, palette = setup(view)
    renderer.apply(item, ColorRangeState(palette, 0))
    entry = item._color_range_prepared[color_range.FINAL_SIDE]
    generation = item._color_range_generation
    renderer.apply(item, None)
    assert item._color_range_prepared == {}
    late = QtGui.QImage(item.pixmap().size(),
                        QtGui.QImage.Format.Format_RGBA8888)
    renderer.on_done(item, generation, color_range.FINAL_SIDE, entry, late)
    assert item._color_range_prepared == {}
