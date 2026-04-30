"""Detail pages for PortProtonQt."""

import os
import shlex
from collections.abc import Callable
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QMessageBox,
    QScrollArea,
    QBoxLayout,
)
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QDesktopServices

from portprotonqt.detail_pages.widgets import (
    create_scroll_area,
    create_back_button,
    create_content_frame,
    setup_adaptive_layout,
    create_cover_frame,
    create_protondb_badge,
    create_steam_badge,
    create_portproton_badge,
    create_anticheat_badge,
    create_details_widget,
    COVER_WIDTH,
    COVER_HEIGHT,
    ECONOMY_COVER_SIZE,
)
from portprotonqt.detail_pages.utils import (
    setup_image_loading,
    validate_detail_page,
    set_opacity_safe,
    create_focus_helper,
    toggle_favorite,
    check_autoinstall_installed,
)
from portprotonqt.howlongtobeat_api import HowLongToBeat, GameEntry
from portprotonqt.config import (
    favorites_config,
    get_portproton_start_command,
    ui_config,
)
from portprotonqt.custom_widgets import AutoSizeButton, ClickableLabel, FlowLayout
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.portproton_api import PortProtonAPI
from portprotonqt.downloader import Downloader
from portprotonqt.animations import DetailPageAnimations
from portprotonqt.debug_utils import DebugLogManager
from portprotonqt.steam_api import get_steam_compat_tool, get_steam_home, get_steam_libs, safe_vdf_load

logger = get_logger(__name__)


