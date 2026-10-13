# This file is part of BeeRef.
#
# BeeRef is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BeeRef is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BeeRef.  If not, see <https://www.gnu.org/licenses/>.

"""Color Range: an image shown as flat zones of a palette's colors."""

from dataclasses import dataclass

import numpy as np
from PyQt6 import QtGui
from PyQt6.QtCore import Qt

from beeref.palette.extract import _rgba_array


DEFAULT_LEVEL = 26
FINAL_SIDE = 2048
PREVIEW_SIDE = 512
# Neighborhood radius at level 100, as a fraction of the longer side.
# Larger radii distort the image more than they simplify it.
MAX_RADIUS = 0.0126
PASSES = 2

_RGB_TO_LMS = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                        [0.2119034982, 0.6806995451, 0.1073969566],
                        [0.0883024619, 0.2817188376, 0.6299787005]],
                       np.float32)
_LMS_TO_LAB = np.array([[0.2104542553, 0.7936177850, -0.0040720123],
                        [1.9779984951, -2.4285922050, 0.4505937099],
                        [0.0259040371, 0.7827717662, -0.8086757660]],
                       np.float32)


@dataclass(frozen=True)
class ColorRangeState:
    """An image's Color Range binding: which palette, how simplified."""
    palette: object
    level: int = DEFAULT_LEVEL


@dataclass
class Prepared:
    """An image's OKLab pixels at working resolution."""
    source: QtGui.QImage
    lab: np.ndarray
    mask: np.ndarray


def to_oklab(rgb):
    """Convert an (..., 3) uint8 sRGB array to OKLab."""
    c = rgb.astype(np.float32) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return np.cbrt(c @ _RGB_TO_LMS.T) @ _LMS_TO_LAB.T


def quantize(lab, palette_lab):
    """Index of the nearest palette color for every pixel."""
    best = np.zeros(lab.shape[:2], np.uint16)
    best_dist = np.full(lab.shape[:2], np.inf, np.float32)
    for index, color in enumerate(palette_lab):
        dist = ((lab - color) ** 2).sum(axis=-1)
        closer = dist < best_dist
        best[closer] = index
        best_dist[closer] = dist[closer]
    return best


def _box_sum(values, radius):
    """Sum of ``values`` over the (2r+1)² square around each pixel."""
    size = 2 * radius + 1
    padded = np.pad(values, ((radius + 1, radius), (radius + 1, radius)))
    total = padded.cumsum(axis=0).cumsum(axis=1)
    return (total[size:, size:] - total[:-size, size:]
            - total[size:, :-size] + total[:-size, :-size])


def simplify(labels, k, radius, mask):
    """Majority filter: each opaque pixel takes its neighborhood's most
    frequent label. Transparent pixels do not vote; ties keep the pixel's
    own label."""
    if radius <= 0:
        return labels
    out = labels
    for _ in range(PASSES):
        best = out.copy()
        best_count = np.full(out.shape, -1, np.int32)
        for index in range(k):
            own = out == index
            counts = _box_sum((own & mask).astype(np.int32), radius)
            better = (counts > best_count) | ((counts == best_count) & own)
            best[better] = index
            best_count[better] = counts[better]
        out = np.where(mask, best, out)
    return out


def radius_for(level, long_side):
    return round(level / 100 * MAX_RADIUS * long_side)


def _qimage(rgba):
    rgba = np.ascontiguousarray(rgba)
    h, w = rgba.shape[:2]
    data = rgba.tobytes()  # must outlive the QImage until it is copied
    image = QtGui.QImage(data, w, h, 4 * w,
                         QtGui.QImage.Format.Format_RGBA8888)
    return image.copy()


def prepare(image, max_side):
    """Working-resolution OKLab copy of ``image``."""
    if image.isNull():
        return Prepared(image, np.zeros((0, 0, 3), np.float32),
                        np.zeros((0, 0), bool))
    work = image
    if max(image.width(), image.height()) > max_side:
        work = image.scaled(max_side, max_side,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
    rgba = _rgba_array(work)
    return Prepared(image, to_oklab(rgba[..., :3]), rgba[..., 3] > 0)


def render(prepared, colors, level):
    """The source image as flat zones of ``colors`` (at least one)."""
    if prepared.mask.size == 0:
        return QtGui.QImage(prepared.source)
    h, w = prepared.mask.shape
    palette_rgb = np.array([c.getRgb()[:3] for c in colors], np.uint8)
    labels = quantize(prepared.lab, to_oklab(palette_rgb))
    labels = simplify(labels, len(colors), radius_for(level, max(w, h)),
                      prepared.mask)
    rgba = np.empty((h, w, 4), np.uint8)
    rgba[..., :3] = palette_rgb[labels]
    rgba[..., 3] = 255
    image = _qimage(rgba)
    source = prepared.source
    if image.size() != source.size():
        image = image.scaled(source.size(),
                             Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.FastTransformation)
    full = _rgba_array(image).copy()
    full[..., 3] = _rgba_array(source)[..., 3]
    return _qimage(full)
