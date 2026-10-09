from PyQt6 import QtCore, QtGui


def stripes(colors, widths=None, height=20):
    """Image of vertical stripes, one per color (RGB tuples or QColors)."""
    widths = widths or [20] * len(colors)
    image = QtGui.QImage(sum(widths), height,
                         QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    x = 0
    for color, width in zip(colors, widths):
        painter.fillRect(x, 0, width, height, QtGui.QColor(*color)
                         if isinstance(color, tuple) else color)
        x += width
    painter.end()
    return image
