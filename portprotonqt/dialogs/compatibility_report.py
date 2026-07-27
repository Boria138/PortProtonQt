"""Compatibility report dialog."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.dialogs.base import DraggableDialog
from portprotonqt.localization import _


class CompatibilityReportDialog(DraggableDialog):
    """Display a readable compatibility report."""

    def __init__(self, parent, theme, report: str) -> None:
        super().__init__(parent)
        metrics = theme.COMPATIBILITY_REPORT_DIALOG
        self.setWindowTitle(_("Compatibility report"))
        self.setModal(True)
        self.setMinimumSize(metrics["minimum_width"], metrics["minimum_height"])
        self.setStyleSheet(
            theme.MAIN_WINDOW_STYLE + theme.COMPATIBILITY_REPORT_DIALOG_STYLE
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*([metrics["margin"]] * 4))
        layout.setSpacing(metrics["spacing"])
        layout.addWidget(self._create_header())

        report_view = QPlainTextEdit()
        report_view.setObjectName("compatibilityReport")
        report_view.setReadOnly(True)
        report_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        report_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        report_view.setStyleSheet(theme.SCROLL_STYLE)
        report_view.setPlainText(report)
        report_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        report_view.customContextMenuRequested.connect(
            lambda position: self._show_context_menu(report_view, theme, position)
        )
        layout.addWidget(report_view, stretch=1)
        layout.addLayout(self._create_buttons(theme))

    def _create_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("compatibilityHeader")
        layout = QVBoxLayout(header)
        title = QLabel(_("Compatibility report"))
        title.setObjectName("compatibilityTitle")
        summary = QLabel(
            _("The program stopped. Compatibility details were collected automatically.")
        )
        summary.setObjectName("compatibilitySummary")
        summary.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(summary)
        return header

    def _create_buttons(self, theme) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addStretch()
        close_button = AutoSizeButton(_("Close"))
        close_button.setStyleSheet(theme.ACTION_BUTTON_ACTIVE_STYLE)
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)
        layout.addWidget(close_button)
        return layout

    def _show_context_menu(
        self, report_view: QPlainTextEdit, theme: Any, position: QPoint
    ) -> None:
        menu = report_view.createStandardContextMenu()
        menu.setWindowFlags(
            menu.windowFlags()
            | Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
        )
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        menu.setStyleSheet(theme.CONTEXT_MENU_STYLE)
        menu.exec(report_view.viewport().mapToGlobal(position))
