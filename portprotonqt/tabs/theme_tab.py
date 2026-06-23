import os
import shutil
import tarfile
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

import requests

from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from portprotonqt.config.base import THEMES_DIRS
from portprotonqt.config import load_theme_metainfo, ui_config, window_config
from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.downloader import get_requests_session
from portprotonqt.image_utils import ImageCarousel
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.theme_manager import load_theme_screenshots
from portprotonqt.tray_manager import restart_application_process

logger = get_logger(__name__)
THEME_STORE_ITEM = _("Theme Store…")
THEME_STORE_API_URL = "https://ppdb.linux-gaming.ru/api/ppqt/themes"
THEME_STORE_TIMEOUT = 20
THEME_STORE_DOWNLOAD_TIMEOUT = 60
THEME_STORE_IMAGE_WORKERS = 8
THEME_STORE_CARD_BATCH_SIZE = 20
THEME_STORE_VOTES_ICON = "★"
THEME_STORE_DOWNLOADS_ICON = "⇩"


def _theme_store_download_url(theme_id: int) -> str:
    return f"{THEME_STORE_API_URL}/{theme_id}/download"


def _theme_store_preview_urls(theme_data: dict) -> list[str]:
    raw_urls = (
        theme_data.get("dark_screenshot_urls")
        or theme_data.get("screenshot_urls")
        or theme_data.get("light_screenshot_urls")
        or []
    )
    return [_theme_store_absolute_url(url) for url in raw_urls if isinstance(url, str)]


def _theme_store_variant_urls(theme_data: dict, variant: str) -> list[str]:
    if variant == "light":
        raw_urls = theme_data.get("light_screenshot_urls") or []
    else:
        raw_urls = theme_data.get("dark_screenshot_urls") or []
    if not raw_urls:
        raw_urls = theme_data.get("screenshot_urls") or []
    return [_theme_store_absolute_url(url) for url in raw_urls if isinstance(url, str)]


def _theme_store_absolute_url(url: str) -> str:
    if url.startswith("http"):
        return url
    return f"https://ppdb.linux-gaming.ru/{url.lstrip('/')}"


def _safe_theme_entry_name(name: str) -> bool:
    if not name or os.path.isabs(name):
        return False
    if os.sep in name or (os.altsep and os.altsep in name):
        return False
    return os.path.normpath(name) == name and name not in (".", "..")


def _is_safe_archive_path(target_dir: str, member_name: str) -> bool:
    target_root = os.path.realpath(target_dir)
    member_path = os.path.realpath(os.path.join(target_dir, member_name))
    return member_path.startswith(target_root + os.sep)


def _safe_extract_zip(zip_path: str, target_dir: str) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if not _is_safe_archive_path(target_dir, member.filename):
                raise ValueError("Theme archive contains unsafe paths")
        archive.extractall(target_dir)


def _safe_extract_tar(tar_path: str, target_dir: str) -> None:
    with tarfile.open(tar_path) as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                raise ValueError("Theme archive contains links")
            if not _is_safe_archive_path(target_dir, member.name):
                raise ValueError("Theme archive contains unsafe paths")
        archive.extractall(target_dir)


def _safe_extract_archive(archive_path: str, target_dir: str) -> None:
    if zipfile.is_zipfile(archive_path):
        _safe_extract_zip(archive_path, target_dir)
        return
    if tarfile.is_tarfile(archive_path):
        _safe_extract_tar(archive_path, target_dir)
        return
    raise ValueError("Unsupported theme archive format")


def _find_theme_dirs(root_dir: str) -> list[str]:
    if os.path.exists(os.path.join(root_dir, "styles.py")):
        return [root_dir]

    theme_dirs = []
    for entry in os.listdir(root_dir):
        entry_path = os.path.join(root_dir, entry)
        if os.path.isdir(entry_path) and os.path.exists(os.path.join(entry_path, "styles.py")):
            theme_dirs.append(entry_path)
    return theme_dirs


