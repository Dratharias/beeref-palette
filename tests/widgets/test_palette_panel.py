from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

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


def test_panel_buttons_never_take_keyboard_focus(main_window):
    # Space pans the canvas; a focused checkbox or button would eat it.
    from PyQt6 import QtWidgets
    extracted(main_window)
    side = sidebar(main_window)
    widgets = (side.findChildren(QtWidgets.QAbstractButton)
               + side.findChildren(QtWidgets.QAbstractScrollArea))
    assert widgets
    for widget in widgets:
        assert widget.focusPolicy() == Qt.FocusPolicy.NoFocus, widget


def test_clear_region_menu(main_window):
    palette = extracted(main_window)
    row = sidebar(main_window).panel.rows[0]
    row.menu_button.menu().aboutToShow.emit()
    assert not row.clear_region_action.isEnabled()
    palette.source_region = [(0, 0), (1, 0), (1, 1)]
    row.menu_button.menu().aboutToShow.emit()
    assert row.clear_region_action.isEnabled()
    row.clear_region_action.trigger()
    assert palette.source_region is None


def two_rows(main_window):
    extracted(main_window)
    controller = main_window.view.palette_controller
    first = controller.store.active
    controller.rename(first, 'Billet')
    controller.new_palette()
    controller.add_point_at(
        controller.store.palettes[0].points[0].item.sceneBoundingRect()
        .center())
    return controller, sidebar(main_window).panel.rows


def show_menu(row):
    row.menu_button.menu().aboutToShow.emit()


def test_merge_menu_lists_other_palettes(main_window):
    controller, rows = two_rows(main_window)
    show_menu(rows[0])
    labels = [a.text() for a in rows[0].merge_menu.actions()]
    assert labels == ['Palette 2']
    assert rows[0].merge_menu.isEnabled()


def test_merge_menu_disabled_with_single_palette(main_window):
    extracted(main_window)
    row = sidebar(main_window).panel.rows[0]
    show_menu(row)
    assert not row.merge_menu.isEnabled()
    assert not row.export_merged_menu.isEnabled()


def test_merge_menu_creates_merged_palette(main_window):
    controller, rows = two_rows(main_window)
    show_menu(rows[0])
    rows[0].merge_menu.actions()[0].trigger()
    names = [p.name for p in controller.store.palettes]
    assert names == ['Billet', 'Billet', 'Palette 2']
    assert len(controller.store.palettes[1].points) == 4


def test_all_palettes_entry_with_three_palettes(main_window):
    controller, rows = two_rows(main_window)
    controller.new_palette()
    rows = sidebar(main_window).panel.rows
    show_menu(rows[0])
    labels = [a.text() for a in rows[0].merge_menu.actions()
              if not a.isSeparator()]
    assert labels == ['Palette 2', 'Palette 3', 'All palettes']


def test_export_merged_menu(main_window, tmpdir):
    controller, rows = two_rows(main_window)
    show_menu(rows[0])
    target = str(tmpdir.join('both.aco'))
    with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName',
               return_value=(target, '')) as dialog:
        rows[0].export_merged_menu.actions()[0].trigger()
    assert dialog.call_args.args[2].endswith('Untitled - Billet.aco')
    from tests.palette.aco_reader import read_aco
    assert len(read_aco(target)) == 4
    assert len(controller.store.palettes) == 2


def test_plus_swatch_shows_it_is_waiting_for_a_click(main_window):
    extracted(main_window)
    view = main_window.view
    strip = sidebar(main_window).panel.rows[0].strip
    assert not strip.is_picking()
    plus = strip.cell_rect(len(strip.palette.points)).center()
    with patch('beeref.widgets.BeeNotification') as notification:
        QTest.mouseClick(strip, Qt.MouseButton.LeftButton, pos=plus)
    assert view.active_mode == view.PICK_POINT_MODE
    assert strip.is_picking()
    notification.assert_called_once()
    view.cancel_active_modes()
    assert not strip.is_picking()


def test_plus_swatch_tooltip_and_cursor(main_window):
    extracted(main_window)
    strip = sidebar(main_window).panel.rows[0].strip
    plus = strip.cell_rect(len(strip.palette.points)).center()
    assert 'click on an image' in strip.tooltip_at(plus).lower()
    hover(strip, plus)
    assert strip.cursor().shape() == Qt.CursorShape.PointingHandCursor
    hover(strip, strip.cell_rect(0).center())
    assert strip.cursor().shape() != Qt.CursorShape.PointingHandCursor


def hover(widget, pos):
    # QTest.mouseMove sends no move event on the offscreen platform
    from PyQt6 import QtCore, QtGui, QtWidgets
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove, QtCore.QPointF(pos),
        QtCore.QPointF(widget.mapToGlobal(pos)), Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(widget, event)


def test_plus_swatch_adds_beyond_twelve(main_window):
    palette = extracted(main_window)
    controller = main_window.view.palette_controller
    item = palette.points[0].item
    while len(palette.points) < 13:
        controller.add_point_at(item.sceneBoundingRect().center())
    assert len(palette.points) == 13
