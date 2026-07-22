"""Sound manager for UI feedback sounds, integrated with the theme system."""
import sys
from pathlib import Path

from PySide6.QtCore import QUrl, qInstallMessageHandler

from portprotonqt.config import ui_config
from portprotonqt.logger import get_logger
from portprotonqt.theme_security import is_safe_sound_file

logger = get_logger(__name__)
SOUND_EVENTS = frozenset({
    "navigate", "click", "confirm", "back", "toggle", "open",
    "keyboard_key", "tab_switch",
    "game_launch", "gamepad_connect",
})
MISSING_MEDIA_BACKEND_WARNING = "No QtMultimedia backends found."


def _multimedia_message_handler(message_type: object, context: object, message: str) -> None:
    if message.startswith(MISSING_MEDIA_BACKEND_WARNING):
        return
    print(message, file=sys.stderr)


class _SoundSlot:
    """A single player slot that pre-loads a sound file."""

    def __init__(self) -> None:
        previous_handler = qInstallMessageHandler(_multimedia_message_handler)
        try:
            from PySide6.QtMultimedia import QSoundEffect
            self._effect = QSoundEffect()
        finally:
            qInstallMessageHandler(previous_handler)
        self._effect.setLoopCount(1)
        self._loaded_event: str | None = None

    def play(self, event: str, url: QUrl) -> None:
        if (
            self._loaded_event == event
            and self._effect.isPlaying()
        ):
            return
        if self._loaded_event != event:
            self._effect.setSource(url)
            self._loaded_event = event
        self._effect.stop()
        self._effect.play()

    def reset(self) -> None:
        self._effect.stop()
        self._effect.setSource(QUrl())
        self._loaded_event = None


class SoundManager:
    """Manages UI feedback sounds, loading from theme directories."""

    _instance: "SoundManager | None" = None

    def __new__(cls) -> "SoundManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._enabled = ui_config.get_sounds_enabled()
        self._sounds_dirs: list[str] = []
        try:
            self._slots = [_SoundSlot() for _ in range(4)]
        except ImportError as e:
            logger.warning("UI sounds are unavailable: %s", e)
            self._slots = []
        self._slot_index = 0
        self._url_cache: dict[str, QUrl] = {}

    def set_sounds_dirs(self, dirs: list[str]) -> None:
        if dirs != self._sounds_dirs:
            self._sounds_dirs = dirs
            self._url_cache.clear()
            for slot in self._slots:
                slot.reset()

    def reload_config(self) -> None:
        self._enabled = ui_config.get_sounds_enabled()

    def _find_sound_path(self, event: str) -> Path | None:
        if event not in SOUND_EVENTS:
            return None
        for sounds_dir in self._sounds_dirs:
            path = Path(sounds_dir) / f"{event}.wav"
            if path.is_file() and is_safe_sound_file(str(path)):
                return path
        return None

    def _get_url(self, event: str) -> QUrl | None:
        if event in self._url_cache:
            return self._url_cache[event]
        path = self._find_sound_path(event)
        if path is None:
            return None
        url = QUrl.fromLocalFile(str(path))
        self._url_cache[event] = url
        return url

    def play(self, event: str) -> None:
        if not self._enabled:
            return
        url = self._get_url(event)
        if url is None or not self._slots:
            return
        for slot in self._slots:
            if slot._loaded_event == event:
                slot.play(event, url)
                return
        slot = self._slots[self._slot_index]
        self._slot_index = (self._slot_index + 1) % len(self._slots)
        slot.play(event, url)

    def play_widget_sound(self, widget: object) -> None:
        from PySide6.QtWidgets import QCheckBox, QComboBox, QPushButton
        from portprotonqt.custom_widgets import AutoSizeButton, ClickableLabel, NavLabel
        property_method = getattr(widget, "property", None)
        sound_event = property_method("sound_event") if callable(property_method) else None
        if sound_event is False:
            return
        if isinstance(sound_event, str) and sound_event in SOUND_EVENTS:
            self.play(sound_event)
            return
        if isinstance(widget, (QPushButton, AutoSizeButton)):
            self.play("click")
        elif isinstance(widget, QCheckBox):
            self.play("toggle")
        elif isinstance(widget, QComboBox):
            self.play("open")
        elif isinstance(widget, (ClickableLabel, NavLabel)):
            self.play("click")

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        ui_config.set_sounds_enabled(enabled)

    @property
    def enabled(self) -> bool:
        return self._enabled
