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

"""Adobe Photoshop swatch (.aco) writer.

Read by Photoshop, Clip Studio Paint (as color sets) and other apps that
import .aco files.
"""

import struct


def _color_record(color):
    return struct.pack('>5H', 0, color.red() * 257, color.green() * 257,
                       color.blue() * 257, 0)


def write_aco(path, colors, names=None):
    """Write ``colors`` (QColors) as a v1 + v2 .aco file at ``path``."""
    if names is None:
        names = [color.name().upper() for color in colors]
    data = bytearray(struct.pack('>HH', 1, len(colors)))
    for color in colors:
        data += _color_record(color)
    data += struct.pack('>HH', 2, len(colors))
    for color, name in zip(colors, names):
        encoded = name.encode('utf-16-be')
        data += _color_record(color)
        data += struct.pack('>I', len(encoded) // 2 + 1)
        data += encoded + b'\0\0'
    with open(path, 'wb') as f:
        f.write(data)
