"""Type-to-confirm + acknowledgment dialog for destructive operations.

The OK button stays disabled until the user has typed the exact
confirmation token AND ticked the acknowledgment checkbox — this is the
GUI half of the safety story described in the plan (core-side enforcement
is app.core.devices.safety / the user_confirmed flag on run_drive_erase).
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class ConfirmDestructiveDialog(QDialog):
    def __init__(self, warning_text: str, confirm_token: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Destructive Operation")
        self._confirm_token = confirm_token

        layout = QVBoxLayout(self)

        warning = QLabel(warning_text)
        warning.setWordWrap(True)
        layout.addWidget(warning)

        layout.addWidget(QLabel(f"Type the following to confirm: {confirm_token}"))
        self._input = QLineEdit()
        self._input.textChanged.connect(self._update_ok_state)
        layout.addWidget(self._input)

        self._ack = QCheckBox("I understand this action is irreversible and have selected the correct target.")
        self._ack.stateChanged.connect(self._update_ok_state)
        layout.addWidget(self._ack)

        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._update_ok_state()

    def _update_ok_state(self) -> None:
        ok_enabled = self._input.text() == self._confirm_token and self._ack.isChecked()
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(ok_enabled)

    @staticmethod
    def confirm(parent, warning_text: str, confirm_token: str) -> bool:
        dialog = ConfirmDestructiveDialog(warning_text, confirm_token, parent)
        return dialog.exec() == QDialog.Accepted
