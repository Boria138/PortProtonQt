import time
import threading
from typing import Protocol, cast
from evdev import InputDevice, ecodes, list_devices
import pyudev
from PySide6.QtWidgets import QWidget, QStackedWidget, QApplication, QScrollArea, QLineEdit, QDialog
from PySide6.QtCore import Qt, QObject, QEvent, QPoint, Signal, Slot
from PySide6.QtGui import QKeyEvent
from portprotonqt.logger import get_logger
from portprotonqt.image_utils import FullscreenDialog
from portprotonqt.custom_widgets import NavLabel
from portprotonqt.game_card import GameCard
from portprotonqt.config_utils import read_fullscreen_config, read_window_geometry, save_window_geometry

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
    stackedWidget: QStackedWidget
    tabButtons: dict[int, QWidget]
    gamesListWidget: QWidget
    currentDetailPage: QWidget | None
    current_exec_line: str | None
    current_add_game_dialog: QDialog | None  # Добавляем для отслеживания диалога

# Mapping of actions to evdev button codes, includes PlayStation, Xbox, and Switch controllers
BUTTONS = {
    'confirm':   {ecodes.BTN_A},
    'back':      {ecodes.BTN_B},
    'add_game':  {ecodes.BTN_Y},
    'prev_tab':  {ecodes.BTN_TL,    ecodes.BTN_TL2},
    'next_tab':  {ecodes.BTN_TR,    ecodes.BTN_TR2},
    'confirm_stick': {ecodes.BTN_THUMBL, ecodes.BTN_THUMBR},
    'context_menu': {ecodes.BTN_START},
    'menu':      {ecodes.BTN_SELECT, ecodes.BTN_MODE},
}

