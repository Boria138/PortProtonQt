"""Tests for local Wine/Proton archive installation."""

import io
import tarfile
from typing import Any, cast

from PySide6.QtCore import QMimeData, QUrl

from portprotonqt.dialogs.proton_manager import ProtonManager
from portprotonqt.dialogs.wine_extractor import ExtractionThread
from portprotonqt.tabs import library_tab


def test_dropped_wine_archives_accepts_supported_local_files(tmp_path) -> None:
    wine_archive = tmp_path / "WINE_LG_11-10.tar.xz"
    wine_archive.touch()
    unsupported = tmp_path / "wine.zip"
    unsupported.touch()
    mime_data = QMimeData()
    mime_data.setUrls(
        [QUrl.fromLocalFile(str(wine_archive)), QUrl.fromLocalFile(str(unsupported))]
    )

    archives = ProtonManager._get_dropped_wine_archives(mime_data)

    assert archives == [str(wine_archive)]


def test_extraction_rejects_path_traversal(tmp_path) -> None:
    archive_path = tmp_path / "WINE_LG.tar.gz"
    outside_path = tmp_path / "escaped"
    with tarfile.open(archive_path, "w:gz") as archive:
        entry = tarfile.TarInfo("../escaped")
        entry.size = 7
        archive.addfile(entry, io.BytesIO(b"escaped"))
    errors = []
    thread = ExtractionThread(str(archive_path), str(tmp_path / "dist"))
    thread.error.connect(errors.append)

    thread.run()

    assert errors
    assert not outside_path.exists()


def test_extraction_does_not_change_process_directory(tmp_path, monkeypatch) -> None:
    archive_path = tmp_path / "WINE_LG.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        entry = tarfile.TarInfo("WINE_LG/version")
        entry.size = 2
        archive.addfile(entry, io.BytesIO(b"11"))
    monkeypatch.setattr("os.chdir", lambda _path: (_ for _ in ()).throw(AssertionError()))
    errors = []
    thread = ExtractionThread(str(archive_path), str(tmp_path / "dist"))
    thread.error.connect(errors.append)

    thread.run()

    assert not errors
    assert (tmp_path / "dist/WINE_LG/version").read_bytes() == b"11"


def test_library_drop_opens_manager_for_wine_archive(tmp_path, monkeypatch) -> None:
    archive_path = tmp_path / "PROTON_LG_10-30.tar.xz"
    archive_path.touch()
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(archive_path))])
    calls = []

    class Event:
        accepted = False

        def mimeData(self):
            return mime_data

        def acceptProposedAction(self):
            self.accepted = True

    class Window:
        portproton_location = "/tmp/PortProtonQt"
        input_manager = None

    monkeypatch.setattr(
        library_tab, "show_proton_manager", lambda *args, **kwargs: calls.append(kwargs)
    )
    event = Event()

    library_tab.MainWindowLibraryTabMixin.dropEvent(cast(Any, Window()), event)

    assert event.accepted
    assert calls[0]["local_archives"] == [str(archive_path)]
