import time
import threading
import os
import math
from typing import Protocol, cast, Any
from evdev import InputDevice, InputEvent, UInput, ecodes, list_devices, ff
from enum import Enum
from pyudev import Context, Monitor, Device, Devices
from PySide6.QtWidgets import QWidget, QStackedWidget, QApplication, QScrollArea, QLineEdit, QDialog, QMenu, QComboBox, QListView, QMessageBox, QListWidget, QTableWidget, QAbstractItemView, QSlider, QCheckBox
from PySide6.QtCore import Qt, QObject, QEvent, QPoint, Signal, Slot, QTimer
from PySide6.QtGui import QKeyEvent, QMouseEvent
from portprotonqt.logger import get_logger
from portprotonqt.image_utils import FullscreenDialog
from portprotonqt.custom_widgets import NavLabel, AutoSizeButton
from portprotonqt.game_card import GameCard
from portprotonqt.config_utils import read_fullscreen_config, read_window_geometry, save_window_geometry, read_auto_fullscreen_gamepad, read_rumble_config, read_gamepad_type
from portprotonqt.dialogs import AddGameDialog
from portprotonqt.virtual_keyboard import VirtualKeyboard
import select

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
    def openSystemOverlay(self) -> None:
        ...
    def on_slider_released(self) -> None:
        ...
    def on_auto_slider_released(self) -> None:
        ...
    def isActiveWindow(self) -> bool:
        ...
    def refreshGames(self) -> None:
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

# Mapping of actions to evdev button codes, includes Xbox, PlayStation and Nintendo Switch controllers
# https://github.com/torvalds/linux/blob/master/drivers/hid/hid-playstation.c
# https://github.com/torvalds/linux/blob/master/drivers/input/joystick/xpad.c
# https://github.com/torvalds/linux/blob/master/drivers/hid/hid-nintendo
BUTTONS = {
    'confirm':       {ecodes.BTN_SOUTH},           # A (Xbox) / Cross (PS) / B (Switch)
    'back':          {ecodes.BTN_EAST},            # B (Xbox) / Circle (PS) / A (Switch)
    'add_game':      {ecodes.BTN_NORTH},           # X (Xbox) / Triangle (PS) / Y (Switch)
    'prev_dir':      {ecodes.BTN_WEST},            # Y (Xbox) / Square (PS) / X (Switch)
    'prev_tab':      {ecodes.BTN_TL, ecodes.BTN_Z},              # LB (Xbox) / L1 (PS) / L (Switch) and BTN_Z for hat switch
    'next_tab':      {ecodes.BTN_TR, ecodes.BTN_C},              # RB (Xbox) / R1 (PS) / R (Switch) and BTN_C for hat switch
    'context_menu':  {ecodes.BTN_START},           # Start (Xbox) / Options (PS) / + (Switch)
    'menu':          {ecodes.BTN_SELECT},          # Select (Xbox) / Share (PS) / - (Switch)
    'guide':         {ecodes.BTN_MODE},            # Xbox Button / PS Button / Home (Switch)
    'increase_size': {ecodes.ABS_RZ, ecodes.BTN_TR2},              # RT (Xbox) / R2 (PS) / ZR (Switch) and BTN_TR2 for Bluetooth
    'decrease_size': {ecodes.ABS_Z, ecodes.BTN_TL2},               # LT (Xbox) / L2 (PS) / ZL (Switch) and BTN_TL2 for Bluetooth
}

class GamepadType(Enum):
    XBOX = "Xbox"
    PLAYSTATION = "PlayStation"
    UNKNOWN = "Unknown"

