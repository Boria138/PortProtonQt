import time
import threading
import os
import math
import ctypes
import ctypes.util
from functools import lru_cache
from dataclasses import dataclass
from typing import Protocol, cast, Any
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEO_ALLOW_SCREENSAVER", "1")
import pygame
from pygame._sdl2 import controller
from evdev import UInput, ecodes
from enum import Enum
from shiboken6 import isValid
from PySide6.QtWidgets import QWidget, QStackedWidget, QApplication, QScrollArea, QAbstractScrollArea, QLineEdit, QDialog, QMenu, QComboBox, QListView, QMessageBox, QListWidget, QTableWidget, QAbstractItemView, QSlider, QCheckBox, QPushButton
from PySide6.QtCore import Qt, QObject, QEvent, QPoint, Signal, Slot, QTimer, QThread
from PySide6.QtGui import QKeySequence
from portprotonqt.logger import get_logger
from portprotonqt.image_utils import FullscreenDialog
from portprotonqt.custom_widgets import NavLabel, AutoSizeButton
from portprotonqt.game_card import GameCard
from portprotonqt.config import display_config, gamepad_config, window_config
from portprotonqt.dialogs import AddGameDialog
from portprotonqt.virtual_keyboard import VirtualKeyboard

logger = get_logger(__name__)

class MainWindowProtocol(Protocol):
    def activateFocusedWidget(self) -> None:
        ...
    def goBackDetailPage(self, page: QWidget | None) -> None:
        ...
    def switchTab(self, index: int) -> None:
        ...
    def openAddGameDialog(self, exe_path: str | None = None) -> None:
        ...
    def toggleGame(self, exec_line: str | None, button: QWidget | None = None) -> None:
        ...
    def on_slider_released(self) -> None:
        ...
    def on_auto_slider_released(self) -> None:
        ...
    def isActiveWindow(self) -> bool:
        ...
    def refreshGames(self) -> None:
        ...
    def handleSystemTableGamepadAction(self, table: QTableWidget, action: str) -> bool:
        ...
    def handleSystemGamepadAction(self, action: str) -> bool:
        ...
    stackedWidget: QStackedWidget
    tabButtons: dict[int, QWidget]
    gamesListWidget: QWidget
    autoInstallContainer: QWidget | None
    currentDetailPage: QWidget | None
    current_exec_line: str | None
    current_add_game_dialog: AddGameDialog | None
    game_library_manager: Any  # GameLibraryManager - using Any to avoid circular import
    auto_size_slider: QSlider | None

PAD_BUTTON_SOUTH = 1000
PAD_BUTTON_EAST = 1001
PAD_BUTTON_WEST = 1002
PAD_BUTTON_NORTH = 1003
PAD_BUTTON_SELECT = 1004
PAD_BUTTON_GUIDE = 1005
PAD_BUTTON_START = 1006
PAD_BUTTON_LEFT_SHOULDER = 1007
PAD_BUTTON_RIGHT_SHOULDER = 1008
PAD_AXIS_LEFT_TRIGGER = 1100
PAD_AXIS_RIGHT_TRIGGER = 1101
PAD_AXIS_LEFT_X = 1200
PAD_AXIS_LEFT_Y = 1201
PAD_AXIS_RIGHT_X = 1202
PAD_AXIS_RIGHT_Y = 1203
PAD_DPAD_X = 1300
PAD_DPAD_Y = 1301

BUTTONS = {
    'confirm':       {PAD_BUTTON_SOUTH},           # A (Xbox) / Cross (PS) / B (Switch)
    'back':          {PAD_BUTTON_EAST},            # B (Xbox) / Circle (PS) / A (Switch)
    'add_game':      {PAD_BUTTON_WEST},            # X (Xbox) / Square (PS) / Y (Switch)
    'prev_dir':      {PAD_BUTTON_NORTH},           # Y (Xbox) / Triangle (PS) / X (Switch)
    'prev_tab':      {PAD_BUTTON_LEFT_SHOULDER},
    'next_tab':      {PAD_BUTTON_RIGHT_SHOULDER},
    'context_menu':  {PAD_BUTTON_START},
    'menu':          {PAD_BUTTON_SELECT},
    'guide':         {PAD_BUTTON_GUIDE},
    'increase_size': {PAD_AXIS_RIGHT_TRIGGER},
    'decrease_size': {PAD_AXIS_LEFT_TRIGGER},
}

class GamepadType(Enum):
    XBOX = "Xbox"
    PLAYSTATION = "PlayStation"
    UNKNOWN = "Unknown"

SDL_INIT_GAMEPAD = 0x00002000
SDL_GAMEPAD_TYPE_STANDARD = 1
SDL_GAMEPAD_TYPE_XBOX360 = 2
SDL_GAMEPAD_TYPE_XBOXONE = 3
SDL_GAMEPAD_TYPE_PS3 = 4
SDL_GAMEPAD_TYPE_PS4 = 5
SDL_GAMEPAD_TYPE_PS5 = 6
SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO = 7
SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_LEFT = 8
SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_RIGHT = 9
SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_PAIR = 10
SDL_GAMEPAD_TYPE_GAMECUBE = 11
SDL_GAMEPAD_TYPE_STEAM = 12
SDL3_XBOX_LIKE_TYPES = {
    SDL_GAMEPAD_TYPE_STANDARD,
    SDL_GAMEPAD_TYPE_XBOX360,
    SDL_GAMEPAD_TYPE_XBOXONE,
    SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO,
    SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_LEFT,
    SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_RIGHT,
    SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_PAIR,
    SDL_GAMEPAD_TYPE_GAMECUBE,
    SDL_GAMEPAD_TYPE_STEAM,
}
SDL3_PLAYSTATION_TYPES = {
    SDL_GAMEPAD_TYPE_PS3,
    SDL_GAMEPAD_TYPE_PS4,
    SDL_GAMEPAD_TYPE_PS5,
}


def _get_sdl3_error(sdl: ctypes.CDLL) -> str:
    """Return the current SDL3 error message."""
    error = sdl.SDL_GetError()
    if not error:
        return ""
    return error.decode(errors="replace")


def _configure_sdl3_gamepad_api(sdl: ctypes.CDLL) -> None:
    """Configure ctypes signatures for the SDL3 gamepad calls used here."""
    sdl.SDL_InitSubSystem.argtypes = [ctypes.c_uint32]
    sdl.SDL_InitSubSystem.restype = ctypes.c_bool
    sdl.SDL_GetGamepads.argtypes = [ctypes.POINTER(ctypes.c_int)]
    sdl.SDL_GetGamepads.restype = ctypes.POINTER(ctypes.c_uint32)
    sdl.SDL_GetGamepadTypeForID.argtypes = [ctypes.c_uint32]
    sdl.SDL_GetGamepadTypeForID.restype = ctypes.c_int
    sdl.SDL_GetGamepadNameForID.argtypes = [ctypes.c_uint32]
    sdl.SDL_GetGamepadNameForID.restype = ctypes.c_char_p
    sdl.SDL_GetError.argtypes = []
    sdl.SDL_GetError.restype = ctypes.c_char_p
    sdl.SDL_free.argtypes = [ctypes.c_void_p]
    sdl.SDL_free.restype = None


@lru_cache(maxsize=1)
def _load_sdl3() -> ctypes.CDLL | None:
    """Load SDL3 and initialize its gamepad subsystem when available."""
    library_names = (
        ctypes.util.find_library("SDL3"),
        "libSDL3.so.0",
        "libSDL3.so",
    )
    for library_name in library_names:
        if not library_name:
            continue
        try:
            sdl = ctypes.CDLL(library_name)
            _configure_sdl3_gamepad_api(sdl)
        except (AttributeError, OSError) as e:
            logger.debug("Failed to load SDL3 from %s: %s", library_name, e)
            continue
        if sdl.SDL_InitSubSystem(SDL_INIT_GAMEPAD):
            return sdl
        logger.debug("Failed to initialize SDL3 gamepad subsystem: %s", _get_sdl3_error(sdl))
    return None


def _decode_sdl3_name(name: bytes | None) -> str:
    """Decode a SDL3 device name."""
    if not name:
        return ""
    return name.decode(errors="replace")


def _gamepad_type_from_sdl3_value(sdl_type: int) -> GamepadType | None:
    """Map SDL_GamepadType to the existing UI icon families."""
    if sdl_type in SDL3_PLAYSTATION_TYPES:
        return GamepadType.PLAYSTATION
    if sdl_type in SDL3_XBOX_LIKE_TYPES:
        return GamepadType.XBOX
    return None


def _get_sdl3_gamepad_type(gamepad: "PygameGamepad") -> GamepadType | None:
    """Read SDL_GamepadType from SDL3 for the current pygame controller."""
    sdl = _load_sdl3()
    if sdl is None:
        return None

    count = ctypes.c_int()
    gamepads = sdl.SDL_GetGamepads(ctypes.byref(count))
    if not gamepads:
        return None

    try:
        target_name = gamepad.name.casefold()
        for index in range(count.value):
            gamepad_id = gamepads[index]
            sdl_name = _decode_sdl3_name(sdl.SDL_GetGamepadNameForID(gamepad_id))
            if count.value > 1 and sdl_name.casefold() != target_name:
                continue
            gamepad_type = _gamepad_type_from_sdl3_value(sdl.SDL_GetGamepadTypeForID(gamepad_id))
            if gamepad_type is not None:
                return gamepad_type
    finally:
        sdl.SDL_free(gamepads)
    return None


@dataclass
class PygameGamepad:
    """Small wrapper that preserves the old InputManager gamepad contract."""

    controller: Any
    name: str
    path: str
    instance_id: int

    def close(self) -> None:
        """Release local references for the SDL joystick object."""
        try:
            self.controller.quit()
        except (AttributeError, pygame.error) as e:
            logger.debug("Failed to close pygame controller: %s", e)


SDL_CONTROLLER_BUTTON_TO_ECODE = {
    0: PAD_BUTTON_SOUTH,
    1: PAD_BUTTON_EAST,
    2: PAD_BUTTON_WEST,
    3: PAD_BUTTON_NORTH,
    4: PAD_BUTTON_SELECT,
    5: PAD_BUTTON_GUIDE,
    6: PAD_BUTTON_START,
    9: PAD_BUTTON_LEFT_SHOULDER,
    10: PAD_BUTTON_RIGHT_SHOULDER,
}

SDL_CONTROLLER_AXIS_TO_ECODE = {
    0: PAD_AXIS_LEFT_X,
    1: PAD_AXIS_LEFT_Y,
    2: PAD_AXIS_RIGHT_X,
    3: PAD_AXIS_RIGHT_Y,
    4: PAD_AXIS_LEFT_TRIGGER,
    5: PAD_AXIS_RIGHT_TRIGGER,
}

PYGAME_AXIS_SCALE = 32767

class MouseEmulationThread(QThread):
    """Thread for creating UInput virtual mouse device without blocking UI."""

    finished = Signal(bool)  # Emitted when done (True = success, False = failed)

    def run(self):
        """Run UInput device creation in background thread."""
        try:
            if not os.path.exists('/dev/uinput'):
                logger.error("EMUL: /dev/uinput does not exist")
                self.finished.emit(False)
                return

            if not os.access('/dev/uinput', os.W_OK):
                logger.error("EMUL: No write access to /dev/uinput")
                self.finished.emit(False)
                return

            ui = UInput({
                ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT],
                ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL],
            }, name="Virtual DPad Mouse")

            self.finished.emit(True)
            # Store device in thread result
            self._device = ui

        except PermissionError as e:
            logger.error("EMUL: Permission denied for /dev/uinput: %s", e)
            self.finished.emit(False)
        except Exception as ex:
            logger.error(f"EMUL: Error creating virtual mouse: {ex}", exc_info=True)
            self.finished.emit(False)

    def get_device(self) -> UInput | None:
        """Get the created UInput device after thread finishes."""
        return getattr(self, '_device', None)


