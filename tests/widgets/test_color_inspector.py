from PyQt6 import QtGui, QtWidgets

from beeref.items import BeePixmapItem
from beeref.widgets.color_inspector import ColorInspector
from tests.palette.helpers import stripes


def test_values(qtbot):
    inspector = ColorInspector()
    qtbot.addWidget(inspector)
    inspector.set_color(QtGui.QColor(211, 28, 28))
    labels = {k: v.text() for k, v in inspector.value_labels.items()}
    assert labels == {'Hue': '0', 'Saturation': '87', 'Value': '83',
                      'Red': '211', 'Green': '28', 'Blue': '28',
                      'Hex': '#D31C1C'}
    assert inspector.copy_button.isEnabled()


def test_copy_hex(qtbot):
    inspector = ColorInspector()
    qtbot.addWidget(inspector)
    inspector.set_color(QtGui.QColor(211, 28, 28))
    inspector.copy_button.click()
    assert QtWidgets.QApplication.clipboard().text() == '#D31C1C'


def test_empty_state_and_paint(qtbot):
    inspector = ColorInspector()
    qtbot.addWidget(inspector)
    inspector.set_color(None)
    assert not inspector.copy_button.isEnabled()
    assert inspector.value_labels['Hex'].text() == '–'
    inspector.set_color(QtGui.QColor(128, 128, 128))
    assert not inspector.grab().isNull()


def test_panel_follows_selected_point(main_window):
    view = main_window.view
    item = BeePixmapItem(stripes([(211, 28, 28)]))
    view.scene.addItem(item)
    view.palette_controller.extract_into_active(item)
    store = view.palette_controller.store
    store.select_point(store.active.points[0])
    inspector = main_window.palette_sidebar.panel.inspector
    assert inspector.value_labels['Hex'].text() == '#D31C1C'
    store.select_point(None)
    assert inspector.value_labels['Hex'].text() == '–'