class InputManager(QObject):
    """
    Manages input from gamepads and keyboards for navigating the application interface.
    Supports gamepad hotplugging, button and axis events, and keyboard event filtering
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
        type_str = read_gamepad_type()
        if type_str == "playstation":
            self.gamepad_type = GamepadType.PLAYSTATION
        elif type_str == "xbox":
            self.gamepad_type = GamepadType.XBOX
        else:
            self.gamepad_type = GamepadType.UNKNOWN
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
        self.gamepad: InputDevice | None = None
        self.gamepad_thread: threading.Thread | None = None
        self.running = True
        self._is_fullscreen = read_fullscreen_config()
        self.rumble_effect_id: int | None = None  # Store the rumble effect ID
        self.lt_pressed = False
        self.rt_pressed = False
        self.last_trigger_time = 0.0
        self.trigger_cooldown = 0.2

        # Mouse emulation attributes
        self.mouse_emulation_enabled = True
        self.ui = None
        self.stick_x_raw = 0
        self.stick_y_raw = 0

        # Параметры осей (будут заполнены из ядра)
        self.center_x = 127      # центр X оси
        self.center_y = 127      # центр Y оси
        self.min_value = 0       # минимум осей
        self.max_value = 255     # максимум осей
        self.deadzone_value = 15 # мёртвая зона из ядра (flat параметр)

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
        self.guide_held = False
        # Variables for key combination handling
        self.guide_pressed_time = 0
        self.select_pressed_time = 0
        self.guide_timer = QTimer(self)
        self.guide_timer.setSingleShot(True)
        self.guide_timer.timeout.connect(self._handle_guide_timeout)
        self.guide_combination_timeout = 0.3  # 300ms timeout for combination
        self.in_guide_combination_attempt = False  # Flag to track if we're in a guide+select combination attempt

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
        self.initial_nav_delay = 0.1  # Начальная задержка перед первым повторением (сек)
        self.repeat_nav_delay = 0.05  # Интервал между повторениями (сек)
        self.stick_activated = False
        self.stick_value = 0  # Текущее значение стика (для плавности)
        self.dead_zone = 8000  # Мертвая зона стика

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

        # Install keyboard event filter
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        # Initialize evdev + hotplug
        self.init_gamepad()

    def _async_enable_mouse_emulation(self):
        """Asynchronously enable mouse emulation to avoid blocking startup."""
        self.enable_mouse_emulation()

    def _update_emulation_flag(self):
        """Update emulation_active flag based on Qt app focus (main thread only)."""
        active = QApplication.activeWindow()
        self.emulation_active = (active is None)  # True for external windows (e.g., winefile)
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
        if code == ecodes.ABS_HAT0X and value != 0:
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
        elif code == ecodes.ABS_HAT0Y and value != 0:
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
        """Настройка обработки геймпада для FileExplorer"""
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
        """Восстановление оригинальных обработчиков (дефолт возвращаем)"""
        try:
            if self.file_explorer:
                # Additional cleanup for file explorer
                self.nav_timer.stop()
                self._restore_original_handlers('file_explorer')
                logger.debug("Gamepad handling successfully restored")
        except Exception as e:
            logger.error(f"Error restoring gamepad handlers: {e}")

    def handle_file_explorer_button(self, button_code, value):
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
                    self.original_button_handler(button_code)

        except Exception as e:
            logger.error(f"Error in FileExplorer button handler: {e}")

    def handle_file_explorer_dpad(self, code, value, current_time):
        try:
            # 1. Handle Popups (Menus)
            popup = QApplication.activePopupWidget()
            if isinstance(popup, QMenu):
                if code == ecodes.ABS_HAT0Y and value != 0:
                    actions = popup.actions()
                    if not actions:
                        return
                    current_action = popup.activeAction()
                    current_idx = actions.index(current_action) if current_action in actions else -1

                    if value > 0:  # Down
                        next_idx = (current_idx + 1) % len(actions) if current_idx != -1 else 0
                    else:  # Up
                        next_idx = (current_idx - 1) % len(actions) if current_idx != -1 else len(actions) - 1

                    popup.setActiveAction(actions[next_idx])
                return

            # 2. Validate State
            if not self.file_explorer or not hasattr(self.file_explorer, 'file_list') or not self.file_explorer.file_list:
                return

            focused_widget = QApplication.focusWidget()

            # 3. Handle Drive Buttons Navigation (Horizontal)
            if code in (ecodes.ABS_HAT0X, ecodes.ABS_X) and \
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
            elif code in (ecodes.ABS_HAT0Y, ecodes.ABS_Y):
                # Move from buttons to list
                if isinstance(focused_widget, AutoSizeButton) and focused_widget in self.file_explorer.drive_buttons:
                    if value > 0 and self.file_explorer.file_list.count() > 0:
                        self.file_explorer.file_list.setFocus()
                        self.file_explorer.file_list.setCurrentRow(0)
                        self.file_explorer.file_list.scrollToItem(self.file_explorer.file_list.currentItem())
                    return

                # D-pad: Fixed speed
                if code == ecodes.ABS_HAT0Y:
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
                elif code == ecodes.ABS_Y:
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

            if code == ecodes.ABS_HAT0Y:  # Up/Down
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

    # TABLE NAVIGATION METHODS
    def handle_table_navigation(self, table: QTableWidget, code: int, value: int):
        """
        Обрабатывает навигацию по таблице

        Args:
            table: QTableWidget для обработки навигации
            code: Код события (обычно ABS_HAT0X или ABS_HAT0Y)
            value: Значение события (направление)
        """
        row_count = table.rowCount()
        if row_count <= 0:
            return
        current_row = table.currentRow()
        if current_row < 0:
            current_row = 0
            table.setCurrentCell(0, 0)

        if code == ecodes.ABS_HAT0Y and value != 0:
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
        elif code == ecodes.ABS_HAT0X and value != 0:
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
        Обрабатывает подтверждение (например, нажатие A) для таблицы

        Args:
            table: QTableWidget для обработки подтверждения
        """
        current_row = table.currentRow()
        current_col = table.currentColumn()
        if current_row >= 0 and current_col >= 0:
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
        Устанавливает навигацию для виджета

        Args:
            widget: QWidget для настройки навигации
            navigation_type: Тип навигации ('table', 'list', 'combo', 'default')
            **kwargs: Дополнительные параметры для навигации
        """
        widget.installEventFilter(self)
        # Use direct assignment for custom navigation properties, with type ignore for pyright
        widget._navigation_type = navigation_type  # type: ignore
        for key, value in kwargs.items():
            setattr(widget, f'_{key}', value)

    def handle_widget_navigation(self, widget: QWidget, code: int, value: int):
        """
        Обрабатывает навигацию по виджету

        Args:
            widget: QWidget для обработки навигации
            code: Код события (обычно ABS_HAT0X или ABS_HAT0Y)
            value: Значение события (направление)
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
        Обрабатывает навигацию по списку

        Args:
            list_widget: QListWidget для обработки навигации
            code: Код события (обычно ABS_HAT0X или ABS_HAT0Y)
            value: Значение события (направление)
        """
        if code == ecodes.ABS_HAT0Y and value != 0:
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
        Обрабатывает навигацию по комбинированному виджету

        Args:
            combo_widget: QComboBox для обработки навигации
            code: Код события (обычно ABS_HAT0X или ABS_HAT0Y)
            value: Значение события (направление)
        """
        if code == ecodes.ABS_HAT0Y and value != 0:
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

            if code == ecodes.ABS_HAT0Y:  # Up/Down
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
            if self._handle_common_ui_elements(button_code):
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

                # 3. Advanced Tab Combo Box Logic
                table = self._get_current_settings_table()
                open_combo = None
                if table and table == self.settings_dialog.advanced_table:
                    for r in range(table.rowCount()):
                        w = table.cellWidget(r, 1)
                        if isinstance(w, QComboBox) and w.view().isVisible():
                            open_combo = w
                            break

                # B Button - Close combo or dialog
                if button_code in BUTTONS['back']:
                    if open_combo:
                        open_combo.hidePopup()
                        if table:
                            table.setFocus()
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
                        if table:
                            table.setFocus()
                        return

                    # Standard interaction
                    focused = QApplication.focusWidget()
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

                # 4. Global Shortcuts
                if button_code in BUTTONS['add_game']:  # X: Apply
                    self.settings_dialog.apply_changes()

                elif button_code in BUTTONS['prev_dir']:  # Y: Search + Keyboard
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
                if code in (ecodes.ABS_X, ecodes.ABS_Y):  # Sticks
                    if abs(value) < self.dead_zone:
                        self.current_dpad_code = None
                        self.current_dpad_value = 0
                        self.dpad_timer.stop()
                        return
                    normalized_value = 1 if value > self.dead_zone else -1
                else:  # D-pad
                    normalized_value = value

                if normalized_value != 0:
                    if code in (ecodes.ABS_HAT0X, ecodes.ABS_X):
                        if normalized_value > 0:
                            kb.move_focus_right()
                        else:
                            kb.move_focus_left()
                    elif code in (ecodes.ABS_HAT0Y, ecodes.ABS_Y):
                        if normalized_value > 0:
                            kb.move_focus_down()
                        else:
                            kb.move_focus_up()
                return

            # 2. Combo Box Navigation (within Advanced Table)
            table = self._get_current_settings_table()
            if not table or table.rowCount() == 0:
                return

            if self.settings_dialog and table == self.settings_dialog.advanced_table and table.currentRow() >= 0:
                cell_widget = table.cellWidget(table.currentRow(), 1)
                if isinstance(cell_widget, QComboBox) and cell_widget.view().isVisible():
                    if code == ecodes.ABS_HAT0Y and value != 0:
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

            if code == ecodes.ABS_HAT0Y:  # Up/Down
                step = -1 if value < 0 else 1
                new_row = current_row + step

                while 0 <= new_row < table.rowCount() and table.isRowHidden(new_row):
                    new_row += step

                if 0 <= new_row < table.rowCount():
                    focus_column = 1 if (self.settings_dialog and table == self.settings_dialog.advanced_table) else 0
                    table.setCurrentCell(new_row, focus_column)
                    table.setFocus(Qt.FocusReason.OtherFocusReason)

            elif code == ecodes.ABS_HAT0X:  # Left/Right
                current_col = table.currentColumn()
                if value < 0:  # Left
                    if current_col > 0:
                        table.setCurrentCell(current_row, max(0, current_col - 1))
                else:  # Right
                    if current_col < table.columnCount() - 1:
                        table.setCurrentCell(current_row, min(table.columnCount() - 1, current_col + 1))

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

    def _focus_first_row_in_current_settings_table(self):
        table = self._get_current_settings_table()
        if table and table.rowCount() > 0:
            col = 1 if (self.settings_dialog and table == self.settings_dialog.advanced_table) else 0
            table.setCurrentCell(0, col)
            table.setFocus(Qt.FocusReason.OtherFocusReason)

    def handle_navigation_repeat(self):
        """Плавное повторение движения с переменной скоростью для FileExplorer"""
        try:
            if not self.file_explorer or not hasattr(self.file_explorer, 'file_list') or not self.file_explorer.file_list:
                return

            if self.current_direction != 0:
                now = time.time()
                # Динамический интервал в зависимости от stick_value
                dynamic_delay = self.repeat_nav_delay / self.stick_value
                if now - self.last_nav_time >= dynamic_delay:
                    self.file_explorer.move_selection(self.current_direction)
                    self.last_nav_time = now
        except Exception as e:
            logger.error(f"Error in navigation repeat: {e}")

    def enable_mouse_emulation(self):
        """Enable mouse emulation mode (creates virtual mouse device)."""
        if self.mouse_emulation_enabled and self.ui is not None:
            logger.debug("EMUL: Mouse emulation already enabled, skipping")
            return

        try:
            logger.info("EMUL: Attempting to create UInput virtual mouse...")
            if not os.path.exists('/dev/uinput'):
                logger.error("EMUL: /dev/uinput does not exist")
                self.mouse_emulation_enabled = False
                return

            if not os.access('/dev/uinput', os.W_OK):
                logger.error("EMUL: No write access to /dev/uinput")
                self.mouse_emulation_enabled = False
                return

            self.ui = UInput({
                ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT],
                ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL],
            }, name="Virtual DPad Mouse")

            self.mouse_emulation_enabled = True
            logger.info("EMUL: Virtual mouse created successfully")

        except PermissionError as e:
            logger.error("EMUL: Permission denied for /dev/uinput: %s", e)
            self.mouse_emulation_enabled = False
        except Exception as ex:
            logger.error(f"EMUL: Error creating virtual mouse: {ex}", exc_info=True)
            self.mouse_emulation_enabled = False

    def disable_mouse_emulation(self):
        """Disable mouse emulation mode (closes virtual mouse device)."""
        logger.info("EMUL: Disabling mouse emulation...")
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
        """Обработка прокрутки с правого стика Y"""
        if not self.mouse_emulation_enabled or not self.emulation_active or not self.ui:
            return

        # Нормализуем от центра
        centered_value = raw_value - self.center_y

        if abs(centered_value) < self.deadzone_value:
            self.scroll_accumulator = 0.0
            return

        # Нормализуем значение (-1.0 до 1.0)
        range_val = (self.max_value - self.min_value) / 2
        normalized = centered_value / range_val

        # Накапливаем прокрутку
        self.scroll_accumulator += normalized * self.scroll_sensitivity

        # Отправляем события прокрутки
        while abs(self.scroll_accumulator) >= self.scroll_threshold:
            scroll_step = 1 if self.scroll_accumulator > 0 else -1
            self.scroll_wheel(-scroll_step)
            self.scroll_accumulator -= scroll_step * self.scroll_threshold

    def update_mouse_position(self):
        """Постоянное обновление позиции мыши на основе состояния стика"""
        if not self.ui or not self.emulation_active:
            return

        # Центрируем значения
        x = self.stick_x_raw - self.center_x
        y = self.stick_y_raw - self.center_y

        # Применяем мёртвую зону из ядра
        magnitude = math.sqrt(x * x + y * y)

        if magnitude < self.deadzone_value:
            return

        if magnitude > 0:
            norm_x = x / magnitude
            norm_y = y / magnitude
        else:
            return

        # Нормализуем по диапазону оси
        max_range = (self.max_value - self.min_value) / 2
        adjusted_magnitude = (magnitude - self.deadzone_value) / (max_range - self.deadzone_value)
        adjusted_magnitude = max(0.0, min(1.0, adjusted_magnitude))

        # Нелинейная кривая
        adjusted_magnitude = math.pow(adjusted_magnitude, 1.5)

        speed = adjusted_magnitude * self.sensitivity
        dx = int(norm_x * speed)
        dy = int(norm_y * speed)

        if dx != 0 or dy != 0:
            self.move_mouse(dx, dy)

    def move_mouse(self, dx, dy):
        """Сдвиг системного курсора"""
        if self.ui:
            self.ui.write(ecodes.EV_REL, ecodes.REL_X, dx)
            self.ui.write(ecodes.EV_REL, ecodes.REL_Y, dy)
            self.ui.syn()

    def scroll_wheel(self, steps):
        """Прокрутка колеса мыши"""
        if self.ui:
            self.ui.write(ecodes.EV_REL, ecodes.REL_WHEEL, steps)
            self.ui.syn()

    def click_left(self):
        """Клик левой кнопкой мыши"""
        if self.ui:
            self.ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
            self.ui.syn()
            self.ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
            self.ui.syn()

    def click_right(self):
        """Клик правой кнопкой мыши"""
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
                    save_window_geometry(window.width(), window.height())
                window.showFullScreen()
                self._is_fullscreen = True
            elif not enable and self._is_fullscreen:
                window.showNormal()
                width, height = read_window_geometry()
                if width > 0 and height > 0:
                    window.resize(width, height)
                self._is_fullscreen = False
                save_window_geometry(width, height)
        except Exception as e:
            logger.error(f"Error in handle_fullscreen_slot: {e}", exc_info=True)

    def disable_gamepad_handling(self) -> None:
        """Отключает обработку событий геймпада."""
        self._gamepad_handling_enabled = False
        self.stop_rumble()
        self.dpad_timer.stop()
        self.nav_timer.stop()

    def enable_gamepad_handling(self) -> None:
        """Включает обработку событий геймпада."""
        self._gamepad_handling_enabled = True

    def trigger_rumble(self, duration_ms: int = 200, strong_magnitude: int = 0x8000, weak_magnitude: int = 0x8000) -> None:
        """Trigger a rumble effect on the gamepad if supported."""
        if not read_rumble_config():
            return
        if not self.gamepad:
            return
        try:
            # Check if the gamepad supports force feedback
            caps = self.gamepad.capabilities()
            if ecodes.EV_FF not in caps or ecodes.FF_RUMBLE not in caps.get(ecodes.EV_FF, []):
                logger.debug("Gamepad does not support force feedback or rumble")
                return

            # Create a rumble effect
            rumble = ff.Rumble(strong_magnitude=strong_magnitude, weak_magnitude=weak_magnitude)
            effect = ff.Effect(
                id=-1,  # Let evdev assign an ID
                type=ecodes.FF_RUMBLE,
                direction=0,  # Direction (not used for rumble)
                replay=ff.Replay(length=duration_ms, delay=0),
                u=ff.EffectType(ff_rumble_effect=rumble)
            )

            # Upload the effect
            self.rumble_effect_id = self.gamepad.upload_effect(effect)
            # Play the effect
            event = InputEvent(0, 0, ecodes.EV_FF, self.rumble_effect_id, 1)
            self.gamepad.write_event(event)
            # Schedule effect erasure after duration
            QTimer.singleShot(duration_ms, self.stop_rumble)
        except Exception as e:
            logger.error(f"Error triggering rumble: {e}", exc_info=True)

    def stop_rumble(self) -> None:
        """Stop the rumble effect and clean up."""
        if self.gamepad and self.rumble_effect_id is not None:
            try:
                self.gamepad.erase_effect(self.rumble_effect_id)
                self.rumble_effect_id = None
            except Exception as e:
                logger.error(f"Error stopping rumble: {e}", exc_info=True)

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
                logger.debug("Guide button pressed alone, opening system overlay")
                active = QApplication.activeWindow()
                if not isinstance(active, QDialog):
                    self._parent.openSystemOverlay()

        self.guide_held = False
        self.in_guide_combination_attempt = False
        self.guide_pressed_time = 0
        self.select_pressed_time = 0


    @Slot(int, int)
    def handle_button_slot(self, button_code: int, value: int) -> None:
        # Handle common UI elements like QMessageBox, QMenu, etc. FIRST
        # This ensures that any active dialogs are handled before main window logic
        if self._handle_common_ui_elements(button_code):
            return

        active_window = QApplication.activeWindow()

        # Обработка виртуальной клавиатуры в AddGameDialog (handle both press and release)
        if isinstance(active_window, AddGameDialog):
            focused = QApplication.focusWidget()
            if button_code in BUTTONS['confirm'] and value == 1 and isinstance(focused, QLineEdit):
                # Показываем клавиатуру при нажатии A на поле ввода (only on press)
                active_window.show_keyboard_for_widget(focused)
                return

            # Если клавиатура видима, обрабатываем её кнопки (including release)
            if hasattr(active_window, 'keyboard') and active_window.keyboard.isVisible():
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
                keyboard = getattr(self._parent, 'keyboard', None)
                if keyboard:
                    keyboard.show_for_widget(focused)
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
            if isinstance(focused, GameCard):
                if button_code in BUTTONS['context_menu']:
                    pos = QPoint(focused.width() // 2, focused.height() // 2)
                    menu = focused._show_context_menu(pos)
                    if menu:
                        menu.setFocus(Qt.FocusReason.OtherFocusReason)
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
                idx = (self._parent.stackedWidget.currentIndex() - 1) % len(self._parent.tabButtons)
                self._parent.switchTab(idx)
                self._parent.tabButtons[idx].setFocus(Qt.FocusReason.OtherFocusReason)
            elif button_code in BUTTONS['next_tab']:
                idx = (self._parent.stackedWidget.currentIndex() + 1) % len(self._parent.tabButtons)
                self._parent.switchTab(idx)
                self._parent.tabButtons[idx].setFocus(Qt.FocusReason.OtherFocusReason)
            elif button_code in BUTTONS['increase_size']:
                current_tab = self._parent.stackedWidget.currentIndex()
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
            elif button_code in BUTTONS['decrease_size']:
                current_tab = self._parent.stackedWidget.currentIndex()
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

    @Slot(int, int, float)
    def handle_dpad_slot(self, code: int, value: int, current_time: float) -> None:
        keyboard = None
        active_window = QApplication.activeWindow()

        # Проверяем клавиатуру в активном окне (AddGameDialog или главном окне)
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
        self.current_dpad_code = code
        self.current_dpad_value = value
        if not self.axis_moving:
            self.axis_moving = True
            self.last_move_time = current_time
            self.current_axis_delay = self.initial_axis_move_delay
            self.dpad_timer.start(int(self.repeat_axis_move_delay * 1000))

        if keyboard and keyboard.isVisible():
            # Обработка горизонтального перемещения (LEFT/RIGHT)
            if code in (ecodes.ABS_HAT0X, ecodes.ABS_X):
                normalized_value = 0
                if code == ecodes.ABS_X:  # Левый стик
                    # Применяем мертвую зону
                    if abs(value) < self.dead_zone:
                        self.current_dpad_code = None
                        self.current_dpad_value = 0
                        self.axis_moving = False
                        self.dpad_timer.stop()
                        return
                    normalized_value = 1 if value > self.dead_zone else -1
                else:  # D-pad
                    normalized_value = value  # D-pad уже дает -1, 0, 1

                if normalized_value != 0:
                    if normalized_value > 0:  # Вправо
                        keyboard.move_focus_right()
                    elif normalized_value < 0:  # Влево
                        keyboard.move_focus_left()
                return

            # Обработка вертикального перемещения (UP/DOWN)
            elif code in (ecodes.ABS_HAT0Y, ecodes.ABS_Y):
                normalized_value = 0
                if code == ecodes.ABS_Y:  # Левый стик
                    # Применяем мертвую зону
                    if abs(value) < self.dead_zone:
                        self.current_dpad_code = None
                        self.current_dpad_value = 0
                        self.axis_moving = False
                        self.dpad_timer.stop()
                        return
                    normalized_value = 1 if value > self.dead_zone else -1
                else:  # D-pad
                    normalized_value = value  # D-pad уже дает -1, 0, 1

                if normalized_value != 0:
                    if normalized_value > 0:  # Вниз
                        keyboard.move_focus_down()
                    elif normalized_value < 0:  # Вверх
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
                if code == ecodes.ABS_HAT0X and value != 0:  # Horizontal navigation
                    if value > 0:  # Right
                        active.focusNextChild()
                    elif value < 0:  # Left
                        active.focusPreviousChild()
                elif code == ecodes.ABS_HAT0Y and value != 0:  # Vertical navigation
                    if value > 0:  # Down
                        active.focusNextChild()
                    elif value < 0:  # Up
                        active.focusPreviousChild()
                return
            # Handle SystemOverlay, AddGameDialog, or other QDialog navigation with D-pad
            elif isinstance(active, QDialog) and code == ecodes.ABS_HAT0X and value != 0:
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
            elif isinstance(active, QDialog) and code == ecodes.ABS_HAT0Y and value != 0 and not isinstance(focused, QTableWidget):  # Keep up/down for other dialogs
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
                if code == ecodes.ABS_HAT0Y and value != 0:
                    actions = popup.actions()
                    if actions:
                        current_idx = actions.index(popup.activeAction()) if popup.activeAction() in actions else 0
                        if value < 0:  # Up
                            next_idx = (current_idx - 1) % len(actions)
                            popup.setActiveAction(actions[next_idx])
                        elif value > 0:  # Down
                            next_idx = (current_idx + 1) % len(actions)
                            popup.setActiveAction(actions[next_idx])
                    return
                return

            # Handle QListView navigation with D-pad
            if isinstance(focused, QListView) and code == ecodes.ABS_HAT0Y and value != 0:
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
            if isinstance(active, FullscreenDialog) and code == ecodes.ABS_HAT0X:
                if value < 0:
                    active.show_prev()
                elif value > 0:
                    active.show_next()
                return


            # Table navigation using generalized methods
            if isinstance(focused, QTableWidget):
                self.handle_table_navigation(focused, code, value)
                return

            # Search focus logic for tabs 0 and 1
            if code == ecodes.ABS_HAT0Y and value < 0:
                focused = QApplication.focusWidget()
                current_index = self._parent.stackedWidget.currentIndex()
                if current_index in (0, 1) and isinstance(focused, GameCard):
                    if current_index == 0:
                        container = self._parent.gamesListWidget
                        search_edit = getattr(self._parent, 'searchEdit', None)
                    else:
                        container = self._parent.autoInstallContainer
                        search_edit = getattr(self._parent, 'autoInstallSearchLineEdit', None)
                    if container and search_edit:
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
                                search_edit.setFocus()
                                return

            # Game cards navigation for tabs 0 and 1
            if code in (ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y):
                current_index = self._parent.stackedWidget.currentIndex()
                if current_index in (0, 1):
                    container = self._parent.gamesListWidget if current_index == 0 else self._parent.autoInstallContainer
                    if container is None:
                        return
                    self._navigate_game_cards(container, current_index, code, value)
                    return

            # Button navigation on detail pages (horizontal layout)
            if code in (ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y):
                focused = QApplication.focusWidget()
                page = self._parent.stackedWidget.currentWidget()

                # Check if we're on a detail page and focused widget is a button
                if isinstance(focused, AutoSizeButton):
                    # Find all buttons in the same horizontal layout (same parent, same Y position)
                    parent_widget = focused.parentWidget()
                    if parent_widget:
                        # Find all AutoSizeButtons in the parent that are horizontally aligned
                        buttons = parent_widget.findChildren(AutoSizeButton)
                        # Filter buttons that are approximately on the same horizontal level (similar Y positions)
                        y_tolerance = 20  # pixels tolerance for vertical alignment
                        current_y = focused.geometry().y() + focused.geometry().height() // 2
                        aligned_buttons = []
                        for btn in buttons:
                            btn_center_y = btn.geometry().y() + btn.geometry().height() // 2
                            if abs(btn_center_y - current_y) <= y_tolerance:
                                aligned_buttons.append(btn)

                        # Sort buttons by x position for left-to-right navigation
                        if len(aligned_buttons) > 1:
                            aligned_buttons.sort(key=lambda b: b.geometry().x() + b.geometry().width() // 2)

                            # Find current button index
                            try:
                                current_index = aligned_buttons.index(focused)
                            except ValueError:
                                current_index = -1

                            if current_index >= 0:
                                if code == ecodes.ABS_HAT0X:  # Horizontal navigation (left/right)
                                    if value < 0 and current_index > 0:  # Left
                                        aligned_buttons[current_index - 1].setFocus(Qt.FocusReason.OtherFocusReason)
                                        return
                                    elif value > 0 and current_index < len(aligned_buttons) - 1:  # Right
                                        aligned_buttons[current_index + 1].setFocus(Qt.FocusReason.OtherFocusReason)
                                        return
                                elif code == ecodes.ABS_HAT0Y:  # Vertical navigation (up/down)
                                    # For buttons on the same row, up/down should go to other controls
                                    # So we'll continue to the next section of code for general navigation
                                    pass

            # Vertical navigation in other tabs
            if code == ecodes.ABS_HAT0Y and value != 0:
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
        # Проверяем клавиатуру в активном окне
        active_window = QApplication.activeWindow()
        keyboard = None

        # Сначала проверяем AddGameDialog
        if isinstance(active_window, AddGameDialog):
            keyboard = getattr(active_window, 'keyboard', None)
        else:
            # Если это не AddGameDialog, проверяем клавиатуру в главном окне
            keyboard = getattr(self._parent, 'keyboard', None)

        if not keyboard or not isinstance(keyboard, VirtualKeyboard) or not keyboard.isVisible():
            return

        # Обработка кнопок геймпада
        if button_code in BUTTONS['confirm']:  # Кнопка A/Cross - подтверждение
            if value == 1:
                keyboard.activateFocusedKey()
        elif button_code in BUTTONS['back']:  # Кнопка B/Circle - скрыть клавиатуру
            if value == 1:
                keyboard.hide()
                # Возвращаем фокус на поле ввода
                if keyboard.current_input_widget:
                    keyboard.current_input_widget.setFocus()
        elif button_code in BUTTONS['prev_tab']:  # LB/L1 - переключение раскладки
            if value == 1:
                keyboard.on_lang_click()
        elif button_code in BUTTONS['next_tab']:  # RB/R1 - переключение Shift
            if value == 1:
                keyboard.on_shift_click(not keyboard.shift_pressed)
        elif button_code in BUTTONS['context_menu']:  # Кнопка Start - подтверждение
            if value == 1:
                keyboard.activateFocusedKey()
        elif button_code in BUTTONS['menu']:  # Кнопка Select - скрыть клавиатуру
            if value == 1:
                keyboard.hide()
                # Возвращаем фокус на поле ввода
                if keyboard.current_input_widget:
                    keyboard.current_input_widget.setFocus()
        elif button_code in BUTTONS['add_game']:  # Кнопка X - Backspace (now holdable)
            if value == 1:
                keyboard.on_backspace_pressed()
            elif value == 0:
                keyboard.stop_backspace_repeat()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        app = QApplication.instance()
        if not app:
            return super().eventFilter(obj, event)

        if event.type() == QEvent.Type.MouseButtonPress:
            mouse_event = cast(QMouseEvent, event)
            if mouse_event.button() == Qt.MouseButton.ExtraButton1:
                # Handle ExtraButton1 as "back" action, similar to Escape
                active_win = QApplication.activeWindow()
                focused = QApplication.focusWidget()
                if isinstance(focused, QLineEdit):
                    return False  # Skip if in QLineEdit
                if isinstance(active_win, QDialog):
                    active_win.reject()
                    return True
                self._parent.goBackDetailPage(self._parent.currentDetailPage)
                return True

        # Ensure obj is a QObject
        if not isinstance(obj, QObject):
            logger.debug(f"Skipping event filter for non-QObject: {type(obj).__name__}")
            return False

        # Handle key press and release events
        if not isinstance(event, QKeyEvent):
            return super().eventFilter(obj, event)

        key = event.key()
        modifiers = event.modifiers()
        focused = QApplication.focusWidget()
        popup = QApplication.activePopupWidget()
        active_win = QApplication.activeWindow()

        # Handle key press events
        if event.type() == QEvent.Type.KeyPress:
            # Handle FileExplorer specific logic
            if self.file_explorer:
                # Handle drive buttons in FileExplorer
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if isinstance(focused, AutoSizeButton) and hasattr(self.file_explorer, 'drive_buttons') and focused in self.file_explorer.drive_buttons:
                        self.file_explorer.select_drive()
                        return True
                    elif isinstance(focused, QListWidget) and focused == self.file_explorer.file_list:
                        current_item = focused.currentItem()
                        if current_item:
                            selected = current_item.text()
                            full_path = os.path.join(self.file_explorer.current_path, selected)
                            if os.path.isdir(full_path):
                                if selected == "../":
                                    self.file_explorer.previous_dir()
                                else:
                                    self.file_explorer.current_path = os.path.normpath(full_path)
                                    self.file_explorer.update_file_list()
                            elif not self.file_explorer.directory_only:
                                self.file_explorer.file_signal.file_selected.emit(os.path.normpath(full_path))
                                self.file_explorer.accept()
                            return True
                    else:
                        self._parent.activateFocusedWidget()
                        return True

                # Handle FileExplorer navigation with right arrow key
                if key == Qt.Key.Key_Right:
                    try:
                        if hasattr(self.file_explorer, 'drive_buttons') and self.file_explorer.drive_buttons:
                            if not isinstance(focused, AutoSizeButton) or focused not in self.file_explorer.drive_buttons:
                                self.file_explorer.drive_buttons[0].setFocus()
                                self.file_explorer.ensure_button_visible(self.file_explorer.drive_buttons[0])
                            else:
                                current_idx = self.file_explorer.drive_buttons.index(focused)
                                next_idx = min(current_idx + 1, len(self.file_explorer.drive_buttons) - 1)
                                self.file_explorer.drive_buttons[next_idx].setFocus()
                                self.file_explorer.ensure_button_visible(self.file_explorer.drive_buttons[next_idx])
                            return True
                    except Exception as e:
                        logger.error(f"Error handling right arrow in FileExplorer: {e}")
                        return True

                # Handle Backspace for FileExplorer navigation
                if key == Qt.Key.Key_Backspace:
                    self.file_explorer.previous_dir()
                    return True

            # Handle QLineEdit cursor movement with Left/Right arrows
            if isinstance(focused, QLineEdit) and key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                if key == Qt.Key.Key_Left:
                    focused.cursorBackward(False, 1)  # Move cursor left by one character
                elif key == Qt.Key.Key_Right:
                    focused.cursorForward(False, 1)  # Move cursor right by one character
                return True  # Consume the event to prevent further processing

            # Open system overlay with Insert
            if key == Qt.Key.Key_Insert:
                if not popup and not isinstance(active_win, QDialog):
                    self._parent.openSystemOverlay()
                    return True

            # Refresh game grid with F5
            if key == Qt.Key.Key_F5:
                self._parent.refreshGames()
                return True

            # Close application with Ctrl+Q
            if key == Qt.Key.Key_Q and modifiers & Qt.KeyboardModifier.ControlModifier:
                app.quit()
                return True

            # Handle Backspace for FileExplorer navigation (move to parent directory)
            if key == Qt.Key.Key_Backspace and self.file_explorer:
                self.file_explorer.previous_dir()
                return True

            # Close Dialogs with Escape
            if key == Qt.Key.Key_Escape:
                if isinstance(focused, QLineEdit):
                    return False
                if isinstance(active_win, QDialog):
                    active_win.reject()
                    return True

            # FullscreenDialog navigation
            if isinstance(active_win, FullscreenDialog):
                if key in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Backspace):
                    active_win.close()
                    return True
                elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                    # Navigate screenshots in FullscreenDialog
                    if key == Qt.Key.Key_Left:
                        active_win.show_prev()
                    elif key == Qt.Key.Key_Right:
                        active_win.show_next()
                    return True  # Consume event to prevent tab switching

            # Handle common UI elements like QMessageBox before tab switching
            # Check if there's an active QMessageBox that should handle the arrow keys first
            active = QApplication.activeWindow()
            if isinstance(active, QMessageBox):
                # Prevent tab switching when there's an active QMessageBox
                # Let the default Qt behavior handle the QMessageBox focus navigation
                if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
                    # Just continue to let the default processing handle the QMessageBox
                    pass  # Allow the event to continue to the default processing

            # Handle tab switching with Left/Right arrow keys when not in GameCard focus or QLineEdit or QTableWidget or AutoSizeButton
            # Also skip if there's an active QMessageBox or other QDialog
            active = QApplication.activeWindow()
            if (key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and
                not isinstance(focused, GameCard | QLineEdit | QTableWidget | AutoSizeButton) and
                not self.file_explorer and
                not isinstance(active, QMessageBox)):
                if not isinstance(active, QDialog) or not hasattr(active, 'tab_widget'):
                    idx = self._parent.stackedWidget.currentIndex()
                    total = len(self._parent.tabButtons)
                    if key == Qt.Key.Key_Left:
                        new_idx = (idx - 1) % total
                        self._parent.switchTab(new_idx)
                        self._parent.tabButtons[new_idx].setFocus(Qt.FocusReason.OtherFocusReason)
                        return True
                    elif key == Qt.Key.Key_Right:
                        new_idx = (idx + 1) % total
                        self._parent.switchTab(new_idx)
                        self._parent.tabButtons[new_idx].setFocus(Qt.FocusReason.OtherFocusReason)
                        return True

            # Map arrow keys to D-pad press events for other contexts
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
                now = time.time()
                dpad_code = None
                dpad_value = 0
                if key == Qt.Key.Key_Up:
                    dpad_code = ecodes.ABS_HAT0Y
                    dpad_value = -1
                elif key == Qt.Key.Key_Down:
                    dpad_code = ecodes.ABS_HAT0Y
                    dpad_value = 1
                elif key == Qt.Key.Key_Left:
                    dpad_code = ecodes.ABS_HAT0X
                    dpad_value = -1
                elif key == Qt.Key.Key_Right:
                    dpad_code = ecodes.ABS_HAT0X
                    dpad_value = 1

                if dpad_code is not None:
                    self.dpad_moved.emit(dpad_code, dpad_value, now)
                    return True

            # Context menu for GameCard
            if isinstance(focused, GameCard):
                if key == Qt.Key.Key_F10 and modifiers & Qt.KeyboardModifier.ShiftModifier:
                    pos = QPoint(focused.width() // 2, focused.height() // 2)
                    focused._show_context_menu(pos)
                    return True

            # General actions: Activate, Back, Add
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # Special handling for table widgets
                if isinstance(focused, QTableWidget):
                    self.handle_table_confirm(focused)
                    return True
                self._parent.activateFocusedWidget()
                return True
            elif key in (Qt.Key.Key_Escape, Qt.Key.Key_Backspace):
                if isinstance(focused, QLineEdit):
                    return False
                self._parent.goBackDetailPage(self._parent.currentDetailPage)
                return True
            elif key == Qt.Key.Key_E:
                if isinstance(focused, QLineEdit):
                    return False
                # Only open AddGameDialog if in library tab (index 0)
                if self._parent.stackedWidget.currentIndex() == 0:
                    self._parent.openAddGameDialog()
                    return True

            # Toggle fullscreen with F11
            if key == Qt.Key.Key_F11 and not self._is_gamescope_session:
                self.toggle_fullscreen.emit(not self._is_fullscreen)
                return True

        # Handle key release events for arrow keys
        elif event.type() == QEvent.Type.KeyRelease:
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
                now = time.time()
                dpad_code = None
                if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                    dpad_code = ecodes.ABS_HAT0Y
                elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                    dpad_code = ecodes.ABS_HAT0X

                if dpad_code is not None:
                    # Emit release event with value 0 to stop continuous movement
                    self.dpad_moved.emit(dpad_code, 0, now)
                    return True

        return super().eventFilter(obj, event)

    def init_gamepad(self) -> None:
        self.udev_context = Context()
        self.Devices = Devices
        self.monitor_ready = False
        self.monitor_event = threading.Event()

        # Подключаем сигнал hotplug к обработчику в главном потоке
        self.gamepad_hotplug.connect(self._on_gamepad_hotplug)

        # Debounce timer для отложенной проверки геймпада (в главном потоке Qt)
        self.gamepad_check_timer = QTimer()
        self.gamepad_check_timer.setSingleShot(True)
        self.gamepad_check_timer.timeout.connect(self.check_gamepad)

        # Первоначальная проверка
        self.check_gamepad()

        # Запускаем udev monitor в отдельном потоке
        threading.Thread(target=self.run_udev_monitor, daemon=True).start()
        logger.info("Gamepad support initialized with hotplug (evdev + pyudev)")

    def run_udev_monitor(self) -> None:
        """
        Безопасный неблокирующий udev monitor для геймпадов.
        Использует select.poll() вместо блокирующего monitor.poll().
        """
        try:
            logger.info("Starting udev monitor...")
            monitor = Monitor.from_netlink(self.udev_context)
            monitor.filter_by(subsystem='input')

            try:
                monitor.start()
            except Exception as e:
                logger.error(f"Failed to start udev monitor: {e}")
                return

            fd = monitor.fileno()
            poller = select.poll()
            poller.register(fd, select.POLLIN)

            # Короткий дренаж событий при запуске (0.5 сек)
            drain_start = time.time()
            drained_count = 0
            while time.time() - drain_start < 0.5:
                events = poller.poll(100)
                if not events:
                    continue
                try:
                    _ = monitor.poll(timeout=0)  # просто читаем, не обрабатываем
                    drained_count += 1
                except Exception:
                    break

            self.monitor_ready = True
            self.monitor_event.set()
            logger.info(f"Drained {drained_count} initial events, now monitoring hotplug...")

            # Основной цикл
            while self.running:
                events = poller.poll(1000)  # 1 сек таймаут
                if not events:
                    continue  # просто ждём, не блокируем

                try:
                    device = monitor.poll(timeout=0)
                except Exception as e:
                    logger.debug(f"Monitor poll failed: {e}")
                    continue

                if not device:
                    continue

                action = device.action
                if action and self._is_joystick_device(device):
                    logger.info(f"Joystick hotplug event: {action} for {device.sys_name}")
                    # отправляем сигнал в Qt-поток
                    self.handle_udev_event(action, device)

            logger.info("udev monitor stopped gracefully")

        except Exception as e:
            logger.error(f"Error in udev monitor: {e}", exc_info=True)

    def _is_joystick_device(self, device: Device) -> bool:
        """
        Быстрая проверка: является ли устройство джойстиком.
        Проверяет ID_INPUT_JOYSTICK из udev базы данных.
        """
        try:
            # Проверяем свойство ID_INPUT_JOYSTICK
            if device.get('ID_INPUT_JOYSTICK') == '1':
                return True

            # Дополнительно: проверяем родительские устройства
            # (некоторые контроллеры имеют свойство только у родителя)
            parent = device.parent
            if parent and parent.get('ID_INPUT_JOYSTICK') == '1':
                return True

            return False
        except Exception as e:
            logger.debug(f"Error checking joystick device: {e}")
            return False


    def handle_udev_event(self, action: str, device: Device) -> None:
        """
        Обработчик udev событий для джойстиков.
        Отправляет сигнал в главный поток Qt вместо прямого вызова QTimer.
        """
        try:
            if action == 'add':
                # Отправляем сигнал в главный поток Qt
                # QTimer будет запущен там безопасно
                logger.debug("Emitting gamepad add signal")
                self.gamepad_hotplug.emit('add')

            elif action == 'remove' and self.gamepad:
                # Проверяем конкретно наш геймпад по пути устройства
                device_node = device.device_node  # например, /dev/input/event3

                if device_node and self.gamepad.path == device_node:
                    logger.info(f"Connected gamepad disconnected: {device_node}")
                    # Отправляем сигнал в главный поток
                    self.gamepad_hotplug.emit('remove')

        except Exception as e:
            logger.error(f"Error handling udev event: {e}", exc_info=True)


    def _on_gamepad_hotplug(self, action: str) -> None:
        """
        Обработчик сигнала hotplug, выполняется в главном потоке Qt.
        Безопасно работает с QTimer.
        """
        try:
            if action == 'add':
                # Debounce: откладываем проверку на 200ms
                # Множественные события за короткое время объединяются в один вызов
                logger.debug("Scheduling gamepad check (debounced)")
                self.gamepad_check_timer.start(200)

            elif action == 'remove':
                # Немедленная обработка отключения
                self.stop_rumble()
                self.gamepad = None

                if self.gamepad_thread:
                    self.gamepad_thread.join(timeout=2.0)

                if read_auto_fullscreen_gamepad() and not read_fullscreen_config():
                    self.toggle_fullscreen.emit(False)

        except Exception as e:
            logger.error(f"Error in hotplug handler: {e}", exc_info=True)

    def check_gamepad(self) -> None:
        """
        Проверка и подключение геймпада.
        Вызывается из главного потока Qt через QTimer (debounced).
        """
        try:
            new_gamepad = self.find_gamepad()

            if new_gamepad:
                if not self.gamepad or new_gamepad.path != self.gamepad.path:
                    logger.info(f"Gamepad connected: {new_gamepad.name} at {new_gamepad.path}")
                    self.stop_rumble()
                    self.gamepad = new_gamepad

                    if self.gamepad_thread and self.gamepad_thread.is_alive():
                        self.gamepad_thread.join(timeout=2.0)

                    def start_monitoring():
                        # Ожидание готовности udev monitor без busy-wait
                        if not self.monitor_event.wait(timeout=2.0):
                            logger.warning("Timeout waiting for udev monitor readiness")
                        self.monitor_gamepad()

                    self.gamepad_thread = threading.Thread(
                        target=start_monitoring,
                        daemon=True
                    )
                    self.gamepad_thread.start()

                    # Автоматический фуллскрин при подключении геймпада
                    if read_auto_fullscreen_gamepad() and not read_fullscreen_config():
                        self.toggle_fullscreen.emit(True)

            elif self.gamepad and not any(self.gamepad.path == path for path in list_devices()):
                logger.info("Gamepad no longer detected")
                self.stop_rumble()
                self.gamepad = None

                if self.gamepad_thread and self.gamepad_thread.is_alive():
                    self.gamepad_thread.join(timeout=2.0)

                if read_auto_fullscreen_gamepad() and not read_fullscreen_config():
                    self.toggle_fullscreen.emit(False)

        except Exception as e:
            logger.error(f"Error checking gamepad: {e}", exc_info=True)

    def find_gamepad(self) -> InputDevice | None:
        """
        Находит первый доступный геймпад.
        Оптимизирован: предварительная фильтрация по capabilities перед udev-запросами.
        """
        try:
            devices = [InputDevice(path) for path in list_devices()]

            if not devices:
                return None

            logger.debug(f"Checking {len(devices)} devices for gamepad...")

            for device in devices:
                # Skip ASRock LED controller (известная проблема)
                if device.info.vendor == 0x26ce and device.info.product == 0x01a2:
                    continue

                # Предварительная фильтрация: проверяем capabilities
                # Джойстик должен иметь хотя бы оси (ABS) или кнопки (KEY)
                # Это избегает udev-запросов для явно не-джойстиков
                caps = device.capabilities(verbose=False)
                has_abs_axes = ecodes.EV_ABS in caps
                has_buttons = ecodes.EV_KEY in caps

                if not (has_abs_axes or has_buttons):
                    continue

                # Только для потенциальных джойстиков делаем udev-запрос
                try:
                    udev_device = self.Devices.from_device_file(
                        self.udev_context,
                        device.path
                    )
                    is_joystick = udev_device.get('ID_INPUT_JOYSTICK')

                    if is_joystick == '1':
                        logger.info(f"Found gamepad: {device.name}")
                        self.detect_gamepad_axes(device)
                        return device

                except Exception as e:
                    logger.debug(f"Could not check udev properties for {device.path}: {e}")
                    continue

            logger.debug("No gamepad found")
            return None

        except Exception as e:
            logger.error(f"Error finding gamepad: {e}", exc_info=True)
            return None

    def detect_gamepad_axes(self, device: InputDevice) -> None:
        """Читаем параметры осей из ядра (диапазон и мёртвую зону)"""
        try:
            caps = device.capabilities()
            if ecodes.EV_ABS not in caps:
                return

            abs_axes = caps[ecodes.EV_ABS]
            for code, absinfo in cast(Any, abs_axes):
                if code == ecodes.ABS_X:
                    self.min_value = absinfo.min
                    self.max_value = absinfo.max
                    self.center_x = (absinfo.min + absinfo.max) // 2
                    self.center_y = (absinfo.min + absinfo.max) // 2
                    self.stick_x_raw = self.center_x
                    self.stick_y_raw = self.center_y

                    # Берём мёртвую зону из ядра (flat параметр)
                    self.deadzone_value = absinfo.flat if absinfo.flat > 0 else 15

                    logger.info(
                        f"Gamepad axes: min={self.min_value}, max={self.max_value}, "
                        f"center={self.center_x}, deadzone={self.deadzone_value}"
                    )
                    break
        except Exception as ex:
            logger.error(f"Error detecting gamepad axes: {ex}")

    def monitor_gamepad(self) -> None:
        try:
            while self.running:
                current_time = time.time()

                if self.gamepad:
                    try:
                        # Non-blocking read with short timeout
                        events = []
                        r, w, x = select.select([self.gamepad.fd], [], [], 0.001)
                        if r:
                            events = list(self.gamepad.read())

                        # Process events
                        for event in events:
                            if not self.running:
                                break

                            # UI signal handling (always, for internal app)
                            if event.type == ecodes.EV_KEY:
                                if event.code == ecodes.BTN_START:
                                    self.start_held = (event.value == 1)

                                if event.code in BUTTONS['guide']:
                                    self.guide_held = (event.value == 1)

                                if event.value == 1:
                                    if ((event.code in BUTTONS['guide'] and self.start_held) or
                                        (event.code == ecodes.BTN_START and self.guide_held)):
                                        self.emulation_triggered = not self.emulation_triggered

                                self.button_event.emit(event.code, event.value)
                                # Special handling for menu on press only
                                # Only handle menu button if our main window is currently active
                                if (event.value == 1 and event.code in BUTTONS['menu'] and
                                    not self._is_gamescope_session and not self.in_guide_combination_attempt):
                                    # Check if our main window is the currently active window
                                    if self._parent.isActiveWindow():
                                        self.toggle_fullscreen.emit(not self._is_fullscreen)
                            elif event.type == ecodes.EV_ABS:
                                if event.code in {ecodes.ABS_Z, ecodes.ABS_RZ}:
                                    # Trigger handling for UI
                                    if current_time - self.last_trigger_time < self.trigger_cooldown:
                                        continue
                                    if event.code == ecodes.ABS_Z:  # LT/L2
                                        if event.value > 128 and not self.lt_pressed:
                                            self.lt_pressed = True
                                            self.button_event.emit(event.code, 1)
                                            self.last_trigger_time = current_time
                                        elif event.value <= 128 and self.lt_pressed:
                                            self.lt_pressed = False
                                            self.button_event.emit(event.code, 0)
                                    elif event.code == ecodes.ABS_RZ:  # RT/R2
                                        if event.value > 128 and not self.rt_pressed:
                                            self.rt_pressed = True
                                            self.button_event.emit(event.code, 1)
                                            self.last_trigger_time = current_time
                                        elif event.value <= 128 and self.rt_pressed:
                                            self.rt_pressed = False
                                            self.button_event.emit(event.code, 0)
                                else:
                                    self.dpad_moved.emit(event.code, event.value, current_time)

                            # Mouse emulation (only for external windows + triggered)
                            if self.mouse_emulation_enabled and self.emulation_active and self.emulation_triggered:
                                if event.type == ecodes.EV_ABS:
                                    if event.code == ecodes.ABS_HAT0X:
                                        if event.value == -1:
                                            self.move_mouse(-10, 0)
                                        elif event.value == 1:
                                            self.move_mouse(10, 0)
                                    elif event.code == ecodes.ABS_HAT0Y:
                                        if event.value == -1:
                                            self.move_mouse(0, -10)
                                        elif event.value == 1:
                                            self.move_mouse(0, 10)
                                    elif event.code == ecodes.ABS_X:
                                        self.stick_x_raw = event.value
                                    elif event.code == ecodes.ABS_Y:
                                        if event.code not in (ecodes.ABS_GAS, ecodes.ABS_BRAKE):
                                            self.stick_y_raw = event.value
                                    elif event.code == ecodes.ABS_RY:
                                        self.handle_scroll(event.value)
                                    elif event.code in (ecodes.ABS_GAS, ecodes.ABS_BRAKE):
                                        pass  # Триггеры - не обрабатываем
                                elif event.type == ecodes.EV_KEY:
                                    if event.code in (ecodes.BTN_SOUTH, ecodes.BTN_A) and event.value == 1:
                                        self.click_left()
                                    elif event.code in (ecodes.BTN_EAST, ecodes.BTN_B) and event.value == 1:
                                        self.click_right()

                        # Periodic mouse position update
                        if current_time - self.last_update >= self.update_interval:
                            self.update_mouse_position()
                            self.last_update = current_time

                    except OSError as e:
                        if e.errno == 19:  # ENODEV
                            logger.info("Gamepad disconnected during monitoring")
                        else:
                            logger.error(f"IOError in gamepad monitoring: {e}")
                        self.gamepad = None
                        self.stick_x_raw = self.center_x
                        self.stick_y_raw = self.center_y
                        self.scroll_accumulator = 0.0
                        self.start_held = False
                        self.guide_held = False
                        self.emulation_triggered = False
                        break
                    except Exception as ex:
                        logger.error(f"Unexpected error in gamepad monitoring: {ex}")
                        break
                else:
                    time.sleep(0.1)
                    if not self.running:
                        break
        except Exception as e:
            logger.error(f"Error in gamepad monitoring thread: {e}", exc_info=True)
        finally:
            if self.gamepad:
                try:
                    self.stop_rumble()
                    self.gamepad.close()
                except Exception:
                    pass
            self.gamepad = None
            self.start_held = False
            self.guide_held = False
            self.emulation_triggered = False

    def cleanup(self) -> None:
        """
        Корректное завершение работы с геймпадом и udev монитором.
        """
        try:
            # Mouse emulation cleanup
            self.disable_mouse_emulation()

            # Stop focus check timer
            self.focus_check_timer.stop()

            # Флаг для остановки udev monitor loop
            self.running = False

            # Останавливаем все таймеры
            if hasattr(self, 'gamepad_check_timer'):
                self.gamepad_check_timer.stop()
            self.dpad_timer.stop()
            self.nav_timer.stop()

            # Очистка геймпада
            self.stop_rumble()

            if self.gamepad_thread:
                self.gamepad_thread.join(timeout=2.0)

            if self.gamepad:
                self.gamepad.close()

            self.gamepad = None
            self.gamepad_type = GamepadType.UNKNOWN

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
