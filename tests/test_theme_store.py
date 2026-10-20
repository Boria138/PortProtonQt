"""Theme store UI race regression tests."""

from types import SimpleNamespace
from typing import Any, cast
import io
import tarfile
import zipfile

import pytest

from PySide6.QtCore import QEvent, QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QEnterEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QProgressDialog, QWidget
from types import MethodType

from portprotonqt.tabs import theme_store
from portprotonqt.tabs.theme_store import ThemeStoreCard, ThemeStoreMixin
from portprotonqt.tabs import theme_store_workers
from portprotonqt.tabs.library_tab import MainWindowLibraryTabMixin
from portprotonqt.tabs.workers import MainWindowWorkersMixin


@pytest.mark.parametrize("outcome", ["installed", "failed", "wine_archives"])
def test_theme_zip_drop_starts_retained_worker(tmp_path, monkeypatch, outcome) -> None:
    _app = QApplication.instance() or QApplication([])
    archive_path = tmp_path / "theme.zip"
    archive_path.touch()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(archive_path))])
    accepted = []
    event = SimpleNamespace(
        mimeData=lambda: mime,
        acceptProposedAction=lambda: accepted.append(True),
        ignore=lambda: accepted.append(False),
    )
    started = []
    monkeypatch.setattr(theme_store_workers.ThemeArchiveInstallWorker, "start", lambda self: started.append(self))
    window = cast(Any, QWidget())
    window.theme = SimpleNamespace(MESSAGE_BOX_STYLE="", PROGRESS_BAR_STYLE="")
    window._on_dropped_theme_installed = started.append
    window._on_dropped_theme_failed = started.append
    window._on_dropped_wine_archives = started.append
    window._install_dropped_theme_archives = MethodType(
        MainWindowLibraryTabMixin._install_dropped_theme_archives, window
    )
    MainWindowLibraryTabMixin.dragEnterEvent(cast(Any, window), event)
    MainWindowLibraryTabMixin.dropEvent(cast(Any, window), event)

    assert accepted == [True, True]
    assert started == window._themeArchiveWorkers
    assert started[0].paths == [str(archive_path)]
    progress = window.findChild(QProgressDialog)
    assert progress is not None
    assert progress.isVisible()
    assert progress.isModal()
    assert progress.minimum() == progress.maximum() == 0
    worker = started[0]
    getattr(worker, outcome).emit("error" if outcome == "failed" else ["custom"])
    assert progress.isVisible() == (outcome == "installed")
    worker.finished.emit()
    assert not progress.isVisible()
    assert window._themeArchiveWorkers == []


@pytest.mark.parametrize("archive_format", ["zip", "tar.gz"])
def test_dropped_theme_archive_installs_and_applies(tmp_path, monkeypatch, archive_format) -> None:
    archive_path = tmp_path / f"theme.{archive_format}"
    if archive_format == "zip":
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("custom/styles.py", "color = 'blue'\n")
    else:
        with tarfile.open(archive_path, "w:gz") as archive:
            content = b"color = 'blue'\n"
            entry = tarfile.TarInfo("custom/styles.py")
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))
    themes_dir = tmp_path / "themes"
    monkeypatch.setattr(theme_store_workers, "THEMES_DIRS", [themes_dir])
    applied = []
    invalidated = []
    refreshed = []
    window = SimpleNamespace(
        theme_manager=SimpleNamespace(invalidate_theme=invalidated.append),
        _refresh_theme_combo=refreshed.append,
        _apply_theme_and_restart=lambda name, variant: applied.append((name, variant)),
    )
    monkeypatch.setattr("portprotonqt.tabs.library_tab.ui_config.get_theme_variant", lambda: "dark")
    worker = theme_store_workers.ThemeArchiveInstallWorker([str(archive_path)])
    worker.installed.connect(
        lambda names: MainWindowLibraryTabMixin._on_dropped_theme_installed(cast(Any, window), names)
    )
    errors = []
    worker.failed.connect(errors.append)
    worker.run()

    assert not errors
    assert (themes_dir / "custom/styles.py").read_text() == "color = 'blue'\n"
    assert invalidated == refreshed == ["custom"]
    assert applied == [("custom", "dark")]


def test_dropped_archives_keep_wine_and_reject_unsafe_theme(tmp_path, monkeypatch) -> None:
    wine = tmp_path / "wine.tar.gz"
    with tarfile.open(wine, "w:gz") as archive:
        archive.addfile(tarfile.TarInfo("wine/bin/wine"))
    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("../styles.py", "")
    monkeypatch.setattr(theme_store_workers, "THEMES_DIRS", [tmp_path / "themes"])
    worker = theme_store_workers.ThemeArchiveInstallWorker([str(wine), str(unsafe)])
    wines = []
    errors = []
    installed = []
    worker.wine_archives.connect(wines.append)
    worker.failed.connect(errors.append)
    worker.installed.connect(installed.append)
    worker.run()

    assert wines == [[str(wine)]]
    assert len(errors) == 1
    assert installed == []
    assert not (tmp_path / "styles.py").exists()


def test_shutdown_waits_for_dropped_theme_workers() -> None:
    worker = SimpleNamespace()
    stopped = []
    window = SimpleNamespace(
        _themeArchiveWorkers=[worker],
        _stopWorkerThread=lambda *args: None,
        _stopWorkerThreads=lambda name: MainWindowWorkersMixin._stopWorkerThreads(cast(Any, window), name),
        _stopWorker=lambda *args: stopped.append(args),
    )
    MainWindowWorkersMixin._stopBackgroundWorkers(cast(Any, window))

    assert stopped == [(worker, "_themeArchiveWorkers", None)]
    assert window._themeArchiveWorkers == []


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
