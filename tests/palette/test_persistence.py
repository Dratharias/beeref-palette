import sqlite3

from beeref.fileio import load_bee, save_bee, schema
from beeref.items import BeePixmapItem
from beeref.palette.model import Palette, SamplePoint
from tests.palette.helpers import stripes

RED, BLUE = (220, 30, 30), (40, 60, 210)


def board(view):
    a = BeePixmapItem(stripes([RED, BLUE]))
    b = BeePixmapItem(stripes([BLUE]))
    view.scene.addItem(a)
    view.scene.addItem(b)
    store = view.scene.palettes
    lava = Palette('Lava',
                   [SamplePoint(a, 0.1, 0.5), SamplePoint(b, 0.5, 0.5)],
                   source_item=a)
    mood = Palette('Mood', [SamplePoint(a, 0.9, 0.5)])
    store.add(lava)
    store.add(mood)
    store.set_active(mood)
    store.auto_extract = True
    return a, b


def reload(view, filename):
    view.scene.clear()
    load_bee(filename, view.scene)
    view.scene.add_queued_items()
    view.palette_controller.restore_loaded()
    return view.scene.palettes


def test_schema_version_is_4():
    assert schema.USER_VERSION == 4


def test_round_trip(view, tmpfile):
    board(view)
    save_bee(tmpfile, view.scene, create_new=True)
    store = reload(view, tmpfile)
    assert [p.name for p in store.palettes] == ['Lava', 'Mood']
    lava, mood = store.palettes
    assert [(p.x, p.y) for p in lava.points] == [(0.1, 0.5), (0.5, 0.5)]
    assert lava.points[0].item is lava.source_item
    assert lava.points[1].item is not lava.points[0].item
    assert store.active is mood and store.auto_extract


def test_resave_in_place_rewrites_palettes(view, tmpfile):
    board(view)
    save_bee(tmpfile, view.scene, create_new=True)
    view.scene.palettes.remove(view.scene.palettes.palettes[0])
    save_bee(tmpfile, view.scene)
    assert [p.name for p in reload(view, tmpfile).palettes] == ['Mood']


def test_deleted_image_points_not_saved(view, tmpfile):
    a, b = board(view)
    view.scene.removeItem(b)
    save_bee(tmpfile, view.scene, create_new=True)
    lava = reload(view, tmpfile).palettes[0]
    assert len(lava.points) == 1


def test_orphan_rows_from_upstream_are_ignored(view, tmpfile):
    a, b = board(view)
    save_bee(tmpfile, view.scene, create_new=True)
    con = sqlite3.connect(tmpfile)      # upstream deletes items with FKs off
    con.execute('DELETE FROM items WHERE id = ?', (b.save_id,))
    con.commit()
    con.close()
    lava = reload(view, tmpfile).palettes[0]
    assert len(lava.points) == 1


def test_version_2_file_migrates(view, tmpfile):
    con = sqlite3.connect(tmpfile)
    for statement in schema.SCHEMA[:2]:
        con.execute(statement)
    con.execute('PRAGMA user_version=2')
    con.commit()
    con.close()
    store = reload(view, tmpfile)
    assert store.palettes == []


def test_scene_clear_clears_palettes(view):
    board(view)
    view.scene.clear()
    assert view.scene.palettes.palettes == []


def png_bytes(colors):
    from PyQt6 import QtCore
    buf = QtCore.QBuffer()
    buf.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    stripes(colors).save(buf, 'PNG')
    return bytes(buf.data())


def test_points_do_not_follow_a_reused_item_id(view, tmpfile):
    a, b = board(view)
    save_bee(tmpfile, view.scene, create_new=True)
    con = sqlite3.connect(tmpfile)      # upstream: delete b, add an image
    con.execute('DELETE FROM items WHERE id = ?', (b.save_id,))
    con.execute('DELETE FROM sqlar WHERE item_id = ?', (b.save_id,))
    new_id = con.execute(
        "INSERT INTO items (type, x, y, z, scale, rotation, flip, data) "
        "VALUES ('pixmap', 0, 0, 0, 1, 0, 1, json_object('filename', 'g'))"
    ).lastrowid
    data = png_bytes([(30, 180, 60), (90, 90, 90)])
    con.execute('INSERT INTO sqlar (item_id, name, mode, sz, data) '
                'VALUES (?, ?, ?, ?, ?)',
                (new_id, f'{new_id:04}.png', 0o644, len(data), data))
    con.commit()
    con.close()
    assert new_id == b.save_id
    lava = reload(view, tmpfile).palettes[0]
    assert len(lava.points) == 1


def test_points_on_unreadable_image_survive_a_save(view, tmpfile):
    a, b = board(view)
    save_bee(tmpfile, view.scene, create_new=True)
    con = sqlite3.connect(tmpfile)
    con.execute("UPDATE sqlar SET data = x'00' WHERE item_id = ?",
                (b.save_id,))
    con.commit()
    con.close()
    reload(view, tmpfile)
    save_bee(tmpfile, view.scene)
    con = sqlite3.connect(tmpfile)
    rows = con.execute('SELECT item_id FROM palette_points').fetchall()
    con.close()
    assert (b.save_id,) in rows


TRIANGLE = [(0.1, 0.1), (0.9, 0.2), (0.5, 0.9)]


def test_region_round_trip(view, tmpfile):
    a, _ = board(view)
    view.scene.palettes.palettes[0].source_region = TRIANGLE
    save_bee(tmpfile, view.scene, create_new=True)
    store = reload(view, tmpfile)
    assert store.palettes[0].source_region == TRIANGLE
    assert store.palettes[1].source_region is None


def test_region_dropped_with_its_source_image(view, tmpfile):
    a, _ = board(view)
    view.scene.palettes.palettes[0].source_region = TRIANGLE
    view.scene.removeItem(a)
    save_bee(tmpfile, view.scene, create_new=True)
    store = reload(view, tmpfile)
    assert store.palettes[0].source_region is None


def test_version_3_file_migrates_and_keeps_palettes(view, tmpfile):
    a, _ = board(view)
    save_bee(tmpfile, view.scene, create_new=True)
    # Turn the file back into a version 3 file (no region column)
    con = sqlite3.connect(tmpfile)
    con.execute('ALTER TABLE palettes DROP COLUMN source_region')
    con.execute('PRAGMA user_version=3')
    con.commit()
    con.close()
    store = reload(view, tmpfile)
    assert [p.name for p in store.palettes] == ['Lava', 'Mood']
    assert len(store.palettes[0].points) == 2
    con = sqlite3.connect(tmpfile)
    assert con.execute('PRAGMA user_version').fetchone()[0] == 4
