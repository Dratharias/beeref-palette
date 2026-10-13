import numpy as np
from PyQt6 import QtCore, QtGui

from beeref.palette import color_range as cr
from tests.palette.helpers import stripes

RED, MAUVE, BLUE = (220, 30, 30), (200, 40, 60), (40, 60, 210)


def qcolors(*colors):
    return [QtGui.QColor(*c) for c in colors]


def pixel(image, x, y):
    return image.pixelColor(x, y).getRgb()


def test_to_oklab_reference_values():
    rgb = np.array([[255, 255, 255], [0, 0, 0], [255, 0, 0]], np.uint8)
    lab = cr.to_oklab(rgb)
    np.testing.assert_allclose(lab[0], [1, 0, 0], atol=1e-3)
    np.testing.assert_allclose(lab[1], [0, 0, 0], atol=1e-6)
    np.testing.assert_allclose(lab[2], [0.62796, 0.22486, 0.12585], atol=1e-3)


def test_quantize_picks_nearest_palette_color():
    lab = cr.to_oklab(np.array([[RED, MAUVE, BLUE]], np.uint8))
    palette = cr.to_oklab(np.array([RED, BLUE], np.uint8))
    assert cr.quantize(lab, palette).tolist() == [[0, 0, 1]]


def test_quantize_tie_goes_to_first_color():
    lab = cr.to_oklab(np.array([[RED]], np.uint8))
    palette = cr.to_oklab(np.array([RED, RED], np.uint8))
    assert cr.quantize(lab, palette).tolist() == [[0]]


def test_simplify_radius_zero_is_identity():
    labels = np.array([[0, 1], [1, 0]], np.uint16)
    out = cr.simplify(labels, 2, 0, np.ones((2, 2), bool))
    assert out.tolist() == labels.tolist()


def test_simplify_absorbs_small_island():
    labels = np.zeros((21, 21), np.uint16)
    labels[10, 10] = 1
    out = cr.simplify(labels, 2, 1, np.ones((21, 21), bool))
    assert not out.any()


def test_simplify_keeps_large_zones():
    labels = np.zeros((21, 21), np.uint16)
    labels[:, 10:] = 1
    out = cr.simplify(labels, 2, 1, np.ones((21, 21), bool))
    assert out.tolist() == labels.tolist()


def test_simplify_transparent_pixels_do_not_vote():
    labels = np.ones((3, 3), np.uint16)
    labels[1, 1] = 0
    mask = np.zeros((3, 3), bool)
    mask[1, 1] = True
    out = cr.simplify(labels, 2, 1, mask)
    assert out.tolist() == labels.tolist()


def test_radius_for():
    assert cr.radius_for(0, 2048) == 0
    assert cr.radius_for(100, 1000) == 30
    assert cr.radius_for(50, 2048) == 31


def test_render_maps_to_palette_colors_and_keeps_size():
    image = stripes([RED, MAUVE, BLUE])
    result = cr.render(cr.prepare(image, cr.FINAL_SIDE), qcolors(RED, BLUE), 0)
    assert result.size() == image.size()
    assert pixel(result, 5, 5) == (*RED, 255)
    assert pixel(result, 30, 5) == (*RED, 255)
    assert pixel(result, 50, 5) == (*BLUE, 255)


def test_render_one_color_palette_is_flat():
    image = stripes([RED, BLUE])
    result = cr.render(cr.prepare(image, cr.FINAL_SIDE), qcolors(BLUE), 50)
    assert {pixel(result, x, 5) for x in range(40)} == {(*BLUE, 255)}


def test_render_preserves_alpha():
    image = QtGui.QImage(10, 10, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.fillRect(0, 0, 5, 10, QtGui.QColor(*RED))
    painter.end()
    result = cr.render(cr.prepare(image, cr.FINAL_SIDE), qcolors(BLUE), 0)
    assert pixel(result, 2, 5) == (*BLUE, 255)
    assert result.pixelColor(7, 5).alpha() == 0


def test_render_fully_transparent_image():
    image = QtGui.QImage(8, 8, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    result = cr.render(cr.prepare(image, cr.FINAL_SIDE), qcolors(RED), 50)
    assert result.size() == image.size()
    assert result.pixelColor(4, 4).alpha() == 0


def test_null_image_renders_as_is():
    prepared = cr.prepare(QtGui.QImage(), cr.PREVIEW_SIDE)
    assert cr.render(prepared, qcolors(RED), 50).isNull()


def test_prepare_caps_working_size():
    image = stripes([RED, BLUE], widths=[1500, 1500], height=30)
    prepared = cr.prepare(image, cr.FINAL_SIDE)
    assert prepared.lab.shape[1] == 2048
    result = cr.render(prepared, qcolors(RED, BLUE), 30)
    assert result.size() == image.size()


def test_preview_and_final_agree_on_large_zones():
    image = stripes([RED, BLUE], widths=[400, 400], height=100)
    preview = cr.render(cr.prepare(image, cr.PREVIEW_SIDE), qcolors(RED, BLUE), 50)
    final = cr.render(cr.prepare(image, cr.FINAL_SIDE), qcolors(RED, BLUE), 50)
    for x in (100, 700):
        assert pixel(preview, x, 50) == pixel(final, x, 50)
