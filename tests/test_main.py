from unittest.mock import patch, MagicMock

from PyQt6 import QtCore

from beeref.__main__ import BeeRefMainWindow, main
from beeref.assets import BeeAssets
from beeref.view import BeeGraphicsView


@patch('PyQt6.QtWidgets.QWidget.show')
def test_beeref_mainwindow_init(show_mock, qapp):
    window = BeeRefMainWindow(qapp)
    assert window.windowTitle() == 'BeeRef Palette'
    assert BeeAssets().logo == BeeAssets().logo
    assert window.windowIcon()
    assert window.contentsMargins() == QtCore.QMargins(0, 0, 0, 0)
    assert isinstance(window.view, BeeGraphicsView)
    show_mock.assert_called()


@patch('beeref.view.BeeGraphicsView.open_from_file')
def test_beerefapplication_fileopenevent(open_mock, qapp, main_window):
    event = MagicMock()
    event.type.return_value = QtCore.QEvent.Type.FileOpen
    event.file.return_value = 'test.bee'
    assert qapp.event(event) is True
    open_mock.assert_called_once_with('test.bee')


@patch('beeref.__main__.BeeRefApplication')
@patch('beeref.__main__.CommandlineArgs')
@patch('beeref.config.BeeSettings.on_startup')
def test_main(startup_mock, args_mock, app_mock, qapp):
    app_mock.return_value = qapp
    args_mock.return_value.filename = None
    args_mock.return_value.loglevel = 'WARN'
    args_mock.return_value.debug_raise_error = ''

    with patch.object(qapp, 'exec') as exec_mock:
        main()
        exec_mock.assert_called_once_with()

    args_mock.assert_called_once_with(with_check=True)
    startup_mock.assert_called()


def test_mainwindow_default_size_fills_most_of_screen(settings, qapp):
    settings.remove('MainWindow/geometry')
    window = BeeRefMainWindow(qapp)
    available = window.screen().availableGeometry()
    assert window.width() >= int(available.width() * 0.75)
    assert window.height() >= int(available.height() * 0.75)
    window.deleteLater()


def test_mainwindow_saves_geometry_when_app_quits(settings, qapp):
    window = BeeRefMainWindow(qapp)
    window.resize(640, 480)
    settings.remove('MainWindow/geometry')
    qapp.aboutToQuit.emit()
    assert settings.value('MainWindow/geometry') is not None
    window.deleteLater()
