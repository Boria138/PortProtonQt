from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QObject, QThread, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from portprotonqt.config import ui_config
from portprotonqt.custom_widgets import AutoHideScrollArea, AutoSizeButton, CustomComboBox, FlowLayout
from portprotonqt.image_utils import ImageCarousel
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.tabs.theme_store_workers import (
    THEME_STORE_CARD_BATCH_SIZE,
    THEME_STORE_DOWNLOADS_ICON,
    THEME_STORE_IMAGE_WORKERS,
    THEME_STORE_VOTES_ICON,
    ThemeStoreDetailImageWorker,
    ThemeStoreDownloadWorker,
    ThemeStoreImageWorker,
    ThemeStoreListWorker,
    _theme_store_preview_urls,
    _theme_store_variant_urls,
)

logger = get_logger(__name__)
THEME_STORE_ITEM = _("Theme Store…")


class ThemeStoreCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, theme_data: dict, theme: Any, card_width: int = 280):
        super().__init__()
        self.theme_data = theme_data
        self.card_width = card_width
        self.setObjectName("themeStoreCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedWidth(card_width)
        self.setStyleSheet(theme.THEME_STORE_CARD_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.previewLabel = QLabel()
        self.previewLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previewLabel.setFixedHeight(int(card_width * 0.57))
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

    def set_preview(self, pixmap: QPixmap) -> None:
        preview_size = self.previewLabel.size()
        if preview_size.width() <= 0 or preview_size.height() <= 0:
            return
        scaled = pixmap.scaled(
            preview_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.previewLabel.setPixmap(scaled)

    def update_card_size(self, new_width: int) -> None:
        self.card_width = new_width
        self.setFixedWidth(new_width)
        self.previewLabel.setFixedHeight(int(new_width * 0.57))

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


class ThemeStoreMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

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
        self._themeStoreCardWidth = ui_config.get_theme_store_card_width()
        layout.addLayout(self._create_theme_store_sort_header())
        self._create_theme_store_grid(layout)
        self._create_theme_store_size_slider(layout)
        self._resizeDebounceTimer = QTimer()
        self._resizeDebounceTimer.setSingleShot(True)
        self._resizeDebounceTimer.setInterval(150)
        self._resizeDebounceTimer.timeout.connect(self._relayout_theme_store)
        self._themeStoreViewport = self.themeStoreScrollArea.viewport()
        self._themeStoreViewport.installEventFilter(cast(QObject, self))
        return page

    def _create_theme_store_sort_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.addStretch(1)
        self.themeStoreSortCombo = CustomComboBox(theme=self.theme)
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
        header.addStretch(1)
        return header

    def _create_theme_store_grid(self, layout: QVBoxLayout) -> None:
        self.themeStoreScrollArea = AutoHideScrollArea(theme=self.theme)
        self.themeStoreScrollArea.setWidgetResizable(True)
        self.themeStoreScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.themeStoreGridWidget = QWidget()
        self.themeStoreGridLayout = FlowLayout(self.themeStoreGridWidget, center_rows=True)
        self.themeStoreGridLayout.setContentsMargins(14, 14, 14, 14)
        self.themeStoreGridLayout._spacing = 16
        self.themeStoreScrollArea.setWidget(self.themeStoreGridWidget)
        layout.addWidget(self.themeStoreScrollArea)

    def _create_theme_store_size_slider(self, layout: QVBoxLayout) -> None:
        sliderLayout = QHBoxLayout()
        sliderLayout.addStretch()
        self.themeStoreSizeSlider = QSlider(Qt.Orientation.Horizontal)
        self.themeStoreSizeSlider.setMinimum(150)
        self.themeStoreSizeSlider.setMaximum(600)
        self.themeStoreSizeSlider.setValue(self._themeStoreCardWidth)
        self.themeStoreSizeSlider.setTickInterval(10)
        self.themeStoreSizeSlider.setFixedWidth(150)
        self.themeStoreSizeSlider.setStyleSheet(self.theme.SLIDER_SIZE_STYLE)
        self._register_gamepad_tooltip(self.themeStoreSizeSlider, f"{self._themeStoreCardWidth} px")
        self.themeStoreSizeSlider.sliderReleased.connect(self._on_theme_store_slider_released)
        sliderLayout.addWidget(self.themeStoreSizeSlider)
        layout.addLayout(sliderLayout)

    def _create_theme_store_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(self._create_theme_store_detail_header())
        layout.addWidget(self._create_theme_store_detail_body(), stretch=1)
        return page

    def _create_theme_store_detail_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        self.themeStoreBackButton = AutoSizeButton(_("Back"))
        self.themeStoreBackButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.themeStoreBackButton.setProperty("sound_event", "back")
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
        header.setContentsMargins(0, 0, 0, 20)
        return header

    def _create_theme_store_detail_body(self) -> AutoHideScrollArea:
        scrollArea = AutoHideScrollArea(theme=self.theme)
        scrollArea.setWidgetResizable(True)
        scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scrollContent = QWidget()
        scrollLayout = QVBoxLayout(scrollContent)
        scrollLayout.setContentsMargins(0, 0, 0, 0)
        self._add_theme_store_carousel(scrollLayout)
        self._add_theme_store_variant_buttons(scrollLayout)
        self.themeStoreDescription = QTextBrowser()
        self.themeStoreDescription.setStyleSheet(self.theme.THEME_STORE_DESCRIPTION_STYLE)
        scrollLayout.addWidget(self.themeStoreDescription)
        scrollLayout.addStretch(1)
        scrollArea.setWidget(scrollContent)
        return scrollArea

    def _add_theme_store_carousel(self, scrollLayout: QVBoxLayout) -> None:
        self.themeStoreCarousel = ImageCarousel([], theme=self.theme)
        self.themeStoreCarousel.setObjectName("themeStoreScreenshotsCarousel")
        self.themeStoreCarousel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.themeStoreCarousel.setMinimumHeight(self.theme.themeStoreDetailCarouselMinHeight)
        self.themeStoreCarousel.setStyleSheet(self.theme.CAROUSEL_WIDGET_STYLE)
        scrollLayout.addWidget(self.themeStoreCarousel, stretch=1)

        self.themeStoreDetailMeta = QLabel()
        self.themeStoreDetailMeta.setStyleSheet(self.theme.CONTENT_STYLE)
        scrollLayout.addWidget(self.themeStoreDetailMeta)

    def _add_theme_store_variant_buttons(self, scrollLayout: QVBoxLayout) -> None:
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

    def _show_theme_store(self) -> None:
        self.themeContentStack.setCurrentWidget(self.themeStorePage)
        self.themeVariantCombo.hide()
        self._load_theme_store()

    def _load_theme_store(self) -> None:
        self.themeStoreStatusLabel.show()
        self.themeStoreStatusLabel.setText(_("Loading…"))
        sort_key, order_key = self._theme_store_sort_args()
        current_worker = getattr(self, "themeStoreListWorker", None)
        if current_worker is not None:
            self._keep_theme_store_list_worker(current_worker)
        worker = ThemeStoreListWorker(sort_key, order_key)
        worker.loaded.connect(self._on_theme_store_loaded)
        worker.failed.connect(self._on_theme_store_failed)
        worker.finished.connect(
            lambda finished_worker=worker: self._on_list_worker_finished(finished_worker)
        )
        self.themeStoreListWorker = worker
        worker.start()

    def _keep_theme_store_list_worker(self, worker: QThread) -> None:
        worker_pool = getattr(self, "_listWorkerPool", [])
        if worker not in worker_pool and worker.isRunning():
            worker_pool.append(worker)
        self._listWorkerPool = worker_pool

    def _on_list_worker_finished(self, worker: QThread) -> None:
        if getattr(self, "themeStoreListWorker", None) is worker:
            self.themeStoreListWorker = None
        self._listWorkerPool = [
            item for item in getattr(self, "_listWorkerPool", [])
            if item.isRunning()
        ]

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
        worker = getattr(self, "themeStoreImageWorker", None)
        if worker is not None:
            worker.cancel()
        self._load_theme_store()

    def _on_theme_store_loaded(self, themes: list) -> None:
        sender = self.sender()
        if sender is not None and sender is not getattr(self, "themeStoreListWorker", None):
            return
        self.themeStoreLoaded = True
        self.themeStoreStatusLabel.hide()
        self.themeStoreThemes = themes
        self._populate_theme_store_cards()
        self._schedule_visible_image_load()

    def _on_theme_store_failed(self, message: str) -> None:
        sender = self.sender()
        if sender is not None and sender is not getattr(self, "themeStoreListWorker", None):
            return
        logger.warning("Failed to load theme store: %s", message)
        self.themeStoreStatusLabel.show()
        self.themeStoreStatusLabel.setText(_("Failed to load themes"))

    def _populate_theme_store_cards(self) -> None:
        self._cancel_theme_store_image_worker()
        self.themeStoreCards = {}
        self.themeStoreCardsByUrl = {}
        self.themeStoreLoadedUrls = set()
        self._scrollConnected = False
        while self.themeStoreGridLayout.count():
            item = self.themeStoreGridLayout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.themeStoreGridIndex = 0
        self._add_next_card_batch()

    def _calc_theme_store_card_width(self) -> int:
        width = self.themeStoreScrollArea.viewport().width()
        spacing = self.themeStoreGridLayout._spacing
        margins = self.themeStoreGridLayout.contentsMargins()
        available = width - margins.left() - margins.right()
        desired = self._themeStoreCardWidth
        cols = max(1, round(available / desired))
        return max(150, (available - spacing * (cols - 1)) // cols)

    def _add_next_card_batch(self) -> None:
        all_themes = getattr(self, "themeStoreThemes", [])
        if self.themeStoreGridIndex >= len(all_themes):
            return
        actual_width = self._calc_theme_store_card_width()
        end = min(self.themeStoreGridIndex + THEME_STORE_CARD_BATCH_SIZE, len(all_themes))
        for index in range(self.themeStoreGridIndex, end):
            theme_data = all_themes[index]
            card = ThemeStoreCard(theme_data, self.theme, actual_width)
            card.clicked.connect(self._show_theme_store_detail)
            urls = _theme_store_preview_urls(theme_data)
            if urls:
                url = urls[0]
                self.themeStoreCardsByUrl[url] = card
            self.themeStoreGridLayout.addWidget(card)
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
            self._cancel_theme_store_image_worker()
        worker = ThemeStoreImageWorker(pending)
        worker.loaded.connect(self._on_theme_store_preview_loaded)
        worker.finished.connect(
            lambda finished_worker=worker: self._on_image_worker_finished(finished_worker)
        )
        self.themeStoreImageWorker = worker
        worker.start()

    def _cancel_theme_store_image_worker(self) -> None:
        worker = getattr(self, "themeStoreImageWorker", None)
        if worker is None:
            return
        worker.cancel()
        self._keep_theme_store_image_worker(worker)
        self.themeStoreImageWorker = None

    def _keep_theme_store_image_worker(self, worker: QThread) -> None:
        worker_pool = getattr(self, "_imageWorkerPool", [])
        if worker not in worker_pool and worker.isRunning():
            worker_pool.append(worker)
        self._imageWorkerPool = worker_pool

    def _on_image_worker_finished(self, worker: QThread) -> None:
        if getattr(self, "themeStoreImageWorker", None) is worker:
            self.themeStoreImageWorker = None
        self._imageWorkerPool = [
            item for item in getattr(self, "_imageWorkerPool", [])
            if item.isRunning()
        ]

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
        viewport = self.themeStoreScrollArea.viewport()
        viewport_height = viewport.height()
        total = self.themeStoreGridLayout.count()
        urls: list[str] = []
        for i in range(start_item, total):
            if i >= total:
                break
            item = self.themeStoreGridLayout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if widget is None:
                continue
            pos = widget.mapTo(viewport, widget.rect().topLeft())
            if pos.y() > viewport_height * 3:
                break
            if isinstance(widget, ThemeStoreCard):
                card_urls = _theme_store_preview_urls(widget.theme_data)
                if card_urls:
                    urls.append(card_urls[0])
        return urls

    def _theme_store_column_count(self) -> int:
        width = self.themeStoreScrollArea.viewport().width()
        return max(1, width // self._themeStoreCardWidth)

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

    def _on_theme_store_slider_released(self) -> None:
        new_width = self.themeStoreSizeSlider.value()
        if new_width == self._themeStoreCardWidth:
            return
        self._themeStoreCardWidth = new_width
        ui_config.set_theme_store_card_width(new_width)
        self._gamepad_tooltip_map[self.themeStoreSizeSlider] = f"{new_width} px"
        self._populate_theme_store_cards()

    def eventFilter(self, obj, event):
        if (obj == getattr(self, "_themeStoreViewport", None)
                and hasattr(self, "_resizeDebounceTimer")
                and event.type() == event.Type.Resize):
            self._resizeDebounceTimer.start()
        parent_event_filter = getattr(super(), "eventFilter", None)
        if parent_event_filter is None:
            return False
        return parent_event_filter(obj, event)

    def _relayout_theme_store(self) -> None:
        if not getattr(self, "themeStoreLoaded", False):
            return
        actual_width = self._calc_theme_store_card_width()
        for i in range(self.themeStoreGridLayout.count()):
            item = self.themeStoreGridLayout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, ThemeStoreCard):
                widget.update_card_size(actual_width)
        self.themeStoreGridLayout.invalidate()
        self.themeStoreGridWidget.adjustSize()
        self.themeStoreGridWidget.updateGeometry()
        QTimer.singleShot(0, self._schedule_visible_image_load)

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
        self._cancel_theme_store_detail_image_worker()
        self.themeStoreCarousel.update_images([])
        if not urls:
            return
        self.themeStoreDetailImages = [None] * len(urls)
        worker = ThemeStoreDetailImageWorker(urls)
        worker.image_loaded.connect(self._on_theme_store_detail_image_loaded)
        worker.finished.connect(
            lambda finished_worker=worker: self._on_detail_image_worker_finished(finished_worker)
        )
        self.themeStoreDetailImageWorker = worker
        worker.start()

    def _cancel_theme_store_detail_image_worker(self) -> None:
        worker = getattr(self, "themeStoreDetailImageWorker", None)
        if worker is None:
            return
        worker.cancel()
        self._keep_theme_store_detail_image_worker(worker)
        self.themeStoreDetailImageWorker = None

    def _keep_theme_store_detail_image_worker(self, worker: QThread) -> None:
        worker_pool = getattr(self, "_detailImageWorkerPool", [])
        if worker not in worker_pool and worker.isRunning():
            worker_pool.append(worker)
        self._detailImageWorkerPool = worker_pool

    def _on_detail_image_worker_finished(self, worker: QThread) -> None:
        if getattr(self, "themeStoreDetailImageWorker", None) is worker:
            self.themeStoreDetailImageWorker = None
        self._detailImageWorkerPool = [
            item for item in getattr(self, "_detailImageWorkerPool", [])
            if item.isRunning()
        ]

    def _on_theme_store_detail_image_loaded(self, index: int, data: bytes) -> None:
        sender = self.sender()
        if sender is not None and sender is not getattr(self, "themeStoreDetailImageWorker", None):
            return
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
