"""Detail page utilities for PortProtonQt."""

import os
from weakref import WeakKeyDictionary
from collections.abc import Callable
from PySide6.QtWidgets import QWidget, QApplication, QLabel
from PySide6.QtCore import QTimer, Qt, QObject, Signal
from PySide6.QtGui import QPixmap

from portprotonqt.image_utils import load_pixmap_async, round_corners
from portprotonqt.config import favorites_config
from portprotonqt.logger import get_logger

logger = get_logger(__name__)
_pixmap_relays: WeakKeyDictionary[QWidget, "_PixmapReadyRelay"] = WeakKeyDictionary()


class _PixmapReadyRelay(QObject):
    """Relay pixmap updates to GUI thread safely."""

    pixmap_ready = Signal(object)


def setup_image_loading(
    detail_page: QWidget,
    image_label: QLabel,
    cover_path: str | None,
    main_window,
    cover_width: int = 300,
    cover_height: int = 450,
) -> None:
    """Setup async image loading with palette-based stylesheet."""
    relay = _PixmapReadyRelay(detail_page)
    relay.pixmap_ready.connect(
        lambda pixmap: _on_pixmap_ready(pixmap, detail_page, image_label, main_window),
        Qt.ConnectionType.QueuedConnection,
    )
    _pixmap_relays[detail_page] = relay

    if cover_path:
        load_pixmap_async(
            cover_path,
            cover_width,
            cover_height,
            lambda pixmap: relay.pixmap_ready.emit(pixmap),
        )
    else:
        _apply_no_cover_style(detail_page, main_window.theme)


def _on_pixmap_ready(pixmap: QPixmap, detail_page: QWidget, image_label: QLabel, main_window) -> None:
    """Handle pixmap loaded callback."""
    if not _is_detail_page_valid(detail_page):
        return
    try:
        rounded = round_corners(pixmap, 10)
        image_label.setPixmap(rounded)
        logger.debug("Pixmap set for imageLabel")
        _setup_palette_stylesheet(detail_page, pixmap, main_window)
    except RuntimeError:
        logger.warning("Detail page already deleted, skipping pixmap update")


def _setup_palette_stylesheet(detail_page: QWidget, pixmap: QPixmap | None, main_window) -> None:
    """Setup palette-based stylesheet after image load."""
    if pixmap is None:
        return

    def on_palette_ready(palette: list) -> None:
        _on_palette_ready(palette, detail_page, main_window)

    main_window.getColorPalette_from_pixmap(pixmap, num_colors=5, callback=on_palette_ready)


def _on_palette_ready(palette: list, detail_page: QWidget, main_window) -> None:
    """Handle palette ready callback."""
    if not _is_detail_page_valid(detail_page):
        return
    _apply_palette_stylesheet(detail_page, palette, main_window)


def _apply_palette_stylesheet(detail_page: QWidget, palette: list, main_window) -> None:
    """Apply palette-based stylesheet to detail page."""
    try:
        dark_palette = [
            main_window.darkenColor(color, factor=200) for color in palette
        ]
        stops = ",\n".join(
            [
                f"stop:{i/(len(dark_palette)-1):.2f} {dark_palette[i].name()}"
                for i in range(len(dark_palette))
            ]
        )
        detail_page.setStyleSheet(main_window.theme.detail_page_style(stops))
        detail_page.update()
        logger.debug("Stylesheet updated with palette")
    except RuntimeError:
        logger.warning("Detail page already deleted, skipping palette update")


def _apply_no_cover_style(detail_page: QWidget, theme) -> None:
    """Apply no-cover stylesheet to detail page."""
    try:
        detail_page.setStyleSheet(theme.DETAIL_PAGE_NO_COVER_STYLE)
        detail_page.update()
    except RuntimeError:
        logger.warning("Detail page already deleted, skipping no-cover stylesheet update")


def _is_detail_page_valid(detail_page: QWidget) -> bool:
    """Check if detail page is still valid and visible."""
    return (
        detail_page is not None
        and not detail_page.isHidden()
        and detail_page.parent() is not None
    )


def validate_detail_page(detail_page: QWidget) -> bool:
    """Validate detail page before operations."""
    if not _is_detail_page_valid(detail_page):
        logger.warning("Detail page is None, hidden, or no longer valid")
        return False
    return True


