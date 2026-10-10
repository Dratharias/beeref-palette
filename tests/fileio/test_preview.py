import os
import sqlite3
import time
from datetime import datetime
from unittest.mock import patch


from beeref.fileio import save_bee
from beeref.fileio.preview import board_preview, relative_date
from beeref.items import BeePixmapItem
from beeref.palette.model import Palette, SamplePoint
from tests.palette.helpers import stripes

RED, GREEN, BLUE = (220, 30, 30), (30, 180, 60), (40, 60, 210)


def save_board(view, path, palette=True):
    a = BeePixmapItem(stripes([RED, GREEN], height=40))
    b = BeePixmapItem(stripes([BLUE], height=40))
    view.scene.addItem(a)
    view.scene.addItem(b)
    if palette:
        view.scene.palettes.add(Palette('Lava', [
            SamplePoint(a, 0.25, 0.5), SamplePoint(a, 0.75, 0.5),
            SamplePoint(b, 0.5, 0.5)]))
    save_bee(path, view.scene, create_new=True)


def rgb(color):
    return (color.red(), color.green(), color.blue())


def test_preview_has_image_and_first_palette_colors(view, tmpdir):
    path = str(tmpdir.join('board.bee'))
    save_board(view, path)
    image, colors = board_preview(path, str(tmpdir.join('cache')))
    assert not image.isNull()
    assert image.width() <= 320 and image.height() <= 220
    assert [rgb(c) for c in colors] == [RED, GREEN, BLUE]


def test_preview_without_palettes(view, tmpdir):
    path = str(tmpdir.join('board.bee'))
    save_board(view, path, palette=False)
    image, colors = board_preview(path, str(tmpdir.join('cache')))
    assert not image.isNull()
    assert colors == []


def test_preview_of_upstream_file_without_palette_tables(view, tmpdir):
    path = str(tmpdir.join('board.bee'))
    save_board(view, path)
    con = sqlite3.connect(path)
    con.execute('DROP TABLE palette_points')
    con.commit()
    con.close()
    image, colors = board_preview(path, str(tmpdir.join('cache')))
    assert not image.isNull() and colors == []


def test_preview_of_missing_or_broken_file(tmpdir):
    broken = tmpdir.join('broken.bee')
    broken.write('not a database')
    for path in (str(broken), str(tmpdir.join('missing.bee'))):
        image, colors = board_preview(path, str(tmpdir.join('cache')))
        assert image.isNull() and colors == []


def test_preview_is_cached_until_the_file_changes(view, tmpdir):
    path = str(tmpdir.join('board.bee'))
    cache = str(tmpdir.join('cache'))
    save_board(view, path)
    board_preview(path, cache)
    with patch('beeref.fileio.preview.sqlite3.connect') as connect:
        image, colors = board_preview(path, cache)
        connect.assert_not_called()
    assert not image.isNull() and len(colors) == 3
    later = time.time() + 10
    os.utime(path, (later, later))
    with patch('beeref.fileio.preview.sqlite3.connect',
               side_effect=sqlite3.connect) as connect:
        board_preview(path, cache)
        connect.assert_called_once()


def test_relative_date():
    now = datetime(2026, 10, 9, 18, 0)
    assert relative_date(datetime(2026, 10, 9, 8, 0), now) == 'today'
    assert relative_date(datetime(2026, 10, 8, 23, 0), now) == 'yesterday'
    assert relative_date(datetime(2026, 10, 4, 12, 0), now) == '5 days ago'
    assert relative_date(datetime(2026, 8, 1, 12, 0), now) == '2026-08-01'
