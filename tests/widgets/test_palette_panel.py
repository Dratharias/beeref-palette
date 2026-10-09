from unittest.mock import patch

from PyQt6.QtCore import Qt

from beeref.items import BeePixmapItem
from tests.palette.helpers import stripes

RED, GREEN, BLUE = (220, 30, 30), (30, 180, 60), (40, 60, 210)


def sidebar(main_window):
    return main_window.palette_sidebar


def extracted(main_window):
    view = main_window.view
    item = BeePixmapItem(stripes([RED, GREEN, BLUE]))
    view.scene.addItem(item)
    view.palette_controller.extract_into_active(item)
    return view.palette_controller.store.active


def test_sidebar_is_right_of_view(main_window):
    layout = main_window.centralWidget().layout()
    assert layout.itemAt(0).widget() is main_window.view
    assert layout.itemAt(1).widget() is sidebar(main_window)


def test_collapse_persists(main_window, settings):
    side = sidebar(main_window)
    side.chevron.click()
    assert side.is_collapsed() and not side.panel.isVisibleTo(side)
    assert settings.value('PalettePanel/collapsed', type=bool) is True
    side.chevron.click()
    assert not side.is_collapsed()


def test_toggle_action(main_window, settings):
    side = sidebar(main_window)
    visible = side.isVisibleTo(main_window)
    main_window.view.on_action_toggle_palette_panel()
    assert side.isVisibleTo(main_window) is not visible
    assert settings.value('PalettePanel/visible', type=bool) is not visible


def test_new_palette_button_adds_row(main_window):
    panel = sidebar(main_window).panel
    panel.new_button.click()
    assert len(panel.rows) == 1
    assert panel.rows[0].name_edit.text() == 'Palette 1'


def test_auto_and_count_controls(main_window, settings):
    panel = sidebar(main_window).panel
    panel.auto_checkbox.setChecked(True)
    assert main_window.view.palette_controller.store.auto_extract
    panel.count_spinbox.setValue(9)
    assert settings.valueOrDefault('Palette/color_count') == 9


def test_rename_keeps_focus_while_store_changes(qtbot, main_window):
    main_window.show()
    panel = sidebar(main_window).panel
    panel.new_button.click()
    edit = panel.rows[0].name_edit
    edit.selectAll()
    qtbot.keyClicks(edit, 'Mag')    # offscreen windows never get focus
    main_window.view.palette_controller.store.notify()
    assert panel.rows[0].name_edit is edit and edit.text() == 'Mag'
    qtbot.keyClicks(edit, 'ma')
    edit.editingFinished.emit()
    assert main_window.view.palette_controller.store.active.name == 'Magma'


def test_swatch_click_selects_and_right_click_removes(qtbot, main_window):
    palette = extracted(main_window)
    strip = sidebar(main_window).panel.rows[0].strip
    first = palette.points[0]
    qtbot.mouseClick(strip, Qt.MouseButton.LeftButton,
                     pos=strip.cell_rect(0).center())
    store = main_window.view.palette_controller.store
    assert store.selected_point is first
    qtbot.mouseClick(strip, Qt.MouseButton.RightButton,
                     pos=strip.cell_rect(0).center())
    assert first not in palette.points


def test_swatch_drag_reorders(qtbot, main_window):
    palette = extracted(main_window)
    strip = sidebar(main_window).panel.rows[0].strip
    first = palette.points[0]
    qtbot.mousePress(strip, Qt.MouseButton.LeftButton,
                     pos=strip.cell_rect(0).center())
    qtbot.mouseRelease(strip, Qt.MouseButton.LeftButton,
                       pos=strip.cell_rect(2).center())
    assert palette.points[2] is first


def test_plus_cell_enters_pick_mode(qtbot, main_window):
    palette = extracted(main_window)
    strip = sidebar(main_window).panel.rows[0].strip
    qtbot.mouseClick(strip, Qt.MouseButton.LeftButton,
                     pos=strip.cell_rect(len(palette.points)).center())
    assert main_window.view.active_mode == main_window.view.PICK_POINT_MODE


def test_export_menu(main_window, tmpdir):
    extracted(main_window)
    row = sidebar(main_window).panel.rows[0]
    target = str(tmpdir.join('out.aco'))
    with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName',
               return_value=(target, '')):
        row.export()
    assert tmpdir.join('out.aco').check()


def test_export_error_shows_dialog(main_window):
    extracted(main_window)
    row = sidebar(main_window).panel.rows[0]
    with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName',
               return_value=('/nonexistent/dir/x.aco', '')), \
            patch('PyQt6.QtWidgets.QMessageBox.warning') as warning:
        row.export()
    warning.assert_called_once()


def test_regenerate_disabled_without_source(main_window):
    sidebar(main_window).panel.new_button.click()
    row = sidebar(main_window).panel.rows[0]
    row.menu_button.menu().aboutToShow.emit()
    assert not row.regenerate_action.isEnabled()


def test_export_starts_in_palette_dir(main_window, settings, tmpdir):
    target = tmpdir.join('Palettes')
    settings.setValue('Save/palette_dir', str(target))
    extracted(main_window)
    row = sidebar(main_window).panel.rows[0]
    with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName',
               return_value=('', '')) as dialog:
        row.export()
    assert dialog.call_args.args[2] == str(target.join(
        'Untitled - Palette 1.aco'))
    assert target.check(dir=True)