def set_opacity_safe(detail_page: QWidget) -> bool:
    """Safely set window opacity on detail page."""
    try:
        detail_page.setWindowOpacity(1.0)
        return True
    except RuntimeError:
        logger.warning("Detail page is None, hidden, or no longer valid, skipping opacity set")
        return False


def create_focus_helper(
    detail_page: QWidget,
    main_window,
    button: QWidget,
    stacked_widget,
) -> Callable[[], None]:
    """Create focus helper function for detail page buttons."""

    def try_set_focus() -> None:
        if not (button and not button.isHidden()):
            return

        stacked_widget.setCurrentWidget(detail_page)
        detail_page.setFocus(Qt.FocusReason.OtherFocusReason)
        button.setFocus(Qt.FocusReason.OtherFocusReason)
        button.update()
        detail_page.raise_()
        main_window.activateWindow()

        if button.hasFocus():
            logger.debug("Button successfully received focus")
        else:
            logger.debug("Retrying focus...")
            QTimer.singleShot(20, retry_focus)

    def retry_focus() -> None:
        if not (button and not button.isHidden() and not button.hasFocus()):
            return

        QApplication.processEvents()
        main_window.activateWindow()
        stacked_widget.setCurrentWidget(detail_page)
        detail_page.raise_()
        button.setFocus(Qt.FocusReason.OtherFocusReason)
        button.update()

        if not button.hasFocus():
            logger.debug("Final retry...")
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setFocus(Qt.FocusReason.OtherFocusReason)
            QApplication.processEvents()

            if button.hasFocus():
                logger.debug("Button received focus after final retry")
            else:
                logger.debug("Button still doesn't have focus")

    return try_set_focus


def toggle_favorite(game_name: str, main_window) -> str:
    """Toggle favorite status for a game."""
    favorites = favorites_config.get_games()
    if game_name in favorites:
        favorites.remove(game_name)
        favorite_text = "☆"
    else:
        favorites.append(game_name)
        favorite_text = "★"
    favorites_config.set_games(favorites)

    if hasattr(main_window, "game_library_manager"):
        main_window.game_library_manager.update_game_grid()

    return favorite_text


def check_autoinstall_installed(
    script_name: str,
    game_name: str,
    portproton_location: str | None,
    callback: Callable[..., None] | None = None,
) -> bool | None:
    """Check if auto-install game is already installed.

    If callback is provided, runs asynchronously and calls callback with result.
    If callback is None, runs synchronously and returns result.
    """
    if not portproton_location:
        if callback:
            callback(False)
            return None
        return False

    if callback:
        _check_autoinstall_installed_async(
            script_name, game_name, portproton_location, callback
        )
        return None

    return _check_autoinstall_installed_sync(
        script_name, game_name, portproton_location
    )


def _check_autoinstall_installed_sync(
    script_name: str,
    game_name: str,
    portproton_location: str,
) -> bool:
    """Synchronous check for installed autoinstall game."""
    try:
        desktop_files = os.listdir(portproton_location)
    except (OSError, AttributeError):
        return False

    for file in desktop_files:
        if _check_desktop_file(file, portproton_location, script_name, game_name):
            return True

    return False


def _check_autoinstall_installed_async(
    script_name: str,
    game_name: str,
    portproton_location: str,
    callback: Callable[[bool], None],
) -> None:
    """Asynchronous check for installed autoinstall game."""
    from threading import Thread
    from PySide6.QtCore import QTimer

    def worker() -> None:
        result = _check_autoinstall_installed_sync(
            script_name, game_name, portproton_location
        )
        QTimer.singleShot(0, lambda: callback(result))

    thread = Thread(target=worker, daemon=True)
    thread.start()


def _check_desktop_file(
    filename: str,
    location: str,
    script_name: str,
    game_name: str,
) -> bool:
    """Check if desktop file contains script or game name."""
    if not filename.endswith(".desktop"):
        return False

    try:
        with open(os.path.join(location, filename), encoding="utf-8") as f:
            content = f.read()
            return (
                script_name.lower() in content.lower()
                or game_name.lower() in content.lower()
            )
    except (OSError, UnicodeDecodeError):
        return False
