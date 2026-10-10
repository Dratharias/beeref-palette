import os
from unittest.mock import MagicMock, patch

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref.fileio import save_bee
from beeref.items import BeePixmapItem
from beeref.palette.model import Palette, SamplePoint
from beeref.view import BeeGraphicsView
from beeref.widgets.welcome_overlay import BoardTile, WelcomeOverlay
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def make_overlay(qapp):
    parent = QtWidgets.QMainWindow()
    view = BeeGraphicsView(qapp, parent)
    return WelcomeOverlay(view), view


def save_board(view, path):
    item = BeePixmapItem(stripes([RED, BLUE], height=40))
    view.scene.addItem(item)
    view.scene.palettes.add(Palette('Lava', [SamplePoint(item, 0.25, 0.5)]))
    save_bee(path, view.scene, create_new=True)
    view.scene.clear()


@patch('beeref.widgets.welcome_overlay.BeeSettings.get_recent_files',
       return_value=[])
def test_welcome_overlay_when_no_recent_files(files_mock, qapp):
    overlay, _ = make_overlay(qapp)
    overlay.show()
    assert overlay.tiles == []
    assert overlay.recent_widget.isHidden()


def test_welcome_overlay_shows_recent_boards_as_tiles(qapp, view, tmpdir):
    paths = [str(tmpdir.join(f'board{i}.bee')) for i in range(2)]
    for path in paths:
        save_board(view, path)
    overlay = view.welcome_overlay
    with patch('beeref.widgets.welcome_overlay.BeeSettings.get_recent_files',
               return_value=paths):
        overlay.show()
    assert not overlay.recent_widget.isHidden()
    assert [t.name for t in overlay.tiles] == ['board0', 'board1']
    assert overlay.tiles[0].date == 'today'
    assert not overlay.tiles[0].preview.isNull()
    assert len(overlay.tiles[0].colors) == 1
    overlay.tiles[0].grab()


def test_welcome_overlay_shows_at_most_six_tiles(qapp, view, tmpdir):
    path = str(tmpdir.join('board.bee'))
    save_board(view, path)
    overlay = view.welcome_overlay
    with patch('beeref.widgets.welcome_overlay.BeeSettings.get_recent_files',
               return_value=[path] * 9):
        overlay.show()
    assert len(overlay.tiles) == 6


def test_clicking_a_tile_opens_the_board(qapp, view, tmpdir):
    path = str(tmpdir.join('board.bee'))
    save_board(view, path)
    overlay = view.welcome_overlay
    view.open_from_file = MagicMock()
    with patch('beeref.widgets.welcome_overlay.BeeSettings.get_recent_files',
               return_value=[path]):
        overlay.show()
    QTest.mouseClick(overlay.tiles[0], Qt.MouseButton.LeftButton)
    view.open_from_file.assert_called_once_with(path)


def test_tile_without_preview_paints(qapp, tmpdir):
    for path in (str(tmpdir.join('missing.bee')),):
        tile = BoardTile(path, str(tmpdir.join('cache')), MagicMock())
        assert tile.preview.isNull()
        tile.grab()


def test_buttons_open_board_and_add_images(qapp):
    overlay, view = make_overlay(qapp)
    view.on_action_open = MagicMock()
    view.on_action_insert_images = MagicMock()
    overlay.open_button.click()
    overlay.add_images_button.click()
    view.on_action_open.assert_called_once_with()
    view.on_action_insert_images.assert_called_once_with()


def test_previews_are_cached_next_to_the_settings(qapp, settings):
    overlay, _ = make_overlay(qapp)
    assert overlay.cache_dir == os.path.join(
        os.path.dirname(settings.fileName()), 'previews')


@patch('PyQt6.QtWidgets.QGraphicsView.mousePressEvent')
def test_mouse_press_when_move_window_active(mouse_event_mock, qapp):
    overlay, _ = make_overlay(qapp)
    overlay.movewin_active = True
    overlay.mousePressEvent(MagicMock())
    assert overlay.movewin_active is False
    mouse_event_mock.assert_not_called()
