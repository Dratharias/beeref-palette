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
