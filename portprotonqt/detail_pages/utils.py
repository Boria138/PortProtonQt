"""Detail page utilities for PortProtonQt."""

import os
from weakref import WeakKeyDictionary
from collections.abc import Callable
from PySide6.QtWidgets import QWidget, QApplication, QLabel, QGraphicsOpacityEffect
from PySide6.QtCore import QTimer, Qt, QObject, Signal, QPropertyAnimation, QByteArray
from PySide6.QtGui import QPixmap

from portprotonqt.image_utils import get_animated_cover_pixmap
from portprotonqt.image_utils import load_pixmap_async, round_corners, set_animated_cover
from portprotonqt.config import (
    extract_exec_target_path,
    favorites_config,
    parse_desktop_entry,
)
from portprotonqt.logger import get_logger

logger = get_logger(__name__)
_pixmap_relays: WeakKeyDictionary[QWidget, "_PixmapReadyRelay"] = WeakKeyDictionary()
_cover_reveal_animations: WeakKeyDictionary[QLabel, QPropertyAnimation] = WeakKeyDictionary()


class _PixmapReadyRelay(QObject):
    """Relay pixmap updates to GUI thread safely."""

    pixmap_ready = Signal(object)


class _AutoinstallCheckRelay(QObject):
    """Relay autoinstall check results to GUI thread safely."""

    result_ready = Signal(bool)


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
        _prepare_cover_reveal(image_label)
        if _set_animated_cover((detail_page, image_label), cover_path, (cover_width, cover_height), main_window):
            return
        load_pixmap_async(
            cover_path,
            cover_width,
            cover_height,
            lambda pixmap: relay.pixmap_ready.emit(pixmap),
        )
    else:
        _apply_no_cover_style(detail_page, main_window.theme)

def _set_animated_cover(
    cover_widgets: tuple[QWidget, QLabel],
    cover_path: str,
    cover_size: tuple[int, int],
    main_window,
) -> bool:
    """Set animated cover on detail page."""
    if not os.path.isfile(cover_path):
        return False
    detail_page, image_label = cover_widgets
    if not set_animated_cover(image_label, cover_path, cover_size[0], cover_size[1], 10):
        return False
    _setup_palette_stylesheet(detail_page, get_animated_cover_pixmap(image_label), main_window)
    _reveal_cover(image_label, main_window.theme)
    return True


def _on_pixmap_ready(pixmap: QPixmap, detail_page: QWidget, image_label: QLabel, main_window) -> None:
    """Handle pixmap loaded callback."""
    if not _is_detail_page_valid(detail_page):
        return
    try:
        rounded = round_corners(pixmap, 10)
        image_label.setPixmap(rounded)
        _reveal_cover(image_label, main_window.theme)
        logger.debug("Pixmap set for imageLabel")
        _setup_palette_stylesheet(detail_page, pixmap, main_window)
    except RuntimeError:
        logger.warning("Detail page already deleted, skipping pixmap update")


def _prepare_cover_reveal(image_label: QLabel) -> None:
    """Hide cover until the loaded pixmap is ready."""
    effect = QGraphicsOpacityEffect(image_label)
    effect.setOpacity(0.0)
    image_label.setGraphicsEffect(effect)


def _reveal_cover(image_label: QLabel, theme) -> None:
    """Show cover smoothly after async loading finishes."""
    effect = image_label.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(image_label)
        image_label.setGraphicsEffect(effect)

    duration = theme.GAME_CARD_ANIMATION.get("detail_page_fade_duration", 350)
    animation = QPropertyAnimation(effect, QByteArray(b"opacity"), image_label)
    animation.setDuration(duration)
    animation.setStartValue(effect.opacity())
    animation.setEndValue(1.0)
    animation.finished.connect(effect.deleteLater)
    animation.finished.connect(lambda: _cover_reveal_animations.pop(image_label, None))
    _cover_reveal_animations[image_label] = animation
    animation.start()


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
        favorite_icon_name = "star_fav"
    else:
        favorites.append(game_name)
        favorite_icon_name = "star_fav_full"
    favorites_config.set_games(favorites)

    if hasattr(main_window, "game_library_manager"):
        main_window.game_library_manager.update_game_grid()

    return favorite_icon_name


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

    autoinstall_exe = _get_autoinstall_exe_name(script_name)
    if not autoinstall_exe:
        return False

    for file in desktop_files:
        if _check_desktop_file(file, portproton_location, autoinstall_exe):
            return True

    return False


def find_autoinstall_entry_path(
    script_name: str,
    portproton_location: str | None,
) -> str | None:
    """Find installed autoinstall desktop entry path."""
    if not portproton_location:
        return None

    try:
        desktop_files = os.listdir(portproton_location)
    except (OSError, AttributeError):
        return None

    autoinstall_exe = _get_autoinstall_exe_name(script_name)
    if not autoinstall_exe:
        return None

    for filename in desktop_files:
        if not _check_desktop_file(filename, portproton_location, autoinstall_exe):
            continue
        return os.path.join(portproton_location, filename)

    return None


def _check_autoinstall_installed_async(
    script_name: str,
    game_name: str,
    portproton_location: str,
    callback: Callable[[bool], None],
) -> None:
    """Asynchronous check for installed autoinstall game."""
    from threading import Thread

    relay = _AutoinstallCheckRelay(QApplication.instance())

    def on_result(result: bool) -> None:
        callback(result)
        relay.deleteLater()

    relay.result_ready.connect(on_result, Qt.ConnectionType.QueuedConnection)

    def worker() -> None:
        result = _check_autoinstall_installed_sync(
            script_name, game_name, portproton_location
        )
        relay.result_ready.emit(result)

    thread = Thread(target=worker, daemon=True)
    thread.start()


def _check_desktop_file(
    filename: str,
    location: str,
    autoinstall_exe: str,
) -> bool:
    """Check if desktop file targets autoinstall exe."""
    if not filename.endswith(".desktop"):
        return False

    desktop_entry = parse_desktop_entry(os.path.join(location, filename))
    if not desktop_entry:
        return False

    exec_path = extract_exec_target_path(desktop_entry.get("Exec", ""))
    if not exec_path:
        return False
    if not os.path.isfile(exec_path):
        return False

    exec_name = os.path.basename(exec_path).lower()
    real_exec_name = os.path.basename(os.path.realpath(exec_path)).lower()
    return autoinstall_exe.lower() in (exec_name, real_exec_name)


def _get_autoinstall_exe_name(script_name: str) -> str:
    script_path = script_name
    if not os.path.isfile(script_path):
        return ""

    install_exe = ""
    try:
        with open(script_path, encoding="utf-8") as script_file:
            for line in script_file:
                if "PW_EXE_FILE" in line:
                    exe_name = _extract_exe_name(line)
                    if exe_name:
                        return exe_name
                if "PW_AUTOINSTALL_EXE" not in line:
                    continue
                exe_name = _extract_exe_name(line)
                if exe_name:
                    install_exe = exe_name
    except OSError:
        return ""

    return install_exe


def _extract_exe_name(line: str) -> str:
    for part in line.replace("\\", "/").split("/"):
        clean_part = part.strip().strip('"\' }')
        if clean_part.lower().endswith(".exe"):
            return clean_part
    return ""
