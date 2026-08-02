"""Theme store UI race regression tests."""

from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QEnterEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel

from portprotonqt.tabs import theme_store
from portprotonqt.tabs.theme_store import ThemeStoreCard, ThemeStoreMixin


class FakeSignal:
    def __init__(self) -> None:
        self.callbacks: list[Any] = []

    def connect(self, callback: Any) -> None:
        self.callbacks.append(callback)


class FakeWorker:
    def __init__(self, *_args: object) -> None:
        self.loaded = FakeSignal()
        self.failed = FakeSignal()
        self.finished = FakeSignal()
        self.cancelled = False
        self.running = True
        self.started = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True

    def isRunning(self) -> bool:
        return self.running


class FakeLabel:
    def __init__(self) -> None:
        self.visible = False
        self.text = ""

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def setText(self, text: str) -> None:
        self.text = text


class FakeThemeStore(ThemeStoreMixin):
    def __init__(self) -> None:
        self._sender: object | None = None
        self.populated = False
        self.scheduled = False

    def sender(self) -> object | None:
        return self._sender

    def _populate_theme_store_cards(self) -> None:
        self.populated = True

    def _schedule_visible_image_load(self) -> None:
        self.scheduled = True


def test_theme_store_card_uses_mouse_sounds(monkeypatch: Any) -> None:
    app = QApplication.instance() or QApplication([])
    played_events: list[str] = []
    theme = type("Theme", (), {
        "THEME_STORE_CARD_STYLE": "",
        "THEME_STORE_PREVIEW_STYLE": "",
        "THEME_STORE_CARD_TITLE_STYLE": "",
        "THEME_STORE_CARD_META_STYLE": "",
    })()

    monkeypatch.setattr(
        "portprotonqt.sound_manager.SoundManager",
        lambda: SimpleNamespace(play=played_events.append),
    )
    card = ThemeStoreCard({}, theme)
    card.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))
    card.mouseMoveEvent(QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(),
        QPointF(),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    ))
    card.click()

    assert played_events == ["navigate", "open"]
    assert all(
        label.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        for label in card.findChildren(QLabel)
    )
    assert app is not None


def test_load_theme_store_keeps_replaced_list_worker(monkeypatch: Any) -> None:
    window = cast(Any, FakeThemeStore())
    old_worker = FakeWorker()
    window.themeStoreListWorker = old_worker
    window.themeStoreStatusLabel = FakeLabel()
    window.themeStoreSortCombo = type("SortCombo", (), {"currentIndex": lambda self: 0})()
    created_workers: list[FakeWorker] = []

    def create_worker(*args: object) -> FakeWorker:
        worker = FakeWorker(*args)
        created_workers.append(worker)
        return worker

    monkeypatch.setattr(theme_store, "ThemeStoreListWorker", create_worker)

    window._load_theme_store()

    assert old_worker in window._listWorkerPool
    assert window.themeStoreListWorker is created_workers[0]
    assert created_workers[0].started


def test_cancel_theme_store_image_worker_keeps_running_worker() -> None:
    window = cast(Any, FakeThemeStore())
    worker = FakeWorker()
    window.themeStoreImageWorker = worker

    window._cancel_theme_store_image_worker()

    assert worker.cancelled
    assert window.themeStoreImageWorker is None
    assert worker in window._imageWorkerPool


def test_cancel_theme_store_detail_worker_keeps_running_worker() -> None:
    window = cast(Any, FakeThemeStore())
    worker = FakeWorker()
    window.themeStoreDetailImageWorker = worker

    window._cancel_theme_store_detail_image_worker()

    assert worker.cancelled
    assert window.themeStoreDetailImageWorker is None
    assert worker in window._detailImageWorkerPool


def test_stale_list_worker_result_does_not_replace_theme_store_data() -> None:
    window = cast(Any, FakeThemeStore())
    current_worker = object()
    stale_worker = object()
    window.themeStoreListWorker = current_worker
    window.themeStoreStatusLabel = FakeLabel()
    window.themeStoreThemes = [{"name": "current"}]
    window._sender = stale_worker

    window._on_theme_store_loaded([{"name": "stale"}])

    assert window.themeStoreThemes == [{"name": "current"}]
    assert not window.populated
    assert not window.scheduled


def test_visible_image_load_keeps_active_worker(monkeypatch: Any) -> None:
    window = cast(Any, FakeThemeStore())
    worker = FakeWorker()
    window.themeStoreThemes = [{"name": "theme"}]
    window.themeStoreGridIndex = 1
    window.themeStoreLoadedUrls = set()
    window.themeStoreImageWorker = worker
    window._get_visible_theme_urls = lambda: ["preview.png"]

    def fail_worker_creation(*_args: object) -> None:
        raise AssertionError("A second image worker was created")

    monkeypatch.setattr(theme_store, "ThemeStoreImageWorker", fail_worker_creation)

    window._schedule_visible_image_load()

    assert window.themeStoreImageWorker is worker
    assert not worker.cancelled


def test_stale_preview_does_not_mark_url_loaded() -> None:
    window = cast(Any, FakeThemeStore())
    current_worker = object()
    window.themeStoreImageWorker = current_worker
    window.themeStoreLoadedUrls = set()
    window._sender = object()

    window._on_theme_store_preview_loaded("preview.png", b"image")

    assert window.themeStoreLoadedUrls == set()
