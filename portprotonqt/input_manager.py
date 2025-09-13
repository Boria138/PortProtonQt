import time
import threading
import os
from typing import Protocol, cast
from evdev import InputDevice, InputEvent, ecodes, list_devices, ff
from enum import Enum
from pyudev import Context, Monitor, MonitorObserver, Device
from PySide6.QtWidgets import QWidget, QStackedWidget, QApplication, QScrollArea, QLineEdit, QDialog, QMenu, QComboBox, QListView, QMessageBox, QListWidget
from PySide6.QtCore import Qt, QObject, QEvent, QPoint, Signal, Slot, QTimer
from PySide6.QtGui import QKeyEvent, QMouseEvent
from portprotonqt.logger import get_logger
from portprotonqt.image_utils import FullscreenDialog
from portprotonqt.custom_widgets import NavLabel, AutoSizeButton
from portprotonqt.game_card import GameCard
from portprotonqt.config_utils import read_fullscreen_config, read_window_geometry, save_window_geometry, read_auto_fullscreen_gamepad, read_rumble_config
from portprotonqt.dialogs import AddGameDialog

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
    def isActiveWindow(self) -> bool:
        ...
    stackedWidget: QStackedWidget
    tabButtons: dict[int, QWidget]
    gamesListWidget: QWidget
    currentDetailPage: QWidget | None
    current_exec_line: str | None
    current_add_game_dialog: AddGameDialog | None

