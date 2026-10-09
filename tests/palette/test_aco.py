import struct

from PyQt6 import QtGui

from beeref.palette.aco import write_aco
from tests.palette.aco_reader import read_aco


def test_round_trip_default_names(tmpfile):
    write_aco(tmpfile, [QtGui.QColor(211, 28, 28), QtGui.QColor(0, 0, 255)])
    assert read_aco(tmpfile) == [('#D31C1C', (211, 28, 28)),
                                 ('#0000FF', (0, 0, 255))]


def test_custom_names(tmpfile):
    write_aco(tmpfile, [QtGui.QColor(1, 2, 3)], names=['Magma é'])
    assert read_aco(tmpfile) == [('Magma é', (1, 2, 3))]


def test_v1_block_bytes(tmpfile):
    write_aco(tmpfile, [QtGui.QColor(255, 0, 1)])
    with open(tmpfile, 'rb') as f:
        head = f.read(14)
    assert head == struct.pack('>HH5H', 1, 1, 0, 65535, 0, 257, 0)


def test_empty_palette(tmpfile):
    write_aco(tmpfile, [])
    assert read_aco(tmpfile) == []
