import itertools

import numpy as np
from PyQt6 import QtGui

from beeref.palette.extract import MIN_DELTA_E, extract, srgb_to_lab
from tests.palette.helpers import stripes

RED, GREEN, BLUE = (220, 30, 30), (30, 180, 60), (40, 60, 210)
YELLOW, BLACK, WHITE = (240, 220, 40), (10, 10, 10), (250, 250, 250)


def rgb(color):
    return (color.red(), color.green(), color.blue())


def test_two_colors_requested_six():
    result = extract(stripes([RED, BLUE]), 6)
    assert sorted(rgb(c) for _, _, c in result) == sorted([RED, BLUE])


def test_six_colors():
    colors = [RED, GREEN, BLUE, YELLOW, BLACK, WHITE]
    result = extract(stripes(colors), 6)
    assert sorted(rgb(c) for _, _, c in result) == sorted(colors)


def test_n_smaller_than_distinct_colors():
    colors = [RED, GREEN, BLUE, YELLOW, BLACK, WHITE]
    result = extract(stripes(colors), 3)
    found = [rgb(c) for _, _, c in result]
    assert len(found) == 3
    assert len(set(found)) == 3
    assert set(found) <= set(colors)


def test_largest_cluster_first():
    result = extract(stripes([BLUE, RED], widths=[10, 50]), 2)
    assert rgb(result[0][2]) == RED


def test_deterministic():
    image = stripes([RED, GREEN, BLUE, YELLOW], widths=[13, 29, 7, 41])
    first = [(x, y, rgb(c)) for x, y, c in extract(image, 4)]
    second = [(x, y, rgb(c)) for x, y, c in extract(image, 4)]
    assert first == second


def test_transparent_pixels_ignored():
    image = stripes([RED, (0, 0, 0, 0)])
    result = extract(image, 6)
    assert [rgb(c) for _, _, c in result] == [RED]


def test_near_duplicate_shades_are_not_both_returned():
    near_red = (226, 34, 30)
    result = extract(stripes([RED, near_red, GREEN, BLUE]), 6)
    labs = srgb_to_lab(np.array([rgb(c) for _, _, c in result], np.uint8))
    for a, b in itertools.combinations(labs, 2):
        assert np.linalg.norm(a - b) >= MIN_DELTA_E
    assert len(result) == 3


def test_positions_point_at_pixels_of_that_color():
    image = stripes([RED, GREEN, BLUE], widths=[30, 20, 10])
    for x, y, color in extract(image, 3):
        px = image.pixelColor(int(x * image.width()), int(y * image.height()))
        assert rgb(px) == rgb(color)
        assert 0 <= x <= 1 and 0 <= y <= 1


def test_null_and_fully_transparent_images():
    assert extract(QtGui.QImage(), 6) == []
    assert extract(stripes([(0, 0, 0, 0)]), 6) == []


# Regions: polygons in relative image coordinates (0–1)

LEFT_HALF = [(0, 0), (0.5, 0), (0.5, 1), (0, 1)]


def test_region_limits_colors_to_inside():
    image = stripes([RED, GREEN, BLUE, YELLOW])
    result = extract(image, 6, region=LEFT_HALF)
    assert sorted(rgb(c) for _, _, c in result) == sorted([RED, GREEN])


def test_region_points_lie_inside_region():
    image = stripes([RED, GREEN, BLUE, YELLOW])
    for x, y, _ in extract(image, 6, region=LEFT_HALF):
        assert 0 <= x <= 0.5 and 0 <= y <= 1


def test_region_positions_point_at_pixels_of_that_color():
    image = stripes([RED, GREEN, BLUE, YELLOW], widths=[30, 10, 50, 10])
    region = [(0.35, 0.1), (0.95, 0.1), (0.95, 0.9), (0.35, 0.9)]
    result = extract(image, 6, region=region)
    assert result
    for x, y, color in result:
        pixel = image.pixelColor(int(x * image.width()),
                                 int(y * image.height()))
        assert rgb(pixel) == rgb(color)


def test_triangle_region_excludes_outside_corner():
    # Yellow only fills the top-right corner, outside the triangle
    image = QtGui.QImage(100, 100, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor(*BLUE))
    painter = QtGui.QPainter(image)
    painter.fillRect(80, 0, 20, 20, QtGui.QColor(*YELLOW))
    painter.end()
    triangle = [(0, 0), (0, 1), (1, 1)]
    result = extract(image, 6, region=triangle)
    assert [rgb(c) for _, _, c in result] == [BLUE]


def test_small_region_of_large_image_keeps_detail():
    # A 1% accent inside a tiny region must survive the downscale
    image = QtGui.QImage(4000, 3000, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor(*BLACK))
    painter = QtGui.QPainter(image)
    painter.fillRect(2000, 1500, 40, 40, QtGui.QColor(*RED))
    painter.fillRect(2040, 1500, 40, 40, QtGui.QColor(*GREEN))
    painter.end()
    region = [(0.5, 0.5), (0.52, 0.5), (0.52, 0.5133), (0.5, 0.5133)]
    result = extract(image, 6, region=region)
    assert sorted(rgb(c) for _, _, c in result) == sorted([RED, GREEN])


def test_degenerate_region_returns_nothing():
    image = stripes([RED, GREEN])
    assert extract(image, 6, region=[(0.1, 0.1), (0.2, 0.2)]) == []
    assert extract(image, 6, region=[(0.1, 0.1)] * 3) == []


def test_points_avoid_color_edges():
    # Each point's 3×3 neighbourhood must be its own color, so the
    # averaged swatch is not a mix of two stripes.
    image = stripes([RED, GREEN, BLUE], widths=[40, 40, 40], height=40)
    for x, y, color in extract(image, 6):
        px, py = int(x * image.width()), int(y * image.height())
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                neighbour = image.pixelColor(px + dx, py + dy)
                assert rgb(neighbour) == rgb(color)