class InputManager(QObject):
    """
    Manages input from gamepads and keyboards for navigating the application interface.
    Supports gamepad hotplugging, button and axis events, and keyboard event filtering
    for seamless UI interaction. Enables fullscreen mode when a gamepad is connected
    and restores normal mode when disconnected.
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

    @Slot(bool)
    def handle_fullscreen_slot(self, enable: bool) -> None:
        try:
            if read_fullscreen_config():
                return
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

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        app = QApplication.instance()
        if not app:
            return super().eventFilter(obj, event)

        # Handle only key press events
        if not (isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress):
            return super().eventFilter(obj, event)

        key = event.key()
        modifiers = event.modifiers()
        focused = QApplication.focusWidget()
        popup = QApplication.activePopupWidget()

        # Close application with Ctrl+Q
        if key == Qt.Key.Key_Q and modifiers & Qt.KeyboardModifier.ControlModifier:
            app.quit()
            return True

        # Закрытие AddGameDialog на Esc
        if key == Qt.Key.Key_Escape and isinstance(popup, QDialog):
            popup.reject()  # Закрываем диалог
            return True

        # Skip navigation keys if a popup is open
        if popup:
            return False

        # FullscreenDialog navigation
        active_win = QApplication.activeWindow()
        if isinstance(active_win, FullscreenDialog):
            if key == Qt.Key.Key_Right:
                active_win.show_next()
                return True
            if key == Qt.Key.Key_Left:
                active_win.show_prev()
                return True
            if key in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Backspace):
                active_win.close()
                return True

        # Launch/stop game on detail page
        if self._parent.currentDetailPage and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._parent.current_exec_line:
                self._parent.toggleGame(self._parent.current_exec_line, None)
                return True

        # Context menu for GameCard
        if isinstance(focused, GameCard):
            if key == Qt.Key.Key_F10 and Qt.KeyboardModifier.ShiftModifier:
                pos = QPoint(focused.width() // 2, focused.height() // 2)
                focused._show_context_menu(pos)
                return True

        # Navigation in Library tab
        if self._parent.stackedWidget.currentIndex() == 0:
            game_cards = self._parent.gamesListWidget.findChildren(GameCard)
            scroll_area = self._parent.gamesListWidget.parentWidget()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parentWidget()

            if isinstance(focused, GameCard):
                current_index = game_cards.index(focused) if focused in game_cards else -1
                if key == Qt.Key.Key_Down:
                    if current_index >= 0 and current_index + 1 < len(game_cards):
                        next_card = game_cards[current_index + 1]
                        next_card.setFocus()
                        if scroll_area:
                            scroll_area.ensureWidgetVisible(next_card, 50, 50)
                        return True
                elif key == Qt.Key.Key_Up:
                    if current_index > 0:
                        prev_card = game_cards[current_index - 1]
                        prev_card.setFocus()
                        if scroll_area:
                            scroll_area.ensureWidgetVisible(prev_card, 50, 50)
                        return True
                    elif current_index == 0:
                        self._parent.tabButtons[0].setFocus()
                        return True
                elif key == Qt.Key.Key_Left:
                    if current_index > 0:
                        prev_card = game_cards[current_index - 1]
                        prev_card.setFocus()
                        if scroll_area:
                            scroll_area.ensureWidgetVisible(prev_card, 50, 50)
                        return True
                elif key == Qt.Key.Key_Right:
                    if current_index >= 0 and current_index + 1 < len(game_cards):
                        next_card = game_cards[current_index + 1]
                        next_card.setFocus()
                        if scroll_area:
                            scroll_area.ensureWidgetVisible(next_card, 50, 50)
                        return True

        # Tab switching with Left/Right keys
        idx = self._parent.stackedWidget.currentIndex()
        total = len(self._parent.tabButtons)
        if key == Qt.Key.Key_Left and not isinstance(focused, GameCard):
            new = (idx - 1) % total
            self._parent.switchTab(new)
            self._parent.tabButtons[new].setFocus()
            return True
        if key == Qt.Key.Key_Right and not isinstance(focused, GameCard):
            new = (idx + 1) % total
            self._parent.switchTab(new)
            self._parent.tabButtons[new].setFocus()
            return True

        # Navigate down into tab content
        if key == Qt.Key.Key_Down:
            if isinstance(focused, NavLabel):
                page = self._parent.stackedWidget.currentWidget()
                focusables = page.findChildren(QWidget, options=Qt.FindChildOption.FindChildrenRecursively)
                focusables = [w for w in focusables if w.focusPolicy() & Qt.FocusPolicy.StrongFocus]
                if focusables:
                    focusables[0].setFocus()
                    return True
            else:
                if focused is not None:
                    focused.focusNextChild()
                    return True

        # Navigate up through tab content
        if key == Qt.Key.Key_Up:
            if isinstance(focused, NavLabel):
                return True
            if focused is not None:
                focused.focusPreviousChild()
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
            self._parent.openAddGameDialog()
            return True

        # Toggle fullscreen with F11
        if key == Qt.Key.Key_F11:
            if read_fullscreen_config():
                return True
            self.toggle_fullscreen.emit(not self._is_fullscreen)
            return True

        return super().eventFilter(obj, event)

    def init_gamepad(self) -> None:
        self.check_gamepad()
        threading.Thread(target=self.run_udev_monitor, daemon=True).start()
        logger.info("Gamepad support initialized with hotplug (evdev + pyudev)")

    def run_udev_monitor(self) -> None:
        try:
            context = pyudev.Context()
            monitor = pyudev.Monitor.from_netlink(context)
            monitor.filter_by(subsystem='input')
            observer = pyudev.MonitorObserver(monitor, self.handle_udev_event)
            observer.start()
            while self.running:
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error in udev monitor: {e}", exc_info=True)

    def handle_udev_event(self, action: str, device: pyudev.Device) -> None:
        try:
            if action == 'add':
                time.sleep(0.1)
                self.check_gamepad()
            elif action == 'remove' and self.gamepad:
                if not any(self.gamepad.path == path for path in list_devices()):
                    logger.info("Gamepad disconnected")
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
                self.gamepad = new_gamepad
                if self.gamepad_thread:
                    self.gamepad_thread.join()
                self.gamepad_thread = threading.Thread(target=self.monitor_gamepad, daemon=True)
                self.gamepad_thread.start()
                # Signal to enter fullscreen mode
                self.toggle_fullscreen.emit(True)
        except Exception as e:
            logger.error(f"Error checking gamepad: {e}", exc_info=True)

    def find_gamepad(self) -> InputDevice | None:
        try:
            devices = [InputDevice(path) for path in list_devices()]
            for device in devices:
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
                if event.type == ecodes.EV_KEY and event.value == 1:
                    self.button_pressed.emit(event.code)
                elif event.type == ecodes.EV_ABS:
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
                    self.gamepad.close()
                except Exception:
                    pass
            self.gamepad = None

    @Slot(int)
    def handle_button_slot(self, button_code: int) -> None:
        try:
            # Игнорировать события геймпада, если игра запущена
            if getattr(self._parent, '_gameLaunched', False):
                return

            app = QApplication.instance()
            if not app:
                return
            active = QApplication.activeWindow()
            focused = QApplication.focusWidget()

            # Закрытие AddGameDialog на кнопку B
            if button_code in BUTTONS['back'] and isinstance(active, QDialog):
                active.reject()  # Закрываем диалог
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
                    focused._show_context_menu(pos)
                    return

            # Game launch on detail page
            if (button_code in BUTTONS['confirm'] or button_code in BUTTONS['confirm_stick']) and self._parent.currentDetailPage is not None:
                if self._parent.current_exec_line:
                    self._parent.toggleGame(self._parent.current_exec_line, None)
                    return

            # Standard navigation
            if button_code in BUTTONS['confirm'] or button_code in BUTTONS['confirm_stick']:
                self._parent.activateFocusedWidget()
            elif button_code in BUTTONS['back'] or button_code in BUTTONS['menu']:
                self._parent.goBackDetailPage(getattr(self._parent, 'currentDetailPage', None))
            elif button_code in BUTTONS['add_game']:
                self._parent.openAddGameDialog()
            elif button_code in BUTTONS['prev_tab']:
                idx = (self._parent.stackedWidget.currentIndex() - 1) % len(self._parent.tabButtons)
                self._parent.switchTab(idx)
                self._parent.tabButtons[idx].setFocus(Qt.FocusReason.OtherFocusReason)
            elif button_code in BUTTONS['next_tab']:
                idx = (self._parent.stackedWidget.currentIndex() + 1) % len(self._parent.tabButtons)
                self._parent.switchTab(idx)
                self._parent.tabButtons[idx].setFocus(Qt.FocusReason.OtherFocusReason)
        except Exception as e:
            logger.error(f"Error in handle_button_slot: {e}", exc_info=True)

    @Slot(int, int, float)
    def handle_dpad_slot(self, code: int, value: int, current_time: float) -> None:
        try:
            # Игнорировать события геймпада, если игра запущена
            if getattr(self._parent, '_gameLaunched', False):
                return

            app = QApplication.instance()
            if not app:
                return
            active = QApplication.activeWindow()

            # Fullscreen horizontal
            if isinstance(active, FullscreenDialog) and code == ecodes.ABS_HAT0X:
                if value < 0:
                    active.show_prev()
                elif value > 0:
                    active.show_next()
                return

            # Vertical navigation (DPAD up/down)
            if code == ecodes.ABS_HAT0Y:
                if value == 0:
                    return
                focused = QApplication.focusWidget()
                page = self._parent.stackedWidget.currentWidget()
                if value > 0:
                    if isinstance(focused, NavLabel):
                        focusables = page.findChildren(QWidget, options=Qt.FindChildOption.FindChildrenRecursively)
                        focusables = [w for w in focusables if w.focusPolicy() & Qt.FocusPolicy.StrongFocus]
                        if focusables:
                            focusables[0].setFocus()
                            return
                    elif focused:
                        focused.focusNextChild()
                        return
                elif value < 0 and focused:
                    focused.focusPreviousChild()
                    return

            # Horizontal wrap navigation repeat logic
            if code != ecodes.ABS_HAT0X:
                return
            if value == 0:
                self.axis_moving = False
                self.current_axis_delay = self.initial_axis_move_delay
                return
            if not self.axis_moving:
                self.trigger_dpad_movement(code, value)
                self.last_move_time = current_time
                self.axis_moving = True
            elif current_time - self.last_move_time >= self.current_axis_delay:
                self.trigger_dpad_movement(code, value)
                self.last_move_time = current_time
                self.current_axis_delay = self.repeat_axis_move_delay
        except Exception as e:
            logger.error(f"Error in handle_dpad_slot: {e}", exc_info=True)

    def trigger_dpad_movement(self, code: int, value: int) -> None:
        try:
            if code != ecodes.ABS_HAT0X:
                return
            idx = self._parent.stackedWidget.currentIndex()
            if value < 0:
                new = (idx - 1) % len(self._parent.tabButtons)
            else:
                new = (idx + 1) % len(self._parent.tabButtons)
            self._parent.switchTab(new)
            self._parent.tabButtons[new].setFocus(Qt.FocusReason.OtherFocusReason)
        except Exception as e:
            logger.error(f"Error in trigger_dpad_movement: {e}", exc_info=True)

    def cleanup(self) -> None:
        try:
            self.running = False
            if self.gamepad_thread:
                self.gamepad_thread.join()
            if self.gamepad:
                self.gamepad.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
