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
    lava = Palette('Lava', [SamplePoint(a, 0.1, 0.5), SamplePoint(b, 0.5, 0.5)],
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
    data = view.scene.palettes.pending
    items = {i.save_id: i for i in view.scene.items_for_save()}
    view.scene.palettes.restore(data, items)
    return view.scene.palettes


def test_schema_version_is_3():
    assert schema.USER_VERSION == 3


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