# Mapping of actions to evdev button codes, includes Xbox, PlayStation and Nintendo Switch controllers
# https://github.com/torvalds/linux/blob/master/drivers/hid/hid-playstation.c
# https://github.com/torvalds/linux/blob/master/drivers/input/joystick/xpad.c
# https://github.com/torvalds/linux/blob/master/drivers/hid/hid-nintendo
BUTTONS = {
    'confirm':       {ecodes.BTN_SOUTH},           # A (Xbox) / Cross (PS) / B (Switch)
    'back':          {ecodes.BTN_EAST},            # B (Xbox) / Circle (PS) / A (Switch)
    'add_game':      {ecodes.BTN_NORTH},           # X (Xbox) / Triangle (PS) / Y (Switch)
    'prev_dir':      {ecodes.BTN_WEST},            # Y (Xbox) / Square (PS) / X (Switch)
    'prev_tab':      {ecodes.BTN_TL},              # LB (Xbox) / L1 (PS) / L (Switch)
    'next_tab':      {ecodes.BTN_TR},              # RB (Xbox) / R1 (PS) / R (Switch)
    'context_menu':  {ecodes.BTN_START},           # Start (Xbox) / Options (PS) / + (Switch)
    'menu':          {ecodes.BTN_SELECT},          # Select (Xbox) / Share (PS) / - (Switch)
    'guide':         {ecodes.BTN_MODE},            # Xbox Button / PS Button / Home (Switch)
    'increase_size': {ecodes.ABS_RZ},              # RT (Xbox) / R2 (PS) / ZR (Switch)
    'decrease_size': {ecodes.ABS_Z},               # LT (Xbox) / L2 (PS) / ZL (Switch)
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
    button_pressed = Signal(int)  # Signal for button presses
    dpad_moved = Signal(int, int, float)  # Signal for D-pad movements
    toggle_fullscreen = Signal(bool)  # Signal for toggling fullscreen mode (True for fullscreen, False for normal)

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
        self.gamepad_type = GamepadType.UNKNOWN
        # Ensure attributes exist on main_window
        self._parent.currentDetailPage = getattr(self._parent, 'currentDetailPage', None)
        self._parent.current_exec_line = getattr(self._parent, 'current_exec_line', None)
        self._parent.current_add_game_dialog = getattr(self._parent, 'current_add_game_dialog', None)
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
        self.button_pressed.connect(self.handle_button_slot)
        self.dpad_moved.connect(self.handle_dpad_slot)
        self.toggle_fullscreen.connect(self.handle_fullscreen_slot)

        # Install keyboard event filter
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        # Initialize evdev + hotplug
        self.init_gamepad()

    def detect_gamepad_type(self, device: InputDevice) -> GamepadType:
        """
        Определяет тип геймпада по capabilities
        """
        caps = device.capabilities()
        keys = set(caps.get(ecodes.EV_KEY, []))

        # Для EV_ABS вытаскиваем только коды (первый элемент кортежа)
        abs_axes = {a if isinstance(a, int) else a[0] for a in caps.get(ecodes.EV_ABS, [])}

        # Xbox layout
        if {ecodes.BTN_SOUTH, ecodes.BTN_EAST, ecodes.BTN_NORTH, ecodes.BTN_WEST}.issubset(keys):
            if {ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_RX, ecodes.ABS_RY}.issubset(abs_axes):
                self.gamepad_type = GamepadType.XBOX
                return GamepadType.XBOX

        # PlayStation layout
        if ecodes.BTN_TOUCH in keys or (ecodes.BTN_DPAD_UP in keys and ecodes.BTN_EAST in keys):
            self.gamepad_type = GamepadType.PLAYSTATION
            logger.info(f"Detected {self.gamepad_type.value} controller: {device.name}")
            return GamepadType.PLAYSTATION

        # Steam Controller / Deck (трекпады)
        if any(a for a in abs_axes if a >= ecodes.ABS_MT_SLOT):
            self.gamepad_type = GamepadType.XBOX
            logger.info(f"Detected {self.gamepad_type.value} controller: {device.name}")
            return GamepadType.XBOX

        # Fallback
        self.gamepad_type = GamepadType.XBOX
        return GamepadType.XBOX

    def enable_file_explorer_mode(self, file_explorer):
        """Настройка обработки геймпада для FileExplorer"""
        try:
            self.file_explorer = file_explorer
            self.original_button_handler = self.handle_button_slot
            self.original_dpad_handler = self.handle_dpad_slot
            self.original_gamepad_state = self._gamepad_handling_enabled
            self.handle_button_slot = self.handle_file_explorer_button
            self.handle_dpad_slot = self.handle_file_explorer_dpad
            self._gamepad_handling_enabled = True
            logger.debug("Gamepad handling successfully connected for FileExplorer")
        except Exception as e:
            logger.error(f"Error connecting gamepad handlers for FileExplorer: {e}")

    def disable_file_explorer_mode(self):
        """Восстановление оригинальных обработчиков главного окна программы (дефолт возвращаем)"""
        try:
            if self.file_explorer:
                self.handle_button_slot = self.original_button_handler
                self.handle_dpad_slot = self.original_dpad_handler
                self._gamepad_handling_enabled = self.original_gamepad_state
                self.file_explorer = None
                self.nav_timer.stop()
                logger.debug("Gamepad handling successfully restored")
        except Exception as e:
            logger.error(f"Error restoring gamepad handlers: {e}")

    def handle_file_explorer_button(self, button_code):
        try:
            popup = QApplication.activePopupWidget()
            if isinstance(popup, QMenu):
                if button_code in BUTTONS['confirm']:  # A button (BTN_SOUTH)
                    if popup.activeAction():
                        popup.activeAction().trigger()
                        popup.close()
                    return
                elif button_code in BUTTONS['back']:  # B button
                    popup.close()
                    return
                return  # Skip other handling if menu is open

            if not self.file_explorer or not hasattr(self.file_explorer, 'file_list'):
                logger.debug("No file explorer or file_list available")
                return

            focused_widget = QApplication.focusWidget()
            if button_code in BUTTONS['confirm']:  # A button (BTN_SOUTH)
                if isinstance(focused_widget, AutoSizeButton) and hasattr(self.file_explorer, 'drive_buttons') and focused_widget in self.file_explorer.drive_buttons:
                    self.file_explorer.select_drive()  # Select the focused drive
                elif self.file_explorer.file_list.count() == 0:
                    logger.debug("File list is empty")
                    return
                else:
                    selected = self.file_explorer.file_list.currentItem().text()
                    full_path = os.path.join(self.file_explorer.current_path, selected)
                    if os.path.isdir(full_path):
                        self.file_explorer.current_path = os.path.normpath(full_path)
                        self.file_explorer.update_file_list()
                    elif not self.file_explorer.directory_only:
                        self.file_explorer.file_signal.file_selected.emit(os.path.normpath(full_path))
                        self.file_explorer.accept()
                    else:
                        logger.debug("Selected item is not a directory, cannot select: %s", full_path)
            elif button_code in BUTTONS['context_menu']:  # Start button (BTN_START)
                if self.file_explorer.file_list.count() == 0:
                    logger.debug("File list is empty, cannot show context menu")
                    return
                current_item = self.file_explorer.file_list.currentItem()
                if current_item:
                    item_rect = self.file_explorer.file_list.visualItemRect(current_item)
                    pos = item_rect.center()  # Use local coordinates for itemAt check
                    self.file_explorer.show_folder_context_menu(pos)
                else:
                    logger.debug("No item selected for context menu")
            elif button_code in BUTTONS['add_game']:  # X button
                if self.file_explorer.file_list.count() == 0:
                    logger.debug("File list is empty")
                    return
                selected = self.file_explorer.file_list.currentItem().text()
                full_path = os.path.join(self.file_explorer.current_path, selected)
                if os.path.isdir(full_path):
                    self.file_explorer.file_signal.file_selected.emit(os.path.normpath(full_path))
                    self.file_explorer.accept()
                else:
                    logger.debug("Selected item is not a directory: %s", full_path)
            elif button_code in BUTTONS['back']:  # B button
                self.file_explorer.close()
            elif button_code in BUTTONS['prev_dir']:  # Y button
                self.file_explorer.previous_dir()
            else:
                if self.original_button_handler:
                    self.original_button_handler(button_code)
        except Exception as e:
            logger.error("Error in FileExplorer button handler: %s", e)

    def handle_file_explorer_dpad(self, code, value, current_time):
        """Обработка движения D-pad и левого стика для FileExplorer"""
        try:
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
                        popup.setActiveAction(actions[next_idx])
                    elif value < 0:  # Up
                        next_idx = (current_idx - 1) % len(actions) if current_idx != -1 else len(actions) - 1
                        popup.setActiveAction(actions[next_idx])
                return  # Skip other handling if menu is open

            if not self.file_explorer or not hasattr(self.file_explorer, 'file_list') or not self.file_explorer.file_list:
                logger.debug("No file explorer or file_list available")
                return

            focused_widget = QApplication.focusWidget()
            if code in (ecodes.ABS_HAT0X, ecodes.ABS_X) and hasattr(self.file_explorer, 'drive_buttons') and self.file_explorer.drive_buttons:
                # Navigate drive buttons horizontally
                if not isinstance(focused_widget, AutoSizeButton) or focused_widget not in self.file_explorer.drive_buttons:
                    # If not focused on a drive button, focus the first one
                    self.file_explorer.drive_buttons[0].setFocus()
                    self.file_explorer.ensure_button_visible(self.file_explorer.drive_buttons[0])
                    return
                current_idx = self.file_explorer.drive_buttons.index(focused_widget)
                if value < 0:  # Left
                    next_idx = max(current_idx - 1, 0)
                    self.file_explorer.drive_buttons[next_idx].setFocus()
                    self.file_explorer.ensure_button_visible(self.file_explorer.drive_buttons[next_idx])
                elif value > 0:  # Right
                    next_idx = min(current_idx + 1, len(self.file_explorer.drive_buttons) - 1)
                    self.file_explorer.drive_buttons[next_idx].setFocus()
                    self.file_explorer.ensure_button_visible(self.file_explorer.drive_buttons[next_idx])
            elif code in (ecodes.ABS_HAT0Y, ecodes.ABS_Y):
                if isinstance(focused_widget, AutoSizeButton) and focused_widget in self.file_explorer.drive_buttons:
                    # Move focus to file list if navigating down from drive buttons
                    if value > 0 and self.file_explorer.file_list.count() > 0:
                        self.file_explorer.file_list.setFocus()
                        self.file_explorer.file_list.setCurrentRow(0)
                        self.file_explorer.file_list.scrollToItem(self.file_explorer.file_list.currentItem())
                    return
                # Для D-pad - реакция с фиксированной скоростью
                if code == ecodes.ABS_HAT0Y:
                    if value != 0:
                        self.current_direction = value
                        self.stick_value = 1.0  # Максимальная скорость для D-pad
                        if not self.nav_timer.isActive():
                            self.file_explorer.move_selection(self.current_direction)
                            self.last_nav_time = current_time
                            self.nav_timer.start(int(self.initial_nav_delay * 1000))
                    else:
                        self.current_direction = 0
                        self.nav_timer.stop()
                # Для стика - плавное управление с учетом степени отклонения
                elif code == ecodes.ABS_Y:
                    if abs(value) < self.dead_zone:
                        if self.stick_activated:
                            self.current_direction = 0
                            self.nav_timer.stop()
                            self.stick_activated = False
                        return
                    normalized_value = (abs(value) - self.dead_zone) / (32768 - self.dead_zone)
                    speed_factor = 0.3 + (normalized_value * 0.7)  # От 30% до 100% скорости
                    self.current_direction = -1 if value < 0 else 1
                    self.stick_value = speed_factor
                    self.stick_activated = True
                    if not self.nav_timer.isActive():
                        self.file_explorer.move_selection(self.current_direction)
                        self.last_nav_time = current_time
                        self.nav_timer.start(int(self.initial_nav_delay * 1000))
            elif self.original_dpad_handler:
                self.original_dpad_handler(code, value, current_time)
        except Exception as e:
            logger.error("Error in FileExplorer dpad handler: %s", e)

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

    @Slot(int)
    def handle_button_slot(self, button_code: int) -> None:
        if not self._gamepad_handling_enabled:
            return
        try:

            app = QApplication.instance()
            if not app or not self._parent.isActiveWindow():
                return
            active = QApplication.activeWindow()
            focused = QApplication.focusWidget()
            popup = QApplication.activePopupWidget()
            modal_dialog = QApplication.activeModalWidget()

            # Handle Guide button to open system overlay
            if button_code in BUTTONS['guide']:
                if not popup and not isinstance(active, QDialog):
                    self._parent.openSystemOverlay()
                    return

            # Handle QMenu (context menu)
            if isinstance(popup, QMenu):
                if button_code in BUTTONS['confirm']:
                    if popup.activeAction():
                        popup.activeAction().trigger()
                        popup.close()
                    return
                elif button_code in BUTTONS['back']:
                    popup.close()
                    return
                return

            # Handle QMessageBox
            if isinstance(active, QMessageBox):
                if button_code in BUTTONS['confirm']:
                    active.accept()  # Close QMessageBox with the default button
                    return
                elif button_code in BUTTONS['back']:
                    active.reject()  # Close QMessageBox on back button
                    return
                return

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

            # Game launch on detail page
            if (button_code in BUTTONS['confirm']) and self._parent.currentDetailPage is not None and modal_dialog is None:
                if self._parent.current_exec_line:
                    self.trigger_rumble()
                    self._parent.toggleGame(self._parent.current_exec_line, None)
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
            elif button_code in BUTTONS['increase_size'] and self._parent.stackedWidget.currentIndex() == 0:
                # Increase card size with RT (Xbox) / R2 (PS)
                size_slider = getattr(self._parent, 'sizeSlider', None)
                if size_slider:
                    new_value = min(size_slider.value() + 10, size_slider.maximum())
                    size_slider.setValue(new_value)
                    self._parent.on_slider_released()
            elif button_code in BUTTONS['decrease_size'] and self._parent.stackedWidget.currentIndex() == 0:
                # Decrease card size with LT (Xbox) / L2 (PS)
                size_slider = getattr(self._parent, 'sizeSlider', None)
                if size_slider:
                    new_value = max(size_slider.value() - 10, size_slider.minimum())
                    size_slider.setValue(new_value)
                    self._parent.on_slider_released()
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
        if not self._gamepad_handling_enabled:
            return
        try:

            app = QApplication.instance()
            active = QApplication.activeWindow()
            focused = QApplication.focusWidget()
            popup = QApplication.activePopupWidget()
            if not app or not active:
                return

            # Update D-pad state
            if value != 0:
                self.current_dpad_code = code
                self.current_dpad_value = value
                if not self.axis_moving:
                    self.axis_moving = True
                    self.last_move_time = current_time
                    self.current_axis_delay = self.initial_axis_move_delay
                    self.dpad_timer.start(int(self.repeat_axis_move_delay * 1000))  # Start timer (in milliseconds)
            else:
                self.current_dpad_code = None
                self.current_dpad_value = 0
                self.axis_moving = False
                self.current_axis_delay = self.initial_axis_move_delay
                self.dpad_timer.stop()  # Stop timer when D-pad is released
                return

            # Handle SystemOverlay, AddGameDialog, or QMessageBox navigation with D-pad
            if isinstance(active, QDialog) and code == ecodes.ABS_HAT0X and value != 0:
                if isinstance(active, QMessageBox):  # Specific handling for QMessageBox
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
            elif isinstance(active, QDialog) and code == ecodes.ABS_HAT0Y and value != 0:  # Keep up/down for other dialogs
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

            # Library tab navigation (index 0)
            if self._parent.stackedWidget.currentIndex() == 0 and code in (ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y):
                focused = QApplication.focusWidget()
                game_cards = self._parent.gamesListWidget.findChildren(GameCard)
                if not game_cards:
                    return

                scroll_area = self._parent.gamesListWidget.parentWidget()
                while scroll_area and not isinstance(scroll_area, QScrollArea):
                    scroll_area = scroll_area.parentWidget()

                # If no focused widget or not a GameCard, focus the first card
                if not isinstance(focused, GameCard) or focused not in game_cards:
                    game_cards[0].setFocus()
                    if scroll_area:
                        scroll_area.ensureWidgetVisible(game_cards[0], 50, 50)
                    return

                cards = self._parent.gamesListWidget.findChildren(GameCard, options=Qt.FindChildOption.FindChildrenRecursively)
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
                    current_col_idx = min(range(len(current_row)), key=lambda i: abs((current_row[i].pos().x() + current_row[i].width() / 2) - focused_x), default=0) # type: ignore

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
                            self._parent.tabButtons[0].setFocus(Qt.FocusReason.OtherFocusReason)

            # Vertical navigation in other tabs
            elif code == ecodes.ABS_HAT0Y and value != 0:
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

            # Handle tab switching with Left/Right arrow keys when not in GameCard focus or QLineEdit
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and not isinstance(focused, GameCard | QLineEdit) and not self.file_explorer:
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

            # Launch/stop game on detail page
            if self._parent.currentDetailPage and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._parent.current_exec_line:
                    self._parent.toggleGame(self._parent.current_exec_line, None)
                    return True

            # Context menu for GameCard
            if isinstance(focused, GameCard):
                if key == Qt.Key.Key_F10 and modifiers & Qt.KeyboardModifier.ShiftModifier:
                    pos = QPoint(focused.width() // 2, focused.height() // 2)
                    focused._show_context_menu(pos)
                    return True

            # General actions: Activate, Back, Add
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
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
        self.check_gamepad()
        threading.Thread(target=self.run_udev_monitor, daemon=True).start()
        logger.info("Gamepad support initialized with hotplug (evdev + pyudev)")

    def run_udev_monitor(self) -> None:
        try:
            context = Context()
            monitor = Monitor.from_netlink(context)
            monitor.filter_by(subsystem='input')
            observer = MonitorObserver(monitor, self.handle_udev_event)
            observer.start()
            while self.running:
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error in udev monitor: {e}", exc_info=True)

    def handle_udev_event(self, action: str, device: Device) -> None:
        try:
            if action == 'add':
                time.sleep(0.1)
                self.check_gamepad()
            elif action == 'remove' and self.gamepad:
                if not any(self.gamepad.path == path for path in list_devices()):
                    logger.info("Gamepad disconnected")
                    self.stop_rumble()
                    self.gamepad = None
                    if self.gamepad_thread:
                        self.gamepad_thread.join()
                    # Signal to exit fullscreen mode
                    self.toggle_fullscreen.emit(False)
        except Exception as e:
            logger.error(f"Error handling udev event: {e}", exc_info=True)

    def check_gamepad(self) -> None:
        try:
            new_gamepad = self.find_gamepad()
            if new_gamepad and new_gamepad != self.gamepad:
                logger.info(f"Gamepad connected: {new_gamepad.name}")
                self.detect_gamepad_type(new_gamepad)
                logger.info(f"Detected gamepad type: {self.gamepad_type.value}")
                self.stop_rumble()
                self.gamepad = new_gamepad
                if self.gamepad_thread:
                    self.gamepad_thread.join()
                self.gamepad_thread = threading.Thread(target=self.monitor_gamepad, daemon=True)
                self.gamepad_thread.start()
                # Send signal for fullscreen mode only if:
                # 1. auto_fullscreen_gamepad is enabled
                # 2. fullscreen is not already enabled (to avoid conflict)
                if read_auto_fullscreen_gamepad() and not read_fullscreen_config():
                    self.toggle_fullscreen.emit(True)
        except Exception as e:
            logger.error(f"Error checking gamepad: {e}", exc_info=True)

    def find_gamepad(self) -> InputDevice | None:
        try:
            devices = [InputDevice(path) for path in list_devices()]
            for device in devices:
                # Skip ASRock LED controller (vendor ID: 26ce, product ID: 01a2)
                if device.info.vendor == 0x26ce and device.info.product == 0x01a2:
                    logger.debug(f"Skipping ASRock LED controller: {device.name}")
                    continue
                caps = device.capabilities()
                if ecodes.EV_KEY in caps or ecodes.EV_ABS in caps:
                    return device
            return None
        except Exception as e:
            logger.error(f"Error finding gamepad: {e}", exc_info=True)
            return None

    def monitor_gamepad(self) -> None:
        try:
            if not self.gamepad:
                return
            for event in self.gamepad.read_loop():
                if not self.running:
                    break
                if event.type not in (ecodes.EV_KEY, ecodes.EV_ABS):
                    continue
                now = time.time()

                # Проверка фокуса: игнорируем события, если окно не в фокусе
                app = QApplication.instance()
                if not app or not self._parent.isActiveWindow():
                    continue

                if event.type == ecodes.EV_KEY and event.value == 1:
                    if event.code in BUTTONS['menu'] and not self._is_gamescope_session:
                        self.toggle_fullscreen.emit(not self._is_fullscreen)
                    else:
                        self.button_pressed.emit(event.code)
                elif event.type == ecodes.EV_ABS:
                    if event.code in {ecodes.ABS_Z, ecodes.ABS_RZ}:
                        # Проверяем, достаточно ли времени прошло с последнего срабатывания
                        if now - self.last_trigger_time < self.trigger_cooldown:
                            continue
                        if event.code == ecodes.ABS_Z:  # LT/L2
                            if event.value > 128 and not self.lt_pressed:
                                self.lt_pressed = True
                                self.button_pressed.emit(event.code)
                                self.last_trigger_time = now
                            elif event.value <= 128 and self.lt_pressed:
                                self.lt_pressed = False
                        elif event.code == ecodes.ABS_RZ:  # RT/R2
                            if event.value > 128 and not self.rt_pressed:
                                self.rt_pressed = True
                                self.button_pressed.emit(event.code)
                                self.last_trigger_time = now
                            elif event.value <= 128 and self.rt_pressed:
                                self.rt_pressed = False
                    else:
                        self.dpad_moved.emit(event.code, event.value, now)
        except OSError as e:
            if e.errno == 19:  # ENODEV: No such device
                logger.info("Gamepad disconnected during event loop")
            else:
                logger.error(f"OSError in gamepad monitoring: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error in gamepad monitoring: {e}", exc_info=True)
        finally:
            if self.gamepad:
                try:
                    self.stop_rumble()
                    self.gamepad.close()
                except Exception:
                    pass
            self.gamepad = None

    def cleanup(self) -> None:
        try:
            self.running = False
            self.dpad_timer.stop()
            self.nav_timer.stop()
            self.stop_rumble()
            if self.gamepad_thread:
                self.gamepad_thread.join()
            if self.gamepad:
                self.gamepad.close()
            self.gamepad = None
            self.gamepad_type = GamepadType.UNKNOWN
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
