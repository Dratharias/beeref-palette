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

"""Dominant, visually distinct colors of an image."""

import numpy as np
from PyQt6 import QtGui
from PyQt6.QtCore import Qt


MAX_SIDE = 64
MIN_DELTA_E = 15.0
MAX_ITERATIONS = 20

_SRGB_TO_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                         [0.2126729, 0.7151522, 0.0721750],
                         [0.0193339, 0.1191920, 0.9503041]])
_WHITE_D65 = np.array([0.95047, 1.0, 1.08883])


def srgb_to_lab(rgb):
    """Convert an (..., 3) uint8 sRGB array to CIE Lab (D65)."""
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = c @ _SRGB_TO_XYZ.T / _WHITE_D65
    eps, kappa = 216 / 24389, 24389 / 27
    f = np.where(xyz > eps, np.cbrt(xyz), (kappa * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], axis=-1)


def _rgba_array(image):
    img = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    w, h = img.width(), img.height()
    raw = img.constBits().asstring(img.sizeInBytes())
    arr = np.frombuffer(raw, np.uint8).reshape(h, img.bytesPerLine())
    return arr[:, :w * 4].reshape(h, w, 4)


def _nearest(points, centroids):
    d2 = ((points[:, None, :] - centroids[None, :, :]) ** 2).sum(-1)
    return np.argmin(d2, axis=1), d2


def _kmeans(points, k, rng):
    """k-means with k-means++ seeding; returns (centroids, labels)."""
    centroids = [points[rng.integers(len(points))]]
    while len(centroids) < k:
        _, d2 = _nearest(points, np.array(centroids))
        weights = d2.min(axis=1)
        total = weights.sum()
        if total == 0:
            break
        centroids.append(points[rng.choice(len(points), p=weights / total)])
    centroids = np.array(centroids)
    for _ in range(MAX_ITERATIONS):
        labels, _ = _nearest(points, centroids)
        updated = np.array([
            points[labels == i].mean(axis=0) if np.any(labels == i)
            else centroids[i]
            for i in range(len(centroids))])
        if np.allclose(updated, centroids):
            break
        centroids = updated
    labels, _ = _nearest(points, centroids)
    return centroids, labels


def extract(image, n, min_delta_e=MIN_DELTA_E):
    """Return up to ``n`` distinct dominant colors of ``image``.

    Each entry is ``(x, y, color)`` with x/y relative to the image (0–1)
    and pointing at a real pixel of that color; largest cluster first.
    """
    if image.isNull() or n < 1:
        return []
    small = image
    if max(image.width(), image.height()) > MAX_SIDE:
        small = image.scaled(MAX_SIDE, MAX_SIDE,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.FastTransformation)
    rgba = _rgba_array(small)
    h, w = rgba.shape[:2]
    ys, xs = np.nonzero(rgba[..., 3] >= 128)
    if len(xs) == 0:
        return []
    rgb = rgba[ys, xs, :3]
    lab = srgb_to_lab(rgb)
    k = min(3 * n, len(np.unique(rgb, axis=0)))
    centroids, labels = _kmeans(lab, k, np.random.default_rng(0))
    sizes = np.bincount(labels, minlength=len(centroids))

    kept = []
    for i in np.argsort(-sizes, kind='stable'):
        if sizes[i] == 0:
            continue
        if all(np.linalg.norm(centroids[i] - centroids[j]) >= min_delta_e
               for j in kept):
            kept.append(i)
            if len(kept) == n:
                break

    result = []
    for i in kept:
        members = np.nonzero(labels == i)[0]
        best = members[np.argmin(((lab[members] - centroids[i]) ** 2).sum(-1))]
        r, g, b = (int(v) for v in rgb[best])
        result.append(((xs[best] + 0.5) / w, (ys[best] + 0.5) / h,
                       QtGui.QColor(r, g, b)))
    return result
