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

"""Small previews of .bee boards for the welcome screen."""

from datetime import datetime
import hashlib
import logging
import os
import sqlite3

from PyQt6 import QtCore, QtGui


logger = logging.getLogger(__name__)

WIDTH = 320
HEIGHT = 200
MAX_IMAGES = 4
MAX_COLORS = 12
BACKGROUND = QtGui.QColor(30, 30, 30)


def relative_date(when, now=None):
    now = now or datetime.now()
    days = (now.date() - when.date()).days
    if days <= 0:
        return 'today'
    if days == 1:
        return 'yesterday'
    if days < 7:
        return f'{days} days ago'
    return when.strftime('%Y-%m-%d')


def _cells(count):
    """Cell rects of the mosaic for 1–4 images."""
    if count == 1:
        return [QtCore.QRect(0, 0, WIDTH, HEIGHT)]
    if count == 2:
        half = WIDTH // 2
        return [QtCore.QRect(0, 0, half, HEIGHT),
                QtCore.QRect(half, 0, WIDTH - half, HEIGHT)]
    w, h = WIDTH // 2, HEIGHT // 2
    rects = [QtCore.QRect(0, 0, w, h), QtCore.QRect(w, 0, WIDTH - w, h),
             QtCore.QRect(0, h, w, HEIGHT - h),
             QtCore.QRect(w, h, WIDTH - w, HEIGHT - h)]
    if count == 3:
        # The first (topmost) image takes the whole left column
        return [QtCore.QRect(0, 0, w, HEIGHT)] + rects[1::2]
    return rects


def _decode(blob, cell):
    """Decode an image scaled down to cover ``cell``, cropped to it."""
    buffer = QtCore.QBuffer()
    buffer.setData(QtCore.QByteArray(blob))
    buffer.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
    reader = QtGui.QImageReader(buffer)
    size = reader.size()
    if size.isValid() and size.width() > 0 and size.height() > 0:
        scale = max(cell.width() / size.width(),
                    cell.height() / size.height())
        if scale < 1:
            reader.setScaledSize(QtCore.QSize(
                max(1, round(size.width() * scale)),
                max(1, round(size.height() * scale))))
    image = reader.read()
    if image.isNull():
        return image
    image = image.scaled(
        cell.size(), QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        QtCore.Qt.TransformationMode.SmoothTransformation)
    x = (image.width() - cell.width()) // 2
    y = (image.height() - cell.height()) // 2
    return image.copy(x, y, cell.width(), cell.height())


def _read(path):
    uri = f'file:{path}?mode=ro'
    con = sqlite3.connect(uri, uri=True)
    try:
        blobs = [row[0] for row in con.execute(
            'SELECT sqlar.data FROM sqlar JOIN items '
            'ON sqlar.item_id = items.id ORDER BY items.z DESC LIMIT ?',
            (MAX_IMAGES,))]
        try:
            colors = [QtGui.QColor(row[0]) for row in con.execute(
                'SELECT pp.color FROM palette_points pp '
                'JOIN palettes p ON p.id = pp.palette_id '
                'WHERE p.position = (SELECT MIN(position) FROM palettes) '
                'ORDER BY pp.position LIMIT ?', (MAX_COLORS,))]
        except sqlite3.Error:
            colors = []
    finally:
        con.close()
    image = QtGui.QImage(WIDTH, HEIGHT, QtGui.QImage.Format.Format_RGB32)
    image.fill(BACKGROUND)
    painter = QtGui.QPainter(image)
    for blob, cell in zip(blobs, _cells(len(blobs))):
        painter.drawImage(cell.topLeft(), _decode(blob, cell))
    painter.end()
    return (image if blobs else QtGui.QImage()), colors


def _cache_file(path, cache_dir):
    key = hashlib.sha1(os.path.abspath(path).encode()).hexdigest()
    return os.path.join(cache_dir, f'{key}.png')


def board_preview(path, cache_dir):
    """(mosaic QImage, first palette's QColors) of a board.

    Cached as PNG in ``cache_dir`` until the board file changes. A
    missing or unreadable board gives a null image and no colors.
    """
    try:
        stamp = str(os.stat(path).st_mtime_ns)
    except OSError:
        return QtGui.QImage(), []
    cached_path = _cache_file(path, cache_dir)
    cached = QtGui.QImage(cached_path)
    if not cached.isNull() and cached.text('mtime') == stamp:
        names = cached.text('colors')
        return cached, [QtGui.QColor(n) for n in names.split()]
    try:
        image, colors = _read(path)
    except sqlite3.Error as e:
        logger.debug(f'No preview for {path}: {e}')
        return QtGui.QImage(), []
    if not image.isNull():
        image.setText('mtime', stamp)
        image.setText('colors', ' '.join(c.name() for c in colors))
        os.makedirs(cache_dir, exist_ok=True)
        if not image.save(cached_path, 'PNG'):
            logger.debug(f'Could not cache preview {cached_path}')
    return image, colors