def _install_theme_archive(archive_path: str) -> list[str]:
    user_themes_dir = str(THEMES_DIRS[0])
    installed_names = []
    os.makedirs(user_themes_dir, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ppqt-theme-") as temp_dir:
        _safe_extract_archive(archive_path, temp_dir)
        for source_dir in _find_theme_dirs(temp_dir):
            theme_name = os.path.basename(source_dir)
            if not _safe_theme_entry_name(theme_name):
                logger.warning("Skipping unsafe theme name: %s", theme_name)
                continue
            target_dir = os.path.join(user_themes_dir, theme_name)
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            shutil.move(source_dir, target_dir)
            installed_names.append(theme_name)
    return installed_names


class ThemeStoreListWorker(QThread):
    loaded = Signal(list)
    failed = Signal(str)

    def __init__(self, sort_key: str = "votes", order_key: str = "desc"):
        super().__init__()
        self.sort_key = sort_key
        self.order_key = order_key

    def run(self) -> None:
        session = get_requests_session()
        try:
            response = session.get(
                THEME_STORE_API_URL,
                params={"sort": self.sort_key, "order": self.order_key},
                timeout=THEME_STORE_TIMEOUT,
            )
            response.raise_for_status()
            self.loaded.emit(response.json().get("themes", []))
        except (ValueError, requests.RequestException) as error:
            self.failed.emit(str(error))
        finally:
            session.close()


class ThemeStoreImageWorker(QThread):
    loaded = Signal(str, bytes)

    def __init__(self, urls: list[str]):
        super().__init__()
        self.urls = urls
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        session = get_requests_session()
        try:
            with ThreadPoolExecutor(max_workers=THEME_STORE_IMAGE_WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_image, session, url): url
                    for url in self.urls
                }
                for future in as_completed(futures):
                    if self._cancelled:
                        break
                    url = futures[future]
                    data = future.result()
                    if data:
                        self.loaded.emit(url, data)
        finally:
            session.close()

    def _fetch_image(self, session: requests.Session, url: str) -> bytes | None:
        try:
            response = session.get(url, timeout=THEME_STORE_TIMEOUT)
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            logger.warning("Failed to load theme preview %s: %s", url, error)
            return None


class ThemeStoreDetailImageWorker(QThread):
    image_loaded = Signal(int, bytes)

    def __init__(self, urls: list[str]):
        super().__init__()
        self.urls = urls
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        session = get_requests_session()
        try:
            with ThreadPoolExecutor(max_workers=THEME_STORE_IMAGE_WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_image, session, url): index
                    for index, url in enumerate(self.urls)
                }
                for future in as_completed(futures):
                    if self._cancelled:
                        break
                    index = futures[future]
                    image = future.result()
                    if image:
                        self.image_loaded.emit(index, image)
        finally:
            session.close()

    def _fetch_image(self, session: requests.Session, url: str) -> bytes | None:
        try:
            response = session.get(url, timeout=THEME_STORE_TIMEOUT)
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            logger.warning("Failed to load theme screenshot %s: %s", url, error)
            return None


class ThemeStoreDownloadWorker(QThread):
    installed = Signal(list)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, theme_id: int):
        super().__init__()
        self.theme_id = theme_id
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        archive_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as archive:
                archive_path = archive.name
            self._download_archive(archive_path)
            if not self._cancelled:
                self.installed.emit(_install_theme_archive(archive_path))
        except (
            OSError,
            ValueError,
            tarfile.TarError,
            zipfile.BadZipFile,
            requests.RequestException,
        ) as error:
            if not self._cancelled:
                self.failed.emit(str(error))
        finally:
            if archive_path and os.path.exists(archive_path):
                os.remove(archive_path)

    def _download_archive(self, archive_path: str) -> None:
        session = get_requests_session()
        url = _theme_store_download_url(self.theme_id)
        with session.get(url, stream=True, timeout=THEME_STORE_DOWNLOAD_TIMEOUT) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            with open(archive_path, "wb") as archive:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._cancelled:
                        break
                    if chunk:
                        archive.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self.progress.emit(int(downloaded * 100 / total))


class ThemeStoreCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, theme_data: dict, theme: Any):
        super().__init__()
        self.theme_data = theme_data
        self.setObjectName("themeStoreCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(theme.themeStoreCardMinWidth)
        self.setFixedHeight(theme.themeStoreCardHeight)
        self.setStyleSheet(theme.THEME_STORE_CARD_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.previewLabel = QLabel()
        self.previewLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previewLabel.setFixedHeight(theme.themeStorePreviewHeight)
        self.previewLabel.setStyleSheet(theme.THEME_STORE_PREVIEW_STYLE)
        layout.addWidget(self.previewLabel)

        name = str(theme_data.get("name", ""))
        nameLabel = QLabel(name)
        nameLabel.setStyleSheet(theme.THEME_STORE_CARD_TITLE_STYLE)
        layout.addWidget(nameLabel)

        author = str(theme_data.get("author") or _("Unknown"))
        authorLabel = QLabel(_("by {0}").format(author))
        authorLabel.setStyleSheet(theme.THEME_STORE_CARD_META_STYLE)
        layout.addWidget(authorLabel)

        statsLabel = QLabel(self._stats_text())
        statsLabel.setStyleSheet(theme.THEME_STORE_CARD_META_STYLE)
        layout.addWidget(statsLabel)
        layout.addStretch(1)

    def set_preview(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            self.previewLabel.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.previewLabel.setPixmap(scaled)

    def _stats_text(self) -> str:
        votes = self.theme_data.get("votes_count", 0)
        downloads = self.theme_data.get("downloads_count", 0)
        return f"{THEME_STORE_VOTES_ICON} {votes}    {THEME_STORE_DOWNLOADS_ICON} {downloads}"

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.click()
        super().mousePressEvent(event)

    def click(self) -> None:
        self.clicked.emit(self.theme_data)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow

    _MainWindowTypingBase = QMainWindow
else:
    _MainWindowTypingBase = object


class MainWindowThemeTabMixin(_MainWindowTypingBase):
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def createThemeTab(self):
        """Themes tab"""
        self.themeTabWidget = QWidget()
        self.themeTabWidget.setStyleSheet(self.theme.OTHER_PAGES_WIDGET_STYLE + self.theme.THEME_TAB_FOCUS_STYLE)
        self.themeTabWidget.setObjectName("otherPage")
        mainLayout = QVBoxLayout(self.themeTabWidget)
        mainLayout.setContentsMargins(10, 14, 10, 10)
        mainLayout.setSpacing(10)

        # 1. Top line: Title and theme list
        self.themeTabHeaderLayout = QHBoxLayout()

        self.themeTabTitleLabel = QLabel(_("Select Theme:"))
        self.themeTabTitleLabel.setObjectName("tabTitle")
        self.themeTabTitleLabel.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.themeTabTitleLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.themeTabHeaderLayout.addWidget(self.themeTabTitleLabel)

        self.themesCombo = QComboBox()
        self.themesCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.themesCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.themesCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.themesCombo.setObjectName("themeTabCombo")
        self.themesCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        theme_names = self.theme_manager.get_available_themes()
        available_themes = ui_config.get_theme_bases(theme_names)
        current_theme_base = ui_config.get_theme_base()
        if current_theme_base in available_themes:
            available_themes.remove(current_theme_base)
            available_themes.insert(0, current_theme_base)
        self.themesCombo.addItems(available_themes)
        self.themesCombo.addItem(_(THEME_STORE_ITEM), THEME_STORE_ITEM)
        self.themeTabHeaderLayout.addWidget(self.themesCombo)

        self.themeVariantCombo = QComboBox()
        self.themeVariantCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.themeVariantCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.themeVariantCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.themeVariantCombo.setObjectName("themeVariantCombo")
        self.themeVariantCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.themeVariantCombo.addItem(_("Dark"), "dark")
        self.themeVariantCombo.addItem(_("Light"), "light")
        self.themeVariantCombo.addItem(_("Auto"), "auto")
        current_variant = ui_config.get_theme_variant()
        variant_index = self.themeVariantCombo.findData(current_variant)
        if variant_index >= 0:
            self.themeVariantCombo.setCurrentIndex(variant_index)
        self.themeTabHeaderLayout.addWidget(self.themeVariantCombo)
        self.themeTabHeaderLayout.addStretch(1)

        mainLayout.addLayout(self.themeTabHeaderLayout)

        self.themeContentStack = QStackedWidget()
        self.themeInstalledPage = QWidget()
        installedLayout = QVBoxLayout(self.themeInstalledPage)
        installedLayout.setContentsMargins(0, 0, 0, 0)
        installedLayout.setSpacing(10)

        def hasThemeVariants(theme_name: str) -> bool:
            if theme_name == _(THEME_STORE_ITEM):
                return False
            return ui_config.resolve_theme(theme_name, "dark") != ui_config.resolve_theme(theme_name, "light")

        def updateThemeVariantVisibility(*_args: object) -> None:
            self.themeVariantCombo.setVisible(hasThemeVariants(self.themesCombo.currentText()))

        # 2. Screenshots carousel
        self.screenshotsCarousel = ImageCarousel([])
        self.screenshotsCarousel.setStyleSheet(self.theme.CAROUSEL_WIDGET_STYLE)
        self.screenshotsCarousel.setObjectName("themeScreenshotsCarousel")
        self.screenshotsCarousel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.screenshotsCarousel.prevArrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.screenshotsCarousel.nextArrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        installedLayout.addWidget(self.screenshotsCarousel, stretch=1)

        # 3. Theme info
        self.themeInfoLayout = QVBoxLayout()
        self.themeInfoLayout.setSpacing(10)

        self.themeMetainfoLabel = QLabel()
        self.themeMetainfoLabel.setWordWrap(True)
        self.themeMetainfoLabel.setOpenExternalLinks(True)
        self.themeMetainfoLabel.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.themeMetainfoLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.themeInfoLayout.addWidget(self.themeMetainfoLabel)

        self.applyButton = AutoSizeButton(_("Apply Theme"), icon=self.theme_manager.get_icon("apply", as_path=True))
        self.applyButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.applyButton.setObjectName("themeApplyButton")
        self.applyButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.themeInfoLayout.addWidget(self.applyButton)

        installedLayout.addLayout(self.themeInfoLayout)
        self.themeContentStack.addWidget(self.themeInstalledPage)
        self.themeStorePage = self._create_theme_store_page()
        self.themeContentStack.addWidget(self.themeStorePage)
        mainLayout.addWidget(self.themeContentStack, stretch=1)

        # Preview update function
        def updateThemePreview(*_args: object) -> None:
            if self.themesCombo.currentData() == THEME_STORE_ITEM:
                self._show_theme_store()
                return
            self.themeContentStack.setCurrentWidget(self.themeInstalledPage)
            updateThemeVariantVisibility()
            base_theme = self.themesCombo.currentText()
            variant = self.themeVariantCombo.currentData() or "light"
            theme_name = ui_config.resolve_theme(base_theme, variant)
            meta = load_theme_metainfo(theme_name)
            link = meta.get("author_link", "")
            link_html = f'<a href="{link}">{link}</a>' if link else _("No link")
            unknown_author = _("Unknown")

            preview_text = (
                "<b>" + _("Name:") + "</b> " + meta.get('name', theme_name) + "<br>" +
                "<b>" + _("Description:") + "</b> " + meta.get('description', '') + "<br>" +
                "<b>" + _("Author:") + "</b> " + meta.get('author', unknown_author) + "<br>" +
                "<b>" + _("Link:") + "</b> " + link_html
            )
            self.themeMetainfoLabel.setText(preview_text)
            self.themeMetainfoLabel.setStyleSheet(self.theme.CONTENT_STYLE)

            screenshots = load_theme_screenshots(theme_name)
            if screenshots:
                self.screenshotsCarousel.update_images([
                    (pixmap, caption)
                    for pixmap, caption in screenshots
                ])
                self.screenshotsCarousel.show()
            else:
                self.screenshotsCarousel.hide()

        updateThemePreview()
        self.themesCombo.currentTextChanged.connect(updateThemePreview)
        self.themeVariantCombo.currentTextChanged.connect(updateThemePreview)

        # Theme apply logic
        def on_apply() -> None:
            selected_theme = ui_config.resolve_theme(
                self.themesCombo.currentText(),
                self.themeVariantCombo.currentData() or "light",
            )
            if selected_theme:
                self._apply_theme_and_restart(
                    selected_theme,
                    self.themeVariantCombo.currentData() or "light",
                )

        self.applyButton.clicked.connect(on_apply)

        # Add widget to stackedWidget
        self.theme_tab_index = self.stackedWidget.addWidget(self.themeTabWidget)

    def restart_application(self):
        """Restart application."""
        if not self.isFullScreen():
            window_config.set_geometry(self.width(), self.height())
        restart_application_process()

    def _create_theme_store_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.theme.themeStorePageSpacing)

        self.themeStoreStatusLabel = QLabel()
        self.themeStoreStatusLabel.setStyleSheet(self.theme.CONTENT_STYLE)
        self.themeStoreStatusLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.themeStoreStatusLabel)

        self.themeStoreStack = QStackedWidget()
        self.themeStoreListPage = self._create_theme_store_list_page()
        self.themeStoreDetailPage = self._create_theme_store_detail_page()
        self.themeStoreStack.addWidget(self.themeStoreListPage)
        self.themeStoreStack.addWidget(self.themeStoreDetailPage)
        layout.addWidget(self.themeStoreStack, stretch=1)
        return page

    def _create_theme_store_list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        title = QLabel(_("Themes"))
        title.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        header.addWidget(title)
        header.addStretch(1)
        sortLabel = QLabel(_("Sort by:"))
        sortLabel.setStyleSheet(self.theme.CONTENT_STYLE)
        header.addWidget(sortLabel)
        self.themeStoreSortCombo = QComboBox()
        self.themeStoreSortCombo.addItems([
            _("Most voted"),
            _("Most downloaded"),
            _("Newest"),
            _("Recently updated"),
            _("Name (A-Z)"),
        ])
        self.themeStoreSortCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.themeStoreSortCombo.currentIndexChanged.connect(self._on_theme_store_sort_changed)
        header.addWidget(self.themeStoreSortCombo)
        layout.addLayout(header)

        self.themeStoreScrollArea = QScrollArea()
        self.themeStoreScrollArea.setWidgetResizable(True)
        self.themeStoreScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.themeStoreScrollArea.setStyleSheet(self.theme.THEME_STORE_SCROLL_STYLE + self.theme.SCROLL_STYLE)
        self.themeStoreGridWidget = QWidget()
        self.themeStoreGridLayout = QGridLayout(self.themeStoreGridWidget)
        margin = self.theme.themeStoreGridOuterMargin
        self.themeStoreGridLayout.setContentsMargins(margin, margin, margin, margin)
        self.themeStoreGridLayout.setSpacing(self.theme.themeStoreGridSpacing)
        self.themeStoreScrollArea.setWidget(self.themeStoreGridWidget)
        layout.addWidget(self.themeStoreScrollArea)
        return page

    def _create_theme_store_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QHBoxLayout()
        self.themeStoreBackButton = AutoSizeButton(_("Back"))
        self.themeStoreBackButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.themeStoreBackButton.clicked.connect(self._show_theme_store_list)
        header.addWidget(self.themeStoreBackButton)
        header.addStretch(1)
        self.themeStoreDetailTitle = QLabel()
        self.themeStoreDetailTitle.setStyleSheet(self.theme.THEME_STORE_DETAIL_TITLE_STYLE)
        header.addWidget(self.themeStoreDetailTitle)
        header.addStretch(1)
        self.themeStoreDownloadButton = AutoSizeButton(_("Download"))
        self.themeStoreDownloadButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.themeStoreDownloadButton.clicked.connect(self._download_current_store_theme)
        header.addWidget(self.themeStoreDownloadButton)
        layout.addLayout(header)

        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scrollArea.setStyleSheet(self.theme.THEME_STORE_SCROLL_STYLE + self.theme.SCROLL_STYLE)
        scrollContent = QWidget()
        scrollLayout = QVBoxLayout(scrollContent)
        scrollLayout.setContentsMargins(0, 0, 0, 0)

        self.themeStoreCarousel = ImageCarousel([], theme=self.theme)
        self.themeStoreCarousel.setObjectName("themeStoreScreenshotsCarousel")
        self.themeStoreCarousel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.themeStoreCarousel.setMinimumHeight(self.theme.themeStoreDetailCarouselMinHeight)
        self.themeStoreCarousel.setStyleSheet(self.theme.CAROUSEL_WIDGET_STYLE)
        scrollLayout.addWidget(self.themeStoreCarousel, stretch=1)

        self.themeStoreDetailMeta = QLabel()
        self.themeStoreDetailMeta.setStyleSheet(self.theme.CONTENT_STYLE)
        scrollLayout.addWidget(self.themeStoreDetailMeta)

        variantLayout = QHBoxLayout()
        self.themeStoreDarkButton = AutoSizeButton(_("Dark"))
        self.themeStoreDarkButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.themeStoreDarkButton.clicked.connect(lambda: self._set_theme_store_preview_variant("dark"))
        variantLayout.addWidget(self.themeStoreDarkButton)
        self.themeStoreLightButton = AutoSizeButton(_("Light"))
        self.themeStoreLightButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.themeStoreLightButton.clicked.connect(lambda: self._set_theme_store_preview_variant("light"))
        variantLayout.addWidget(self.themeStoreLightButton)
        variantLayout.addStretch(1)
        scrollLayout.addLayout(variantLayout)

        self.themeStoreDescription = QTextBrowser()
        self.themeStoreDescription.setStyleSheet(self.theme.THEME_STORE_DESCRIPTION_STYLE)
        scrollLayout.addWidget(self.themeStoreDescription)
        scrollLayout.addStretch(1)

        scrollArea.setWidget(scrollContent)
        layout.addWidget(scrollArea, stretch=1)
        return page

    def _show_theme_store(self) -> None:
        self.themeContentStack.setCurrentWidget(self.themeStorePage)
        self.themeVariantCombo.hide()
        if getattr(self, "themeStoreLoaded", False):
            QTimer.singleShot(50, self._schedule_visible_image_load)
            return
        self._load_theme_store()

    def _load_theme_store(self) -> None:
        self.themeStoreStatusLabel.show()
        self.themeStoreStatusLabel.setText(_("Loading…"))
        sort_key, order_key = self._theme_store_sort_args()
        self.themeStoreListWorker = ThemeStoreListWorker(sort_key, order_key)
        self.themeStoreListWorker.loaded.connect(self._on_theme_store_loaded)
        self.themeStoreListWorker.failed.connect(self._on_theme_store_failed)
        self.themeStoreListWorker.finished.connect(
            lambda: setattr(self, "themeStoreListWorker", None)
        )
        self.themeStoreListWorker.start()

    def _theme_store_sort_args(self) -> tuple[str, str]:
        mapping = [
            ("votes", "desc"),
            ("downloads", "desc"),
            ("created", "desc"),
            ("updated", "desc"),
            ("name", "asc"),
        ]
        index = self.themeStoreSortCombo.currentIndex()
        return mapping[index] if 0 <= index < len(mapping) else mapping[0]

    def _on_theme_store_sort_changed(self, _index: int) -> None:
        if not getattr(self, "themeStoreLoaded", False):
            return
        self.themeStoreLoaded = False
        if getattr(self, "themeStoreImageWorker", None) is not None:
            self.themeStoreImageWorker.cancel()
        self._load_theme_store()

    def _on_theme_store_loaded(self, themes: list) -> None:
        self.themeStoreLoaded = True
        self.themeStoreStatusLabel.hide()
        self.themeStoreThemes = themes
        self._populate_theme_store_cards()
        self._schedule_visible_image_load()

    def _on_theme_store_failed(self, message: str) -> None:
        logger.warning("Failed to load theme store: %s", message)
        self.themeStoreStatusLabel.show()
        self.themeStoreStatusLabel.setText(_("Failed to load themes"))

    def _populate_theme_store_cards(self) -> None:
        self.themeStoreCards = {}
        self.themeStoreCardsByUrl = {}
        self.themeStoreLoadedUrls = set()
        self._imageWorkerPool = []
        while self.themeStoreGridLayout.count():
            item = self.themeStoreGridLayout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.themeStoreGridIndex = 0
        self._add_next_card_batch()

    def _add_next_card_batch(self) -> None:
        all_themes = getattr(self, "themeStoreThemes", [])
        if self.themeStoreGridIndex >= len(all_themes):
            return
        columns = self._theme_store_column_count()
        end = min(self.themeStoreGridIndex + THEME_STORE_CARD_BATCH_SIZE, len(all_themes))
        for index in range(self.themeStoreGridIndex, end):
            theme_data = all_themes[index]
            card = ThemeStoreCard(theme_data, self.theme)
            card.clicked.connect(self._show_theme_store_detail)
            urls = _theme_store_preview_urls(theme_data)
            if urls:
                url = urls[0]
                self.themeStoreCardsByUrl[url] = card
            row, column = divmod(index, columns)
            self.themeStoreGridLayout.addWidget(card, row, column)
        self.themeStoreGridIndex = end
        if self.themeStoreGridIndex < len(all_themes):
            QTimer.singleShot(0, self._add_next_card_batch)
        else:
            self._connect_scroll_lazy_loading()

    def _connect_scroll_lazy_loading(self) -> None:
        if getattr(self, "_scrollConnected", False):
            return
        self._scrollConnected = True
        self.themeStoreScrollArea.verticalScrollBar().valueChanged.connect(self._on_theme_store_scroll)
        self._scrollDebounceTimer = QTimer()
        self._scrollDebounceTimer.setSingleShot(True)
        self._scrollDebounceTimer.setInterval(100)
        self._scrollDebounceTimer.timeout.connect(self._schedule_visible_image_load)
        self._schedule_visible_image_load()

    def _on_theme_store_scroll(self, _value: int) -> None:
        self._scrollDebounceTimer.start()

    def _schedule_visible_image_load(self) -> None:
        if self.themeStoreGridIndex < len(getattr(self, "themeStoreThemes", [])):
            return
        visible_urls = self._get_visible_theme_urls()
        pending = [
            url for url in visible_urls
            if url not in self.themeStoreLoadedUrls
        ]
        if not pending:
            return
        if getattr(self, "themeStoreImageWorker", None) is not None:
            self.themeStoreImageWorker.cancel()
            self._imageWorkerPool.append(self.themeStoreImageWorker)
        worker = ThemeStoreImageWorker(pending)
        worker.loaded.connect(self._on_theme_store_preview_loaded)
        worker.finished.connect(self._on_image_worker_finished)
        self.themeStoreImageWorker = worker
        worker.start()

    def _on_image_worker_finished(self) -> None:
        self._imageWorkerPool = [w for w in self._imageWorkerPool if w.isRunning()]

    def _get_visible_theme_urls(self) -> list[str]:
        viewport = self.themeStoreScrollArea.viewport()
        viewport_rect = viewport.rect()
        first_visible = -1
        for i in range(self.themeStoreGridLayout.count()):
            item = self.themeStoreGridLayout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if widget is None:
                continue
            pos = widget.mapTo(viewport, widget.rect().topLeft())
            if viewport_rect.contains(pos):
                first_visible = i
                break
        if first_visible < 0:
            return list(self.themeStoreCardsByUrl.keys())[:THEME_STORE_IMAGE_WORKERS]
        return self._collect_first_urls_up_to(first_visible)

    def _collect_first_urls_up_to(self, start_item: int) -> list[str]:
        columns = self._theme_store_column_count()
        total = self.themeStoreGridLayout.count()
        urls: list[str] = []
        start_row, start_col = divmod(start_item, columns)
        end_row = start_row + 3
        for i in range(total):
            row, col = divmod(i, columns)
            if row > end_row:
                break
            item = self.themeStoreGridLayout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if widget is None:
                continue
            if isinstance(widget, ThemeStoreCard):
                card_urls = _theme_store_preview_urls(widget.theme_data)
                if card_urls:
                    urls.append(card_urls[0])
        return urls

    def _theme_store_column_count(self) -> int:
        width = self.themeStoreScrollArea.viewport().width()
        min_width = self.theme.themeStoreGridMinColumnWidth
        return max(1, width // min_width)

    def _on_theme_store_preview_loaded(self, url: str, data: bytes) -> None:
        self.themeStoreLoadedUrls.add(url)
        card = self.themeStoreCardsByUrl.get(url)
        pixmap = QPixmap()
        if card and pixmap.loadFromData(data):
            card.set_preview(pixmap)

    def _show_theme_store_detail(self, theme_data: dict) -> None:
        self.themeStoreCurrentTheme = theme_data
        self.themeStoreDetailTitle.setText(str(theme_data.get("name", "")))
        self.themeStoreDetailMeta.setText(self._theme_store_meta_text(theme_data))
        desc = theme_data.get("description_ru") or theme_data.get("description") or ""
        self.themeStoreDescription.setPlainText(str(desc))
        self._update_theme_store_variant_buttons(theme_data)
        self.themeStoreStack.setCurrentWidget(self.themeStoreDetailPage)
        variant = self._initial_theme_store_variant(theme_data)
        self._set_theme_store_preview_variant(variant)

    def _show_theme_store_list(self) -> None:
        self.themeStoreStack.setCurrentWidget(self.themeStoreListPage)
        QTimer.singleShot(50, self._schedule_visible_image_load)

    def _theme_store_meta_text(self, theme_data: dict) -> str:
        author = theme_data.get("author") or _("Unknown")
        votes = theme_data.get("votes_count", 0)
        downloads = theme_data.get("downloads_count", 0)
        return (
            _("by {0}").format(author)
            + f"    {THEME_STORE_VOTES_ICON} {votes}"
            + f"    {THEME_STORE_DOWNLOADS_ICON} {downloads}"
        )

    def _initial_theme_store_variant(self, theme_data: dict) -> str:
        if theme_data.get("dark_screenshot_urls"):
            return "dark"
        if theme_data.get("light_screenshot_urls"):
            return "light"
        return "dark"

    def _update_theme_store_variant_buttons(self, theme_data: dict) -> None:
        self.themeStoreDarkButton.setVisible(bool(theme_data.get("dark_screenshot_urls")))
        self.themeStoreLightButton.setVisible(bool(theme_data.get("light_screenshot_urls")))

    def _set_theme_store_preview_variant(self, variant: str) -> None:
        self.themeStorePreviewVariant = variant
        active_style = getattr(self.theme, "ACTION_BUTTON_ACTIVE_STYLE", self.theme.ACTION_BUTTON_STYLE)
        self.themeStoreDarkButton.setStyleSheet(
            active_style if variant == "dark" else self.theme.ACTION_BUTTON_STYLE
        )
        self.themeStoreLightButton.setStyleSheet(
            active_style if variant == "light" else self.theme.ACTION_BUTTON_STYLE
        )
        theme_data = getattr(self, "themeStoreCurrentTheme", {})
        self._load_theme_store_detail_images(theme_data, variant)

    def _load_theme_store_detail_images(self, theme_data: dict, variant: str) -> None:
        urls = _theme_store_variant_urls(theme_data, variant)
        self.themeStoreCarousel.update_images([])
        if not urls:
            return
        if getattr(self, "themeStoreDetailImageWorker", None) is not None:
            self.themeStoreDetailImageWorker.cancel()
        self.themeStoreDetailImages = [None] * len(urls)
        self.themeStoreDetailImageWorker = ThemeStoreDetailImageWorker(urls)
        self.themeStoreDetailImageWorker.image_loaded.connect(self._on_theme_store_detail_image_loaded)
        self.themeStoreDetailImageWorker.finished.connect(
            lambda: setattr(self, "themeStoreDetailImageWorker", None)
        )
        self.themeStoreDetailImageWorker.start()

    def _on_theme_store_detail_image_loaded(self, index: int, data: bytes) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        images = getattr(self, "themeStoreDetailImages", [])
        if index < len(images):
            images[index] = pixmap
        screenshots = [(img, "") for img in images if img is not None]
        self.themeStoreCarousel.update_images(screenshots)

    def _download_current_store_theme(self) -> None:
        self._download_store_theme(getattr(self, "themeStoreCurrentTheme", {}))

    def _download_store_theme(self, theme_data: dict) -> None:
        theme_id = theme_data.get("id")
        if not isinstance(theme_id, int):
            self.themeStoreStatusLabel.show()
            self.themeStoreStatusLabel.setText(_("Failed to download theme"))
            return
        self.themeStoreDownloadButton.setEnabled(False)
        self.themeStoreDownloadButton.setText(_("Downloading…"))
        self.themeStoreDownloadWorker = ThemeStoreDownloadWorker(theme_id)
        self.themeStoreDownloadWorker.progress.connect(self._on_store_download_progress)
        self.themeStoreDownloadWorker.installed.connect(self._on_store_theme_installed)
        self.themeStoreDownloadWorker.failed.connect(self._on_store_theme_failed)
        self.themeStoreDownloadWorker.finished.connect(self._on_store_download_finished)
        self.themeStoreDownloadWorker.start()

    def _on_store_download_progress(self, percent: int) -> None:
        self.themeStoreDownloadButton.setText(_("Downloading… {0}%").format(percent))

    def _on_store_download_finished(self) -> None:
        self.themeStoreDownloadButton.setEnabled(True)
        self.themeStoreDownloadButton.setText(_("Download"))
        self.themeStoreDownloadWorker = None

    def _on_store_theme_installed(self, theme_names: list) -> None:
        if not theme_names:
            self.themeStoreDownloadButton.setEnabled(True)
            self.themeStoreDownloadButton.setText(_("Download"))
            self.themeStoreStatusLabel.show()
            self.themeStoreStatusLabel.setText(_("Failed to install theme"))
            return
        variant = getattr(self, "themeStorePreviewVariant", "dark")
        theme_name = ui_config.resolve_theme(theme_names[0], variant)
        if theme_name not in theme_names:
            theme_name = theme_names[0]
        self._refresh_theme_combo(theme_name)
        self._apply_theme_and_restart(theme_name, variant)

    def _on_store_theme_failed(self, message: str) -> None:
        logger.warning("Failed to install theme from store: %s", message)
        self.themeStoreStatusLabel.show()
        self.themeStoreStatusLabel.setText(_("Failed to install theme"))

    def _refresh_theme_combo(self, selected_theme: str) -> None:
        theme_names = self.theme_manager.get_available_themes()
        available_themes = ui_config.get_theme_bases(theme_names)
        selected_base = ui_config.get_theme_bases([selected_theme])[0]
        if selected_base in available_themes:
            available_themes.remove(selected_base)
            available_themes.insert(0, selected_base)
        self.themesCombo.blockSignals(True)
        self.themesCombo.clear()
        self.themesCombo.addItems(available_themes)
        self.themesCombo.addItem(_(THEME_STORE_ITEM), THEME_STORE_ITEM)
        self.themesCombo.blockSignals(False)

    def _apply_theme_and_restart(self, theme_name: str, variant: str) -> None:
        theme_module = self.theme_manager.apply_theme(theme_name)
        if not theme_module:
            return
        ui_config.set_theme(theme_name)
        ui_config.set_theme_variant(variant)
        self._save_theme_tab_state()
        QTimer.singleShot(500, lambda: self.restart_application())

    def _save_theme_tab_state(self) -> None:
        xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
        state_file = os.path.join(xdg_data_home, "PortProtonQt", "state.txt")
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                f.write("theme_tab\n")
            logger.info(f"State saved to {state_file}")
        except OSError as e:
            logger.error(f"Failed to save state to {state_file}: {e}")

    def restore_state(self):
        """Restore application state after restart."""
        xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
        state_file = os.path.join(xdg_data_home, "PortProtonQt", "state.txt")
        logger.info(f"Checking for state file: {state_file}")
        if os.path.exists(state_file):
            try:
                with open(state_file, encoding="utf-8") as f:
                    state = f.read().strip()
                    logger.info(f"State file contents: '{state}'")
                    if state == "theme_tab":
                        logger.info("Restoring to theme tab")
                        theme_index = getattr(self, "theme_tab_index", -1)
                        if theme_index >= 0 and self.stackedWidget.count() > theme_index:
                            self.switchTab(theme_index)
                        else:
                            logger.warning("Theme tab is not available yet")
                    else:
                        logger.warning(f"Unexpected state value: '{state}'")
                os.remove(state_file)
                logger.info(f"State file {state_file} removed")
            except Exception as e:
                logger.error(f"Failed to read or process state file {state_file}: {e}")
        else:
            logger.info(f"State file {state_file} does not exist")
