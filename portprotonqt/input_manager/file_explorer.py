import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLineEdit,
    QMenu,
    QPushButton,
    QTableWidget,
    QWidget,
)

from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.input_manager.constants import (
    BUTTONS,
    PAD_AXIS_LEFT_X,
    PAD_AXIS_LEFT_Y,
    PAD_DPAD_X,
    PAD_DPAD_Y,
)
from portprotonqt.logger import get_logger
from portprotonqt.input_manager.mixin import InputMixin
from portprotonqt.virtual_keyboard import VirtualKeyboard

logger = get_logger(__name__)


class FileExplorerInputMixin(InputMixin):
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
                self._handle_default_button(button_code, value)

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
                if code == PAD_DPAD_X and value == 0:
                    return

                is_drive_button = (
                    isinstance(focused_widget, AutoSizeButton) and
                    focused_widget in self.file_explorer.drive_buttons
                )
                if code == PAD_AXIS_LEFT_X:
                    if abs(value) < self.dead_zone or not is_drive_button:
                        return
                    value = 1 if value > self.dead_zone else -1

                if not is_drive_button:
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
                    if code == PAD_DPAD_Y and value > 0 and self.file_explorer.file_list.count() > 0:
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
            else:
                self._handle_default_dpad(code, value, current_time)

        except Exception as e:
            logger.error(f"Error in FileExplorer dpad handler: {e}")
