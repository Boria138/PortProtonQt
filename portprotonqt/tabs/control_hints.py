"""Main window control hints mixin."""

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStackedWidget, QWidget

from portprotonqt.custom_widgets import FlowLayout
from portprotonqt.input_manager import GamepadType
from portprotonqt.localization import _
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

GAMEPAD_HINT_ACTIONS = ("confirm", "back", "add_game", "search", "decrease_size", "increase_size", "context_menu", "menu", "guide_select", "mouse_emulation", "prev_section", "next_section")
COMBINATION_HINT_ACTIONS = ("guide_select", "mouse_emulation")
VOLUME_HINT_ACTIONS = ("decrease_size", "increase_size")


class MainWindowControlHintsMixin:
    """Provide control hints and navigation icon logic for main window."""

    theme: Any
    theme_manager: Any
    input_manager: Any
    stackedWidget: QStackedWidget
    leftNavButton: QLabel
    rightNavButton: QLabel
    current_theme_name: str
    system_tab_index: int
    hintsLabels: list[tuple[QWidget, Any, str | None]]
    gamepadHintTextLabels: dict[str, QLabel]
    gamepadHintDefaultTexts: dict[str, str]
    gamepadHintContainers: dict[str, QWidget]

    def get_button_icon(self, action: str, gtype: GamepadType) -> str:
        """Get the icon name for a specific action and gamepad type."""
        mappings = {
            'confirm': {
                GamepadType.XBOX: "xbox_a",
                GamepadType.PLAYSTATION: "ps_cross",
            },
            'back': {
                GamepadType.XBOX: "xbox_b",
                GamepadType.PLAYSTATION: "ps_circle",
            },
            'add_game': {
                GamepadType.XBOX: "xbox_x",
                GamepadType.PLAYSTATION: "ps_triangle",
            },
            'context_menu': {
                GamepadType.XBOX: "xbox_start",
                GamepadType.PLAYSTATION: "ps_options",
            },
            'menu': {
                GamepadType.XBOX: "xbox_view",
                GamepadType.PLAYSTATION: "ps_share",
            },
            'search': {
                GamepadType.XBOX: "xbox_y",
                GamepadType.PLAYSTATION: "ps_square",
            },
            'decrease_size': {
                GamepadType.XBOX: "xbox_lt",
                GamepadType.PLAYSTATION: "ps_l2",
            },
            'increase_size': {
                GamepadType.XBOX: "xbox_rt",
                GamepadType.PLAYSTATION: "ps_r2",
            },
            'prev_dir': {
                GamepadType.XBOX: "xbox_y",
                GamepadType.PLAYSTATION: "ps_square",
            },
            'guide_select': {
                GamepadType.XBOX: "xbox_xbox",
                GamepadType.PLAYSTATION: "ps_ps",
            },
            'prev_section': {
                GamepadType.XBOX: "dpad_left",
                GamepadType.PLAYSTATION: "dpad_left",
            },
            'next_section': {
                GamepadType.XBOX: "dpad_right",
                GamepadType.PLAYSTATION: "dpad_right",
            },
        }
        return mappings.get(action, {}).get(gtype, "placeholder")

    def get_nav_icon(self, direction: str, gtype: GamepadType) -> str:
        """Get the icon name for navigation direction and gamepad type."""
        if direction == 'left':
            action = 'prev_tab'
        else:
            action = 'next_tab'
        mappings = {
            'prev_tab': {
                GamepadType.XBOX: "xbox_lb",
                GamepadType.PLAYSTATION: "ps_l1",
            },
            'next_tab': {
                GamepadType.XBOX: "xbox_rb",
                GamepadType.PLAYSTATION: "ps_r1",
            },
        }
        return mappings.get(action, {}).get(gtype, "placeholder")

    def createControlHintsWidget(self) -> QWidget:
        """Create a widget displaying control hints for gamepad and keyboard."""
        logger.debug("Creating control hints widget")
        hintsWidget = QWidget()
        hintsWidget.setStyleSheet(self.theme.STATUS_BAR_STYLE)

        hintsLayout = FlowLayout(hintsWidget)
        hintsLayout.setContentsMargins(10, 0, 10, 0)

        gamepad_actions = [
            ("confirm", _("Select")),
            ("back", _("Back")),
            ("add_game", _("Add Game")),
            ("decrease_size", _("Volume") + " -"),
            ("increase_size", _("Volume") + " +"),
            ("context_menu", _("Menu")),
            ("menu", _("Fullscreen")),
            ("search", _("Search")),
            ("guide_select", _("Refresh Grid")),
            ("mouse_emulation", _("Mouse Emulation")),
            ("prev_section", _("Prev Tab")),
            ("next_section", _("Next Tab")),
        ]

        keyboard_hints = [
            ("key_enter", _("Select")),
            ("key_backspace", _("Back")),
            ("key_e", _("Add Game")),
            ("key_context", _("Menu")),
            ("key_f11", _("Fullscreen")),
            ("key_f5", _("Refresh Grid")),
        ]

        self.hintsLabels = []
        self.gamepadHintTextLabels = {}
        self.gamepadHintDefaultTexts = {}
        self.gamepadHintContainers = {}

        def makeHint(icon_name: str, action_text: str, is_gamepad: bool, action: str | None = None):
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 5, 0, 0)
            layout.setSpacing(6)

            icon_label = QLabel()
            icon_label.setFixedSize(26, 26)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            pixmap = QPixmap()
            for candidate in (
                self.theme_manager.get_theme_image(icon_name, self.current_theme_name),
                self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
            ):
                if candidate is not None and pixmap.load(str(candidate)):
                    break

            if not pixmap.isNull():
                icon_label.setPixmap(
                    pixmap.scaled(
                        26,
                        26,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

            layout.addWidget(icon_label)

            text_label = QLabel(action_text)
            text_label.setStyleSheet(self.theme.LAST_LAUNCH_VALUE_STYLE)
            text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(text_label)

            if is_gamepad:
                container.setVisible(False)
                self.hintsLabels.append((container, icon_label, action))
                if action is not None:
                    self.gamepadHintContainers[action] = container
                    self.gamepadHintTextLabels[action] = text_label
                    self.gamepadHintDefaultTexts[action] = action_text
            else:
                container.setVisible(True)
                self.hintsLabels.append((container, icon_label, None))

            hintsLayout.addWidget(container)

        def makeCombinationHint(action_text: str, action: str | None = None):
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 5, 0, 0)
            layout.setSpacing(6)

            guide_icon = QLabel()
            guide_icon.setFixedSize(26, 26)
            guide_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            pixmap = QPixmap()
            for candidate in (
                self.theme_manager.get_theme_image("xbox_xbox", self.current_theme_name),
                self.theme_manager.get_theme_image("ps_ps", self.current_theme_name),
                self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
            ):
                if candidate is not None and pixmap.load(str(candidate)):
                    break

            if not pixmap.isNull():
                guide_icon.setPixmap(
                    pixmap.scaled(
                        26,
                        26,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

            layout.addWidget(guide_icon)

            plus_icon = QLabel()
            plus_icon.setFixedSize(26, 26)
            plus_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            plus_pixmap = QPixmap()
            for candidate in (
                self.theme_manager.get_theme_image("key_+", self.current_theme_name),
                self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
            ):
                if candidate is not None and plus_pixmap.load(str(candidate)):
                    break

            if not plus_pixmap.isNull():
                plus_icon.setPixmap(
                    plus_pixmap.scaled(
                        26,
                        26,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

            layout.addWidget(plus_icon)

            select_icon = QLabel()
            select_icon.setFixedSize(26, 26)
            select_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            if action == "mouse_emulation":
                pixmap2 = QPixmap()
                for candidate in (
                    self.theme_manager.get_theme_image("xbox_start", self.current_theme_name),
                    self.theme_manager.get_theme_image("ps_options", self.current_theme_name),
                    self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
                ):
                    if candidate is not None and pixmap2.load(str(candidate)):
                        break
            else:
                pixmap2 = QPixmap()
                for candidate in (
                    self.theme_manager.get_theme_image("xbox_view", self.current_theme_name),
                    self.theme_manager.get_theme_image("ps_share", self.current_theme_name),
                    self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
                ):
                    if candidate is not None and pixmap2.load(str(candidate)):
                        break

            if not pixmap2.isNull():
                select_icon.setPixmap(
                    pixmap2.scaled(
                        26,
                        26,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

            layout.addWidget(select_icon)

            text_label = QLabel(action_text)
            text_label.setStyleSheet(self.theme.LAST_LAUNCH_VALUE_STYLE)
            text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(text_label)

            container.setVisible(False)
            self.hintsLabels.append((container, [guide_icon, plus_icon, select_icon], action))
            if action is not None:
                self.gamepadHintContainers[action] = container
                self.gamepadHintTextLabels[action] = text_label
                self.gamepadHintDefaultTexts[action] = action_text

            hintsLayout.addWidget(container)

        for action, text in gamepad_actions:
            if action in COMBINATION_HINT_ACTIONS:
                makeCombinationHint(text, action)
            else:
                makeHint("placeholder", text, True, action)

        for icon, text in keyboard_hints:
            makeHint(icon, text, False)

        return hintsWidget

    def updateNavButtons(self, *args) -> None:
        """Update navigation buttons based on gamepad connection status and type."""
        is_gamepad_connected = self.input_manager.gamepad is not None
        gtype = self.input_manager.gamepad_type
        logger.debug(
            "Updating nav buttons, gamepad connected: %s, type: %s",
            is_gamepad_connected,
            gtype.value,
        )

        left_pix = QPixmap()
        if is_gamepad_connected:
            left_icon_name = self.get_nav_icon('left', gtype)
        else:
            left_icon_name = "key_left"
        left_icon = self.theme_manager.get_theme_image(left_icon_name, self.current_theme_name)
        if left_icon:
            left_pix.load(str(left_icon))
        if not left_pix.isNull():
            self.leftNavButton.setPixmap(
                left_pix.scaled(
                    32,
                    32,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self.leftNavButton.setVisible(True)

        right_pix = QPixmap()
        if is_gamepad_connected:
            right_icon_name = self.get_nav_icon('right', gtype)
        else:
            right_icon_name = "key_right"
        right_icon = self.theme_manager.get_theme_image(right_icon_name, self.current_theme_name)
        if right_icon:
            right_pix.load(str(right_icon))
        if not right_pix.isNull():
            self.rightNavButton.setPixmap(
                right_pix.scaled(
                    32,
                    32,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self.rightNavButton.setVisible(True)

    def updateControlHints(self, *args) -> None:
        """Update control hints based on gamepad connection status and type."""
        if not hasattr(self, "hintsLabels"):
            return
        is_gamepad_connected = self.input_manager.gamepad is not None
        gtype = self.input_manager.gamepad_type
        current_tab_index = self.stackedWidget.currentIndex()
        system_section_index = -1
        section_stack = getattr(self, "systemSectionStack", None)
        if isinstance(section_stack, QStackedWidget):
            system_section_index = section_stack.currentIndex()
        hints_state = (
            is_gamepad_connected,
            gtype.value,
            current_tab_index,
            system_section_index,
            getattr(self, "current_theme_name", ""),
        )
        if hints_state == getattr(self, "_last_control_hints_state", None):
            return
        self._last_control_hints_state = hints_state

        on_system_tab = self.stackedWidget.currentIndex() == getattr(self, "system_tab_index", -1)
        logger.debug(
            "Updating control hints, gamepad connected: %s, type: %s",
            is_gamepad_connected,
            gtype.value,
        )

        for container, icon_element, action in self.hintsLabels:
            if action in GAMEPAD_HINT_ACTIONS:
                if is_gamepad_connected:
                    if action in ("prev_section", "next_section"):
                        container.setVisible(False)
                    elif not on_system_tab:
                        container.setVisible(True)
                    if (
                        isinstance(icon_element, list)
                        and len(icon_element) == 3
                        and action in COMBINATION_HINT_ACTIONS
                    ):
                        guide_icon, plus_icon, select_icon = icon_element

                        if gtype == GamepadType.XBOX:
                            guide_icon_name = "xbox_xbox"
                        elif gtype == GamepadType.PLAYSTATION:
                            guide_icon_name = "ps_ps"
                        else:
                            guide_icon_name = "xbox_xbox"

                        guide_pixmap = QPixmap()
                        for candidate in (
                            self.theme_manager.get_theme_image(guide_icon_name, self.current_theme_name),
                            self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
                        ):
                            if candidate is not None and guide_pixmap.load(str(candidate)):
                                break

                        if not guide_pixmap.isNull():
                            guide_icon.setPixmap(
                                guide_pixmap.scaled(
                                    26,
                                    26,
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation,
                                )
                            )

                        plus_pixmap = QPixmap()
                        for candidate in (
                            self.theme_manager.get_theme_image("key_+", self.current_theme_name),
                            self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
                        ):
                            if candidate is not None and plus_pixmap.load(str(candidate)):
                                break

                        if not plus_pixmap.isNull():
                            plus_icon.setPixmap(
                                plus_pixmap.scaled(
                                    26,
                                    26,
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation,
                                )
                            )

                        select_icon_name = "xbox_view"
                        if action == "guide_select":
                            if gtype == GamepadType.XBOX:
                                select_icon_name = "xbox_view"
                            elif gtype == GamepadType.PLAYSTATION:
                                select_icon_name = "ps_share"
                        elif action == "mouse_emulation":
                            if gtype == GamepadType.XBOX:
                                select_icon_name = "xbox_start"
                            elif gtype == GamepadType.PLAYSTATION:
                                select_icon_name = "ps_options"
                            else:
                                select_icon_name = "xbox_start"

                        select_pixmap = QPixmap()
                        for candidate in (
                            self.theme_manager.get_theme_image(select_icon_name, self.current_theme_name),
                            self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
                        ):
                            if candidate is not None and select_pixmap.load(str(candidate)):
                                break

                        if not select_pixmap.isNull():
                            select_icon.setPixmap(
                                select_pixmap.scaled(
                                    26,
                                    26,
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation,
                                )
                            )
                    else:
                        if isinstance(icon_element, list):
                            logger.warning(
                                "Unexpected list found for single-icon hint with action: %s",
                                action,
                            )
                            continue
                        icon_label = icon_element
                        icon_name = self.get_button_icon(action, gtype)
                        icon_path = self.theme_manager.get_theme_image(icon_name, self.current_theme_name)
                        pixmap = QPixmap()
                        if icon_path:
                            pixmap.load(str(icon_path))
                        if not pixmap.isNull():
                            icon_label.setPixmap(
                                pixmap.scaled(
                                    26,
                                    26,
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation,
                                )
                            )
                        else:
                            placeholder = self.theme_manager.get_theme_image(
                                "placeholder",
                                self.current_theme_name,
                            )
                            if placeholder:
                                pixmap.load(str(placeholder))
                                icon_label.setPixmap(
                                    pixmap.scaled(
                                        26,
                                        26,
                                        Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                )
                else:
                    container.setVisible(False)
            else:
                container.setVisible(not is_gamepad_connected and not on_system_tab)

        self._updateSystemGamepadHintTexts()
        self.updateNavButtons()

    def _setGamepadHintText(self, action: str, text: str) -> None:
        label = getattr(self, "gamepadHintTextLabels", {}).get(action)
        if label is not None:
            label.setText(text)

    def _setGamepadHintVisible(self, action: str, visible: bool) -> None:
        container = getattr(self, "gamepadHintContainers", {}).get(action)
        if container is not None:
            container.setVisible(visible)

    def _updateSystemGamepadHintTexts(self) -> None:
        default_texts = getattr(self, "gamepadHintDefaultTexts", {})
        if not default_texts:
            return
        for action, text in default_texts.items():
            self._setGamepadHintText(action, text)
        for action in VOLUME_HINT_ACTIONS:
            self._setGamepadHintVisible(action, False)

        if self.stackedWidget.currentIndex() != getattr(self, "system_tab_index", -1):
            return

        for action in GAMEPAD_HINT_ACTIONS:
            self._setGamepadHintVisible(action, False)

        if self.input_manager.gamepad is None:
            return

        self._setGamepadHintVisible("prev_section", True)
        self._setGamepadHintVisible("next_section", True)

        section_stack = getattr(self, "systemSectionStack", None)
        if not isinstance(section_stack, QStackedWidget):
            return

        section_index = section_stack.currentIndex()
        wifi_index = getattr(self, "systemSectionWifiIndex", -1)
        vpn_index = getattr(self, "systemSectionVpnIndex", -1)
        bluetooth_index = getattr(self, "systemSectionBluetoothIndex", -1)
        storage_index = getattr(self, "systemSectionStorageIndex", -1)
        audio_index = getattr(self, "systemSectionAudioIndex", -1)

        if section_index == wifi_index:
            self._setGamepadHintVisible("confirm", True)
            self._setGamepadHintVisible("back", True)
            self._setGamepadHintVisible("add_game", True)
            self._setGamepadHintText("confirm", _("Connect"))
            self._setGamepadHintText("back", _("Disconnect"))
            self._setGamepadHintText("add_game", _("Enable/Disable"))
            return
        if section_index == vpn_index:
            self._setGamepadHintVisible("confirm", True)
            self._setGamepadHintVisible("back", True)
            self._setGamepadHintVisible("add_game", True)
            self._setGamepadHintText("confirm", _("Connect"))
            self._setGamepadHintText("back", _("Disconnect"))
            self._setGamepadHintText("add_game", _("Add VPN"))
            return
        if section_index == bluetooth_index:
            self._setGamepadHintVisible("confirm", True)
            self._setGamepadHintVisible("back", True)
            self._setGamepadHintVisible("add_game", True)
            self._setGamepadHintVisible("search", True)
            self._setGamepadHintText("confirm", _("Connect"))
            self._setGamepadHintText("back", _("Disconnect"))
            self._setGamepadHintText("add_game", _("Enable/Disable"))
            self._setGamepadHintText("search", _("Scan"))
            return
        if section_index == storage_index:
            self._setGamepadHintVisible("confirm", True)
            self._setGamepadHintVisible("back", True)
            self._setGamepadHintText("confirm", _("Mount"))
            self._setGamepadHintText("back", _("Unmount"))
            return
        if section_index == audio_index:
            self._setGamepadHintVisible("confirm", True)
            self._setGamepadHintVisible("decrease_size", True)
            self._setGamepadHintVisible("increase_size", True)
            self._setGamepadHintText("confirm", _("Set output"))
            return
