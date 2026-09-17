"""Headless GUI smoke tests: every page builds, navigation works, and the
safety-relevant UI behaviour (confirm dialog gating, simulation default)
holds after the redesign."""
from PySide6.QtWidgets import QDialogButtonBox

from app.config.settings import SIMULATION_MODE_DEFAULT
from app.gui.widgets.confirm_dialog import ConfirmDestructiveDialog


def test_all_pages_exist_in_sidebar_order(window):
    labels = [b.text().replace("&&", "&") for b in window._nav_group.buttons()]
    assert labels == ["Dashboard", "Drive Eraser", "File & Folder Eraser", "Recovery", "Audit Log", "Reports"]
    assert window._stack.count() == 6
    assert window._stack.currentWidget() is window._dashboard


def test_sidebar_and_dashboard_navigation(window, qtbot):
    window._nav_group.button(3).click()
    assert window._stack.currentWidget() is window._recovery
    window._navigate_to("dashboard")
    window._dashboard.navigate_requested.emit("file_eraser")
    assert window._stack.currentWidget() is window._file_eraser
    assert window._nav_group.checkedButton() is window._nav_group.button(2)


def test_fresh_install_shows_empty_states(window):
    dash = window._dashboard
    assert dash._table.rowCount() == 0
    assert not dash._empty.isHidden()
    assert dash._entries_tile._value.text() == "0"
    assert window._reports._list.count() == 0


def test_dashboard_shows_real_ledger_entries_after_refresh(window, tmp_path):
    ledger = window._ledger
    ledger.append_entry("file_erase", "/tmp/example.txt", {"ok": True})
    window._dashboard.refresh()
    assert window._dashboard._table.rowCount() == 1
    assert window._dashboard._table.item(0, 2).text() == "/tmp/example.txt"
    assert window._dashboard._empty.isHidden()
    assert window._dashboard._chain_tile._value.text() == "Intact"


def test_simulation_mode_starts_checked(window):
    assert SIMULATION_MODE_DEFAULT is True
    assert window._drive_eraser._simulation_checkbox.isChecked()


def test_simulation_note_switches_when_toggled(window):
    view = window._drive_eraser
    view._simulation_checkbox.setChecked(False)
    assert view._simulation_on_note.isHidden() and not view._simulation_off_note.isHidden()
    view._simulation_checkbox.setChecked(True)
    assert not view._simulation_on_note.isHidden() and view._simulation_off_note.isHidden()


def test_confirm_dialog_needs_exact_token_and_acknowledgement(qtbot):
    dialog = ConfirmDestructiveDialog("erase 1 file", "ERASE FILES")
    qtbot.addWidget(dialog)
    ok = dialog._buttons.button(QDialogButtonBox.Ok)
    assert not ok.isEnabled()
    dialog._input.setText("ERASE FILES")
    assert not ok.isEnabled()
    dialog._ack.setChecked(True)
    assert ok.isEnabled()
    dialog._input.setText("erase files")
    assert not ok.isEnabled()


def test_file_queue_badge_and_clear(window):
    view = window._file_eraser
    view._queue_list.addItem("/tmp/a.txt")
    view._queue_list.addItem("/tmp/b.txt")
    assert view._count_badge.text() == "2 files"
    assert view._empty_hint.isHidden()
    view._clear_queue()
    assert view._count_badge.text() == "0 files"
    assert not view._empty_hint.isHidden()


def test_recovery_result_tabs_show_counts(window):
    tabs = window._recovery._results_tabs
    assert tabs.tabText(0) == "Recovered Files  (0)"
    assert tabs.tabText(1).startswith("PII / Metadata Artifacts")


def test_file_dialogs_use_the_themed_qt_dialog_on_every_os(window):
    from PySide6.QtWidgets import QApplication, QFileDialog
    from PySide6.QtCore import Qt
    from app.gui.widgets import file_dialogs

    assert QApplication.testAttribute(Qt.AA_DontUseNativeDialogs)
    dialog = file_dialogs._dialog(window, "Pick", QFileDialog.ExistingFile, "Disk images (*.img);;All files (*)")
    assert dialog.testOption(QFileDialog.DontUseNativeDialog)
    assert isinstance(dialog.iconProvider(), file_dialogs.ThemedIconProvider)
    assert dialog.sidebarUrls(), "sidebar should list home folders and drives"
    assert dialog.nameFilters() == ["Disk images (*.img)", "All files (*)"]
    dialog.close()


def test_badges_are_tall_enough_to_stay_rounded(window):
    from app.gui.widgets import ui

    badge = window._file_eraser._count_badge
    assert badge.height() == ui._BADGE_HEIGHT
    assert ui._BADGE_RADIUS * 2 < ui._BADGE_HEIGHT