class DetailPageManager:
    """Manages detail pages for games."""

    def __init__(self, main_window) -> None:
        self.main_window = main_window
        self._detail_page_active = False
        self._current_detail_page: QWidget | None = None
        self._exit_animation_in_progress = False
        self._animations: dict = {}
        self.portproton_api = PortProtonAPI(Downloader(max_workers=4))
        self.debug_log_manager = DebugLogManager()
        self._debug_log_button: AutoSizeButton | None = None
        self._debug_log_timer = None

    def openGameDetailPage(self, game_data: dict) -> None:
        """Open detailed game information page."""
        detail_page = QWidget()
        economy_mode = self._is_economy_mode()
        cover_width = ECONOMY_COVER_SIZE if economy_mode else COVER_WIDTH
        cover_height = ECONOMY_COVER_SIZE if economy_mode else COVER_HEIGHT
        image_label = QLabel()
        image_label.setFixedSize(cover_width, cover_height)

        self._setup_detail_page_common(detail_page, image_label, 0)

        badges = self._create_game_badges(detail_page, game_data)
        cover_frame = create_cover_frame(
            parent=detail_page,
            theme=self.main_window.theme,
            image_label=image_label,
            favorite_label_text=self._get_favorite_text(game_data["name"]),
            on_favorite_click=lambda: self._on_favorite_click(game_data["name"]),
            badges=badges,
            cover_width=cover_width,
            cover_height=cover_height,
        )

        description = "" if economy_mode else game_data["description"]
        game_info_layout = self._create_game_info_layout(game_data)
        buttons_layout = self._create_game_buttons_layout(game_data)
        details_widget = create_details_widget(
            parent=detail_page,
            main_window=self.main_window,
            title=game_data["name"],
            description=description,
            game_info_layout=game_info_layout,
            controller_support=None if economy_mode else game_data.get("controller_support"),
            buttons_layout=buttons_layout,
            show_description=not economy_mode,
        )

        self._finalize_detail_page(
            detail_page, cover_frame, details_widget, image_label,
            game_data.get("exec_line", ""), game_data.get("cover_path")
        )

    def _get_favorite_text(self, name: str) -> str:
        return "★" if name in favorites_config.get_games() else "☆"

    def _is_economy_mode(self) -> bool:
        return ui_config.get_economy_mode()

    def _create_game_badges(self, parent: QWidget, game_data: dict) -> list:
        from portprotonqt.config import game_config

        if self._is_economy_mode():
            return []

        display_filter = game_config.get_display_filter()
        game_source = str(game_data.get("game_source", "")).lower()
        appid = game_data.get("appid", "")
        name = game_data.get("name", "")
        exec_line = game_data.get("exec_line", "")

        steam_visible = game_source == "steam" and display_filter in ("all", "favorites")
        portproton_visible = game_source == "portproton" and display_filter in ("all", "favorites")

        badges = []
        protondb_badge = self._create_protondb_badge(parent, game_data)
        if protondb_badge:
            badges.append(protondb_badge)
        if steam_visible:
            badges.append(self._create_steam_badge(parent, appid))
        if portproton_visible:
            badges.append(self._create_portproton_badge(parent, name, exec_line))
        anticheat_badge = self._create_anticheat_badge(parent, game_data)
        if anticheat_badge:
            badges.append(anticheat_badge)
        return badges

    def _create_protondb_badge(self, parent: QWidget, game_data: dict) -> dict | None:
        badge, visible = create_protondb_badge(
            parent, game_data.get("protondb_tier", ""), game_data.get("appid", ""),
            self.main_window
        )
        return {"label": badge, "visible": True} if badge and visible else None

    def _create_steam_badge(self, parent: QWidget, appid: str) -> dict:
        badge = create_steam_badge(parent, appid, self.main_window)
        return {"label": badge, "visible": True}

    def _create_portproton_badge(self, parent: QWidget, name: str, exec_line: str) -> dict:
        badge = create_portproton_badge(parent, lambda: self.portproton_api.open_ppdb_page(name, exec_line), self.main_window)
        return {"label": badge, "visible": True}

    def _create_anticheat_badge(self, parent: QWidget, game_data: dict) -> dict | None:
        badge, visible = create_anticheat_badge(
            parent,
            game_data.get("anticheat_status", ""),
            game_data.get("name", ""),
            game_data.get("anticheat_slug", ""),
            self.main_window
        )
        return {"label": badge, "visible": True} if badge and visible else None

    def _create_game_info_layout(self, game_data: dict) -> QVBoxLayout:
        game_info_layout = QVBoxLayout()
        game_info_layout.setSpacing(10)

        first_row = self._create_playtime_row(
            game_data.get("last_launch", ""), game_data.get("formatted_playtime", "")
        )
        game_info_layout.addLayout(first_row)

        hltb_layout = QHBoxLayout()
        hltb_layout.setSpacing(10)
        self._setup_hltb_data(game_data.get("name", ""), hltb_layout, game_info_layout)

        return game_info_layout

    def _create_playtime_row(self, last_launch: str, formatted_playtime: str) -> QHBoxLayout:
        """Create first row with last launch and playtime."""
        first_row = QHBoxLayout()
        first_row.setSpacing(10)

        last_launch_title = QLabel(_("LAST LAUNCH"))
        last_launch_title.setStyleSheet(self.main_window.theme.LAST_LAUNCH_TITLE_STYLE)
        last_launch_value = QLabel(last_launch)
        last_launch_value.setStyleSheet(self.main_window.theme.LAST_LAUNCH_VALUE_STYLE)

        playtime_title = QLabel(_("PLAY TIME"))
        playtime_title.setStyleSheet(self.main_window.theme.PLAY_TIME_TITLE_STYLE)
        playtime_value = QLabel(formatted_playtime)
        playtime_value.setStyleSheet(self.main_window.theme.PLAY_TIME_VALUE_STYLE)

        first_row.addWidget(last_launch_title)
        first_row.addWidget(last_launch_value)
        first_row.addSpacing(30)
        first_row.addWidget(playtime_title)
        first_row.addWidget(playtime_value)

        return first_row

    def _setup_hltb_data(
        self, name: str, hltb_layout: QHBoxLayout, game_info_layout: QVBoxLayout
    ) -> None:
        """Setup HowLongToBeat data loading."""
        if self._is_economy_mode():
            return
        hltb = HowLongToBeat(parent=self.main_window)

        def on_hltb_results(results: list) -> None:
            self._on_hltb_results(results, hltb, hltb_layout, game_info_layout)

        hltb.searchCompleted.connect(on_hltb_results)
        hltb.search_with_callback(name, case_sensitive=False)

    def _on_hltb_results(
        self,
        results: list,
        hltb: HowLongToBeat,
        hltb_layout: QHBoxLayout,
        game_info_layout: QVBoxLayout,
    ) -> None:
        """Handle HLTB search results."""
        if not self._detail_page_active or not self._current_detail_page:
            return
        if not self._current_detail_page.parent() or self._current_detail_page.isHidden():
            return

        if not results:
            return

        game = results[0]
        has_data = self._add_hltb_times(game, hltb, hltb_layout)

        if has_data:
            game_info_layout.addLayout(hltb_layout)

    def _add_hltb_times(
        self, game: GameEntry, hltb: HowLongToBeat, hltb_layout: QHBoxLayout
    ) -> bool:
        """Add HLTB time displays to layout."""
        self._add_hltb_time_field(game, hltb, hltb_layout, "main_story", _("MAIN STORY"))
        self._add_hltb_time_field(game, hltb, hltb_layout, "main_extra", _("MAIN + SIDES"))
        self._add_hltb_time_field(game, hltb, hltb_layout, "completionist", _("COMPLETIONIST"))
        return hltb_layout.count() > 0

    def _add_hltb_time_field(
        self,
        game: GameEntry,
        hltb: HowLongToBeat,
        layout: QHBoxLayout,
        field: str,
        title_text: str,
    ) -> None:
        """Add single HLTB time field to layout."""
        time_value = hltb.format_game_time(game, field)
        if not time_value:
            return

        title_style = self.main_window.theme.LAST_LAUNCH_TITLE_STYLE
        value_style = self.main_window.theme.LAST_LAUNCH_VALUE_STYLE

        if field == "main_extra":
            title_style = self.main_window.theme.PLAY_TIME_TITLE_STYLE
            value_style = self.main_window.theme.PLAY_TIME_VALUE_STYLE

        title = QLabel(title_text)
        title.setStyleSheet(title_style)
        value = QLabel(time_value)
        value.setStyleSheet(value_style)
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addSpacing(30)

    def _create_game_buttons_layout(self, game_data: dict) -> FlowLayout:
        """Create buttons layout for game detail page."""
        buttons_layout = FlowLayout(center_rows=False)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        exec_line = game_data.get("exec_line", "")
        game_source = game_data.get("game_source", "")
        appid = game_data.get("appid", "")
        game_name = game_data.get("name", "")
        cover_path = game_data.get("cover_path", "")

        current_exe = self._get_current_exe(exec_line)
        play_button = self._create_play_button(exec_line, current_exe)
        buttons_layout.addWidget(play_button)

        if self._has_game_shortcut(game_name):
            edit_button = self._make_action_button(
                _("Edit Game"),
                self.main_window.theme_manager.get_icon("edit"),
            )
            edit_button.clicked.connect(
                lambda: self.main_window.context_menu_manager.edit_game_shortcut(
                    game_name, exec_line, cover_path
                )
            )
            buttons_layout.addWidget(edit_button)
        elif str(game_source).lower() == "steam" and appid:
            open_folder_button = self._make_action_button(
                _("Open Game Folder"),
                self.main_window.theme_manager.get_icon("search"),
            )
            open_folder_button.clicked.connect(
                lambda: self._open_steam_game_folder(str(appid))
            )
            buttons_layout.addWidget(open_folder_button)
        else:
            add_button = self._make_action_button(
                _("Add Game"),
                self.main_window.theme_manager.get_icon("addgame"),
            )
            add_button.clicked.connect(
                lambda: self.main_window.openAddGameDialog(
                    self._get_file_from_exec(exec_line) or exec_line
                )
            )
            buttons_layout.addWidget(add_button)

        # Show settings button for PortProton games or Steam games using PortProtonQt
        if str(game_source).lower() == "portproton":
            self._add_portproton_buttons(buttons_layout, exec_line)
        elif str(game_source).lower() == "steam" and appid:
            try:
                compat_tool = get_steam_compat_tool(int(appid))
                if compat_tool == "PortProtonQt":
                    self._add_steam_settings_button(buttons_layout, exec_line, str(appid))
            except (ValueError, TypeError):
                pass

        return buttons_layout

    def _get_current_exe(self, exec_line: str) -> str | None:
        """Extract current executable from exec line."""
        entry_exec_split = shlex.split(exec_line)
        if not entry_exec_split:
            return None

        if "--silent" in entry_exec_split and len(entry_exec_split) >= 2:
            silent_index = entry_exec_split.index("--silent")
            file_to_check = entry_exec_split[silent_index + 1] if len(entry_exec_split) > silent_index + 1 else None
        else:
            file_to_check = entry_exec_split[0]

        return os.path.basename(file_to_check) if file_to_check else None

    def _create_play_button(self, exec_line: str, current_exe: str | None) -> AutoSizeButton:
        """Create play/stop button."""
        if self.main_window.target_exe is not None and current_exe == self.main_window.target_exe:
            text = _("Stop")
            icon = self.main_window.theme_manager.get_icon("stop")
        else:
            text = _("Play")
            icon = self.main_window.theme_manager.get_icon("play")

        play_button = self._make_action_button(text, icon)
        play_button.clicked.connect(lambda: self.main_window.toggleGame(exec_line, play_button))
        return play_button

    def _add_portproton_buttons(self, buttons_layout: FlowLayout, exec_line: str) -> None:
        """Add settings and log buttons for PortProton games."""
        file_to_check = self._get_file_from_exec(exec_line)

        settings_icon = self.main_window.theme_manager.get_icon("settings")
        settings_button = self._make_action_button(_("Settings"), settings_icon)
        settings_button.clicked.connect(
            lambda: self.main_window.open_exe_settings(file_to_check, game_source="portproton")
        )
        buttons_layout.addWidget(settings_button)

        log_icon = self.main_window.theme_manager.get_icon("edit")
        log_button = self._make_action_button(_("Create Log"), log_icon)
        log_button.clicked.connect(lambda: self.toggleDebugLog(file_to_check, log_button))
        buttons_layout.addWidget(log_button)
        self._debug_log_button = log_button

    def _add_steam_settings_button(self, buttons_layout: FlowLayout, exec_line: str, appid: str) -> None:
        """Add only settings button for Steam games."""
        # Create fake exe path in steam_scripts folder
        portproton_location = self.main_window.portproton_location
        if not portproton_location:
            return
        steam_scripts_dir = os.path.join(portproton_location, "steam_scripts")
        os.makedirs(steam_scripts_dir, exist_ok=True)
        fake_exe_path = os.path.join(steam_scripts_dir, f"{appid}.exe")
        # Create empty file if it doesn't exist
        if not os.path.exists(fake_exe_path):
            open(fake_exe_path, 'a').close()

        settings_icon = self.main_window.theme_manager.get_icon("settings")
        settings_button = self._make_action_button(_("Settings"), settings_icon)
        settings_button.clicked.connect(
            lambda: self.main_window.open_exe_settings(fake_exe_path, appid, "steam")
        )
        buttons_layout.addWidget(settings_button)

    def _get_file_from_exec(self, exec_line: str) -> str | None:
        """Get file path from exec line."""
        entry_exec_split = shlex.split(exec_line)
        if not entry_exec_split:
            return None

        if "--silent" in entry_exec_split and len(entry_exec_split) >= 2:
            silent_index = entry_exec_split.index("--silent")
            return entry_exec_split[silent_index + 1] if len(entry_exec_split) > silent_index + 1 else None
        return entry_exec_split[0]

    def _open_steam_game_folder(self, appid: str) -> None:
        """Open Steam game installation folder by appid."""
        steam_home = get_steam_home()
        if steam_home is None:
            return

        for lib in get_steam_libs(steam_home):
            manifest = lib / "steamapps" / f"appmanifest_{appid}.acf"
            if not manifest.exists():
                continue
            data = safe_vdf_load(manifest)
            install_dir = data.get("AppState", {}).get("installdir")
            if not install_dir:
                return
            folder_path = lib / "steamapps" / "common" / install_dir
            if not folder_path.exists():
                return
            linux_subdir = folder_path / f"{install_dir}_linux"
            if linux_subdir.exists():
                folder_path = linux_subdir
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_path)))
            return

    def _has_game_shortcut(self, game_name: str) -> bool:
        """Check whether game has a desktop shortcut in PortProton location."""
        context_menu_manager = getattr(self.main_window, "context_menu_manager", None)
        if context_menu_manager is None:
            return False
        desktop_path = context_menu_manager._get_desktop_path(game_name)
        return bool(desktop_path and os.path.exists(desktop_path))

    def _make_action_button(self, text: str, icon) -> AutoSizeButton:
        """Create styled action button."""
        button = AutoSizeButton(text, icon=icon)
        button.setFixedHeight(40)
        button.setMinimumWidth(120)
        button.setStyleSheet(self.main_window.theme.PLAY_BUTTON_STYLE)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        return button

    def _setup_detail_page_common(
        self, detail_page: QWidget, image_label: QLabel, return_tab_index: int
    ) -> None:
        """Common setup for all detail pages."""
        self._detail_page_active = True
        self._current_detail_page = detail_page
        self._return_to_tab_index = return_tab_index

        scroll_area, scroll_content, main_layout = create_scroll_area(
            detail_page, self.main_window.theme
        )

        create_back_button(
            main_layout,
            self.main_window.theme,
            self.main_window.theme_manager,
            lambda: self.goBackDetailPage(detail_page),
        )

        content_frame, content_frame_layout = create_content_frame(
            main_layout, self.main_window.theme
        )
        setup_adaptive_layout(detail_page, content_frame_layout)

        self.main_window.stackedWidget.addWidget(detail_page)
        self.main_window.stackedWidget.setCurrentWidget(detail_page)
        self.main_window.currentDetailPage = detail_page

    def _finalize_detail_page(
        self,
        detail_page: QWidget,
        cover_frame: QWidget,
        details_widget: QWidget,
        image_label: QLabel,
        exec_line: str,
        cover_path: str | None,
    ) -> None:
        """Finalize detail page setup with animations and focus."""
        content_frame_layout = self._get_content_frame_layout(detail_page)
        if content_frame_layout:
            content_frame_layout.addWidget(cover_frame)
            content_frame_layout.addWidget(details_widget)

        main_layout = self._get_main_layout(detail_page)
        if main_layout:
            main_layout.addStretch()

        self.main_window.current_exec_line = exec_line
        self._setup_detail_page_animation(detail_page, image_label, details_widget, cover_path)

    def _setup_detail_page_animation(
        self, detail_page: QWidget, image_label: QLabel, details_widget: QWidget, cover_path: str | None
    ) -> None:
        """Setup animation for detail page."""
        play_button = self._find_play_button(details_widget)

        def setup_focus() -> None:
            if play_button:
                self._setup_focus_after_animation(detail_page, play_button)

        self._start_detail_page_animation(
            detail_page, image_label, cover_path, setup_focus
        )

    def _get_content_frame_layout(self, detail_page: QWidget) -> QBoxLayout | None:
        """Get content frame layout from detail page."""
        scroll_area = detail_page.findChild(QScrollArea)
        if not scroll_area:
            return None
        scroll_content = scroll_area.widget()
        if not scroll_content or not scroll_content.layout():
            return None
        return self._find_content_layout_in_frame(scroll_content.layout())

    def _find_content_layout_in_frame(self, layout) -> QBoxLayout | None:
        """Find content layout inside frame."""
        for i in range(layout.count()):
            item = layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, QFrame):
                return self._find_box_layout_in_widget(widget)
        return None

    def _find_box_layout_in_widget(self, widget: QWidget) -> QBoxLayout | None:
        """Find QBoxLayout in widget children."""
        for child in widget.children():
            if isinstance(child, QBoxLayout):
                return child
        return None

    def _get_main_layout(self, detail_page: QWidget) -> QVBoxLayout | None:
        """Get main layout from detail page."""
        scroll_area = detail_page.findChild(QScrollArea)
        if not scroll_area:
            return None
        scroll_content = scroll_area.widget()
        if not scroll_content:
            return None
        layout = scroll_content.layout()
        return layout if isinstance(layout, QVBoxLayout) else None

    def _setup_focus_after_animation(self, detail_page: QWidget, play_button: QWidget) -> None:
        """Setup focus on play button after animation."""
        focus_helper = create_focus_helper(
            detail_page, self.main_window, play_button, self.main_window.stackedWidget
        )
        QTimer.singleShot(50, focus_helper)

    def _find_play_button(self, details_widget: QWidget) -> QWidget | None:
        """Find play button in details widget."""
        for child in details_widget.children():
            if isinstance(child, AutoSizeButton) and self._is_action_button_text(child.text()):
                return child
        return None

    def _is_action_button_text(self, text: str) -> bool:
        """Check if button text is Play or Stop."""
        return text in (_("Play"), _("Stop"))

    def _on_favorite_click(self, name: str) -> str:
        """Handle favorite toggle click."""
        return toggle_favorite(name, self.main_window)

    def openAutoInstallDetailPage(self, game_data: dict) -> None:
        """Open minimal detail page for auto-install games."""
        detail_page = QWidget()
        economy_mode = self._is_economy_mode()
        cover_width = ECONOMY_COVER_SIZE if economy_mode else COVER_WIDTH
        cover_height = ECONOMY_COVER_SIZE if economy_mode else COVER_HEIGHT
        image_label = QLabel()
        image_label.setFixedSize(cover_width, cover_height)

        self._setup_detail_page_common(detail_page, image_label, 1)

        exec_line = game_data.get("exec_line", "")
        script_name = self._extract_script_name(exec_line)
        description = self._get_enhanced_description(
            script_name, game_data.get("description", "")
        )

        cover_frame = create_cover_frame(
            parent=detail_page,
            theme=self.main_window.theme,
            image_label=image_label,
            cover_width=cover_width,
            cover_height=cover_height,
        )

        buttons_layout = FlowLayout(center_rows=False)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        install_button = self._create_autoinstall_buttons_layout(
            script_name, game_data.get("name", ""), buttons_layout
        )

        details_widget = create_details_widget(
            parent=detail_page,
            main_window=self.main_window,
            title=game_data.get("name", ""),
            description=description,
            buttons_layout=buttons_layout,
        )

        self._finalize_autoinstall_page(detail_page, cover_frame, details_widget, image_label, game_data.get("cover_path"), install_button)

    def _extract_script_name(self, exec_line: str) -> str:
        """Extract script name from exec line."""
        if exec_line and exec_line.startswith("autoinstall:"):
            return exec_line[11:].lstrip(":").strip()
        return ""

    def _get_enhanced_description(self, script_name: str, description: str) -> str:
        """Get enhanced description from metadata if available."""
        if not script_name:
            return description

        import locale

        try:
            current_locale = locale.getlocale()[0] or "en"
        except Exception as e:
            logger.debug("Failed to get current locale: %s", e)
            current_locale = "en"

        lang_code = "ru" if current_locale and "ru" in current_locale.lower() else "en"
        metadata_description = self.portproton_api.get_autoinstall_description(
            script_name, lang_code
        )
        return metadata_description if metadata_description else description

    def _create_autoinstall_buttons_layout(
        self, script_name: str, name: str, buttons_layout: FlowLayout
    ) -> AutoSizeButton:
        """Create install button for auto-install page."""
        install_button = self._make_action_button(_("Install"), self.main_window.theme_manager.get_icon("save"))
        install_button.clicked.connect(lambda: self.main_window.launch_autoinstall(script_name))
        buttons_layout.addWidget(install_button)

        self._check_install_status(script_name, name, install_button)

        return install_button

    def _check_install_status(
        self, script_name: str, name: str, install_button: AutoSizeButton
    ) -> None:
        """Check install status asynchronously and update button."""
        def on_result(is_installed: bool) -> None:
            text = _("Reinstall") if is_installed else _("Install")
            icon_name = "update" if is_installed else "save"
            icon = self.main_window.theme_manager.get_icon(icon_name)
            if icon:
                install_button.setIcon(icon)
            # Update text without changing button size drastically
            install_button.setText(text)

        check_autoinstall_installed(
            script_name, name, self.main_window.portproton_location, callback=on_result
        )

    def _finalize_autoinstall_page(
        self,
        detail_page: QWidget,
        cover_frame: QWidget,
        details_widget: QWidget,
        image_label: QLabel,
        cover_path: str | None,
        install_button: AutoSizeButton,
    ) -> None:
        """Finalize auto-install detail page."""
        content_frame_layout = self._get_content_frame_layout(detail_page)
        if content_frame_layout:
            content_frame_layout.addWidget(cover_frame)
            content_frame_layout.addWidget(details_widget)

        main_layout = self._get_main_layout(detail_page)
        if main_layout:
            main_layout.addStretch()

        self._setup_autoinstall_animation(detail_page, image_label, cover_path, install_button)

    def _setup_autoinstall_animation(self, detail_page: QWidget, image_label: QLabel, cover_path: str | None, install_button: AutoSizeButton) -> None:
        """Setup animation for auto-install page."""
        self._start_detail_page_animation(
            detail_page,
            image_label,
            cover_path,
            lambda: self._setup_autoinstall_focus(detail_page, install_button),
        )

    def _start_detail_page_animation(
        self,
        detail_page: QWidget,
        image_label: QLabel,
        cover_path: str | None,
        setup_focus: Callable[[], None],
    ) -> None:
        """Start detail page animation and image loading."""
        setup_image_loading(
            detail_page,
            image_label,
            cover_path,
            self.main_window,
            image_label.width(),
            image_label.height(),
        )

        def restore_after_animation() -> None:
            if not validate_detail_page(detail_page):
                return
            if not set_opacity_safe(detail_page):
                return
            setup_focus()

        def cleanup_animation() -> None:
            if detail_page in self._animations:
                del self._animations[detail_page]

        detail_animations = DetailPageAnimations(self.main_window, self.main_window.theme)
        detail_animations.animate_detail_page(
            detail_page, restore_after_animation, cleanup_animation
        )

    def _setup_autoinstall_focus(self, detail_page: QWidget, install_button: AutoSizeButton) -> None:
        """Setup focus on install button after animation."""
        focus_helper = create_focus_helper(
            detail_page, self.main_window, install_button, self.main_window.stackedWidget
        )
        QTimer.singleShot(50, focus_helper)

    def toggleFavoriteInDetailPage(self, game_name: str, label: ClickableLabel) -> None:
        """Toggle favorite status from detail page."""
        favorite_text = toggle_favorite(game_name, self.main_window)
        label.setText(favorite_text)

    def toggleDebugLog(self, exe_path: str | None, button: AutoSizeButton) -> None:
        """Toggle debug log creation."""
        if self.debug_log_manager.is_running:
            self._stop_debug_log(button)
        else:
            self._start_debug_log(exe_path, button)

    def _stop_debug_log(self, button: AutoSizeButton) -> None:
        """Stop debug logging and save log."""
        self._stopDebugTimer()
        log_file = self.debug_log_manager.stop()

        button.setText(_("Create Log"))
        icon = self.main_window.theme_manager.get_icon("edit")
        if icon:
            button.setIcon(icon)

        if log_file:
            self._show_log_saved_dialog(log_file)

    def _start_debug_log(self, exe_path: str | None, button: AutoSizeButton) -> None:
        """Start debug logging session."""
        if exe_path is None:
            return
        resolved_exe_path = self.main_window.resolve_launch_file_path(exe_path)
        if resolved_exe_path is None:
            return

        start_command = get_portproton_start_command()
        if not start_command:
            return

        if self.debug_log_manager.start(resolved_exe_path, start_command):
            button.setText(_("Stop Log"))
            icon = self.main_window.theme_manager.get_icon("stop")
            if icon:
                button.setIcon(icon)
            self._startDebugTimer()
        else:
            QMessageBox.warning(
                self.main_window,
                _("Error"),
                _("Failed to start debug session"),
            )

    def _show_log_saved_dialog(self, log_file: str) -> None:
        """Show dialog with log file location."""
        msg_box = QMessageBox(self.main_window)
        msg_box.setWindowTitle(_("Log Saved"))
        msg_box.setText(_("Debug log saved to:") + f"\n{log_file}")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Open)
        msg_box.setButtonText(QMessageBox.StandardButton.Open, _("Open Folder"))

        result = msg_box.exec()

        if result == QMessageBox.StandardButton.Open:
            log_folder = os.path.dirname(log_file)
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(log_folder))
            except Exception as e:
                logger.error("Failed to open folder %s: %s", log_folder, e)

    def _startDebugTimer(self) -> None:
        """Start timer to periodically read debug output."""
        if self._debug_log_timer is not None:
            self._debug_log_timer.stop()

        self._debug_log_timer = QTimer(self.main_window)
        self._debug_log_timer.timeout.connect(self._onDebugTimerTick)
        self._debug_log_timer.start(500)

    def _stopDebugTimer(self) -> None:
        """Stop debug output timer."""
        if self._debug_log_timer is not None:
            self._debug_log_timer.stop()
            self._debug_log_timer.deleteLater()
            self._debug_log_timer = None

    def _onDebugTimerTick(self) -> None:
        """Handle debug timer tick."""
        if not self.debug_log_manager.check_running():
            self._stopDebugTimer()
            log_file = self.debug_log_manager.stop()
            self._update_debug_log_button(log_file)

    def _update_debug_log_button(self, log_file: str | None) -> None:
        """Update debug log button and show dialog if log saved."""
        if self._debug_log_button:
            self._debug_log_button.setText(_("Create Log"))
            icon = self.main_window.theme_manager.get_icon("edit")
            if icon:
                self._debug_log_button.setIcon(icon)

        if log_file:
            logger.info("Debug session ended. Log saved to %s", log_file)
            self._show_log_saved_dialog(log_file)

    def goBackDetailPage(self, page: QWidget | None) -> None:
        """Navigate back from detail page."""
        if page is None or not self._is_valid_page(page) or self._exit_animation_in_progress:
            return

        self._exit_animation_in_progress = True
        self._detail_page_active = False
        self._current_detail_page = None

        def cleanup() -> None:
            self._cleanup_page(page)

        if page and not page.isHidden() and page.parent() is not None:
            detail_animations = DetailPageAnimations(self.main_window, self.main_window.theme)
            detail_animations.animate_detail_page_exit(page, cleanup)
        else:
            logger.warning("Detail page not valid, bypassing animation")
            self._exit_animation_in_progress = False
            cleanup()

    def _is_valid_page(self, page: QWidget) -> bool:
        """Check if page is valid and current."""
        return page == self.main_window.stackedWidget.currentWidget()

    def _cleanup_page(self, page: QWidget) -> None:
        """Clean up detail page and return to tab."""
        try:
            self._cleanup_animations(page)

            if not self._page_in_stacked(page):
                logger.debug("Page not found in stacked widget")
                self._finalize_cleanup()
                return

            self.main_window.stackedWidget.removeWidget(page)
            return_tab_index = getattr(self, "_return_to_tab_index", 0)
            self.main_window.stackedWidget.setCurrentIndex(return_tab_index)

            self._refresh_tab_content(return_tab_index)
            self._finalize_cleanup()

        except RuntimeError:
            logger.debug("Detail page already deleted during cleanup")
            self._exit_animation_in_progress = False
        except Exception as e:
            logger.error("Unexpected error in cleanup: %s", e, exc_info=True)
            self._exit_animation_in_progress = False

    def _cleanup_animations(self, page: QWidget) -> None:
        """Clean up animations for page."""
        if not hasattr(self, "_animations") or page not in self._animations:
            return
        try:
            animation = self._animations[page]
            self._stop_animation_if_running(animation)
            del self._animations[page]
        except (KeyError, RuntimeError):
            pass

    def _stop_animation_if_running(self, animation) -> None:
        if hasattr(animation, "state") and animation.state() == 1:
            animation.stop()

    def _page_in_stacked(self, page: QWidget) -> bool:
        for i in range(self.main_window.stackedWidget.count()):
            if self.main_window.stackedWidget.widget(i) is page:
                return True
        return False

    def _refresh_tab_content(self, tab_index: int) -> None:
        if tab_index == 0 and hasattr(self.main_window, "game_library_manager"):
            if self.main_window.launch_exe and not self.main_window.games:
                QTimer.singleShot(10, lambda: self.main_window.loadGames(force_load=True))
            else:
                QTimer.singleShot(10, lambda: self.main_window.game_library_manager.update_game_grid())
        elif tab_index == 1 and hasattr(self.main_window, "autoInstallContainer"):
            QTimer.singleShot(10, lambda: self.main_window.autoInstallContainer.updateGeometry())
            if hasattr(self.main_window, "autoInstallContainerLayout"):
                QTimer.singleShot(15, lambda: self.main_window.autoInstallContainerLayout.update())

    def _finalize_cleanup(self) -> None:
        self.main_window.currentDetailPage = None
        self.main_window.current_exec_line = None
        self.main_window.current_play_button = None
        self._exit_animation_in_progress = False