class InputManager(QObject):
    """
    Manages input from gamepads and keyboards for navigating the application interface.
    Supports gamepad hotplugging, button and axis events, and pygame keyboard events
    for seamless UI interaction.
    """
    # Signals for gamepad events
    button_event = Signal(int, int)  # Signal for button events: (code, value) where value=1 (press), 0 (release)
    dpad_moved = Signal(int, int, float)  # Signal for D-pad movements
    toggle_fullscreen = Signal(bool)  # Signal for toggling fullscreen mode (True for fullscreen, False for normal)
    gamepad_hotplug = Signal(str)  # 'add' or 'remove'

    def __init__(
        self,
        main_window: MainWindowProtocol,
        axis_deadzone: float = 0.5,
        initial_axis_move_delay: float = 0.3,
        repeat_axis_move_delay: float = 0.15
    ):
        super().__init__(cast(QObject, main_window))
        self._parent = main_window
        self._gamepad_handling_enabled = True
        self.gamepad_type = self._get_configured_gamepad_type()
        self._parent.currentDetailPage = getattr(self._parent, 'currentDetailPage', None)
        self._parent.current_exec_line = getattr(self._parent, 'current_exec_line', None)
        self._parent.current_add_game_dialog = getattr(self._parent, 'current_add_game_dialog', None)
        self._parent.autoInstallContainer = getattr(self._parent, 'autoInstallContainer', None)
        self.axis_deadzone = axis_deadzone
        self.initial_axis_move_delay = initial_axis_move_delay
        self.repeat_axis_move_delay = repeat_axis_move_delay
        self.current_axis_delay = initial_axis_move_delay
        self.last_move_time = 0.0
        self.axis_moving = False
        self.gamepad: PygameGamepad | None = None
        self.gamepad_thread: threading.Thread | None = None
        self.running = True
        self._is_fullscreen = display_config.get_fullscreen()
        self.lt_pressed = False
        self.rt_pressed = False
        self.last_trigger_time = 0.0
        self.trigger_cooldown = 0.2

        # Mouse emulation attributes
        self.mouse_emulation_enabled = True
        self.ui = None
        self.mouse_emulation_thread: MouseEmulationThread | None = None
        self.stick_x_raw = 0
        self.stick_y_raw = 0

        # Axis parameters (will be filled from kernel)
        self.center_x = 127      # X axis center
        self.center_y = 127      # Y axis center
        self.min_value = 0       # axis minimum
        self.max_value = 255     # axis maximum
        self.deadzone_value = 15 # deadzone from kernel (flat parameter)
        self.scroll_axis_code = PAD_AXIS_RIGHT_Y
        self.scroll_center = self.center_y
        self.scroll_min_value = self.min_value
        self.scroll_max_value = self.max_value
        self.scroll_deadzone_value = self.deadzone_value

        self.sensitivity = 8.0

        # Dynamic attributes for different modes (declared here to satisfy type checkers)
        self.winetricks_dialog = None
        self.settings_dialog = None
        self.file_explorer = None
        self.proton_manager_dialog = None
        self.original_button_handler = None
        self.original_dpad_handler = None
        self.original_gamepad_state = None
        self._original_handlers_saved = False
        self.scroll_accumulator = 0.0
        self.scroll_sensitivity = 0.15
        self.scroll_threshold = 0.2
        self.last_update = time.time()
        self.update_interval = 0.016  # ~60 FPS
        self.emulation_active = False
        self.emulation_triggered = False
        self.start_held = False
        self.select_held = False
        self.pending_menu_fullscreen_time = 0.0
        self.guide_held = False
        # Variables for key combination handling
        self.guide_pressed_time = 0
        self.select_pressed_time = 0
        self.guide_timer = QTimer(self)
        self.guide_timer.setSingleShot(True)
        self.guide_timer.timeout.connect(self._handle_guide_timeout)
        self.guide_combination_timeout = 0.3  # 300ms timeout for combination
        self.in_guide_combination_attempt = False  # Flag to track if we're in a guide+select combination attempt
        self._pygame_ready = False
        self._button_states: dict[int, int] = {}
        self._hat_states: dict[int, tuple[int, int]] = {}
        self._axis_states: dict[int, int] = {}
        self._gamepad_polling_suspended = False

        # Focus check timer for emulation flag (runs in main thread)
        self.focus_check_timer = QTimer(self)
        self.focus_check_timer.timeout.connect(self._update_emulation_flag)
        self.focus_check_timer.start(100)  # Check every 100ms

        logger.info("EMUL: Mouse emulation initialized (enabled=%s)", self.mouse_emulation_enabled)

        if self.mouse_emulation_enabled:
            # Initialize mouse emulation asynchronously to avoid blocking startup
            QTimer.singleShot(0, self._async_enable_mouse_emulation)

        # FileExplorer specific attributes
        self.file_explorer = None
        self.original_button_handler = None
        self.original_dpad_handler = None
        self.original_gamepad_state = None
        self.nav_timer = QTimer(self)
        self.nav_timer.timeout.connect(self.handle_navigation_repeat)
        self.current_direction = 0
        self.last_nav_time = 0
        self.initial_nav_delay = 0.1  # Initial delay before first repeat (sec)
        self.repeat_nav_delay = 0.05  # Interval between repeats (sec)
        self.stick_activated = False
        self.stick_value = 0  # Current stick value (for smoothness)
        self.dead_zone = 8000  # Stick deadzone

        self._is_gamescope_session = 'gamescope' in os.environ.get('DESKTOP_SESSION', '').lower()

        # Add variables for continuous D-pad movement
        self.dpad_timer = QTimer(self)
        self.dpad_timer.timeout.connect(self.handle_dpad_repeat)
        self.current_dpad_code = None  # Tracks the current D-pad axis (e.g., ABS_HAT0X, ABS_HAT0Y)
        self.current_dpad_value = 0    # Tracks the current D-pad direction value (e.g., -1, 1)

        # Connect signals to slots
        self.button_event.connect(self.handle_button_slot)
        self.dpad_moved.connect(self.handle_dpad_slot)
        self.toggle_fullscreen.connect(self.handle_fullscreen_slot)

        # Install wheel event filter
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        # Initialize pygame input backend
        self.init_gamepad()
        self.pygame_event_timer = QTimer(self)
        self.pygame_event_timer.timeout.connect(self._process_pygame_events)
        self.pygame_event_timer.start(10)

    def _async_enable_mouse_emulation(self):
        """Asynchronously enable mouse emulation to avoid blocking startup."""
        logger.info("EMUL: Attempting to create UInput virtual mouse...")
        self.mouse_emulation_thread = MouseEmulationThread()
        self.mouse_emulation_thread.finished.connect(self._on_mouse_emulation_finished)
        self.mouse_emulation_thread.start()

    def _on_mouse_emulation_finished(self, success: bool):
        """Handle mouse emulation thread completion."""
        if success and self.mouse_emulation_thread:
            device = self.mouse_emulation_thread.get_device()
            if device:
                self.ui = device
                self.mouse_emulation_enabled = True
                logger.info("EMUL: Virtual mouse created successfully")
        else:
            self.mouse_emulation_enabled = False

    def _update_emulation_flag(self):
        """Update emulation_active flag based on Qt app focus (main thread only)."""
        # True when mouse emulation is enabled (works regardless of focus)
        # The difference is whether other inputs are disabled (based on focus)
        self.emulation_active = self.mouse_emulation_enabled
        if not self.emulation_active:
            self.emulation_triggered = False

    def _navigate_game_cards(self, container, tab_index: int, code: int, value: int) -> None:
        """Common navigation logic for game cards in a container."""
        if container is None:
            return
        focused = QApplication.focusWidget()
        game_cards = container.findChildren(GameCard)
        if not game_cards:
            return

        scroll_area = container.parentWidget()
        while scroll_area and not isinstance(scroll_area, QScrollArea):
            scroll_area = scroll_area.parentWidget()

        # If no focused widget or not a GameCard, focus the first card
        if not isinstance(focused, GameCard) or focused not in game_cards:
            game_cards[0].setFocus()
            if scroll_area:
                scroll_area.ensureWidgetVisible(game_cards[0], 50, 50)
            return

        cards = container.findChildren(GameCard, options=Qt.FindChildOption.FindChildrenRecursively)
        if not cards:
            return
        # Group cards by rows with tolerance for y-position
        rows = {}
        y_tolerance = 10  # Allow slight variations in y-position
        for card in cards:
            y = card.pos().y()
            matched = False
            for row_y in rows:
                if abs(y - row_y) <= y_tolerance:
                    rows[row_y].append(card)
                    matched = True
                    break
            if not matched:
                rows[y] = [card]
        sorted_rows = sorted(rows.items(), key=lambda x: x[0])
        if not sorted_rows:
            return
        current_row_idx = None
        current_col_idx = None
        for row_idx, (_y, row_cards) in enumerate(sorted_rows):
            for idx, card in enumerate(row_cards):
                if card == focused:
                    current_row_idx = row_idx
                    current_col_idx = idx
                    break
            if current_row_idx is not None:
                break

        # Fallback: if focused card not found, select closest row by y-position
        if current_row_idx is None:
            if not sorted_rows:  # Additional safety check
                return
            focused_y = focused.pos().y()
            current_row_idx = min(range(len(sorted_rows)), key=lambda i: abs(sorted_rows[i][0] - focused_y))
            if current_row_idx >= len(sorted_rows):  # Safety check
                return
            current_row = sorted_rows[current_row_idx][1]
            focused_x = focused.pos().x() + focused.width() / 2
            current_col_idx = min(range(len(current_row)), key=lambda i: abs((current_row[i].pos().x() + current_row[i].width() / 2) - focused_x), default=0)

        # Add null checks before using current_row_idx and current_col_idx
        if current_row_idx is None or current_col_idx is None or current_row_idx >= len(sorted_rows):
            return

        current_row = sorted_rows[current_row_idx][1]
        if code == PAD_DPAD_X and value != 0:
            if value < 0:  # Left
                if current_col_idx > 0:
                    next_card = current_row[current_col_idx - 1]
                    next_card.setFocus(Qt.FocusReason.OtherFocusReason)
                    if scroll_area:
                        scroll_area.ensureWidgetVisible(next_card, 50, 50)
                else:
                    if current_row_idx > 0:
                        prev_row = sorted_rows[current_row_idx - 1][1]
                        next_card = prev_row[-1] if prev_row else None
                        if next_card:
                            next_card.setFocus(Qt.FocusReason.OtherFocusReason)
                            if scroll_area:
                                scroll_area.ensureWidgetVisible(next_card, 50, 50)
            elif value > 0:  # Right
                if current_col_idx < len(current_row) - 1:
                    next_card = current_row[current_col_idx + 1]
                    next_card.setFocus(Qt.FocusReason.OtherFocusReason)
                    if scroll_area:
                        scroll_area.ensureWidgetVisible(next_card, 50, 50)
                else:
                    if current_row_idx < len(sorted_rows) - 1:
                        next_row = sorted_rows[current_row_idx + 1][1]
                        next_card = next_row[0] if next_row else None
                        if next_card:
                            next_card.setFocus(Qt.FocusReason.OtherFocusReason)
                            if scroll_area:
                                scroll_area.ensureWidgetVisible(next_card, 50, 50)
        elif code == PAD_DPAD_Y and value != 0:
            if value > 0:  # Down
                if current_row_idx < len(sorted_rows) - 1:
                    next_row = sorted_rows[current_row_idx + 1][1]
                    current_x = focused.pos().x() + focused.width() / 2
                    next_card = min(
                        next_row,
                        key=lambda c: abs((c.pos().x() + c.width() / 2) - current_x),
                        default=None
                    )
                    if next_card:
                        next_card.setFocus(Qt.FocusReason.OtherFocusReason)
                        if scroll_area:
                            scroll_area.ensureWidgetVisible(next_card, 50, 50)
            elif value < 0:  # Up
                if current_row_idx > 0:
                    prev_row = sorted_rows[current_row_idx - 1][1]
                    current_x = focused.pos().x() + focused.width() / 2
                    next_card = min(
                        prev_row,
                        key=lambda c: abs((c.pos().x() + c.width() / 2) - current_x),
                        default=None
                    )
                    if next_card:
                        next_card.setFocus(Qt.FocusReason.OtherFocusReason)
                        if scroll_area:
                            scroll_area.ensureWidgetVisible(next_card, 50, 50)
                elif current_row_idx == 0:
                    self._parent.tabButtons[tab_index].setFocus(Qt.FocusReason.OtherFocusReason)

    # FILE EXPLORER MODE
    def enable_file_explorer_mode(self, file_explorer):
        """Configure gamepad handling for FileExplorer"""
        try:
            self._setup_mode_handlers(
                file_explorer,
                self.handle_file_explorer_button,
                self.handle_file_explorer_dpad,
                'file_explorer'
            )
            logger.debug("Gamepad handling successfully connected for FileExplorer")
        except Exception as e:
            logger.error(f"Error connecting gamepad handlers for FileExplorer: {e}")

    def disable_file_explorer_mode(self):
        """Restore original handlers (return default)"""
        try:
            if self.file_explorer:
                # Additional cleanup for file explorer
                self.nav_timer.stop()
                self._restore_original_handlers('file_explorer')
                logger.debug("Gamepad handling successfully restored")
        except Exception as e:
            logger.error(f"Error restoring gamepad handlers: {e}")

    def handle_file_explorer_button(self, button_code, value):
        active_window = QApplication.activeWindow()
        dialog_keyboard = getattr(active_window, 'keyboard', None) if active_window else None
        if isinstance(dialog_keyboard, VirtualKeyboard) and dialog_keyboard.isVisible():
            self.handle_virtual_keyboard(button_code, value)
            return

        keyboard = getattr(self._parent, 'keyboard', None)
        if keyboard and keyboard.isVisible():
            self.handle_virtual_keyboard(button_code, value)
            return

        if value == 0:  # Ignore releases
            return

        try:
            # 1. Handle Popups (Menus)
            popup = QApplication.activePopupWidget()
            if isinstance(popup, QMenu):
                if button_code in BUTTONS['confirm']:  # A button
                    if popup.activeAction():
                        popup.activeAction().trigger()
                        popup.close()
                    return
                elif button_code in BUTTONS['back']:  # B button
                    popup.close()
                    return
                return  # Skip other handling if menu is open

            active_window = QApplication.activeWindow()
            if isinstance(active_window, QDialog) and active_window != self.file_explorer:
                if button_code in BUTTONS['confirm']:  # A button
                    focused_widget = QApplication.focusWidget()
                    if isinstance(focused_widget, QLineEdit):
                        keyboard = getattr(active_window, 'keyboard', None)
                        if not keyboard:
                            keyboard = getattr(self._parent, 'keyboard', None)
                        if keyboard:
                            focused_widget.setFocus()
                            keyboard.show_for_widget(focused_widget)
                    elif isinstance(focused_widget, QPushButton):
                        focused_widget.click()
                    else:
                        active_window.accept()
                elif button_code in BUTTONS['back']:  # B button
                    active_window.reject()
                return

            # 2. Validate File Explorer state
            if not self.file_explorer or not hasattr(self.file_explorer, 'file_list'):
                logger.debug("No file explorer or file_list available")
                return

            focused_widget = QApplication.focusWidget()

            # 3. Handle Buttons
            if button_code in BUTTONS['confirm']:  # A button
                # Check if a drive button is focused
                if isinstance(focused_widget, AutoSizeButton) and \
                   hasattr(self.file_explorer, 'drive_buttons') and \
                   focused_widget in self.file_explorer.drive_buttons:
                    self.file_explorer.select_drive()
                    return

                if self.file_explorer.file_list.count() == 0:
                    return

                selected = self.file_explorer.file_list.currentItem().text()
                full_path = os.path.join(self.file_explorer.current_path, selected)

                if os.path.isdir(full_path):
                    self.file_explorer.current_path = os.path.normpath(full_path)
                    self.file_explorer.update_file_list()
                elif not self.file_explorer.directory_only:
                    self.file_explorer.file_signal.file_selected.emit(os.path.normpath(full_path))
                    self.file_explorer.accept()
                else:
                    logger.debug(f"Selected item is not a directory: {full_path}")

            elif button_code in BUTTONS['context_menu']:  # Start button
                if self.file_explorer.file_list.count() == 0:
                    return

                current_item = self.file_explorer.file_list.currentItem()
                if current_item:
                    item_rect = self.file_explorer.file_list.visualItemRect(current_item)
                    self.file_explorer.show_folder_context_menu(item_rect.center())

            elif button_code in BUTTONS['add_game']:  # X button
                if self.file_explorer.file_list.count() == 0:
                    return

                selected = self.file_explorer.file_list.currentItem().text()
                full_path = os.path.join(self.file_explorer.current_path, selected)

                if os.path.isdir(full_path):
                    self.file_explorer.file_signal.file_selected.emit(os.path.normpath(full_path))
                    self.file_explorer.accept()

            elif button_code in BUTTONS['back']:  # B button
                self.file_explorer.close()

            elif button_code in BUTTONS['prev_dir']:  # Y button
                self.file_explorer.previous_dir()

            else:
                if self.original_button_handler:
                    self.original_button_handler(button_code, value)

        except Exception as e:
            logger.error(f"Error in FileExplorer button handler: {e}")

    def handle_file_explorer_dpad(self, code, value, current_time):
        try:
            active_window = QApplication.activeWindow()
            keyboard = getattr(active_window, 'keyboard', None) if active_window else None
            if keyboard is None:
                keyboard = getattr(self._parent, 'keyboard', None)

            if keyboard and keyboard.isVisible():
                if code in (PAD_DPAD_X, PAD_AXIS_LEFT_X):
                    normalized_value = value
                    if code == PAD_AXIS_LEFT_X:
                        if abs(value) < self.dead_zone:
                            return
                        normalized_value = 1 if value > self.dead_zone else -1
                    if normalized_value > 0:
                        keyboard.move_focus_right()
                    elif normalized_value < 0:
                        keyboard.move_focus_left()
                elif code in (PAD_DPAD_Y, PAD_AXIS_LEFT_Y):
                    normalized_value = value
                    if code == PAD_AXIS_LEFT_Y:
                        if abs(value) < self.dead_zone:
                            return
                        normalized_value = 1 if value > self.dead_zone else -1
                    if normalized_value > 0:
                        keyboard.move_focus_down()
                    elif normalized_value < 0:
                        keyboard.move_focus_up()
                return

            # 1. Handle Popups (Menus)
            popup = QApplication.activePopupWidget()
            if isinstance(popup, QMenu):
                if code == PAD_DPAD_Y and value != 0:
                    self._navigate_menu_actions(popup, direction_down=value > 0)
                return

            focused_widget = QApplication.focusWidget()
            if isinstance(active_window, QDialog) and active_window != self.file_explorer:
                if not focused_widget or not active_window.focusWidget():
                    focusables = active_window.findChildren(
                        QWidget,
                        options=Qt.FindChildOption.FindChildrenRecursively
                    )
                    focusables = [w for w in focusables if w.focusPolicy() & Qt.FocusPolicy.StrongFocus]
                    if focusables:
                        focusables[0].setFocus(Qt.FocusReason.OtherFocusReason)
                    return
                if code == PAD_DPAD_X and value != 0:
                    if value > 0:
                        active_window.focusNextChild()
                    elif value < 0:
                        active_window.focusPreviousChild()
                    return
                if code == PAD_DPAD_Y and value != 0 and not isinstance(focused_widget, QTableWidget):
                    if value > 0:
                        active_window.focusNextChild()
                    elif value < 0:
                        active_window.focusPreviousChild()
                    return

            # 2. Validate State
            if not self.file_explorer or not hasattr(self.file_explorer, 'file_list') or not self.file_explorer.file_list:
                return

            focused_widget = QApplication.focusWidget()

            # 3. Handle Drive Buttons Navigation (Horizontal)
            if code in (PAD_DPAD_X, PAD_AXIS_LEFT_X) and \
               hasattr(self.file_explorer, 'drive_buttons') and \
               self.file_explorer.drive_buttons:

                if not isinstance(focused_widget, AutoSizeButton) or focused_widget not in self.file_explorer.drive_buttons:
                    # Focus first drive button if not currently on one
                    self.file_explorer.drive_buttons[0].setFocus()
                    self.file_explorer.ensure_button_visible(self.file_explorer.drive_buttons[0])
                    return

                current_idx = self.file_explorer.drive_buttons.index(focused_widget)
                next_idx = current_idx

                if value < 0:  # Left
                    next_idx = max(current_idx - 1, 0)
                elif value > 0:  # Right
                    next_idx = min(current_idx + 1, len(self.file_explorer.drive_buttons) - 1)

                if next_idx != current_idx:
                    self.file_explorer.drive_buttons[next_idx].setFocus()
                    self.file_explorer.ensure_button_visible(self.file_explorer.drive_buttons[next_idx])
                return

            # 4. Handle Vertical Navigation (File List vs Drive Buttons)
            elif code in (PAD_DPAD_Y, PAD_AXIS_LEFT_Y):
                # Move from buttons to list
                if isinstance(focused_widget, AutoSizeButton) and focused_widget in self.file_explorer.drive_buttons:
                    if value > 0 and self.file_explorer.file_list.count() > 0:
                        self.file_explorer.file_list.setFocus()
                        self.file_explorer.file_list.setCurrentRow(0)
                        self.file_explorer.file_list.scrollToItem(self.file_explorer.file_list.currentItem())
                    return

                # D-pad: Fixed speed
                if code == PAD_DPAD_Y:
                    if value != 0:
                        self.current_direction = value
                        self.stick_value = 1.0
                        if not self.nav_timer.isActive():
                            self.file_explorer.move_selection(self.current_direction)
                            self.last_nav_time = current_time
                            self.nav_timer.start(int(self.initial_nav_delay * 1000))
                    else:
                        self.current_direction = 0
                        self.nav_timer.stop()

                # Stick: Analog speed
                elif code == PAD_AXIS_LEFT_Y:
                    if abs(value) < self.dead_zone:
                        if self.stick_activated:
                            self.current_direction = 0
                            self.nav_timer.stop()
                            self.stick_activated = False
                        return

                    normalized_value = (abs(value) - self.dead_zone) / (32768 - self.dead_zone)
                    speed_factor = 0.3 + (normalized_value * 0.7)

                    self.current_direction = -1 if value < 0 else 1
                    self.stick_value = speed_factor
                    self.stick_activated = True

                    if not self.nav_timer.isActive():
                        self.file_explorer.move_selection(self.current_direction)
                        self.last_nav_time = current_time
                        self.nav_timer.start(int(self.initial_nav_delay * 1000))

            # 5. Fallback
            elif self.original_dpad_handler:
                self.original_dpad_handler(code, value, current_time)

        except Exception as e:
            logger.error(f"Error in FileExplorer dpad handler: {e}")

    # WINETRICKS MODE
    def enable_winetricks_mode(self, winetricks_dialog):
        """Setup gamepad handling for WinetricksDialog"""
        try:
            self._setup_mode_handlers(
                winetricks_dialog,
                self.handle_winetricks_button,
                self.handle_winetricks_dpad,
                'winetricks_dialog'
            )
            logger.debug("Gamepad handling successfully connected for WinetricksDialog")
        except Exception as e:
            logger.error(f"Error connecting gamepad handlers for Winetricks: {e}")

    def disable_winetricks_mode(self):
        """Restore original main window handlers"""
        try:
            if self.winetricks_dialog:
                self._restore_original_handlers('winetricks_dialog')
                logger.debug("Gamepad handling successfully restored from Winetricks")
        except Exception as e:
            logger.error(f"Error restoring gamepad handlers from Winetricks: {e}")

    def handle_winetricks_button(self, button_code, value):
        if self.winetricks_dialog is None or value == 0:
            return

        try:
            # Handle common UI elements like QMessageBox, QMenu, etc.
            if self._handle_common_ui_elements(button_code):
                return

            # Winetricks-specific button handling
            focused = QApplication.focusWidget()

            if button_code in BUTTONS['confirm']:  # A: Toggle checkbox
                if isinstance(focused, QTableWidget):
                    self.handle_table_confirm(focused)
                return

            elif button_code in BUTTONS['add_game']:  # X: Install
                self.winetricks_dialog.install_selected(force=False)

            elif button_code in BUTTONS['prev_dir']:  # Y: Force Install
                self.winetricks_dialog.install_selected(force=True)

            elif button_code in BUTTONS['back']:  # B: Cancel
                self.winetricks_dialog.reject()

            elif button_code in BUTTONS['prev_tab']:  # LB
                new_index = max(0, self.winetricks_dialog.tab_widget.currentIndex() - 1)
                self.winetricks_dialog.tab_widget.setCurrentIndex(new_index)
                self._focus_first_row_in_current_table()

            elif button_code in BUTTONS['next_tab']:  # RB
                new_index = min(self.winetricks_dialog.tab_widget.count() - 1, self.winetricks_dialog.tab_widget.currentIndex() + 1)
                self.winetricks_dialog.tab_widget.setCurrentIndex(new_index)
                self._focus_first_row_in_current_table()

            else:
                self._parent.activateFocusedWidget()

        except Exception as e:
            logger.error(f"Error in handle_winetricks_button: {e}")

    def handle_winetricks_dpad(self, code, value, now):
        if self.winetricks_dialog is None:
            return
        try:
            if value == 0:  # Release
                self.dpad_timer.stop()
                self.current_dpad_code = None
                self.current_dpad_value = 0
                return

            # Timer setup
            if self.current_dpad_code != code or self.current_dpad_value != value:
                self.dpad_timer.stop()
                self.dpad_timer.setInterval(150 if self.dpad_timer.isActive() else 300)
                self.dpad_timer.start()
                self.current_dpad_code = code
                self.current_dpad_value = value

            table = self._get_current_table()
            if not table or table.rowCount() == 0:
                return

            current_row = table.currentRow()

            if code == PAD_DPAD_Y:  # Up/Down
                step = -1 if value < 0 else 1
                new_row = current_row + step

                # Skip hidden rows
                while 0 <= new_row < table.rowCount() and table.isRowHidden(new_row):
                    new_row += step

                # Bounds check
                if new_row < 0:
                    new_row = current_row
                if new_row >= table.rowCount():
                    new_row = current_row

                if new_row != current_row:
                    table.setCurrentCell(new_row, 0)
                    table.setFocus(Qt.FocusReason.OtherFocusReason)

        except Exception as e:
            logger.error(f"Error in handle_winetricks_dpad: {e}")

    def _get_current_table(self):
        if self.winetricks_dialog:
            current_container = self.winetricks_dialog.tab_widget.currentWidget()
            if isinstance(current_container, QStackedWidget):
                current_table = current_container.widget(1)
                if isinstance(current_table, QTableWidget):
                    return current_table
        return None

    def _focus_first_row_in_current_table(self):
        table = self._get_current_table()
        if table and table.rowCount() > 0:
            table.setCurrentCell(0, 0)
            table.setFocus(Qt.FocusReason.OtherFocusReason)

    def _get_navigable_menu_actions(self, menu: QMenu) -> list:
        return [
            action
            for action in menu.actions()
            if not action.isSeparator() and action.isEnabled() and action.isVisible()
        ]

    def _navigate_menu_actions(self, menu: QMenu, direction_down: bool) -> None:
        actions = self._get_navigable_menu_actions(menu)
        if not actions:
            return
        current_action = menu.activeAction()
        if current_action not in actions:
            target_index = 0 if direction_down else len(actions) - 1
            menu.setActiveAction(actions[target_index])
            return
        current_index = actions.index(current_action)
        step = 1 if direction_down else -1
        next_index = (current_index + step) % len(actions)
        menu.setActiveAction(actions[next_index])

    # TABLE NAVIGATION METHODS
    def handle_table_navigation(self, table: QTableWidget, code: int, value: int):
        """
        Handle navigation in table

        Args:
            table: QTableWidget for navigation handling
            code: Event code (usually ABS_HAT0X or ABS_HAT0Y)
            value: Event value (direction)
        """
        row_count = table.rowCount()
        if row_count <= 0:
            return
        current_row = table.currentRow()
        if current_row < 0:
            current_row = 0
            table.setCurrentCell(0, 0)

        if code == PAD_DPAD_Y and value != 0:
            # Vertical navigation
            if value > 0:  # Down
                new_row = min(current_row + 1, row_count - 1)
            elif value < 0:  # Up
                new_row = max(current_row - 1, 0)
            else:
                return

            table.setCurrentCell(new_row, table.currentColumn())
            item = table.item(new_row, table.currentColumn())
            if item:
                table.scrollToItem(
                    item,
                    QAbstractItemView.ScrollHint.PositionAtCenter
                )
            table.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        elif code == PAD_DPAD_X and value != 0:
            # Horizontal navigation
            col_count = table.columnCount()
            current_col = table.currentColumn()
            if current_col < 0:
                current_col = 0

            if value < 0:  # Left
                new_col = max(current_col - 1, 0)
            elif value > 0:  # Right
                new_col = min(current_col + 1, col_count - 1)
            else:
                return

            table.setCurrentCell(table.currentRow(), new_col)
            table.setFocus(Qt.FocusReason.OtherFocusReason)
            return

    def handle_table_confirm(self, table: QTableWidget):
        """
        Handle confirmation (e.g., A press) for table

        Args:
            table: QTableWidget for confirmation handling
        """
        current_row = table.currentRow()
        current_col = table.currentColumn()
        if current_row >= 0 and current_col >= 0:
            cell_widget = table.cellWidget(current_row, current_col)
            if isinstance(cell_widget, QCheckBox) and cell_widget.isEnabled():
                cell_widget.setChecked(not cell_widget.isChecked())
                return True
            if cell_widget is not None:
                checkbox = cell_widget.findChild(QCheckBox)
                if checkbox and checkbox.isEnabled():
                    checkbox.setChecked(not checkbox.isChecked())
                    return True

            # Check if the cell contains a checkbox
            item = table.item(current_row, current_col)
            if item and (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                # Toggle the checkbox state
                new_state = Qt.CheckState.Checked if item.checkState() == Qt.CheckState.Unchecked else Qt.CheckState.Unchecked
                item.setCheckState(new_state)
                return True

            # Call custom confirm callback if exists
            callback = getattr(table, '_on_confirm_callback', None)  # type: ignore
            if callback and callable(callback):
                callback(table, current_row, current_col)
                return True

    # WIDGET NAVIGATION METHODS
    def setup_widget_navigation(self, widget: QWidget, navigation_type: str = "default", **kwargs):
        """
        Set navigation for widget

        Args:
            widget: QWidget for navigation setup
            navigation_type: Navigation type ('table', 'list', 'combo', 'default')
            **kwargs: Additional parameters for navigation
        """
        widget.installEventFilter(self)
        # Use direct assignment for custom navigation properties, with type ignore for pyright
        widget._navigation_type = navigation_type  # type: ignore
        for key, value in kwargs.items():
            setattr(widget, f'_{key}', value)

    def handle_widget_navigation(self, widget: QWidget, code: int, value: int):
        """
        Handle navigation in widget

        Args:
            widget: QWidget for navigation handling
            code: Event code (usually ABS_HAT0X or ABS_HAT0Y)
            value: Event value (direction)
        """
        nav_type = getattr(widget, '_navigation_type', 'default')  # type: ignore

        if nav_type == 'table' and isinstance(widget, QTableWidget):
            self.handle_table_navigation(widget, code, value)
        elif nav_type == 'list' and isinstance(widget, QListWidget):
            self.handle_list_navigation(widget, code, value)
        elif nav_type == 'combo' and isinstance(widget, QComboBox):
            self.handle_combo_navigation(widget, code, value)
        else:
            # Default navigation behavior
            if isinstance(widget, QTableWidget):
                self.handle_table_navigation(widget, code, value)
            elif isinstance(widget, QListWidget):
                self.handle_list_navigation(widget, code, value)
            elif isinstance(widget, QComboBox):
                self.handle_combo_navigation(widget, code, value)

    def handle_list_navigation(self, list_widget: QListWidget, code: int, value: int):
        """
        Handle navigation in list

        Args:
            list_widget: QListWidget for navigation handling
            code: Event code (usually ABS_HAT0X or ABS_HAT0Y)
            value: Event value (direction)
        """
        if code == PAD_DPAD_Y and value != 0:
            model = list_widget.model()
            current_index = list_widget.currentIndex()
            if model and current_index.isValid():
                row_count = model.rowCount()
                current_row = current_index.row()
                if value > 0:  # Down
                    next_row = min(current_row + 1, row_count - 1)
                    list_widget.setCurrentIndex(model.index(next_row, current_index.column()))
                elif value < 0:  # Up
                    prev_row = max(current_row - 1, 0)
                    list_widget.setCurrentIndex(model.index(prev_row, current_index.column()))
                list_widget.scrollTo(list_widget.currentIndex(), QListView.ScrollHint.PositionAtCenter)

    def handle_combo_navigation(self, combo_widget: QComboBox, code: int, value: int):
        """
        Handle navigation in combo widget

        Args:
            combo_widget: QComboBox for navigation handling
            code: Event code (usually ABS_HAT0X or ABS_HAT0Y)
            value: Event value (direction)
        """
        if code == PAD_DPAD_Y and value != 0:
            current_index = combo_widget.currentIndex()
            if value > 0:  # Down
                new_index = min(current_index + 1, combo_widget.count() - 1)
            elif value < 0:  # Up
                new_index = max(current_index - 1, 0)
            else:
                return

            if new_index != current_index:
                combo_widget.setCurrentIndex(new_index)

    def _setup_mode_handlers(self, dialog_instance, button_handler, dpad_handler, dialog_attr_name):
        """Common method to setup mode handlers"""
        # Save original handlers if not already saved
        if not hasattr(self, '_original_handlers_saved') or not self._original_handlers_saved:
            self.original_button_handler = self.handle_button_slot
            self.original_dpad_handler = self.handle_dpad_slot
            self.original_gamepad_state = self._gamepad_handling_enabled
            self._original_handlers_saved = True

        # Set the dialog instance
        if dialog_attr_name == 'winetricks_dialog':
            self.winetricks_dialog = dialog_instance
        elif dialog_attr_name == 'settings_dialog':
            self.settings_dialog = dialog_instance
        elif dialog_attr_name == 'file_explorer':
            self.file_explorer = dialog_instance
        elif dialog_attr_name == 'proton_manager_dialog':
            self.proton_manager_dialog = dialog_instance

        # Set new handlers
        self.handle_button_slot = button_handler
        self.handle_dpad_slot = dpad_handler
        self._gamepad_handling_enabled = True

        # Reset dpad timer
        self.dpad_timer.stop()
        self.current_dpad_code = None
        self.current_dpad_value = 0

    def _restore_original_handlers(self, dialog_attr_name):
        """Common method to restore original handlers"""
        if self.original_button_handler is None or self.original_dpad_handler is None or self.original_gamepad_state is None:
            logger.warning("Cannot restore original handlers: handlers not saved")
            return

        # Restore original handlers
        self.handle_button_slot = self.original_button_handler
        self.handle_dpad_slot = self.original_dpad_handler
        self._gamepad_handling_enabled = self.original_gamepad_state

        # Reset dpad timer
        self.dpad_timer.stop()
        self.current_dpad_code = None
        self.current_dpad_value = 0

        # Clear the dialog reference
        if dialog_attr_name == 'winetricks_dialog':
            self.winetricks_dialog = None
        elif dialog_attr_name == 'settings_dialog':
            self.settings_dialog = None
        elif dialog_attr_name == 'file_explorer':
            self.file_explorer = None
        elif dialog_attr_name == 'proton_manager_dialog':
            self.proton_manager_dialog = None

        # Reset the flag so original handlers can be saved again on next enable
        if hasattr(self, '_original_handlers_saved'):
            self._original_handlers_saved = False

    # PROTON MANAGER SUPPORT
    def enable_proton_manager_mode(self, proton_manager_dialog):
        """Setup gamepad handling for ProtonManagerDialog"""
        try:
            self._setup_mode_handlers(
                proton_manager_dialog,
                self.handle_proton_manager_button,
                self.handle_proton_manager_dpad,
                'proton_manager_dialog'
            )
            logger.debug("Gamepad handling successfully connected for ProtonManager")
        except Exception as e:
            logger.error(f"Error connecting gamepad handlers for ProtonManager: {e}")

    def disable_proton_manager_mode(self):
        """Restore original main window handlers"""
        try:
            if self.proton_manager_dialog:
                self._restore_original_handlers('proton_manager_dialog')
                logger.debug("Gamepad handling successfully restored from ProtonManager")
        except Exception as e:
            logger.error(f"Error restoring gamepad handlers from ProtonManager: {e}")

    def handle_proton_manager_button(self, button_code, value):
        if self.proton_manager_dialog is None or value == 0:
            return

        try:
            # Handle common UI elements like QMessageBox, QMenu, etc.
            if self._handle_common_ui_elements(button_code):
                return

            # ProtonManager-specific button handling
            focused = QApplication.focusWidget()

            if button_code in BUTTONS['confirm']:  # A: Toggle checkbox
                if isinstance(focused, QTableWidget):
                    current_row = focused.currentRow()
                    if current_row >= 0:
                        checkbox_widget = focused.cellWidget(current_row, 0)
                        if checkbox_widget:
                            checkbox = checkbox_widget.findChild(QCheckBox)
                            if checkbox and checkbox.isEnabled():
                                checkbox.setChecked(not checkbox.isChecked())
                return

            elif button_code in BUTTONS['add_game']:  # X: Download
                self.proton_manager_dialog.download_selected()

            elif button_code in BUTTONS['prev_dir']:  # Y: Clear
                self.proton_manager_dialog.clear_selection()

            elif button_code in BUTTONS['back']:  # B: Cancel/Close
                # Cancel any active downloads/extractions before closing
                if (self.proton_manager_dialog.current_extraction_thread and
                    self.proton_manager_dialog.current_extraction_thread.isRunning()) or \
                   (self.proton_manager_dialog.current_download_thread and
                    hasattr(self.proton_manager_dialog.current_download_thread, 'isRunning') and
                    self.proton_manager_dialog.current_download_thread.isRunning()):
                    # If there's an active download/extraction, cancel it
                    self.proton_manager_dialog.cancel_current_download()
                else:
                    # If no active processes, just close the dialog
                    self.proton_manager_dialog.reject()

            elif button_code in BUTTONS['prev_tab']:  # LB: Previous tab
                new_index = max(0, self.proton_manager_dialog.tab_widget.currentIndex() - 1)
                self.proton_manager_dialog.tab_widget.setCurrentIndex(new_index)
                self._focus_first_row_in_current_proton_manager_table()

            elif button_code in BUTTONS['next_tab']:  # RB: Next tab
                new_index = min(self.proton_manager_dialog.tab_widget.count() - 1, self.proton_manager_dialog.tab_widget.currentIndex() + 1)
                self.proton_manager_dialog.tab_widget.setCurrentIndex(new_index)
                self._focus_first_row_in_current_proton_manager_table()

            else:
                self._parent.activateFocusedWidget()

        except Exception as e:
            logger.error(f"Error in handle_proton_manager_button: {e}")

    def handle_proton_manager_dpad(self, code, value, now):
        if self.proton_manager_dialog is None:
            return

        try:
            if value == 0:  # Release
                self.dpad_timer.stop()
                self.current_dpad_code = None
                self.current_dpad_value = 0
                return

            # Timer setup
            if self.current_dpad_code != code or self.current_dpad_value != value:
                self.dpad_timer.stop()
                self.dpad_timer.setInterval(150 if self.dpad_timer.isActive() else 300)
                self.dpad_timer.start()
                self.current_dpad_code = code
                self.current_dpad_value = value

            table = self._get_current_proton_manager_table()
            if not table or table.rowCount() == 0:
                return

            current_row = table.currentRow()

            if code == PAD_DPAD_Y:  # Up/Down
                step = -1 if value < 0 else 1
                new_row = current_row + step

                # Skip hidden rows
                while 0 <= new_row < table.rowCount() and table.isRowHidden(new_row):
                    new_row += step

                # Bounds check
                if new_row < 0:
                    new_row = current_row
                if new_row >= table.rowCount():
                    new_row = current_row

                if new_row != current_row:
                    table.setCurrentCell(new_row, 0)
                    table.setFocus(Qt.FocusReason.OtherFocusReason)

        except Exception as e:
            logger.error(f"Error in handle_proton_manager_dpad: {e}")

    def _get_current_proton_manager_table(self):
        if self.proton_manager_dialog:
            current_container = self.proton_manager_dialog.tab_widget.currentWidget()
            if current_container:
                table = current_container.findChild(QTableWidget)
                return table
        return None

    def _focus_first_row_in_current_proton_manager_table(self):
        table = self._get_current_proton_manager_table()
        if table and table.rowCount() > 0:
            table.setCurrentCell(0, 0)
            table.setFocus(Qt.FocusReason.OtherFocusReason)

    # SETTINGS MODE
    def enable_settings_mode(self, settings_dialog):
        """Setup gamepad handling for ExeSettingsDialog"""
        try:
            self._setup_mode_handlers(
                settings_dialog,
                self.handle_settings_button,
                self.handle_settings_dpad,
                'settings_dialog'
            )
            logger.debug("Gamepad handling successfully connected for SettingsDialog")
        except Exception as e:
            logger.error(f"Error connecting gamepad handlers for SettingsDialog: {e}")

    def disable_settings_mode(self):
        """Restore original main window handlers"""
        try:
            if self.settings_dialog:
                self._restore_original_handlers('settings_dialog')
                logger.debug("Gamepad handling successfully restored from Settings")
        except Exception as e:
            logger.error(f"Error restoring gamepad handlers from Settings: {e}")

    def handle_settings_button(self, button_code, value):
        if self.settings_dialog is None:
            return

        try:
            # 1. Virtual Keyboard Handling
            kb = getattr(self.settings_dialog, 'keyboard', None)
            if kb and kb.isVisible():
                if button_code in BUTTONS['back']:
                    if value != 0:  # Only handle press, not release
                        kb.hide()
                        if kb.current_input_widget:
                            kb.current_input_widget.setFocus()
                    return  # Return early to avoid dialog closing logic
                elif button_code in (BUTTONS['confirm'] | BUTTONS['context_menu']):
                    if value != 0:  # Only handle press, not release
                        kb.activateFocusedKey()
                    return
                elif button_code in BUTTONS['prev_tab']:
                    if value != 0:  # Only handle press, not release
                        kb.on_lang_click()
                    return
                elif button_code in BUTTONS['next_tab']:
                    if value != 0:  # Only handle press, not release
                        kb.on_shift_click(not kb.shift_pressed)
                    return
                elif button_code in BUTTONS['add_game']:
                    if value != 0:  # Press event
                        kb.on_backspace_pressed()
                    else:  # Release event
                        kb.stop_backspace_repeat()
                    return

            # Handle common UI elements like QMessageBox, QMenu, etc.
            # Only handle press events (value != 0), ignore release events
            if value != 0 and self._handle_common_ui_elements(button_code):
                return

            # Handle other QDialogs
            if value != 0:  # Only handle press events, not releases
                popup = QApplication.activePopupWidget()
                if isinstance(popup, QDialog):
                    if button_code in BUTTONS['confirm']:
                        popup.accept()
                    elif button_code in BUTTONS['back']:
                        popup.reject()
                    return

                # 3. Combo Box popup handling in settings (Advanced + MangoHud)
                table = self._get_current_settings_table()
                open_combo = self._get_open_settings_combo()

                # B Button - Close combo or dialog
                if button_code in BUTTONS['back']:
                    if open_combo:
                        open_combo.hidePopup()
                        if open_combo.isEditable() and open_combo.lineEdit() is not None:
                            open_combo.lineEdit().setFocus()
                        else:
                            open_combo.setFocus()
                    else:
                        self.settings_dialog.reject()
                    return

                # A Button - Confirm
                if button_code in BUTTONS['confirm']:
                    if open_combo:
                        view = open_combo.view()
                        if view.currentIndex().isValid():
                            open_combo.setCurrentIndex(view.currentIndex().row())
                        open_combo.hidePopup()
                        if open_combo.isEditable() and open_combo.lineEdit() is not None:
                            open_combo.lineEdit().setFocus()
                        else:
                            open_combo.setFocus()
                        return

                    # Standard interaction
                    focused = QApplication.focusWidget()
                    if isinstance(focused, QCheckBox) and focused.isEnabled():
                        focused.setChecked(not focused.isChecked())
                        return
                    if isinstance(focused, QPushButton) and focused.isEnabled():
                        focused.click()
                        return
                    combo_from_focus = None
                    if isinstance(focused, QComboBox):
                        combo_from_focus = focused
                    else:
                        parent = focused.parentWidget() if focused else None
                        if isinstance(parent, QComboBox):
                            combo_from_focus = parent
                    if combo_from_focus and combo_from_focus.isEnabled():
                        combo_from_focus.showPopup()
                        combo_from_focus.setFocus()
                        return
                    if isinstance(focused, QTableWidget) and table and focused.currentRow() >= 0:
                        # Main settings (checkboxes)
                        if self.settings_dialog and table == self.settings_dialog.settings_table:
                            self.handle_table_confirm(focused)
                            return

                        # Advanced settings
                        cell = focused.cellWidget(focused.currentRow(), 1)
                        if isinstance(cell, QComboBox) and cell.isEnabled():
                            cell.showPopup()
                            cell.setFocus()
                            return
                        if isinstance(cell, QLineEdit):
                            cell.setFocus()
                            self.settings_dialog.show_virtual_keyboard(cell)
                            return

                    if isinstance(focused, QLineEdit):
                        self.settings_dialog.show_virtual_keyboard(focused)
                        return
                    if self.settings_dialog.tab_widget.currentIndex() in (2, 3):
                        if isinstance(focused, QCheckBox):
                            focused.toggle()
                            return
                        if isinstance(focused, QPushButton):
                            focused.click()
                            return
                        if isinstance(focused, QComboBox):
                            focused.showPopup()
                            return
                        self._parent.activateFocusedWidget()
                    return

                # 4. Global Shortcuts
                if button_code in BUTTONS['add_game']:  # X: Apply
                    self.settings_dialog.apply_changes()

                elif button_code in BUTTONS['prev_dir']:  # Y: Search + Keyboard
                    focused = QApplication.focusWidget()
                    focused_combo = None
                    if isinstance(focused, QTableWidget) and self.settings_dialog:
                        table = self._get_current_settings_table()
                        if table is not None and table == self.settings_dialog.advanced_table:
                            row = focused.currentRow()
                            if row >= 0:
                                cell_widget = focused.cellWidget(row, 1)
                                if isinstance(cell_widget, QComboBox):
                                    focused_combo = cell_widget
                    if focused_combo is None:
                        if isinstance(focused, QComboBox):
                            focused_combo = focused
                        else:
                            parent = focused.parentWidget() if focused else None
                            if isinstance(parent, QComboBox):
                                focused_combo = parent
                    if focused_combo and focused_combo.isEditable() and focused_combo.isEnabled():
                        line_edit = focused_combo.lineEdit()
                        if line_edit is not None:
                            line_edit.setFocus()
                            self.settings_dialog.show_virtual_keyboard(line_edit)
                            return
                    self.settings_dialog.search_edit.setFocus()
                    self.settings_dialog.show_virtual_keyboard(self.settings_dialog.search_edit)

                elif button_code in BUTTONS['prev_tab']:  # LB
                    idx = max(0, self.settings_dialog.tab_widget.currentIndex() - 1)
                    self.settings_dialog.tab_widget.setCurrentIndex(idx)
                    self._focus_first_row_in_current_settings_table()

                elif button_code in BUTTONS['next_tab']:  # RB
                    idx = min(self.settings_dialog.tab_widget.count() - 1, self.settings_dialog.tab_widget.currentIndex() + 1)
                    self.settings_dialog.tab_widget.setCurrentIndex(idx)
                    self._focus_first_row_in_current_settings_table()

                else:
                    self._parent.activateFocusedWidget()

        except Exception as e:
            logger.error(f"Error in handle_settings_button: {e}")

    def handle_settings_dpad(self, code, value, now):
        if self.settings_dialog is None:
            return

        try:
            # 1. Virtual Keyboard Navigation
            kb = getattr(self.settings_dialog, 'keyboard', None)
            if kb and kb.isVisible():
                normalized_value = 0

                # Normalize Stick vs D-pad
                if code in (PAD_AXIS_LEFT_X, PAD_AXIS_LEFT_Y):  # Sticks
                    if abs(value) < self.dead_zone:
                        self.current_dpad_code = None
                        self.current_dpad_value = 0
                        self.dpad_timer.stop()
                        return
                    normalized_value = 1 if value > self.dead_zone else -1
                else:  # D-pad
                    normalized_value = value

                if normalized_value != 0:
                    if code in (PAD_DPAD_X, PAD_AXIS_LEFT_X):
                        if normalized_value > 0:
                            kb.move_focus_right()
                        else:
                            kb.move_focus_left()
                    elif code in (PAD_DPAD_Y, PAD_AXIS_LEFT_Y):
                        if normalized_value > 0:
                            kb.move_focus_down()
                        else:
                            kb.move_focus_up()
                return

            if self.settings_dialog.tab_widget.currentIndex() in (2, 3):
                focused = QApplication.focusWidget()
                open_combo = self._get_open_settings_combo()
                if open_combo:
                    if code == PAD_DPAD_Y and value != 0:
                        view = open_combo.view()
                        model = view.model()
                        current_index = view.currentIndex()
                        if model and current_index.isValid():
                            row_count = model.rowCount()
                            current_row = current_index.row()
                            if value > 0:
                                next_row = min(current_row + 1, row_count - 1)
                            else:
                                next_row = max(current_row - 1, 0)
                            new_index = model.index(next_row, current_index.column())
                            view.setCurrentIndex(new_index)
                            view.scrollTo(new_index, QAbstractItemView.ScrollHint.PositionAtCenter)
                    return

                if code not in (PAD_DPAD_X, PAD_DPAD_Y, PAD_AXIS_LEFT_X, PAD_AXIS_LEFT_Y):
                    return

                normalized_value = value
                if code in (PAD_AXIS_LEFT_X, PAD_AXIS_LEFT_Y):
                    if abs(value) < self.dead_zone:
                        normalized_value = 0
                    else:
                        normalized_value = 1 if value > 0 else -1

                if normalized_value == 0:
                    self.dpad_timer.stop()
                    self.current_dpad_code = None
                    self.current_dpad_value = 0
                    return

                if code in (PAD_DPAD_X, PAD_DPAD_Y):
                    if self.current_dpad_code != code or self.current_dpad_value != normalized_value:
                        self.dpad_timer.stop()
                        self.dpad_timer.setInterval(120 if self.dpad_timer.isActive() else 220)
                        self.dpad_timer.start()
                        self.current_dpad_code = code
                        self.current_dpad_value = normalized_value

                sections = self._get_mangohud_nav_sections()
                if not sections:
                    return

                if not focused or not self._find_widget_in_sections(focused, sections):
                    self._focus_first_row_in_current_settings_table()
                    return

                if code in (PAD_DPAD_X, PAD_AXIS_LEFT_X):
                    self._move_mangohud_horizontal(focused, normalized_value, sections)
                elif code in (PAD_DPAD_Y, PAD_AXIS_LEFT_Y):
                    self._move_mangohud_vertical(focused, normalized_value, sections)
                return

            # 2. Combo Box Navigation (within Advanced Table)
            table = self._get_current_settings_table()
            if not table or table.rowCount() == 0:
                return

            if self.settings_dialog and table == self.settings_dialog.advanced_table and table.currentRow() >= 0:
                cell_widget = table.cellWidget(table.currentRow(), 1)
                if isinstance(cell_widget, QComboBox) and cell_widget.view().isVisible():
                    if code == PAD_DPAD_Y and value != 0:
                        idx = cell_widget.currentIndex()
                        new_idx = max(0, idx - 1) if value < 0 else min(cell_widget.count() - 1, idx + 1)
                        if new_idx != idx:
                            cell_widget.setCurrentIndex(new_idx)
                    return  # Consume event

            # 3. Standard Table Navigation
            if value == 0:
                self.dpad_timer.stop()
                self.current_dpad_code = None
                self.current_dpad_value = 0
                return

            if self.current_dpad_code != code or self.current_dpad_value != value:
                self.dpad_timer.stop()
                self.dpad_timer.setInterval(150 if self.dpad_timer.isActive() else 300)
                self.dpad_timer.start()
                self.current_dpad_code = code
                self.current_dpad_value = value

            current_row = table.currentRow()

            if code == PAD_DPAD_Y:  # Up/Down
                step = -1 if value < 0 else 1
                new_row = current_row + step

                while 0 <= new_row < table.rowCount() and table.isRowHidden(new_row):
                    new_row += step

                if 0 <= new_row < table.rowCount():
                    focus_column = 1
                    table.setCurrentCell(new_row, focus_column)
                    self._focus_settings_advanced_value_widget(table, new_row)

            elif code == PAD_DPAD_X:  # Left/Right
                if self._move_settings_inline_button_focus(table, value):
                    return
                current_col = table.currentColumn()
                if value < 0:  # Left
                    if current_col > 0:
                        new_col = max(0, current_col - 1)
                        table.setCurrentCell(current_row, new_col)
                        if new_col == 1:
                            self._focus_settings_advanced_value_widget(table, current_row)
                        else:
                            table.setFocus(Qt.FocusReason.OtherFocusReason)
                else:  # Right
                    if current_col < table.columnCount() - 1:
                        new_col = min(table.columnCount() - 1, current_col + 1)
                        table.setCurrentCell(current_row, new_col)
                        if new_col == 1:
                            self._focus_settings_advanced_value_widget(table, current_row)
                        else:
                            table.setFocus(Qt.FocusReason.OtherFocusReason)

        except Exception as e:
            logger.error(f"Error in handle_settings_dpad: {e}")

    def _get_current_settings_table(self):
        if self.settings_dialog:
            idx = self.settings_dialog.tab_widget.currentIndex()
            if idx == 0:
                return self.settings_dialog.settings_table
            elif idx == 1:
                return self.settings_dialog.advanced_table
        return None

    def _get_open_settings_combo(self):
        """Return currently opened combo popup in settings dialog if any."""
        if not self.settings_dialog:
            return None
        for combo in self.settings_dialog.findChildren(
            QComboBox, options=Qt.FindChildOption.FindChildrenRecursively
        ):
            if combo.isVisible() and combo.view().isVisible():
                return combo
        return None

    def _focus_settings_advanced_value_widget(self, table, row):
        """Focus value widget in settings row when available."""
        if not self.settings_dialog:
            table.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if table == self.settings_dialog.settings_table:
            cell_widget = table.cellWidget(row, 1)
            if cell_widget is not None:
                checkbox = cell_widget.findChild(QCheckBox)
                if checkbox and checkbox.isEnabled():
                    checkbox.setFocus(Qt.FocusReason.OtherFocusReason)
                    return
            table.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if table != self.settings_dialog.advanced_table:
            table.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        cell_widget = table.cellWidget(row, 1)
        if isinstance(cell_widget, QComboBox):
            line_edit = cell_widget.lineEdit()
            if cell_widget.isEditable() and line_edit is not None:
                line_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            else:
                cell_widget.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        if isinstance(cell_widget, QLineEdit):
            cell_widget.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        if (
            cell_widget is not None
            and cell_widget.property("ppqt_run_after_exe_widget")
        ):
            line_edit = cell_widget.findChild(QLineEdit)
            if line_edit and line_edit.isEnabled():
                line_edit.setFocus(Qt.FocusReason.OtherFocusReason)
                return
        table.setFocus(Qt.FocusReason.OtherFocusReason)

    def _move_settings_inline_button_focus(self, table: QTableWidget, value: int) -> bool:
        """Move focus between inline line edit and button in settings cell."""
        if not self.settings_dialog or table != self.settings_dialog.advanced_table:
            return False
        if table.currentColumn() != 1:
            return False

        cell_widget = table.cellWidget(table.currentRow(), 1)
        if cell_widget is None or not cell_widget.property("ppqt_run_after_exe_widget"):
            return False

        line_edit = cell_widget.findChild(QLineEdit)
        button = cell_widget.findChild(QPushButton)
        focused = QApplication.focusWidget()
        if value > 0 and focused == line_edit and button and button.isEnabled():
            button.setFocus(Qt.FocusReason.OtherFocusReason)
            return True
        if value < 0 and focused == button and line_edit and line_edit.isEnabled():
            line_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            return True
        return False

    def _focus_first_row_in_current_settings_table(self):
        table = self._get_current_settings_table()
        if table and table.rowCount() > 0:
            col = 1
            table.setCurrentCell(0, col)
            self._focus_settings_advanced_value_widget(table, 0)
            return

        if self.settings_dialog and self.settings_dialog.tab_widget.currentIndex() in (2, 3):
            sections = self._get_mangohud_nav_sections()
            if sections and sections[0]:
                self._focus_mangohud_widget(sections[0][0])

    def _get_mangohud_nav_sections(self):
        """Return MangoHud/Gamescope focusable widgets grouped by visual sections."""
        if not self.settings_dialog:
            return []
        tab_index = self.settings_dialog.tab_widget.currentIndex()
        if tab_index not in (2, 3):
            return []

        sections = []

        value_widgets = []
        if tab_index == 2:
            value_widgets = [
                widget for key, widget in self.settings_dialog.mangohud_widgets.items()
                if key != 'fps_limit_method' and widget.isVisible() and widget.isEnabled()
            ]
        elif tab_index == 3:
            value_widgets = [
                widget for widget in self.settings_dialog.gamescope_widgets.values()
                if widget.isVisible() and widget.isEnabled()
            ]
            value_widgets.extend([
                widget for widget in self.settings_dialog.gamescope_resolution_widgets.values()
                if widget.isVisible() and widget.isEnabled()
            ])

        mangohud_tab = self.settings_dialog.tab_widget.currentWidget()
        preset_buttons = []
        if mangohud_tab:
            preset_buttons = [
                widget for widget in mangohud_tab.findChildren(
                    QPushButton, options=Qt.FindChildOption.FindChildrenRecursively
                )
                if widget.isVisible() and widget.isEnabled()
            ]
        preset_section = self._sort_widgets_by_position(preset_buttons) if preset_buttons else []

        toggle_widgets = []
        category_combo_attr = 'mangohud_category_combo' if tab_index == 2 else 'gamescope_category_combo'
        category_stack_attr = 'mangohud_category_stack' if tab_index == 2 else 'gamescope_category_stack'
        category_combo = getattr(self.settings_dialog, category_combo_attr, None)
        if category_combo and category_combo.isVisible() and category_combo.isEnabled():
            toggle_widgets.append(category_combo)
        category_stack = getattr(self.settings_dialog, category_stack_attr, None)
        if category_stack:
            category_widget = category_stack.currentWidget()
            if category_widget:
                category_checkboxes = [
                    checkbox for checkbox in category_widget.findChildren(
                        QCheckBox, options=Qt.FindChildOption.FindChildrenRecursively
                    )
                    if checkbox.isVisible() and checkbox.isEnabled()
                ]
                toggle_widgets.extend(self._sort_widgets_by_position(category_checkboxes))
        toggle_section = toggle_widgets if toggle_widgets else []

        fps_section = []
        if tab_index == 2:
            fps_widgets = []
            fps_limit_method = self.settings_dialog.mangohud_widgets.get('fps_limit_method')
            if fps_limit_method and fps_limit_method.isVisible() and fps_limit_method.isEnabled():
                fps_widgets.append(fps_limit_method)

            fps_widgets.extend([
                checkbox for checkbox in self.settings_dialog.mangohud_fps_widgets.values()
                if checkbox.isVisible() and checkbox.isEnabled()
            ])
            if fps_widgets:
                fps_section = self._sort_widgets_by_position(fps_widgets)

        extra_edit_attr = 'mangohud_extra_edit' if tab_index == 2 else 'gamescope_extra_edit'
        extra_edit = getattr(self.settings_dialog, extra_edit_attr, None)
        extra_section = [extra_edit] if extra_edit and extra_edit.isVisible() and extra_edit.isEnabled() else []

        if tab_index == 2:
            if preset_section:
                sections.append(preset_section)
            if toggle_section:
                sections.append(toggle_section)
            if value_widgets:
                sections.append(self._sort_widgets_by_position(value_widgets))
            if fps_section:
                sections.append(fps_section)
            if extra_section:
                sections.append(extra_section)
        else:
            # Gamescope UI order: presets -> toggles -> values -> extra.
            if preset_section:
                sections.append(preset_section)
            if toggle_section:
                sections.append(toggle_section)
            if value_widgets:
                sections.append(self._sort_widgets_by_position(value_widgets))
            if extra_section:
                sections.append(extra_section)

        return sections

    def _sort_widgets_by_position(self, widgets):
        """Sort widgets by their y/x position in settings dialog coordinates."""
        return sorted(
            widgets,
            key=lambda widget: (
                widget.mapTo(self.settings_dialog, widget.rect().topLeft()).y(),
                widget.mapTo(self.settings_dialog, widget.rect().topLeft()).x(),
            ),
        )

    def _find_widget_in_sections(self, widget, sections):
        """Find widget position in sections list."""
        for section_index, section in enumerate(sections):
            for widget_index, item in enumerate(section):
                if item is widget:
                    return section_index, widget_index
        return None

    def _focus_mangohud_widget(self, widget):
        """Focus MangoHud widget and ensure it is visible in scroll area."""
        self._ensure_mangohud_widget_visible(widget)
        widget.setFocus(Qt.FocusReason.OtherFocusReason)

    def _ensure_mangohud_widget_visible(self, widget):
        """Auto-scroll MangoHud tab to the currently focused widget."""
        if not self.settings_dialog:
            return
        mangohud_tab = self.settings_dialog.tab_widget.currentWidget()
        if not mangohud_tab:
            return
        scroll_area = mangohud_tab.findChild(QScrollArea)
        if scroll_area:
            scroll_area.ensureWidgetVisible(widget, 20, 20)

    def _move_mangohud_horizontal(self, focused, direction, sections):
        """Move focus left/right inside current MangoHud section."""
        position = self._find_widget_in_sections(focused, sections)
        if not position:
            return
        section_index, _widget_index = position
        target = self._find_mangohud_grid_horizontal_target(
            focused, direction, sections[section_index]
        )
        if target:
            self._focus_mangohud_widget(target)
            return
        target = self._find_mangohud_neighbor_in_section(
            focused, sections[section_index], direction, is_vertical=False
        )
        if target:
            self._focus_mangohud_widget(target)

    def _move_mangohud_vertical(self, focused, direction, sections):
        """Move focus up/down inside section, then across sections."""
        position = self._find_widget_in_sections(focused, sections)
        if not position:
            return
        settings_dialog = self.settings_dialog
        if not settings_dialog:
            return

        section_index, _widget_index = position
        toggle_boundary_reached = False
        if self._is_mangohud_fps_widget(focused):
            fps_target = self._find_mangohud_fps_vertical_target(
                focused, direction, sections[section_index]
            )
            if fps_target:
                self._focus_mangohud_widget(fps_target)
                return
        if self._is_mangohud_toggle_widget(focused):
            toggle_target = self._find_mangohud_toggle_vertical_target(
                focused, direction, sections[section_index]
            )
            if toggle_target:
                self._focus_mangohud_widget(toggle_target)
                return
            toggle_boundary_reached = True

        tab_index = settings_dialog.tab_widget.currentIndex()
        fps_limit_method = None
        if tab_index == 2:
            fps_limit_method = settings_dialog.mangohud_widgets.get('fps_limit_method')
        if direction > 0 and tab_index == 2 and fps_limit_method and focused is fps_limit_method:
            fps_checkboxes = [
                checkbox for checkbox in settings_dialog.mangohud_fps_widgets.values()
                if checkbox.isVisible() and checkbox.isEnabled()
            ]
            if fps_checkboxes:
                first_fps_checkbox = self._sort_widgets_by_position(fps_checkboxes)[0]
                self._focus_mangohud_widget(first_fps_checkbox)
                return

        category_combo_attr = 'mangohud_category_combo' if tab_index == 2 else 'gamescope_category_combo'
        category_stack_attr = 'mangohud_category_stack' if tab_index == 2 else 'gamescope_category_stack'
        category_combo = getattr(settings_dialog, category_combo_attr, None)
        category_stack = getattr(settings_dialog, category_stack_attr, None)
        if direction > 0 and category_combo and focused is category_combo and category_stack:
            current_category_widget = category_stack.currentWidget()
            if current_category_widget:
                category_checkboxes = [
                    checkbox for checkbox in current_category_widget.findChildren(
                        QCheckBox, options=Qt.FindChildOption.FindChildrenRecursively
                    )
                    if checkbox.isVisible() and checkbox.isEnabled()
                ]
                if category_checkboxes:
                    first_checkbox = self._sort_widgets_by_position(category_checkboxes)[0]
                    self._focus_mangohud_widget(first_checkbox)
                    return

        if not toggle_boundary_reached:
            target_in_section = self._find_mangohud_neighbor_in_section(
                focused, sections[section_index], direction, is_vertical=True
            )
            if target_in_section:
                self._focus_mangohud_widget(target_in_section)
                return

        target_section_index = section_index + direction
        if target_section_index < 0 or target_section_index >= len(sections):
            return

        target_section = sections[target_section_index]
        if not target_section:
            return

        category_combo = getattr(settings_dialog, category_combo_attr, None)
        if category_combo and category_combo in target_section:
            self._focus_mangohud_widget(category_combo)
            return

        if target_section_index == 1:
            self._focus_mangohud_widget(target_section[0])
            return

        fps_limit_method = None
        if tab_index == 2:
            fps_limit_method = settings_dialog.mangohud_widgets.get('fps_limit_method')
        if fps_limit_method and fps_limit_method in target_section:
            self._focus_mangohud_widget(fps_limit_method)
            return

        current_center = focused.mapTo(settings_dialog, focused.rect().center()).x()
        target_widget = min(
            target_section,
            key=lambda widget: abs(widget.mapTo(settings_dialog, widget.rect().center()).x() - current_center),
        )
        self._focus_mangohud_widget(target_widget)

    def _find_mangohud_neighbor_in_section(self, focused, section, direction, is_vertical):
        """Find closest focusable neighbor in current section by direction."""
        settings_dialog = self.settings_dialog
        if not settings_dialog:
            return None
        focused_center = focused.mapTo(settings_dialog, focused.rect().center())
        fx = focused_center.x()
        fy = focused_center.y()
        candidates = []

        for widget in section:
            if widget is focused:
                continue
            center = widget.mapTo(settings_dialog, widget.rect().center())
            dx = center.x() - fx
            dy = center.y() - fy

            if is_vertical:
                if direction < 0 and dy >= -4:
                    continue
                if direction > 0 and dy <= 4:
                    continue
                score = abs(dy) + abs(dx) * 3
            else:
                if direction < 0 and dx >= -4:
                    continue
                if direction > 0 and dx <= 4:
                    continue
                score = abs(dx) + abs(dy) * 3

            candidates.append((score, widget))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def _find_mangohud_grid_horizontal_target(
        self, focused: QWidget, direction: int, section: list[QWidget]
    ) -> QWidget | None:
        """Navigate left/right in MangoHud grids with row wrap at edges."""
        settings_dialog = self.settings_dialog
        if not settings_dialog:
            return None
        sorted_widgets = sorted(
            section,
            key=lambda widget: (
                widget.mapTo(settings_dialog, widget.rect().center()).y(),
                widget.mapTo(settings_dialog, widget.rect().center()).x(),
            ),
        )
        rows = []
        tolerance = 24
        for widget in sorted_widgets:
            y = widget.mapTo(settings_dialog, widget.rect().center()).y()
            if not rows:
                rows.append([widget])
                continue
            last_y = rows[-1][0].mapTo(settings_dialog, rows[-1][0].rect().center()).y()
            if abs(y - last_y) <= tolerance:
                rows[-1].append(widget)
            else:
                rows.append([widget])
        for row in rows:
            row.sort(key=lambda widget: widget.mapTo(settings_dialog, widget.rect().center()).x())

        row_idx = -1
        col_idx = -1
        for index, row in enumerate(rows):
            if focused in row:
                row_idx = index
                col_idx = row.index(focused)
                break
        if row_idx == -1:
            return None

        if direction > 0:
            if col_idx + 1 < len(rows[row_idx]):
                return rows[row_idx][col_idx + 1]
            if row_idx + 1 < len(rows):
                return rows[row_idx + 1][0]
            return None
        if direction < 0:
            if col_idx - 1 >= 0:
                return rows[row_idx][col_idx - 1]
            if row_idx - 1 >= 0:
                return rows[row_idx - 1][-1]
            return None
        return None

    def _is_mangohud_fps_widget(self, widget):
        """Check if widget belongs to MangoHud FPS section."""
        if not self.settings_dialog:
            return False
        return widget in set(self.settings_dialog.mangohud_fps_widgets.values())

    def _is_mangohud_toggle_widget(self, widget: QWidget) -> bool:
        """Check if widget belongs to MangoHud/Gamescope toggle checkbox section."""
        if not self.settings_dialog:
            return False
        tab_index = self.settings_dialog.tab_widget.currentIndex()
        if tab_index == 2:
            toggle_keys = getattr(self.settings_dialog, 'mangohud_toggle_widget_keys', {})
        elif tab_index == 3:
            toggle_keys = getattr(self.settings_dialog, 'gamescope_toggle_widget_keys', {})
        else:
            toggle_keys = {}
        return isinstance(widget, QCheckBox) and widget in toggle_keys

    def _find_mangohud_toggle_vertical_target(
        self, focused: QWidget, direction: int, section: list[QWidget]
    ) -> QWidget | None:
        """Navigate toggle checkboxes down/up with automatic next/prev column jump."""
        toggle_widgets = [widget for widget in section if self._is_mangohud_toggle_widget(widget)]
        if not toggle_widgets:
            return None
        return self._find_mangohud_vertical_grid_target(focused, direction, toggle_widgets)

    def _find_mangohud_fps_vertical_target(self, focused, direction, section):
        """Navigate FPS widgets down/up with automatic next/prev column jump."""
        fps_widgets = [widget for widget in section if self._is_mangohud_fps_widget(widget)]
        if not fps_widgets:
            return None
        return self._find_mangohud_vertical_grid_target(focused, direction, fps_widgets)

    def _find_mangohud_vertical_grid_target(
        self, focused: QWidget, direction: int, widgets: list[QWidget]
    ) -> QWidget | None:
        """Find vertical target in grid columns with column-to-column wrap."""
        settings_dialog = self.settings_dialog
        if not settings_dialog:
            return None
        sorted_widgets = sorted(
            widgets,
            key=lambda widget: (
                widget.mapTo(settings_dialog, widget.rect().center()).x(),
                widget.mapTo(settings_dialog, widget.rect().center()).y(),
            ),
        )
        columns = []
        tolerance = 24
        for widget in sorted_widgets:
            x = widget.mapTo(settings_dialog, widget.rect().center()).x()
            if not columns:
                columns.append([widget])
                continue
            last_x = columns[-1][0].mapTo(settings_dialog, columns[-1][0].rect().center()).x()
            if abs(x - last_x) <= tolerance:
                columns[-1].append(widget)
            else:
                columns.append([widget])

        col_idx = -1
        row_idx = -1
        for index, column in enumerate(columns):
            if focused in column:
                col_idx = index
                row_idx = column.index(focused)
                break
        if col_idx == -1:
            return None

        if direction > 0:
            if row_idx + 1 < len(columns[col_idx]):
                return columns[col_idx][row_idx + 1]
            if col_idx + 1 < len(columns):
                return columns[col_idx + 1][0]
            return None

        if direction < 0:
            if row_idx - 1 >= 0:
                return columns[col_idx][row_idx - 1]
            if col_idx - 1 >= 0:
                return columns[col_idx - 1][-1]
            return None
        return None

    def handle_navigation_repeat(self):
        """Smooth movement repeat with variable speed for FileExplorer"""
        try:
            if not self.file_explorer or not hasattr(self.file_explorer, 'file_list') or not self.file_explorer.file_list:
                return

            if self.current_direction != 0:
                now = time.time()
                # Dynamic interval based on stick_value
                dynamic_delay = self.repeat_nav_delay / self.stick_value
                if now - self.last_nav_time >= dynamic_delay:
                    self.file_explorer.move_selection(self.current_direction)
                    self.last_nav_time = now
        except Exception as e:
            logger.error(f"Error in navigation repeat: {e}")

    def disable_mouse_emulation(self):
        """Disable mouse emulation mode (closes virtual mouse device)."""
        logger.info("EMUL: Disabling mouse emulation...")

        # Stop the thread if still running
        thread = self.mouse_emulation_thread
        if thread and thread.isRunning():
            thread.wait()
            self.mouse_emulation_thread = None

        if self.ui:
            try:
                self.ui.close()
                logger.info("EMUL: Virtual mouse closed")
            except Exception as e:
                logger.error("EMUL: Error closing virtual mouse: %s", e)
            self.ui = None
        self.mouse_emulation_enabled = False
        self.stick_x_raw = 0
        self.stick_y_raw = 0
        self.scroll_accumulator = 0.0


    def handle_scroll(self, raw_value):
        """Handle scrolling from right stick Y"""
        if not self.mouse_emulation_enabled or not self.emulation_active or not self.ui:
            return

        # Normalize from center
        centered_value = raw_value - self.scroll_center

        if abs(centered_value) < self.scroll_deadzone_value:
            self.scroll_accumulator = 0.0
            return

        # Normalize value (-1.0 to 1.0)
        range_val = (self.scroll_max_value - self.scroll_min_value) / 2
        if range_val <= 0:
            return
        normalized = centered_value / range_val

        # Accumulate scroll
        self.scroll_accumulator += normalized * self.scroll_sensitivity

        # Send scroll events
        while abs(self.scroll_accumulator) >= self.scroll_threshold:
            scroll_step = 1 if self.scroll_accumulator > 0 else -1
            self.scroll_wheel(-scroll_step)
            self.scroll_accumulator -= scroll_step * self.scroll_threshold

    def update_mouse_position(self):
        """Constant update of mouse position based on stick state"""
        if not self.ui or not self.emulation_active:
            return

        # Center values
        x = self.stick_x_raw - self.center_x
        y = self.stick_y_raw - self.center_y

        # Apply deadzone from kernel
        magnitude = math.sqrt(x * x + y * y)

        if magnitude < self.deadzone_value:
            return

        if magnitude > 0:
            norm_x = x / magnitude
            norm_y = y / magnitude
        else:
            return

        # Normalize to axis range
        max_range = (self.max_value - self.min_value) / 2
        adjusted_magnitude = (magnitude - self.deadzone_value) / (max_range - self.deadzone_value)
        adjusted_magnitude = max(0.0, min(1.0, adjusted_magnitude))

        # Non-linear curve
        adjusted_magnitude = math.pow(adjusted_magnitude, 1.5)

        speed = adjusted_magnitude * self.sensitivity
        dx = int(norm_x * speed)
        dy = int(norm_y * speed)

        if dx != 0 or dy != 0:
            self.move_mouse(dx, dy)

    def move_mouse(self, dx, dy):
        """Move system cursor"""
        if self.ui:
            self.ui.write(ecodes.EV_REL, ecodes.REL_X, dx)
            self.ui.write(ecodes.EV_REL, ecodes.REL_Y, dy)
            self.ui.syn()

    def scroll_wheel(self, steps):
        """Mouse wheel scroll"""
        if self.ui:
            self.ui.write(ecodes.EV_REL, ecodes.REL_WHEEL, steps)
            self.ui.syn()

    def click_left(self):
        """Left mouse button click"""
        if self.ui:
            self.ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
            self.ui.syn()
            self.ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
            self.ui.syn()

    def click_right(self):
        """Right mouse button click"""
        if self.ui:
            self.ui.write(ecodes.EV_KEY, ecodes.BTN_RIGHT, 1)
            self.ui.syn()
            self.ui.write(ecodes.EV_KEY, ecodes.BTN_RIGHT, 0)
            self.ui.syn()

    @Slot(bool)
    def handle_fullscreen_slot(self, enable: bool) -> None:
        try:
            window = self._parent
            if not isinstance(window, QWidget):
                return
            if enable and not self._is_fullscreen:
                if not window.isFullScreen():
                    window_config.set_geometry(window.width(), window.height())
                window.showFullScreen()
                self._is_fullscreen = True
            elif not enable and self._is_fullscreen:
                window.showNormal()
                width, height = window_config.get_geometry()
                if width > 0 and height > 0:
                    window.resize(width, height)
                self._is_fullscreen = False
                window_config.set_geometry(width, height)
        except Exception as e:
            logger.error(f"Error in handle_fullscreen_slot: {e}", exc_info=True)

    def disable_gamepad_handling(self) -> None:
        """Disable gamepad event handling."""
        self._gamepad_handling_enabled = False
        self.dpad_timer.stop()
        self.nav_timer.stop()

    def enable_gamepad_handling(self) -> None:
        """Enable gamepad event handling."""
        self._gamepad_handling_enabled = True

    def suspend_gamepad_polling(self) -> None:
        """Disable PPQT gamepad handling while keeping mouse emulation available."""
        self._gamepad_handling_enabled = False
        self.dpad_timer.stop()
        self.nav_timer.stop()

    def resume_gamepad_polling(self) -> None:
        """Resume SDL controller polling after the external game exits."""
        self._gamepad_polling_suspended = False
        self._gamepad_handling_enabled = True
        self.check_gamepad()

    def _handle_guide_timeout(self) -> None:
        if self.guide_held:
            time_since_guide = time.time() - self.guide_pressed_time
            time_since_select = time.time() - self.select_pressed_time

            if (self.select_pressed_time > self.guide_pressed_time and
                time_since_select <= self.guide_combination_timeout and
                time_since_guide <= self.guide_combination_timeout):
                logger.debug("Guide + Select combination detected, refreshing game grid")
                self._parent.refreshGames()
            else:
                logger.debug("Guide button pressed alone")

        self.guide_held = False
        self.in_guide_combination_attempt = False
        self.guide_pressed_time = 0
        self.select_pressed_time = 0


    @Slot(int, int)
    def handle_button_slot(self, button_code: int, value: int) -> None:
        # Handle common UI elements like QMessageBox, QMenu, etc. FIRST
        # This ensures that any active dialogs are handled before main window logic
        # Only handle press events (value=1), ignore release events (value=0)
        if value == 1 and self._handle_common_ui_elements(button_code):
            return

        active_window = QApplication.activeWindow()

        # Handle virtual keyboard in AddGameDialog (handle both press and release)
        if isinstance(active_window, AddGameDialog):
            focused = QApplication.focusWidget()
            if button_code in BUTTONS['confirm'] and value == 1 and isinstance(focused, QLineEdit):
                # Show keyboard on A press on input field (only on press)
                active_window.show_keyboard_for_widget(focused)
                return

            # If keyboard visible, handle its buttons (including release)
            if hasattr(active_window, 'keyboard') and active_window.keyboard.isVisible():
                self.handle_virtual_keyboard(button_code, value)
                return

        # Active dialog keyboard handling (including release)
        dialog_keyboard = getattr(active_window, 'keyboard', None) if active_window else None
        if isinstance(dialog_keyboard, VirtualKeyboard) and dialog_keyboard.isVisible():
            self.handle_virtual_keyboard(button_code, value)
            return

        # Main window keyboard handling (including release)
        keyboard = getattr(self._parent, 'keyboard', None)
        if keyboard and keyboard.isVisible():
            self.handle_virtual_keyboard(button_code, value)
            return

        # Ignore releases for all other (non-keyboard) button handling
        if value == 0:
            return

        if not self._gamepad_handling_enabled:
            return
        try:

            app = QApplication.instance()
            active = QApplication.activeWindow()
            focused = QApplication.focusWidget()
            if not app or not active:
                return

            current_tab_index = self._parent.stackedWidget.currentIndex()

            if button_code in BUTTONS['confirm'] and isinstance(focused, QLineEdit):
                if isinstance(active, AddGameDialog):
                    keyboard = getattr(active, 'keyboard', None)
                else:
                    keyboard = getattr(self._parent, 'keyboard', None)
                if keyboard:
                    keyboard.show_for_widget(focused)
                    return

            # Y on editable combo opens keyboard for combo input
            if button_code in BUTTONS['prev_dir']:
                focused_combo = None
                if isinstance(focused, QComboBox):
                    focused_combo = focused
                else:
                    parent = focused.parentWidget() if focused else None
                    if isinstance(parent, QComboBox):
                        focused_combo = parent
                if focused_combo and focused_combo.isEditable():
                    line_edit = focused_combo.lineEdit()
                    keyboard = getattr(self._parent, 'keyboard', None)
                    if line_edit and keyboard:
                        line_edit.setFocus()
                        keyboard.show_for_widget(line_edit)
                        return

            # Handle Y button to focus search
            if button_code in BUTTONS['prev_dir']:  # Y button
                search_edit = None
                if current_tab_index == 0:
                    search_edit = getattr(self._parent, 'searchEdit', None)
                elif current_tab_index == 1:
                    search_edit = getattr(self._parent, 'autoInstallSearchLineEdit', None)
                if search_edit:
                    search_edit.setFocus()
                    return

            # Guide + Select combination for refreshing game grid
            if value == 1:
                current_time = time.time()

                if button_code in BUTTONS['guide']:
                    self.guide_held = True
                    self.guide_pressed_time = current_time
                    self.in_guide_combination_attempt = True
                    if hasattr(self, 'guide_timer'):
                        self.guide_timer.start(int(self.guide_combination_timeout * 1000))
                    return
                elif button_code in BUTTONS['menu'] and hasattr(self, 'guide_held') and self.guide_held:
                    self.select_pressed_time = current_time
                    time_since_guide = current_time - self.guide_pressed_time
                    if time_since_guide <= self.guide_combination_timeout:
                        if hasattr(self, 'guide_timer'):
                            self.guide_timer.stop()
                        logger.debug("Guide + Select combination detected, refreshing game grid")
                        self._parent.refreshGames()
                        self.guide_held = False
                        self.in_guide_combination_attempt = False
                        self.guide_pressed_time = 0
                        self.select_pressed_time = 0
                        return
                    else:
                        self.in_guide_combination_attempt = False
                        self.guide_held = False
                        self.guide_pressed_time = 0
                        self.select_pressed_time = 0

            # Handle QComboBox
            if isinstance(focused, QComboBox):
                if button_code in BUTTONS['confirm']:
                    focused.showPopup()
                    return
                if button_code in BUTTONS['back'] and focused.view().isVisible():
                    focused.hidePopup()
                    return

            # Handle QListView
            if isinstance(focused, QListView):
                combo = None
                parent = focused.parentWidget()
                while parent:
                    if isinstance(parent, QComboBox):
                        combo = parent
                        break
                    parent = parent.parentWidget()

                if button_code in BUTTONS['confirm']:
                    idx = focused.currentIndex()
                    if idx.isValid():
                        if combo:
                            combo.setCurrentIndex(idx.row())
                            combo.hidePopup()
                            combo.setFocus(Qt.FocusReason.OtherFocusReason)
                        else:
                            focused.activated.emit(idx)
                            focused.clicked.emit(idx)
                            focused.hide()
                    return

                if button_code in BUTTONS['back']:
                    if combo:
                        combo.hidePopup()
                        combo.setFocus(Qt.FocusReason.OtherFocusReason)
                    else:
                        focused.clearSelection()
                        focused.hide()

            # Close AddGameDialog on B button
            if button_code in BUTTONS['back'] and isinstance(active, QDialog):
                active.reject()
                return

            # FullscreenDialog
            if isinstance(active, FullscreenDialog):
                if button_code in BUTTONS['prev_tab']:
                    active.show_prev()
                elif button_code in BUTTONS['next_tab']:
                    active.show_next()
                elif button_code in BUTTONS['back']:
                    active.close()
                return

            # Context menu for GameCard
            if button_code in BUTTONS['context_menu'] and isinstance(focused, QTableWidget):
                current_row = focused.currentRow()
                current_col = focused.currentColumn()
                if current_col < 0:
                    current_col = 0
                if current_row >= 0:
                    item = focused.item(current_row, current_col)
                    if item is None:
                        item = focused.item(current_row, 0)
                    if item is not None:
                        point = focused.visualItemRect(item).center()
                    else:
                        point = focused.viewport().rect().center()
                else:
                    point = focused.viewport().rect().center()
                focused.customContextMenuRequested.emit(point)
                return

            if button_code in BUTTONS['context_menu'] and isinstance(focused, QWidget):
                if focused.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu:
                    focused.customContextMenuRequested.emit(focused.rect().center())
                    return

            if isinstance(focused, GameCard):
                if button_code in BUTTONS['context_menu']:
                    pos = QPoint(focused.width() // 2, focused.height() // 2)
                    menu = focused._show_context_menu(pos)
                    if menu:
                        menu.setFocus(Qt.FocusReason.OtherFocusReason)
                    return

            if isinstance(focused, QTableWidget):
                system_action = getattr(self._parent, "handleSystemTableGamepadAction", None)
                if callable(system_action):
                    if button_code in BUTTONS['confirm'] and system_action(focused, "confirm"):
                        return
                    if button_code in BUTTONS['back'] and system_action(focused, "back"):
                        return
                    if button_code in BUTTONS['prev_dir'] and system_action(focused, "prev_dir"):
                        return
                    if button_code in BUTTONS['add_game'] and system_action(focused, "add_game"):
                        return

            system_quick_action = getattr(self._parent, "handleSystemGamepadAction", None)
            if (
                callable(system_quick_action)
                and button_code in BUTTONS['add_game']
                and system_quick_action("add_game")
            ):
                return

            # Standard navigation
            if button_code in BUTTONS['confirm']:
                self._parent.activateFocusedWidget()
            elif button_code in BUTTONS['back']:
                self._parent.goBackDetailPage(getattr(self._parent, 'currentDetailPage', None))
            elif button_code in BUTTONS['add_game']:
                if self._parent.stackedWidget.currentIndex() == 0:
                    self._parent.openAddGameDialog()
            elif button_code in BUTTONS['prev_tab']:
                idx = self._parent.stackedWidget.currentIndex()

                # Get only visible tab indices
                visible_tab_indices = []
                if hasattr(self._parent, 'tabButtons'):
                    for i, btn in self._parent.tabButtons.items():
                        if btn.isVisible():
                            visible_tab_indices.append(i)
                    visible_tab_indices.sort()  # Ensure they're in order

                if visible_tab_indices:
                    # Find current position in the visible tabs list
                    try:
                        current_visible_pos = visible_tab_indices.index(idx)
                    except ValueError:
                        # Current index is not visible, default to first visible
                        current_visible_pos = 0

                    new_visible_pos = (current_visible_pos - 1) % len(visible_tab_indices)
                    idx = visible_tab_indices[new_visible_pos]
                    self._parent.switchTab(idx)
                    self._parent.tabButtons[idx].setFocus(Qt.FocusReason.OtherFocusReason)
            elif button_code in BUTTONS['next_tab']:
                idx = self._parent.stackedWidget.currentIndex()

                # Get only visible tab indices
                visible_tab_indices = []
                if hasattr(self._parent, 'tabButtons'):
                    for i, btn in self._parent.tabButtons.items():
                        if btn.isVisible():
                            visible_tab_indices.append(i)
                    visible_tab_indices.sort()  # Ensure they're in order

                if visible_tab_indices:
                    # Find current position in the visible tabs list
                    try:
                        current_visible_pos = visible_tab_indices.index(idx)
                    except ValueError:
                        # Current index is not visible, default to first visible
                        current_visible_pos = 0

                    new_visible_pos = (current_visible_pos + 1) % len(visible_tab_indices)
                    idx = visible_tab_indices[new_visible_pos]
                    self._parent.switchTab(idx)
                    self._parent.tabButtons[idx].setFocus(Qt.FocusReason.OtherFocusReason)
            elif button_code in BUTTONS['increase_size'] and value > 0:
                current_tab = self._parent.stackedWidget.currentIndex()
                system_tab_index = getattr(self._parent, "system_tab_index", -1)
                if current_tab == system_tab_index:
                    section_stack = getattr(self._parent, "systemSectionStack", None)
                    volume_slider = getattr(self._parent, "audioVolumeSlider", None)
                    apply_volume = getattr(self._parent, "_applySelectedAudioVolume", None)
                    if (
                        isinstance(section_stack, QStackedWidget)
                        and section_stack.currentIndex() == 4
                        and isinstance(volume_slider, QSlider)
                    ):
                        new_value = min(volume_slider.value() + 5, volume_slider.maximum())
                        volume_slider.setValue(new_value)
                        if callable(apply_volume):
                            apply_volume()
                        return
                if current_tab == 0:  # Main games library
                    if hasattr(self._parent, 'game_library_manager') and self._parent.game_library_manager:
                        size_slider = getattr(self._parent.game_library_manager, 'sizeSlider', None)
                        if size_slider:
                            new_value = min(size_slider.value() + 10, size_slider.maximum())
                            size_slider.setValue(new_value)
                            self._parent.on_slider_released()
                elif current_tab == 1:  # Auto-install tab
                    auto_size_slider = getattr(self._parent, 'auto_size_slider', None)
                    if auto_size_slider:
                        new_value = min(auto_size_slider.value() + 10, auto_size_slider.maximum())
                        auto_size_slider.setValue(new_value)
                        if hasattr(self._parent, 'on_auto_slider_released'):
                            self._parent.on_auto_slider_released()
            elif button_code in BUTTONS['decrease_size'] and value > 0:
                current_tab = self._parent.stackedWidget.currentIndex()
                system_tab_index = getattr(self._parent, "system_tab_index", -1)
                if current_tab == system_tab_index:
                    section_stack = getattr(self._parent, "systemSectionStack", None)
                    volume_slider = getattr(self._parent, "audioVolumeSlider", None)
                    apply_volume = getattr(self._parent, "_applySelectedAudioVolume", None)
                    if (
                        isinstance(section_stack, QStackedWidget)
                        and section_stack.currentIndex() == 4
                        and isinstance(volume_slider, QSlider)
                    ):
                        new_value = max(volume_slider.value() - 5, volume_slider.minimum())
                        volume_slider.setValue(new_value)
                        if callable(apply_volume):
                            apply_volume()
                        return
                if current_tab == 0:  # Main games library
                    if hasattr(self._parent, 'game_library_manager') and self._parent.game_library_manager:
                        size_slider = getattr(self._parent.game_library_manager, 'sizeSlider', None)
                        if size_slider:
                            new_value = max(size_slider.value() - 10, size_slider.minimum())
                            size_slider.setValue(new_value)
                            self._parent.on_slider_released()
                elif current_tab == 1:  # Auto-install tab
                    auto_size_slider = getattr(self._parent, 'auto_size_slider', None)
                    if auto_size_slider:
                        new_value = max(auto_size_slider.value() - 10, auto_size_slider.minimum())
                        auto_size_slider.setValue(new_value)
                        if hasattr(self._parent, 'on_auto_slider_released'):
                            self._parent.on_auto_slider_released()
        except Exception as e:
            logger.error(f"Error in handle_button_slot: {e}", exc_info=True)

    def handle_dpad_repeat(self) -> None:
        """Handle repeated D-pad input while the D-pad is held."""
        if self.current_dpad_code is not None and self.current_dpad_value != 0:
            now = time.time()
            if (now - self.last_move_time) >= self.current_axis_delay:
                self.handle_dpad_slot(self.current_dpad_code, self.current_dpad_value, now)
                self.last_move_time = now
                self.current_axis_delay = self.repeat_axis_move_delay

    def _get_theme_tab_focusables(self) -> list[QWidget]:
        """Return focusable widgets for the themes tab gamepad navigation."""
        widgets = []
        for attr_name in ("themesCombo", "themeVariantCombo", "screenshotsCarousel", "applyButton"):
            widget = getattr(self._parent, attr_name, None)
            if isinstance(widget, QWidget) and widget.isVisible() and widget.isEnabled():
                widgets.append(widget)
        return widgets

    def _handle_theme_tab_navigation(self, value: int) -> bool:
        """Handle up/down focus movement in themes tab."""
        theme_tab_index = getattr(self._parent, "theme_tab_index", None)
        if theme_tab_index is None or self._parent.stackedWidget.currentIndex() != theme_tab_index:
            return False

        focusables = self._get_theme_tab_focusables()
        if not focusables:
            return False

        focused = QApplication.focusWidget()
        if focused not in focusables:
            focusables[0].setFocus(Qt.FocusReason.OtherFocusReason)
            return True

        current_index = focusables.index(focused)
        if value > 0:
            next_index = (current_index + 1) % len(focusables)
        else:
            next_index = (current_index - 1) % len(focusables)
        focusables[next_index].setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    @Slot(int, int, float)
    def handle_dpad_slot(self, code: int, value: int, current_time: float) -> None:
        active_window = QApplication.activeWindow()
        if isinstance(active_window, AddGameDialog):
            keyboard = getattr(active_window, 'keyboard', None)
        else:
            keyboard = getattr(self._parent, 'keyboard', None)

        # Handle release early
        if value == 0:
            self.current_dpad_code = None
            self.current_dpad_value = 0
            self.axis_moving = False
            self.current_axis_delay = self.initial_axis_move_delay
            self.dpad_timer.stop()
            return

        # Update D-pad state for continuous movement
        is_initial_press = not self.axis_moving
        self.current_dpad_code = code
        self.current_dpad_value = value
        if not self.axis_moving:
            self.axis_moving = True
            self.last_move_time = current_time
            self.current_axis_delay = self.initial_axis_move_delay
            self.dpad_timer.start(int(self.repeat_axis_move_delay * 1000))

        if keyboard and keyboard.isVisible():
            # Handle horizontal movement (LEFT/RIGHT)
            if code in (PAD_DPAD_X, PAD_AXIS_LEFT_X):
                normalized_value = 0
                if code == PAD_AXIS_LEFT_X:  # Left stick
                    # Apply deadzone
                    if abs(value) < self.dead_zone:
                        self.current_dpad_code = None
                        self.current_dpad_value = 0
                        self.axis_moving = False
                        self.dpad_timer.stop()
                        return
                    normalized_value = 1 if value > self.dead_zone else -1
                else:  # D-pad
                    normalized_value = value  # D-pad already gives -1, 0, 1

                if normalized_value != 0:
                    if normalized_value > 0:  # Right
                        keyboard.move_focus_right()
                    elif normalized_value < 0:  # Left
                        keyboard.move_focus_left()
                return

            # Handle vertical movement (UP/DOWN)
            elif code in (PAD_DPAD_Y, PAD_AXIS_LEFT_Y):
                normalized_value = 0
                if code == PAD_AXIS_LEFT_Y:  # Left stick
                    # Apply deadzone
                    if abs(value) < self.dead_zone:
                        self.current_dpad_code = None
                        self.current_dpad_value = 0
                        self.axis_moving = False
                        self.dpad_timer.stop()
                        return
                    normalized_value = 1 if value > self.dead_zone else -1
                else:  # D-pad
                    normalized_value = value  # D-pad already gives -1, 0, 1

                if normalized_value != 0:
                    if normalized_value > 0:  # Down
                        keyboard.move_focus_down()
                    elif normalized_value < 0:  # Up
                        keyboard.move_focus_up()
                return

        if not self._gamepad_handling_enabled:
            return
        if not hasattr(self._parent, 'gamesListWidget') or self._parent.gamesListWidget is None:
            logger.error("gamesListWidget not available yet, skipping D-pad navigation")
            return
        try:

            app = QApplication.instance()
            active = QApplication.activeWindow()
            focused = QApplication.focusWidget()
            popup = QApplication.activePopupWidget()
            if not app or not active:
                return

            # Handle QMessageBox navigation with D-pad (for multiple buttons)
            if isinstance(active, QMessageBox) and not isinstance(focused, QTableWidget):
                if not focused or not active.focusWidget():
                    # If no widget is focused, focus the first focusable widget
                    focusables = active.findChildren(QWidget, options=Qt.FindChildOption.FindChildrenRecursively)
                    focusables = [w for w in focusables if w.focusPolicy() & Qt.FocusPolicy.StrongFocus]
                    if focusables:
                        focusables[0].setFocus(Qt.FocusReason.OtherFocusReason)
                    return
                if code == PAD_DPAD_X and value != 0:  # Horizontal navigation
                    if value > 0:  # Right
                        active.focusNextChild()
                    elif value < 0:  # Left
                        active.focusPreviousChild()
                elif code == PAD_DPAD_Y and value != 0:  # Vertical navigation
                    if value > 0:  # Down
                        active.focusNextChild()
                    elif value < 0:  # Up
                        active.focusPreviousChild()
                return
            # Handle horizontal navigation between AddGameDialog shortcut checkboxes
            if isinstance(active, AddGameDialog) and code in (PAD_DPAD_X, PAD_AXIS_LEFT_X) and value != 0:
                normalized_value = value
                if code == PAD_AXIS_LEFT_X:
                    if abs(value) < self.dead_zone:
                        return
                    normalized_value = 1 if value > self.dead_zone else -1
                checkbox_row = [
                    active.add_to_steam_checkbox,
                    active.add_to_menu_checkbox,
                    active.add_to_desktop_checkbox,
                ]
                focused_checkbox = focused if isinstance(focused, QCheckBox) else None
                if focused_checkbox and focused_checkbox in checkbox_row:
                    current_index = checkbox_row.index(focused_checkbox)
                    if normalized_value < 0 and current_index > 0:
                        checkbox_row[current_index - 1].setFocus(Qt.FocusReason.OtherFocusReason)
                        return
                    if normalized_value > 0 and current_index < len(checkbox_row) - 1:
                        checkbox_row[current_index + 1].setFocus(Qt.FocusReason.OtherFocusReason)
                        return

            # Handle AddGameDialog or other QDialog navigation with D-pad
            elif isinstance(active, QDialog) and code == PAD_DPAD_X and value != 0:
                if not focused or not active.focusWidget():
                    # If no widget is focused, focus the first focusable widget
                    focusables = active.findChildren(QWidget, options=Qt.FindChildOption.FindChildrenRecursively)
                    focusables = [w for w in focusables if w.focusPolicy() & Qt.FocusPolicy.StrongFocus]
                    if focusables:
                        focusables[0].setFocus(Qt.FocusReason.OtherFocusReason)
                    return
                if value > 0:  # Right
                    active.focusNextChild()
                elif value < 0:  # Left
                    active.focusPreviousChild()
                return
            elif isinstance(active, QDialog) and code == PAD_DPAD_Y and value != 0 and not isinstance(focused, QTableWidget):  # Keep up/down for other dialogs
                if not focused or not active.focusWidget():
                    # If no widget is focused, focus the first focusable widget
                    focusables = active.findChildren(QWidget, options=Qt.FindChildOption.FindChildrenRecursively)
                    focusables = [w for w in focusables if w.focusPolicy() & Qt.FocusPolicy.StrongFocus]
                    if focusables:
                        focusables[0].setFocus(Qt.FocusReason.OtherFocusReason)
                    return
                if value > 0:  # Down
                    active.focusNextChild()
                elif value < 0:  # Up
                    active.focusPreviousChild()
                return

            # Handle QMenu navigation with D-pad
            if isinstance(popup, QMenu):
                if code == PAD_DPAD_Y and value != 0:
                    self._navigate_menu_actions(popup, direction_down=value > 0)
                    return
                return

            # Handle QListView navigation with D-pad
            if isinstance(focused, QListView) and code == PAD_DPAD_Y and value != 0:
                model = focused.model()
                current_index = focused.currentIndex()
                if model and current_index.isValid():
                    row_count = model.rowCount()
                    current_row = current_index.row()
                    if value > 0:  # Down
                        next_row = min(current_row + 1, row_count - 1)
                        focused.setCurrentIndex(model.index(next_row, current_index.column()))
                    elif value < 0:  # Up
                        prev_row = max(current_row - 1, 0)
                        focused.setCurrentIndex(model.index(prev_row, current_index.column()))
                    focused.scrollTo(focused.currentIndex(), QListView.ScrollHint.PositionAtCenter)
                return

            # Fullscreen horizontal navigation
            if isinstance(active, FullscreenDialog) and code == PAD_DPAD_X:
                if value < 0:
                    active.show_prev()
                elif value > 0:
                    active.show_next()
                return


            # Table navigation using generalized methods
            if code == PAD_DPAD_X and value != 0:
                system_tab_index = getattr(self._parent, "system_tab_index", -1)
                if self._parent.stackedWidget.currentIndex() == system_tab_index:
                    switch_relative = getattr(self._parent, "switchSystemSectionRelative", None)
                    if callable(switch_relative) and is_initial_press:
                        switched = switch_relative(1 if value > 0 else -1)
                        if switched:
                            section_stack = getattr(self._parent, "systemSectionStack", None)
                            section_buttons = getattr(self._parent, "systemSectionButtons", [])
                            if section_stack is not None and section_buttons:
                                current_index = section_stack.currentIndex()
                                if 0 <= current_index < len(section_buttons):
                                    section_buttons[current_index].setFocus(Qt.FocusReason.OtherFocusReason)
                            return

            # Table navigation using generalized methods
            if isinstance(focused, QTableWidget):
                self.handle_table_navigation(focused, code, value)
                return

            # Search focus logic for tabs 0 and 1
            if code == PAD_DPAD_Y and value < 0:
                focused = QApplication.focusWidget()
                current_index = self._parent.stackedWidget.currentIndex()
                if current_index in (0, 1) and isinstance(focused, GameCard):
                    if current_index == 0:
                        container = self._parent.gamesListWidget
                        toolbar_widgets = self._get_library_toolbar_widgets()
                        focus_target = toolbar_widgets[0] if toolbar_widgets else None
                    else:
                        container = self._parent.autoInstallContainer
                        focus_target = getattr(self._parent, 'autoInstallSearchLineEdit', None)
                    if container and focus_target:
                        game_cards = container.findChildren(GameCard)
                        if game_cards:
                            current_card_pos = focused.pos()
                            current_row_y = current_card_pos.y()
                            is_first_row = True
                            for card in game_cards:
                                if card.pos().y() < current_row_y and card.isVisible():
                                    is_first_row = False
                                    break
                            if is_first_row:
                                focus_target.setFocus(Qt.FocusReason.OtherFocusReason)
                                return

            # Game cards navigation for tabs 0 and 1
            if code in (PAD_DPAD_X, PAD_DPAD_Y):
                current_index = self._parent.stackedWidget.currentIndex()
                if current_index in (0, 1):
                    if self._handle_library_toolbar_navigation(code, value):
                        return
                    if code == PAD_DPAD_Y and value < 0 and self._focus_tab_from_search(current_index):
                        return
                    container = self._parent.gamesListWidget if current_index == 0 else self._parent.autoInstallContainer
                    if container is None:
                        return
                    self._navigate_game_cards(container, current_index, code, value)
                    return

            if code == PAD_DPAD_Y and value != 0 and self._handle_theme_tab_navigation(value):
                return

            # System tab section buttons: do not cycle tabs on Up/Down.
            if code == PAD_DPAD_Y and value != 0:
                system_tab_index = getattr(self._parent, "system_tab_index", -1)
                if self._parent.stackedWidget.currentIndex() == system_tab_index:
                    focused = QApplication.focusWidget()
                    section_buttons = getattr(self._parent, "systemSectionButtons", [])
                    if focused in section_buttons:
                        if value > 0:
                            section_stack = getattr(self._parent, "systemSectionStack", None)
                            focus_targets = getattr(self._parent, "systemSectionFocusTargets", [])
                            if section_stack is not None:
                                current_index = section_stack.currentIndex()
                                if 0 <= current_index < len(focus_targets):
                                    target = focus_targets[current_index]
                                    if target is not None and target.isVisible() and target.isEnabled():
                                        target.setFocus(Qt.FocusReason.OtherFocusReason)
                        return

            # Button navigation on detail pages (horizontal layout)
            if code in (PAD_DPAD_X, PAD_DPAD_Y, PAD_AXIS_LEFT_X, PAD_AXIS_LEFT_Y):
                focused = QApplication.focusWidget()
                page = self._parent.stackedWidget.currentWidget()
                current_detail_page = getattr(self._parent, "currentDetailPage", None)

                normalized_code = code
                normalized_value = value
                if code in (PAD_AXIS_LEFT_X, PAD_AXIS_LEFT_Y):
                    if abs(value) < self.dead_zone:
                        normalized_value = 0
                    else:
                        normalized_value = 1 if value > self.dead_zone else -1
                    normalized_code = PAD_DPAD_X if code == PAD_AXIS_LEFT_X else PAD_DPAD_Y

                # Check if we're on a detail page and focused widget is a button
                if (
                    isinstance(focused, AutoSizeButton)
                    and page is not None
                    and current_detail_page is not None
                    and page == current_detail_page
                    and normalized_value != 0
                ):
                    parent_widget = focused.parentWidget()
                    if parent_widget:
                        buttons = parent_widget.findChildren(
                            AutoSizeButton,
                            options=Qt.FindChildOption.FindDirectChildrenOnly,
                        )
                        buttons = [btn for btn in buttons if btn.isVisible() and btn.isEnabled()]
                        if len(buttons) > 1 and focused in buttons:
                            centers = {
                                btn: (
                                    btn.geometry().x() + btn.geometry().width() // 2,
                                    btn.geometry().y() + btn.geometry().height() // 2,
                                )
                                for btn in buttons
                            }
                            sorted_by_yx = sorted(
                                buttons,
                                key=lambda btn: (centers[btn][1], centers[btn][0]),
                            )
                            row_tolerance = 24
                            rows = []
                            for btn in sorted_by_yx:
                                if not rows:
                                    rows.append([btn])
                                    continue
                                last_row = rows[-1]
                                last_row_y = centers[last_row[0]][1]
                                if abs(centers[btn][1] - last_row_y) <= row_tolerance:
                                    last_row.append(btn)
                                else:
                                    rows.append([btn])
                            for row in rows:
                                row.sort(key=lambda btn: centers[btn][0])

                            current_row_idx = -1
                            current_col_idx = -1
                            for row_idx, row in enumerate(rows):
                                if focused in row:
                                    current_row_idx = row_idx
                                    current_col_idx = row.index(focused)
                                    break
                            if current_row_idx == -1:
                                return

                            target = None
                            if normalized_code == PAD_DPAD_X and normalized_value > 0:
                                if current_col_idx < len(rows[current_row_idx]) - 1:
                                    target = rows[current_row_idx][current_col_idx + 1]
                                elif current_row_idx < len(rows) - 1:
                                    target = rows[current_row_idx + 1][0]
                            elif normalized_code == PAD_DPAD_X and normalized_value < 0:
                                if current_col_idx > 0:
                                    target = rows[current_row_idx][current_col_idx - 1]
                                elif current_row_idx > 0:
                                    target = rows[current_row_idx - 1][-1]
                            elif normalized_code == PAD_DPAD_Y and normalized_value > 0:
                                if current_row_idx < len(rows) - 1:
                                    next_row = rows[current_row_idx + 1]
                                    current_x = centers[focused][0]
                                    target = min(next_row, key=lambda btn: abs(centers[btn][0] - current_x))
                            elif normalized_code == PAD_DPAD_Y and normalized_value < 0:
                                if current_row_idx > 0:
                                    prev_row = rows[current_row_idx - 1]
                                    current_x = centers[focused][0]
                                    target = min(prev_row, key=lambda btn: abs(centers[btn][0] - current_x))

                            if target:
                                target.setFocus(Qt.FocusReason.OtherFocusReason)
                                scroll_area = target.parentWidget()
                                while scroll_area and not isinstance(scroll_area, QScrollArea):
                                    scroll_area = scroll_area.parentWidget()
                                if isinstance(scroll_area, QScrollArea):
                                    scroll_area.ensureWidgetVisible(target, 20, 20)
                                return

            # Vertical navigation in other tabs
            if code == PAD_DPAD_Y and value != 0:
                focused = QApplication.focusWidget()
                page = self._parent.stackedWidget.currentWidget()
                if value > 0:  # Down
                    if isinstance(focused, NavLabel):
                        focusables = page.findChildren(QWidget, options=Qt.FindChildOption.FindChildrenRecursively)
                        focusables = [w for w in focusables if w.focusPolicy() & Qt.FocusPolicy.StrongFocus]
                        if focusables:
                            focusables[0].setFocus()
                            return
                    elif focused:
                        focused.focusNextChild()
                        return
                elif value < 0 and focused:  # Up
                    focused.focusPreviousChild()
                    return

        except Exception as e:
            logger.error(f"Error in handle_dpad_slot: {e}", exc_info=True)

    def handle_virtual_keyboard(self, button_code: int, value: int) -> None:
        active_window = QApplication.activeWindow()
        keyboard = getattr(active_window, 'keyboard', None) if active_window else None
        if keyboard is None:
            keyboard = getattr(self._parent, 'keyboard', None)

        if not keyboard or not isinstance(keyboard, VirtualKeyboard) or not keyboard.isVisible():
            return

        # Handle gamepad buttons
        if button_code in BUTTONS['confirm']:  # A/Cross button - confirm
            if value == 1:
                keyboard.activateFocusedKey()
        elif button_code in BUTTONS['back']:  # B/Circle button - hide keyboard
            if value == 1:
                keyboard.hide()
                # Return focus to input field
                if keyboard.current_input_widget:
                    keyboard.current_input_widget.setFocus()
        elif button_code in BUTTONS['prev_tab']:  # LB/L1 - switch layout
            if value == 1:
                keyboard.on_lang_click()
        elif button_code in BUTTONS['next_tab']:  # RB/R1 - toggle Shift
            if value == 1:
                keyboard.on_shift_click(not keyboard.shift_pressed)
        elif button_code in BUTTONS['context_menu']:  # Start button - confirm
            if value == 1:
                keyboard.activateFocusedKey()
        elif button_code in BUTTONS['menu']:  # Select button - hide keyboard
            if value == 1:
                keyboard.hide()
                # Return focus to input field
                if keyboard.current_input_widget:
                    keyboard.current_input_widget.setFocus()
        elif button_code in BUTTONS['add_game']:  # X button - Backspace (now holdable)
            if value == 1:
                keyboard.on_backspace_pressed()
            elif value == 0:
                keyboard.stop_backspace_repeat()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        app = QApplication.instance()
        if not app:
            return super().eventFilter(obj, event)

        if event.type() == QEvent.Type.Wheel:
            combo = obj if isinstance(obj, QComboBox) else None
            parent = obj.parent() if isinstance(obj, QObject) else None
            while combo is None and isinstance(parent, QObject):
                if isinstance(parent, QComboBox):
                    combo = parent
                    break
                parent = parent.parent()
            if isinstance(combo, QComboBox) and not combo.view().isVisible():
                # Find parent scroll area
                scrollable = combo.parent()
                while scrollable:
                    if isinstance(scrollable, QAbstractScrollArea):
                        old_focus = QApplication.focusWidget()
                        QApplication.sendEvent(scrollable.viewport(), event)
                        if old_focus:
                            old_focus.setFocus()
                        return True
                    scrollable = scrollable.parent()
                return True

        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            key = self._qt_event_to_pygame_key(event)
            if key is not None and event.type() == QEvent.Type.KeyPress:
                return self._handle_pygame_key_press(key, self._qt_modifiers_to_pygame(event))
            if key is not None:
                return self._handle_pygame_key_release(key)

        if event.type() == QEvent.Type.MouseButtonPress:
            button_method = getattr(event, "button", None)
            button = button_method() if callable(button_method) else None
            if button == Qt.MouseButton.ExtraButton1:
                self._handle_back_mouse_button()
                return True

        # Ensure obj is a QObject
        if not isinstance(obj, QObject):
            logger.debug(f"Skipping event filter for non-QObject: {type(obj).__name__}")
            return False

        return super().eventFilter(obj, event)

    def _qt_event_to_pygame_key(self, event: QEvent) -> int | None:
        native_key = self._native_scan_to_pygame_key(event)
        if native_key is not None:
            return native_key
        text_method = getattr(event, "text", None)
        text = text_method() if callable(text_method) else ""
        text = text if isinstance(text, str) else ""
        if text and text.isascii() and text.isprintable():
            return pygame.key.key_code(text.lower())
        key_method = getattr(event, "key", None)
        key_value = key_method() if callable(key_method) else 0
        key = key_value if isinstance(key_value, int) else 0
        name = QKeySequence(key).toString()
        if len(name) == 1 and name.isprintable():
            return pygame.key.key_code(name.lower())
        key_names = {
            "Backspace": pygame.K_BACKSPACE,
            "Down": pygame.K_DOWN,
            "Enter": pygame.K_KP_ENTER,
            "Esc": pygame.K_ESCAPE,
            "F5": pygame.K_F5,
            "F10": pygame.K_F10,
            "F11": pygame.K_F11,
            "Left": pygame.K_LEFT,
            "Return": pygame.K_RETURN,
            "Right": pygame.K_RIGHT,
            "Up": pygame.K_UP,
        }
        return key_names.get(name)

    def _native_scan_to_pygame_key(self, event: QEvent) -> int | None:
        scan_method = getattr(event, "nativeScanCode", None)
        scan_value = scan_method() if callable(scan_method) else 0
        scan_code = scan_value if isinstance(scan_value, int) else 0
        scan_keys = {
            16: pygame.K_q,
            18: pygame.K_e,
            24: pygame.K_q,
            26: pygame.K_e,
        }
        return scan_keys.get(scan_code)

    def _qt_modifiers_to_pygame(self, event: QEvent) -> int:
        modifiers_method = getattr(event, "modifiers", None)
        modifiers = modifiers_method() if callable(modifiers_method) else None
        pygame_modifiers = 0
        if isinstance(modifiers, Qt.KeyboardModifier) and modifiers & Qt.KeyboardModifier.ControlModifier:
            pygame_modifiers |= pygame.KMOD_CTRL
        if isinstance(modifiers, Qt.KeyboardModifier) and modifiers & Qt.KeyboardModifier.ShiftModifier:
            pygame_modifiers |= pygame.KMOD_SHIFT
        return pygame_modifiers

    def _handle_back_mouse_button(self) -> None:
        active_win = QApplication.activeWindow()
        focused = self._focused_widget()
        if isinstance(focused, QLineEdit):
            return
        if isinstance(active_win, QDialog):
            active_win.reject()
            return
        self._parent.goBackDetailPage(self._parent.currentDetailPage)

    def _focused_widget(self) -> QWidget | None:
        focused = QApplication.focusWidget()
        if focused is None or not isValid(focused):
            return None
        return focused

    def _activate_focused_widget(self, focused: QWidget | None) -> None:
        if focused is None or not isValid(focused):
            return
        try:
            self._parent.activateFocusedWidget()
        except RuntimeError as e:
            logger.debug("Focused widget was deleted before activation: %s", e)

    def _handle_pygame_mouse_button(self, event: pygame.event.Event) -> None:
        """Handle mouse input received from the pygame event queue."""
        if getattr(event, "button", None) != pygame.BUTTON_X1:
            return
        self._handle_back_mouse_button()

    def _handle_pygame_key_event(self, event: pygame.event.Event) -> None:
        """Handle keyboard input received from the pygame event queue."""
        key = getattr(event, "key", None)
        if key is None:
            return
        if event.type == pygame.KEYDOWN:
            self._handle_pygame_key_press(key, pygame.key.get_mods())
        elif event.type == pygame.KEYUP:
            self._handle_pygame_key_release(key)

    def _handle_pygame_key_press(self, key: int, modifiers: int) -> bool:
        if self._handle_pygame_system_key(key, modifiers):
            return True
        if self._handle_pygame_file_explorer_key(key):
            return True
        if self._handle_pygame_text_key(key):
            return True
        if self._handle_pygame_dialog_key(key):
            return True
        if self._handle_pygame_tab_key(key):
            return True
        if self._handle_pygame_arrow_press(key):
            return True
        return self._handle_pygame_action_key(key, modifiers)

    def _handle_pygame_system_key(self, key: int, modifiers: int) -> bool:
        if key == pygame.K_F5:
            self._parent.refreshGames()
            return True
        if key == pygame.K_q and modifiers & pygame.KMOD_CTRL:
            app = QApplication.instance()
            if app is not None:
                app.quit()
            return True
        if key == pygame.K_F11 and not self._is_gamescope_session:
            self.toggle_fullscreen.emit(not self._is_fullscreen)
            return True
        return False

    def _handle_pygame_file_explorer_key(self, key: int) -> bool:
        file_explorer = self.file_explorer
        if not file_explorer:
            return False
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._activate_file_explorer_focus()
            return True
        if key == pygame.K_BACKSPACE:
            file_explorer.previous_dir()
            return True
        return False

    def _activate_file_explorer_focus(self) -> None:
        file_explorer = self.file_explorer
        if file_explorer is None:
            return
        focused = self._focused_widget()
        if (
            isinstance(focused, AutoSizeButton) and
            hasattr(file_explorer, 'drive_buttons') and
            focused in file_explorer.drive_buttons
        ):
            file_explorer.select_drive()
            return
        if file_explorer.file_list.count() > 0:
            self._activate_file_explorer_item(file_explorer.file_list)
            return
        self._activate_focused_widget(focused)

    def _activate_file_explorer_item(self, focused: QListWidget) -> None:
        file_explorer = self.file_explorer
        if file_explorer is None:
            return
        current_item = focused.currentItem()
        if current_item is None and focused.count() > 0:
            focused.setCurrentRow(0)
            current_item = focused.currentItem()
        if not current_item:
            return
        selected = current_item.text()
        full_path = os.path.join(file_explorer.current_path, selected)
        if os.path.isdir(full_path):
            if selected == "../":
                file_explorer.previous_dir()
            else:
                file_explorer.current_path = os.path.normpath(full_path)
                file_explorer.update_file_list()
        elif not file_explorer.directory_only:
            file_explorer.file_signal.file_selected.emit(os.path.normpath(full_path))
            file_explorer.accept()

    def _handle_pygame_text_key(self, key: int) -> bool:
        focused = self._focused_widget()
        if isinstance(focused, QLineEdit) and key in (pygame.K_LEFT, pygame.K_RIGHT):
            if key == pygame.K_LEFT:
                focused.cursorBackward(False, 1)
            else:
                focused.cursorForward(False, 1)
            return True
        return False

    def _focused_editable_combo(self, focused: QWidget | None) -> bool:
        if isinstance(focused, QComboBox) and focused.isEditable():
            return True
        parent = focused.parentWidget() if focused else None
        return isinstance(parent, QComboBox) and parent.isEditable()

    def _handle_pygame_dialog_key(self, key: int) -> bool:
        active_win = QApplication.activeWindow()
        focused = self._focused_widget()
        if isinstance(active_win, FullscreenDialog):
            return self._handle_pygame_fullscreen_dialog_key(active_win, key)
        if key != pygame.K_ESCAPE:
            return False
        settings_dialog = self.settings_dialog
        if settings_dialog is not None:
            open_combo = self._get_open_settings_combo()
            if open_combo:
                open_combo.hidePopup()
                settings_dialog.advanced_table.setFocus()
                return True
        if isinstance(focused, QLineEdit):
            return False
        if isinstance(active_win, QDialog):
            active_win.reject()
            return True
        return False

    def _handle_pygame_fullscreen_dialog_key(self, active_win: FullscreenDialog, key: int) -> bool:
        if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_BACKSPACE):
            active_win.close()
            return True
        if key == pygame.K_LEFT:
            active_win.show_prev()
            return True
        if key == pygame.K_RIGHT:
            active_win.show_next()
            return True
        return False

    def _handle_pygame_tab_key(self, key: int) -> bool:
        if key not in (pygame.K_LEFT, pygame.K_RIGHT):
            return False
        focused = self._focused_widget()
        active = QApplication.activeWindow()
        if self.file_explorer or isinstance(active, QMessageBox | QDialog):
            return False
        if isinstance(focused, GameCard | QLineEdit | QTableWidget | AutoSizeButton | QCheckBox):
            return False
        return self._switch_visible_tab(-1 if key == pygame.K_LEFT else 1)

    def _focus_tab_from_search(self, current_index: int) -> bool:
        focused = self._focused_widget()
        search_edit = (
            getattr(self._parent, 'searchEdit', None)
            if current_index == 0
            else getattr(self._parent, 'autoInstallSearchLineEdit', None)
        )
        if focused is not search_edit:
            return False
        tab_button = self._parent.tabButtons.get(current_index)
        if tab_button is None or not tab_button.isVisible():
            return False
        tab_button.setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    def _get_library_toolbar_widgets(self) -> list[QWidget]:
        widgets = []
        for attr_name in ("quickLaunchButton", "addGameButton", "refreshButton", "searchEdit"):
            widget = getattr(self._parent, attr_name, None)
            if isinstance(widget, QWidget) and widget.isVisible() and widget.isEnabled():
                widgets.append(widget)
        return widgets

    def _focus_first_library_card(self) -> bool:
        container = getattr(self._parent, "gamesListWidget", None)
        if container is None:
            return False
        for card in container.findChildren(GameCard):
            if card.isVisible() and card.isEnabled():
                card.setFocus(Qt.FocusReason.OtherFocusReason)
                scroll_area = container.parentWidget()
                while scroll_area and not isinstance(scroll_area, QScrollArea):
                    scroll_area = scroll_area.parentWidget()
                if isinstance(scroll_area, QScrollArea):
                    scroll_area.ensureWidgetVisible(card, 50, 50)
                return True
        return False

    def _handle_library_toolbar_navigation(self, code: int, value: int) -> bool:
        if value == 0 or self._parent.stackedWidget.currentIndex() != 0:
            return False
        toolbar_widgets = self._get_library_toolbar_widgets()
        focused = self._focused_widget()
        if focused not in toolbar_widgets:
            return False
        if code == PAD_DPAD_X:
            current_index = toolbar_widgets.index(cast(QWidget, focused))
            next_index = current_index + (1 if value > 0 else -1)
            if 0 <= next_index < len(toolbar_widgets):
                toolbar_widgets[next_index].setFocus(Qt.FocusReason.OtherFocusReason)
            return True
        if code != PAD_DPAD_Y:
            return False
        if value > 0:
            return self._focus_first_library_card()
        tab_button = self._parent.tabButtons.get(0)
        if tab_button is not None and tab_button.isVisible():
            tab_button.setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    def _switch_visible_tab(self, step: int) -> bool:
        idx = self._parent.stackedWidget.currentIndex()
        visible = [i for i, btn in self._parent.tabButtons.items() if btn.isVisible()]
        visible.sort()
        if not visible:
            return False
        try:
            current_pos = visible.index(idx)
        except ValueError:
            current_pos = 0
        new_idx = visible[(current_pos + step) % len(visible)]
        self._parent.switchTab(new_idx)
        self._parent.tabButtons[new_idx].setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    def _handle_pygame_arrow_press(self, key: int) -> bool:
        dpad = {
            pygame.K_UP: (PAD_DPAD_Y, -1),
            pygame.K_DOWN: (PAD_DPAD_Y, 1),
            pygame.K_LEFT: (PAD_DPAD_X, -1),
            pygame.K_RIGHT: (PAD_DPAD_X, 1),
        }.get(key)
        if dpad is None:
            return False
        self.dpad_moved.emit(dpad[0], dpad[1], time.time())
        return True

    def _handle_pygame_action_key(self, key: int, modifiers: int) -> bool:
        focused = self._focused_widget()
        if isinstance(focused, GameCard) and key == pygame.K_F10 and modifiers & pygame.KMOD_SHIFT:
            pos = QPoint(focused.width() // 2, focused.height() // 2)
            focused._show_context_menu(pos)
            return True
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if isinstance(focused, QTableWidget):
                self.handle_table_confirm(focused)
            else:
                self._activate_focused_widget(focused)
            return True
        elif key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            return self._handle_pygame_back_key(focused)
        elif key == pygame.K_e and not isinstance(focused, QLineEdit):
            if self._parent.stackedWidget.currentIndex() == 0:
                self._parent.openAddGameDialog()
                return True
        return False

    def _handle_pygame_back_key(self, focused: QWidget | None) -> bool:
        if isinstance(focused, QLineEdit) or self._focused_editable_combo(focused):
            return False
        self._parent.goBackDetailPage(self._parent.currentDetailPage)
        return True

    def _handle_pygame_key_release(self, key: int) -> bool:
        if key in (pygame.K_UP, pygame.K_DOWN):
            self.dpad_moved.emit(PAD_DPAD_Y, 0, time.time())
            return True
        elif key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.dpad_moved.emit(PAD_DPAD_X, 0, time.time())
            return True
        return False

    def init_gamepad(self) -> None:
        self._init_pygame_backend()
        self.gamepad_hotplug.connect(self._on_gamepad_hotplug)
        self.gamepad_check_timer = QTimer(self)
        self.gamepad_check_timer.setSingleShot(True)
        self.gamepad_check_timer.timeout.connect(self.check_gamepad)
        self.check_gamepad()
        if not self.gamepad_thread or not self.gamepad_thread.is_alive():
            self.gamepad_thread = threading.Thread(target=self.monitor_gamepad, daemon=True)
            self.gamepad_thread.start()
        logger.info("Gamepad support initialized with pygame events")

    def _init_pygame_backend(self) -> None:
        """Initialize pygame subsystems required for joystick polling."""
        if self._pygame_ready:
            return
        pygame.init()
        controller.init()
        self._pygame_ready = True


    def _on_gamepad_hotplug(self, action: str) -> None:
        try:
            if self._gamepad_polling_suspended:
                return
            if action == 'add':
                self.check_gamepad()
            elif action == 'remove':
                had_gamepad = self.gamepad is not None
                if self.gamepad:
                    self.gamepad.close()
                self.gamepad = None
                self._reset_pygame_state()
                self._refresh_gamepad_ui()
                self.check_gamepad()

                if had_gamepad and not self.gamepad and display_config.get_auto_fullscreen_gamepad() and not display_config.get_fullscreen():
                    self.toggle_fullscreen.emit(False)

        except Exception as e:
            logger.error(f"Error in hotplug handler: {e}", exc_info=True)

    def check_gamepad(self) -> None:
        try:
            if self._gamepad_polling_suspended:
                return
            new_gamepad = self.find_gamepad()

            if new_gamepad:
                if self.gamepad and new_gamepad.path == self.gamepad.path:
                    new_gamepad.close()
                    return
                if self.gamepad:
                    self.gamepad.close()
                self.detect_gamepad_axes(new_gamepad)
                logger.info(f"Gamepad connected: {new_gamepad.name} at {new_gamepad.path}")
                self.gamepad = new_gamepad
                self._reset_pygame_state()
                self.gamepad_type = self._get_effective_gamepad_type(new_gamepad)
                self._refresh_gamepad_ui()

                if display_config.get_auto_fullscreen_gamepad() and not display_config.get_fullscreen():
                    self.toggle_fullscreen.emit(True)

            elif self.gamepad:
                logger.info("Gamepad no longer detected")
                self.gamepad.close()
                self.gamepad = None
                self._reset_pygame_state()
                self._refresh_gamepad_ui()

                if display_config.get_auto_fullscreen_gamepad() and not display_config.get_fullscreen():
                    self.toggle_fullscreen.emit(False)

        except Exception as e:
            logger.error(f"Error checking gamepad: {e}", exc_info=True)

    def _reset_pygame_state(self) -> None:
        """Reset cached joystick state when the active device changes."""
        self._button_states.clear()
        self._hat_states.clear()
        self._axis_states.clear()
        self.stick_x_raw = self.center_x
        self.stick_y_raw = self.center_y
        self.scroll_accumulator = 0.0
        self.lt_pressed = False
        self.rt_pressed = False
        self.start_held = False
        self.select_held = False
        self.pending_menu_fullscreen_time = 0.0
        self.guide_held = False
        self.emulation_triggered = False
        self.gamepad_type = self._get_configured_gamepad_type()

    def _get_configured_gamepad_type(self) -> GamepadType:
        """Return manual gamepad type from config or Unknown for auto mode."""
        value = gamepad_config.get_gamepad_type()
        if value == "playstation":
            return GamepadType.PLAYSTATION
        if value == "xbox":
            return GamepadType.XBOX
        return GamepadType.UNKNOWN

    def _get_effective_gamepad_type(self, gamepad: PygameGamepad) -> GamepadType:
        """Use manual gamepad type when configured, otherwise auto-detect."""
        configured_type = self._get_configured_gamepad_type()
        if configured_type != GamepadType.UNKNOWN:
            return configured_type
        return self._detect_gamepad_type(gamepad)

    def apply_gamepad_type_setting(self) -> None:
        """Apply configured gamepad type to the current device."""
        if self.gamepad is None:
            self.gamepad_type = self._get_configured_gamepad_type()
            return
        self.gamepad_type = self._get_effective_gamepad_type(self.gamepad)

    def _detect_gamepad_type(self, gamepad: PygameGamepad) -> GamepadType:
        """Read gamepad type from SDL."""
        sdl3_type = _get_sdl3_gamepad_type(gamepad)
        if sdl3_type is not None:
            return sdl3_type
        return GamepadType.UNKNOWN

    def _refresh_gamepad_ui(self) -> None:
        """Refresh control hints and virtual keyboard after gamepad changes."""
        update_hints = getattr(self._parent, "updateControlHints", None)
        if callable(update_hints):
            update_hints()
        keyboard = getattr(self._parent, "keyboard", None)
        if keyboard and hasattr(keyboard, "update_keyboard"):
            keyboard.update_keyboard()

    def find_gamepad(self) -> PygameGamepad | None:
        """Find the first SDL controller with a stable standardized mapping."""
        try:
            if not self._pygame_ready:
                return None
            controller_count = controller.get_count()
            if controller_count <= 0:
                return None

            for index in range(controller_count):
                if not controller.is_controller(index):
                    continue
                try:
                    game_controller = controller.Controller(index)
                except pygame.error as e:
                    logger.debug("Skipping unavailable controller %s: %s", index, e)
                    continue
                joystick = game_controller.as_joystick()
                instance_id = joystick.get_instance_id()
                gamepad = PygameGamepad(
                    controller=game_controller,
                    name=game_controller.name,
                    path=f"pygame-controller:{instance_id}",
                    instance_id=instance_id,
                )
                return gamepad
        except Exception as e:
            logger.error(f"Error finding gamepad: {e}", exc_info=True)
        return None

    def detect_gamepad_axes(self, device: PygameGamepad) -> None:
        """Use normalized pygame axis ranges for navigation and mouse emulation."""
        self.min_value = -PYGAME_AXIS_SCALE
        self.max_value = PYGAME_AXIS_SCALE
        self.center_x = 0
        self.center_y = 0
        self.deadzone_value = 4000
        self.scroll_axis_code = PAD_AXIS_RIGHT_Y
        self.scroll_center = 0
        self.scroll_min_value = -PYGAME_AXIS_SCALE
        self.scroll_max_value = PYGAME_AXIS_SCALE
        self.scroll_deadzone_value = self.deadzone_value
        self.stick_x_raw = self.center_x
        self.stick_y_raw = self.center_y
        logger.info("Gamepad axes configured for pygame backend: %s", device.name)

    def _read_controller_axis_value(self, gamepad: PygameGamepad, axis_index: int) -> int:
        """Return a stable signed 16-bit axis value from the SDL controller backend."""
        axis_value = gamepad.controller.get_axis(axis_index)
        if isinstance(axis_value, float):
            axis_value = axis_value * PYGAME_AXIS_SCALE
        return int(max(-PYGAME_AXIS_SCALE, min(PYGAME_AXIS_SCALE, axis_value)))

    def _process_pygame_events(self) -> None:
        """Handle SDL input events from the pygame event queue."""
        if not self._pygame_ready or self._gamepad_polling_suspended:
            return
        event_types = (
            pygame.CONTROLLERDEVICEADDED,
            pygame.CONTROLLERDEVICEREMOVED,
            pygame.KEYDOWN,
            pygame.KEYUP,
            pygame.MOUSEBUTTONDOWN,
        )
        for event in pygame.event.get(event_types):
            if event.type == pygame.CONTROLLERDEVICEADDED:
                device_index = getattr(event, "device_index", None)
                if device_index is not None and controller.is_controller(device_index):
                    self.gamepad_hotplug.emit('add')
            elif event.type == pygame.CONTROLLERDEVICEREMOVED:
                if self.gamepad and getattr(event, "instance_id", None) == self.gamepad.instance_id:
                    self.gamepad_hotplug.emit('remove')
            elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                self._handle_pygame_key_event(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_pygame_mouse_button(event)

    def _poll_button_events(self, gamepad: PygameGamepad, current_time: float) -> None:
        """Emit button changes using evdev-compatible codes."""
        for button_index, button_code in SDL_CONTROLLER_BUTTON_TO_ECODE.items():
            value = int(gamepad.controller.get_button(button_index))
            if self._button_states.get(button_index) == value:
                continue
            self._button_states[button_index] = value
            if button_code in BUTTONS['guide']:
                self.guide_held = value == 1
            if button_code in BUTTONS['menu']:
                self.select_held = value == 1
            if button_code == PAD_BUTTON_START:
                self.start_held = value == 1
            emulation_combo = value == 1 and (
                (button_code in BUTTONS['menu'] and self.start_held) or
                (button_code == PAD_BUTTON_START and self.select_held)
            )
            if emulation_combo:
                self.emulation_triggered = not self.emulation_triggered
                self.pending_menu_fullscreen_time = 0.0
            if self._is_mouse_emulation_active() and value == 1:
                if button_code in BUTTONS['confirm']:
                    self.click_left()
                elif button_code in BUTTONS['back']:
                    self.click_right()
            if self._should_skip_regular_events():
                continue
            self.button_event.emit(button_code, value)
            if (
                value == 1 and button_code in BUTTONS['menu'] and
                not emulation_combo and
                not self._is_gamescope_session and not self.in_guide_combination_attempt and
                self._parent.isActiveWindow()
            ):
                self.pending_menu_fullscreen_time = current_time + self.guide_combination_timeout

    def _handle_pending_menu_fullscreen(self, current_time: float) -> None:
        if not self.pending_menu_fullscreen_time:
            return
        if current_time < self.pending_menu_fullscreen_time:
            return
        self.pending_menu_fullscreen_time = 0.0
        if self.start_held or self.in_guide_combination_attempt:
            return
        self.toggle_fullscreen.emit(not self._is_fullscreen)

    def _poll_hat_events(self, gamepad: PygameGamepad, current_time: float) -> None:
        """Read the joystick hat directly for reliable D-pad support."""
        joystick = gamepad.controller.as_joystick()
        if joystick.get_numhats() <= 0:
            return

        hat_value = joystick.get_hat(0)
        previous_value = self._hat_states.get(0, (0, 0))
        self._hat_states[0] = hat_value

        if self._is_mouse_emulation_active():
            if previous_value[0] != hat_value[0]:
                if hat_value[0] < 0:
                    self.move_mouse(-10, 0)
                elif hat_value[0] > 0:
                    self.move_mouse(10, 0)
            if previous_value[1] != hat_value[1]:
                if hat_value[1] > 0:
                    self.move_mouse(0, -10)
                elif hat_value[1] < 0:
                    self.move_mouse(0, 10)

        if self._should_skip_regular_events():
            return

        if previous_value[0] != hat_value[0]:
            self.dpad_moved.emit(PAD_DPAD_X, hat_value[0], current_time)
        if previous_value[1] != hat_value[1]:
            self.dpad_moved.emit(PAD_DPAD_Y, -hat_value[1], current_time)

    def _poll_axis_events(self, gamepad: PygameGamepad, current_time: float) -> None:
        """Emit axis changes using the same evdev-like codes used by the UI."""
        for axis_index, axis_code in SDL_CONTROLLER_AXIS_TO_ECODE.items():
            raw_value = self._read_controller_axis_value(gamepad, axis_index)
            if axis_code is None:
                continue
            previous_value = self._axis_states.get(axis_index)
            if previous_value == raw_value:
                continue
            self._axis_states[axis_index] = raw_value
            if axis_code == PAD_AXIS_LEFT_X:
                self.stick_x_raw = raw_value
            elif axis_code == PAD_AXIS_LEFT_Y:
                self.stick_y_raw = raw_value
            elif axis_code == self.scroll_axis_code:
                self.handle_scroll(raw_value)
            if self._should_skip_regular_events():
                continue
            if axis_code in (PAD_AXIS_LEFT_TRIGGER, PAD_AXIS_RIGHT_TRIGGER):
                self._emit_trigger_event(axis_code, raw_value, current_time)
                continue
            self.dpad_moved.emit(axis_code, raw_value, current_time)

    def _emit_trigger_event(self, axis_code: int, raw_value: int, current_time: float) -> None:
        """Convert pygame trigger axis values into press/release button events."""
        if current_time - self.last_trigger_time < self.trigger_cooldown:
            return
        is_pressed = raw_value > 16384
        if axis_code == PAD_AXIS_LEFT_TRIGGER and is_pressed != self.lt_pressed:
            self.lt_pressed = is_pressed
            self.button_event.emit(axis_code, int(is_pressed))
            self.last_trigger_time = current_time
        elif axis_code == PAD_AXIS_RIGHT_TRIGGER and is_pressed != self.rt_pressed:
            self.rt_pressed = is_pressed
            self.button_event.emit(axis_code, int(is_pressed))
            self.last_trigger_time = current_time

    def _is_mouse_emulation_active(self) -> bool:
        """Return True when the gamepad currently drives mouse emulation."""
        return self.mouse_emulation_enabled and self.emulation_active and self.emulation_triggered

    def _should_skip_regular_events(self) -> bool:
        """Skip regular UI events while mouse emulation owns the controller."""
        return self._is_mouse_emulation_active() and QApplication.activeWindow() is not None

    def monitor_gamepad(self) -> None:
        try:
            while self.running:
                current_time = time.time()
                if self._gamepad_polling_suspended:
                    time.sleep(0.1)
                    continue
                active_gamepad = self.gamepad
                if not active_gamepad:
                    time.sleep(0.1)
                    continue
                try:
                    self._poll_button_events(active_gamepad, current_time)
                    self._handle_pending_menu_fullscreen(current_time)
                    self._poll_hat_events(active_gamepad, current_time)
                    self._poll_axis_events(active_gamepad, current_time)
                    if (
                        current_time - self.last_update >= self.update_interval and
                        self.mouse_emulation_enabled and self.emulation_active and self.emulation_triggered
                    ):
                        self.update_mouse_position()
                        self.last_update = current_time
                    time.sleep(0.01)
                except pygame.error as e:
                    logger.info("Gamepad disconnected during monitoring: %s", e)
                    self.gamepad_hotplug.emit('remove')
                    time.sleep(0.1)
                except Exception as ex:
                    logger.error(f"Unexpected error in gamepad monitoring: {ex}")
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in gamepad monitoring thread: {e}", exc_info=True)
        finally:
            if self.gamepad:
                try:
                    self.gamepad.close()
                except Exception as e:
                    logger.debug("Failed to close gamepad: %s", e)
            self.gamepad = None
            self._reset_pygame_state()

    def cleanup(self) -> None:
        """
        Proper shutdown of gamepad and udev monitor.
        """
        try:
            # Mouse emulation cleanup
            self.disable_mouse_emulation()

            # Stop focus check timer
            self.focus_check_timer.stop()

            # Flag to stop udev monitor loop
            self.running = False

            # Stop all timers
            if hasattr(self, 'gamepad_check_timer'):
                self.gamepad_check_timer.stop()
            if hasattr(self, 'pygame_event_timer'):
                self.pygame_event_timer.stop()
            self.dpad_timer.stop()
            self.nav_timer.stop()

            if self.gamepad_thread:
                self.gamepad_thread.join(timeout=2.0)

            if self.gamepad:
                self.gamepad.close()

            self.gamepad = None
            self._reset_pygame_state()
            self.gamepad_type = self._get_configured_gamepad_type()
            if self._pygame_ready:
                controller.quit()
                pygame.quit()
                self._pygame_ready = False

            logger.info("Gamepad cleanup completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)

    def _handle_common_ui_elements(self, button_code):
        """
        Common handler for common UI elements like QMessageBox, QMenu, etc.
        Returns True if the event was handled, False otherwise.
        """
        # Check for popup widgets first
        popup = QApplication.activePopupWidget()
        if popup:
            if isinstance(popup, QMessageBox):
                self._handle_qmessagebox_button(popup, button_code)
                return True
            elif isinstance(popup, QMenu):
                if button_code in BUTTONS['confirm']:
                    if popup.activeAction():
                        popup.activeAction().trigger()
                    popup.close()
                elif button_code in BUTTONS['back']:
                    popup.close()
                return True

        # Check for top-level QMessageBox specifically
        active = QApplication.activeWindow()
        if isinstance(active, QMessageBox):
            self._handle_qmessagebox_button(active, button_code)
            return True

        # Check for top-level message boxes (additional check)
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible() and widget != active:
                self._handle_qmessagebox_button(widget, button_code)
                return True

        return False  # Not handled by common handler

    def _handle_qmessagebox_button(self, msg_box, button_code):
        """
        Unified handler for QMessageBox across all modes.
        For single button dialogs, A button accepts the dialog.
        For multiple button dialogs, navigate between buttons and allow selection.
        """
        if button_code in BUTTONS['confirm']:
            # Check if there's a focused button in the message box
            focused_widget = msg_box.focusWidget()
            if focused_widget:
                # If a specific button is focused, click/activate it
                focused_widget.click()
            else:
                # If no button is focused, accept with default behavior
                msg_box.accept()
        elif button_code in BUTTONS['back']:
            # For back button, reject the dialog (typically cancels or selects cancel button)
            msg_box.reject()
