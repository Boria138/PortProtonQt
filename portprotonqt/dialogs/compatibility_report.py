"""Compatibility report dialog."""

from __future__ import annotations

from typing import Any
import os

import orjson

from PySide6.QtCore import QIODevice, QPoint, QSaveFile, Qt, QUrl
from PySide6.QtNetwork import (
    QNetworkAccessManager, QNetworkDiskCache, QNetworkProxy, QNetworkReply, QNetworkRequest,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.config import CACHE_DIR, proxy_config, ui_config
from portprotonqt.dialogs.base import DraggableDialog
from portprotonqt.localization import _
from portprotonqt.logger import get_logger

logger = get_logger(__name__)


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
        self.ppdb_button = AutoSizeButton(_("Download") + " PPDB")
        self.ppdb_button.setStyleSheet(theme.ACTION_BUTTON_STYLE)
        self.ppdb_button.hide()
        self.ppdb_button.clicked.connect(self._download_ppdb)
        layout.addWidget(self.ppdb_button)
        close_button = AutoSizeButton(_("Close"))
        close_button.setStyleSheet(theme.ACTION_BUTTON_ACTIVE_STYLE)
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)
        layout.addWidget(close_button)
        return layout

    def check_ppdb(self, executable: str) -> None:
        if ui_config.get_auto_download_ppdb() or not os.path.isfile(executable):
            return
        self.ppdb_path = executable + ".ppdb"
        self.ppdb_network = QNetworkAccessManager(self)
        self.finished.connect(self.ppdb_network.deleteLater)
        self.ppdb_network.setTransferTimeout(
            QNetworkRequest.TransferTimeoutConstant.DefaultTransferTimeoutConstant.value
        )
        cache = QNetworkDiskCache(self.ppdb_network)
        cache.setCacheDirectory(str(CACHE_DIR / "ppdb_lookup"))
        self.ppdb_network.setCache(cache)
        proxies = proxy_config.get_proxy() or {}
        proxy_url = QUrl(proxies.get("https") or proxies.get("http") or "")
        if proxy_url.host():
            proxy_type = (QNetworkProxy.ProxyType.Socks5Proxy
                          if proxy_url.scheme().startswith("socks")
                          else QNetworkProxy.ProxyType.HttpProxy)
            self.ppdb_network.setProxy(QNetworkProxy(
                proxy_type, proxy_url.host(), max(proxy_url.port(), 0),
                proxy_url.userName(), proxy_url.password(),
            ))
        url = QUrl("https://linux-gaming.ru/api/lookup/exe/")
        url.setPath(url.path() + os.path.basename(executable))
        reply = self.ppdb_network.get(QNetworkRequest(url))
        reply.finished.connect(lambda: self._ppdb_lookup_finished(reply))

    def _ppdb_lookup_finished(self, reply: QNetworkReply) -> None:
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            logger.warning("PPDB lookup failed: %s", reply.errorString())
            return
        try:
            metadata = orjson.loads(bytes(reply.readAll().data()))
        except ValueError as error:
            logger.warning("Invalid PPDB metadata: %s", error)
            return
        if not isinstance(metadata, dict):
            return
        url = metadata.get("ppdb_url")
        if not isinstance(url, str):
            return
        self.ppdb_url = QUrl(url)
        if self.ppdb_url.scheme() in {"https", "http"} and self.ppdb_url.host():
            self.ppdb_button.show()

    def _download_ppdb(self) -> None:
        self.ppdb_button.setEnabled(False)
        self.ppdb_button.setText(_("Downloading…"))
        request = QNetworkRequest(self.ppdb_url)
        request.setAttribute(
            QNetworkRequest.Attribute.CacheLoadControlAttribute,
            QNetworkRequest.CacheLoadControl.AlwaysNetwork,
        )
        reply = self.ppdb_network.get(request)
        reply.finished.connect(lambda: self._ppdb_download_finished(reply))

    def _ppdb_download_finished(self, reply: QNetworkReply) -> None:
        reply.deleteLater()
        self.ppdb_button.setText(_("Download") + " PPDB")
        self.ppdb_button.setEnabled(True)
        if reply.error() != QNetworkReply.NetworkError.NoError:
            logger.warning("PPDB download failed: %s", reply.errorString())
            self.ppdb_button.setText(_("Download process failed"))
            return
        destination = QSaveFile(self.ppdb_path)
        data = reply.readAll()
        if (data.isEmpty() or not destination.open(QIODevice.OpenModeFlag.WriteOnly)
                or destination.write(data) != data.size() or not destination.commit()):
            logger.warning("Failed to save PPDB: %s", destination.errorString())
            self.ppdb_button.setText(_("Download process failed"))
            return
        self.ppdb_button.setText(_("Downloading Complete"))
        self.ppdb_button.setEnabled(False)

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
