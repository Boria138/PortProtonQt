import os
import shlex
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QVBoxLayout, QLabel, QHBoxLayout, QWidget, QApplication)
from PySide6.QtCore import Qt, QUrl, QTimer, QAbstractAnimation
from PySide6.QtGui import QColor, QDesktopServices
from portprotonqt.image_utils import load_pixmap_async, round_corners
from portprotonqt.custom_widgets import ClickableLabel, AutoSizeButton
from portprotonqt.game_card import GameCard
from portprotonqt.howlongtobeat_api import HowLongToBeat
from portprotonqt.config_utils import read_favorites, save_favorites, read_display_filter
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.portproton_api import PortProtonAPI
from portprotonqt.downloader import Downloader
from portprotonqt.animations import DetailPageAnimations

logger = get_logger(__name__)


class DetailPageManager:
    """Manages detail pages for games."""

    def __init__(self, main_window):
        self.main_window = main_window
        self._detail_page_active = False
        self._current_detail_page = None
        self._exit_animation_in_progress = False
        self._animations = {}
        self.portproton_api = PortProtonAPI(Downloader(max_workers=4))

    def openGameDetailPage(self, name, description, cover_path=None, appid="", exec_line="", controller_support="",
                          last_launch="", formatted_playtime="", protondb_tier="", game_source="", anticheat_status=""):
        """Open detailed game information page showing all game stats, playtime and settings."""
        detailPage = QWidget()
        imageLabel = QLabel()
        imageLabel.setFixedSize(300, 450)
        self._detail_page_active = True
        self._current_detail_page = detailPage
        # Store the source tab index (Library is typically index 0)
        self._return_to_tab_index = 0  # Library tab

        # Function to load image and restore effect
        def load_image_and_restore_effect():
            # Check if detail page still exists and is valid
            if not detailPage or detailPage.isHidden() or detailPage.parent() is None:
                logger.warning("Detail page is None, hidden, or no longer valid, skipping image load")
                return

            try:
                detailPage.setWindowOpacity(1.0)
            except RuntimeError:
                logger.warning("Detail page is None, hidden, or no longer valid, skipping opacity set")
                return

            if cover_path:
                def on_pixmap_ready(pixmap):
                    # Check if detail page still exists and is valid
                    if not detailPage or detailPage.isHidden() or detailPage.parent() is None:
                        logger.warning("Detail page is None, hidden, or no longer valid, skipping pixmap update")
                        return
                    try:
                        rounded = round_corners(pixmap, 10)
                        imageLabel.setPixmap(rounded)
                        logger.debug("Pixmap set for imageLabel")

                        def on_palette_ready(palette):
                            # Check if detail page still exists and is valid
                            if not detailPage or detailPage.isHidden() or detailPage.parent() is None:
                                logger.warning("Detail page is None, hidden, or no longer valid, skipping palette update")
                                return
                            try:
                                dark_palette = [self.main_window.darkenColor(color, factor=200) for color in palette]
                                stops = ",\n".join(
                                    [f"stop:{i/(len(dark_palette)-1):.2f} {dark_palette[i].name()}" for i in range(len(dark_palette))]
                                )
                                detailPage.setStyleSheet(self.main_window.theme.detail_page_style(stops))
                                detailPage.update()
                                logger.debug("Stylesheet updated with palette")
                            except RuntimeError:
                                logger.warning("Detail page already deleted, skipping palette stylesheet update")
                        self.main_window.getColorPalette_async(cover_path, num_colors=5, callback=on_palette_ready)
                    except RuntimeError:
                        logger.warning("Detail page already deleted, skipping pixmap update")
                load_pixmap_async(cover_path, 300, 450, on_pixmap_ready)
            else:
                try:
                    detailPage.setStyleSheet(self.main_window.theme.DETAIL_PAGE_NO_COVER_STYLE)
                    detailPage.update()
                except RuntimeError:
                    logger.warning("Detail page already deleted, skipping no-cover stylesheet update")

        def cleanup_animation():
            if detailPage in self._animations:
                del self._animations[detailPage]

        mainLayout = QVBoxLayout(detailPage)
        mainLayout.setContentsMargins(30, 30, 30, 30)
        mainLayout.setSpacing(20)

        backButton = AutoSizeButton(_("Back"), icon=self.main_window.theme_manager.get_icon("back"))
        backButton.setFixedWidth(100)
        backButton.setStyleSheet(self.main_window.theme.ADDGAME_BACK_BUTTON_STYLE)
        backButton.clicked.connect(lambda: self.goBackDetailPage(detailPage))
        mainLayout.addWidget(backButton, alignment=Qt.AlignmentFlag.AlignLeft)

        contentFrame = QFrame()
        contentFrame.setStyleSheet(self.main_window.theme.DETAIL_CONTENT_FRAME_STYLE)
        contentFrameLayout = QHBoxLayout(contentFrame)
        contentFrameLayout.setContentsMargins(20, 20, 20, 20)
        contentFrameLayout.setSpacing(40)
        mainLayout.addWidget(contentFrame)

        # Cover (at left)
        coverFrame = QFrame()
        coverFrame.setFixedSize(300, 450)
        coverFrame.setStyleSheet(self.main_window.theme.COVER_FRAME_STYLE)
        shadow = QGraphicsDropShadowEffect(coverFrame)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 0)
        coverFrame.setGraphicsEffect(shadow)
        coverLayout = QVBoxLayout(coverFrame)
        coverLayout.setContentsMargins(0, 0, 0, 0)

        coverLayout.addWidget(imageLabel)

        # Favorite icon
        favoriteLabelCover = ClickableLabel(coverFrame)
        favoriteLabelCover.setFixedSize(*self.main_window.theme.favoriteLabelSize)
        favoriteLabelCover.setStyleSheet(self.main_window.theme.FAVORITE_LABEL_STYLE)
        favorites = read_favorites()
        if name in favorites:
            favoriteLabelCover.setText("★")
        else:
            favoriteLabelCover.setText("☆")
        favoriteLabelCover.clicked.connect(lambda: self.toggleFavoriteInDetailPage(name, favoriteLabelCover))
        favoriteLabelCover.move(8, 8)
        favoriteLabelCover.raise_()

        # Add badges (ProtonDB, Steam, PortProton, WeAntiCheatYet)
        display_filter = read_display_filter()
        steam_visible = (str(game_source).lower() == "steam" and display_filter in ("all", "favorites"))
        egs_visible = (str(game_source).lower() == "epic" and display_filter in ("all", "favorites"))
        portproton_visible = (str(game_source).lower() == "portproton" and display_filter in ("all", "favorites"))
        right_margin = 8
        badge_spacing = 5
        top_y = 10
        badge_y_positions = []
        badge_width = int(300 * 2/3)

        # ProtonDB badge
        protondb_text = GameCard.getProtonDBText(protondb_tier)
        if protondb_text:
            icon_filename = GameCard.getProtonDBIconFilename(protondb_tier)
            icon = self.main_window.theme_manager.get_icon(icon_filename, self.main_window.current_theme_name)
            protondbLabel = ClickableLabel(
                protondb_text,
                icon=icon,
                parent=coverFrame,
                icon_size=16,
                icon_space=3,
            )
            protondbLabel.setStyleSheet(self.main_window.theme.get_protondb_badge_style(protondb_tier))
            protondbLabel.setFixedWidth(badge_width)
            protondbLabel.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"https://www.protondb.com/app/{appid}")))
            protondb_visible = True
        else:
            protondbLabel = ClickableLabel("", parent=coverFrame, icon_size=16, icon_space=3)
            protondbLabel.setFixedWidth(badge_width)
            protondbLabel.setVisible(False)
            protondb_visible = False

        # Steam badge
        steam_icon = self.main_window.theme_manager.get_icon("steam")
        steamLabel = ClickableLabel(
            "Steam",
            icon=steam_icon,
            parent=coverFrame,
            icon_size=16,
            icon_space=5,
        )
        steamLabel.setStyleSheet(self.main_window.theme.STEAM_BADGE_STYLE)
        steamLabel.setFixedWidth(badge_width)
        steamLabel.setVisible(steam_visible)
        steamLabel.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"https://steamcommunity.com/app/{appid}")))

        # Epic Games Store badge
        egs_icon = self.main_window.theme_manager.get_icon("epic_games")
        egsLabel = ClickableLabel(
            "Epic Games",
            icon=egs_icon,
            parent=coverFrame,
            icon_size=16,
            icon_space=5,
            change_cursor=False
        )
        egsLabel.setStyleSheet(self.main_window.theme.STEAM_BADGE_STYLE)
        egsLabel.setFixedWidth(badge_width)
        egsLabel.setVisible(egs_visible)

        # PortProton badge
        portproton_icon = self.main_window.theme_manager.get_icon("portproton")
        portprotonLabel = ClickableLabel(
            "PortProton",
            icon=portproton_icon,
            parent=coverFrame,
            icon_size=16,
            icon_space=5,
        )
        portprotonLabel.setStyleSheet(self.main_window.theme.STEAM_BADGE_STYLE)
        portprotonLabel.setFixedWidth(badge_width)
        portprotonLabel.setVisible(portproton_visible)
        portprotonLabel.clicked.connect(lambda: self.open_portproton_forum_topic(name))

        # WeAntiCheatYet badge
        anticheat_text = GameCard.getAntiCheatText(anticheat_status)
        if anticheat_text:
            icon_filename = GameCard.getAntiCheatIconFilename(anticheat_status)
            icon = self.main_window.theme_manager.get_icon(icon_filename, self.main_window.current_theme_name)
            anticheatLabel = ClickableLabel(
                anticheat_text,
                icon=icon,
                parent=coverFrame,
                icon_size=16,
                icon_space=3,
            )
            anticheatLabel.setStyleSheet(self.main_window.theme.get_anticheat_badge_style(anticheat_status))
            anticheatLabel.setFixedWidth(badge_width)
            anticheatLabel.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"https://areweanticheatyet.com/game/{name.lower().replace(' ', '-')}")))
            anticheat_visible = True
        else:
            anticheatLabel = ClickableLabel("", parent=coverFrame, icon_size=16, icon_space=3)
            anticheatLabel.setFixedWidth(badge_width)
            anticheatLabel.setVisible(False)
            anticheat_visible = False

        # Position badges
        if steam_visible:
            steam_x = 300 - badge_width - right_margin
            steamLabel.move(steam_x, top_y)
            badge_y_positions.append(top_y + steamLabel.height())
        if egs_visible:
            egs_x = 300 - badge_width - right_margin
            egs_y = badge_y_positions[-1] + badge_spacing if badge_y_positions else top_y
            egsLabel.move(egs_x, egs_y)
            badge_y_positions.append(egs_y + egsLabel.height())
        if portproton_visible:
            portproton_x = 300 - badge_width - right_margin
            portproton_y = badge_y_positions[-1] + badge_spacing if badge_y_positions else top_y
            portprotonLabel.move(portproton_x, portproton_y)
            badge_y_positions.append(portproton_y + portprotonLabel.height())
        if protondb_visible:
            protondb_x = 300 - badge_width - right_margin
            protondb_y = badge_y_positions[-1] + badge_spacing if badge_y_positions else top_y
            protondbLabel.move(protondb_x, protondb_y)
            badge_y_positions.append(protondb_y + protondbLabel.height())
        if anticheat_visible:
            anticheat_x = 300 - badge_width - right_margin
            anticheat_y = badge_y_positions[-1] + badge_spacing if badge_y_positions else top_y
            anticheatLabel.move(anticheat_x, anticheat_y)

        anticheatLabel.raise_()
        protondbLabel.raise_()
        portprotonLabel.raise_()
        egsLabel.raise_()
        steamLabel.raise_()

        contentFrameLayout.addWidget(coverFrame)

        # Game details (at right)
        detailsWidget = QWidget()
        detailsWidget.setStyleSheet(self.main_window.theme.DETAILS_WIDGET_STYLE)
        detailsLayout = QVBoxLayout(detailsWidget)
        detailsLayout.setContentsMargins(20, 20, 20, 20)
        detailsLayout.setSpacing(15)

        titleLabel = QLabel(name)
        titleLabel.setStyleSheet(self.main_window.theme.DETAIL_PAGE_TITLE_STYLE)
        detailsLayout.addWidget(titleLabel)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(self.main_window.theme.DETAIL_PAGE_LINE_STYLE)
        detailsLayout.addWidget(line)

        descLabel = QLabel(description)
        descLabel.setWordWrap(True)
        descLabel.setStyleSheet(self.main_window.theme.DETAIL_PAGE_DESC_STYLE)
        detailsLayout.addWidget(descLabel)

        # Initialize HowLongToBeat
        hltb = HowLongToBeat(parent=self.main_window)

        # Create layout for all game info
        gameInfoLayout = QVBoxLayout()
        gameInfoLayout.setSpacing(10)

        # First row: Last Launch and Play Time
        firstRowLayout = QHBoxLayout()
        firstRowLayout.setSpacing(10)

        # Last Launch
        lastLaunchTitle = QLabel(_("LAST LAUNCH"))
        lastLaunchTitle.setStyleSheet(self.main_window.theme.LAST_LAUNCH_TITLE_STYLE)
        lastLaunchValue = QLabel(last_launch)
        lastLaunchValue.setStyleSheet(self.main_window.theme.LAST_LAUNCH_VALUE_STYLE)
        firstRowLayout.addWidget(lastLaunchTitle)
        firstRowLayout.addWidget(lastLaunchValue)
        firstRowLayout.addSpacing(30)

        # Play Time
        playTimeTitle = QLabel(_("PLAY TIME"))
        playTimeTitle.setStyleSheet(self.main_window.theme.PLAY_TIME_TITLE_STYLE)
        playTimeValue = QLabel(formatted_playtime)
        playTimeValue.setStyleSheet(self.main_window.theme.PLAY_TIME_VALUE_STYLE)
        firstRowLayout.addWidget(playTimeTitle)
        firstRowLayout.addWidget(playTimeValue)

        gameInfoLayout.addLayout(firstRowLayout)

        # Create placeholder for second row (HLTB data)
        hltbLayout = QHBoxLayout()
        hltbLayout.setSpacing(10)

        # Completion time (Main Story, Main + Sides, Completionist)
        def on_hltb_results(results):
            if not hasattr(self, '_detail_page_active') or not self._detail_page_active:
                return
            if not self._current_detail_page or self._current_detail_page.isHidden() or not self._current_detail_page.parent():
                return
            # Additional check: make sure the detail page in the stacked widget is still our current detail page
            if self.main_window.stackedWidget.currentWidget() != self._current_detail_page and self._current_detail_page not in [self.main_window.stackedWidget.widget(i) for i in range(self.main_window.stackedWidget.count())]:
                return

            if results:
                game = results[0]  # Take first result
                main_story_time = hltb.format_game_time(game, "main_story")
                main_extra_time = hltb.format_game_time(game, "main_extra")
                completionist_time = hltb.format_game_time(game, "completionist")

                # Clear layout before adding new elements
                def clear_layout(layout):
                    while layout.count():
                        item = layout.takeAt(0)
                        widget = item.widget()
                        sublayout = item.layout()
                        if widget:
                            widget.deleteLater()
                        elif sublayout:
                            clear_layout(sublayout)

                clear_layout(hltbLayout)

                has_data = False

                if main_story_time is not None:
                    try:
                        mainStoryTitle = QLabel(_("MAIN STORY"))
                        mainStoryTitle.setStyleSheet(self.main_window.theme.LAST_LAUNCH_TITLE_STYLE)
                        mainStoryValue = QLabel(main_story_time)
                        mainStoryValue.setStyleSheet(self.main_window.theme.LAST_LAUNCH_VALUE_STYLE)
                        hltbLayout.addWidget(mainStoryTitle)
                        hltbLayout.addWidget(mainStoryValue)
                        hltbLayout.addSpacing(30)
                        has_data = True
                    except RuntimeError:
                        logger.warning("Detail page already deleted, skipping main story time update")

                if main_extra_time is not None:
                    try:
                        mainExtraTitle = QLabel(_("MAIN + SIDES"))
                        mainExtraTitle.setStyleSheet(self.main_window.theme.PLAY_TIME_TITLE_STYLE)
                        mainExtraValue = QLabel(main_extra_time)
                        mainExtraValue.setStyleSheet(self.main_window.theme.PLAY_TIME_VALUE_STYLE)
                        hltbLayout.addWidget(mainExtraTitle)
                        hltbLayout.addWidget(mainExtraValue)
                        hltbLayout.addSpacing(30)
                        has_data = True
                    except RuntimeError:
                        logger.warning("Detail page already deleted, skipping main extra time update")

                if completionist_time is not None:
                    try:
                        completionistTitle = QLabel(_("COMPLETIONIST"))
                        completionistTitle.setStyleSheet(self.main_window.theme.LAST_LAUNCH_TITLE_STYLE)
                        completionistValue = QLabel(completionist_time)
                        completionistValue.setStyleSheet(self.main_window.theme.LAST_LAUNCH_VALUE_STYLE)
                        hltbLayout.addWidget(completionistTitle)
                        hltbLayout.addWidget(completionistValue)
                        has_data = True
                    except RuntimeError:
                        logger.warning("Detail page already deleted, skipping completionist time update")

                # If there's data, add the layout to the second row
                if has_data:
                    gameInfoLayout.addLayout(hltbLayout)

        # Connect searchCompleted signal to on_hltb_results
        hltb.searchCompleted.connect(on_hltb_results)

        # Start search in background thread
        hltb.search_with_callback(name, case_sensitive=False)

        # Add the game info layout
        detailsLayout.addLayout(gameInfoLayout)

        if controller_support:
            cs = controller_support.lower()
            translated_cs = ""
            if cs == "full":
                translated_cs = _("full")
            elif cs == "partial":
                translated_cs = _("partial")
            elif cs == "none":
                translated_cs = _("none")
            gamepadSupportLabel = QLabel(_("Gamepad Support: {0}").format(translated_cs))
            gamepadSupportLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            gamepadSupportLabel.setStyleSheet(self.main_window.theme.GAMEPAD_SUPPORT_VALUE_STYLE)
            detailsLayout.addWidget(gamepadSupportLabel, alignment=Qt.AlignmentFlag.AlignCenter)

        detailsLayout.addStretch(1)

        # Determine current game ID from exec_line
        entry_exec_split = shlex.split(exec_line)
        if not entry_exec_split:
            return

        if entry_exec_split[0] == "env":
            file_to_check = entry_exec_split[2] if len(entry_exec_split) >= 3 else None
        elif entry_exec_split[0] == "flatpak":
            file_to_check = entry_exec_split[3] if len(entry_exec_split) >= 4 else None
        else:
            file_to_check = entry_exec_split[0]
        current_exe = os.path.basename(file_to_check) if file_to_check else None

        buttons_layout = QHBoxLayout()
        if self.main_window.target_exe is not None and current_exe == self.main_window.target_exe:
            playButton = AutoSizeButton(_("Stop"), icon=self.main_window.theme_manager.get_icon("stop"))
        else:
            playButton = AutoSizeButton(_("Play"), icon=self.main_window.theme_manager.get_icon("play"))

        playButton.setFixedSize(120, 40)
        playButton.setStyleSheet(self.main_window.theme.PLAY_BUTTON_STYLE)
        playButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        playButton.clicked.connect(lambda: self.main_window.toggleGame(exec_line, playButton))
        buttons_layout.addWidget(playButton, alignment=Qt.AlignmentFlag.AlignLeft)

        # Settings button
        settings_icon = self.main_window.theme_manager.get_icon("settings")
        settings_button = AutoSizeButton(_("Settings"), icon=settings_icon)
        settings_button.setFixedSize(120, 40)
        settings_button.setStyleSheet(self.main_window.theme.PLAY_BUTTON_STYLE)
        settings_button.clicked.connect(lambda: self.main_window.open_exe_settings(file_to_check))
        buttons_layout.addWidget(settings_button, alignment=Qt.AlignmentFlag.AlignLeft)
        buttons_layout.addStretch()
        detailsLayout.addLayout(buttons_layout)

        contentFrameLayout.addWidget(detailsWidget)
        mainLayout.addStretch()

        self.main_window.stackedWidget.addWidget(detailPage)
        self.main_window.stackedWidget.setCurrentWidget(detailPage)
        self.main_window.currentDetailPage = detailPage
        self.main_window.current_exec_line = exec_line
        self.main_window.current_play_button = playButton

        # Animation
        detail_animations = DetailPageAnimations(self.main_window, self.main_window.theme)
        detail_animations.animate_detail_page(detailPage, load_image_and_restore_effect, cleanup_animation)

        # Update page reference
        self.main_window.currentDetailPage = detailPage

        original_load = load_image_and_restore_effect

        def enhanced_load():
            original_load()
            QTimer.singleShot(50, try_set_focus)

        def try_set_focus():
            if not (playButton and not playButton.isHidden()):
                return

            # Ensure page is active
            self.main_window.stackedWidget.setCurrentWidget(detailPage)
            detailPage.setFocus(Qt.FocusReason.OtherFocusReason)
            playButton.setFocus(Qt.FocusReason.OtherFocusReason)
            playButton.update()
            detailPage.raise_()
            self.main_window.activateWindow()

            if playButton.hasFocus():
                logger.debug("Play button successfully received focus")
            else:
                logger.debug("Retrying focus...")
                QTimer.singleShot(20, retry_focus)

        def retry_focus():
            if not (playButton and not playButton.isHidden() and not playButton.hasFocus()):
                return

            # Process events to ensure UI state is updated
            QApplication.processEvents()
            self.main_window.activateWindow()
            self.main_window.stackedWidget.setCurrentWidget(detailPage)
            detailPage.raise_()
            playButton.setFocus(Qt.FocusReason.OtherFocusReason)
            playButton.update()

            if not playButton.hasFocus():
                logger.debug("Final retry...")
                playButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                playButton.setFocus(Qt.FocusReason.OtherFocusReason)
                QApplication.processEvents()

                if playButton.hasFocus():
                    logger.debug("Play button received focus after final retry")
                else:
                    logger.debug("Play button still doesn't have focus")

        detail_animations.animate_detail_page(
            detailPage,
            enhanced_load,
            cleanup_animation
        )

    def openAutoInstallDetailPage(self, name, description, cover_path=None, exec_line="", game_source=""):
        """Open minimal detail page for auto-install games with name, description, cover, and install button."""
        detailPage = QWidget()
        imageLabel = QLabel()
        imageLabel.setFixedSize(300, 450)
        self._detail_page_active = True
        self._current_detail_page = detailPage
        # Store the source tab index (Auto Install is typically index 1)
        self._return_to_tab_index = 1  # Auto Install tab

        # Try to get the description from downloaded metadata for richer content
        script_name = ""
        if exec_line and exec_line.startswith("autoinstall:"):
            script_name = exec_line[11:].lstrip(':').strip()

        if script_name:
            # Get localized description based on current UI language
            # Import locale module to detect current locale
            import locale
            try:
                current_locale = locale.getlocale()[0] or 'en'
            except Exception:
                current_locale = 'en'
            lang_code = 'ru' if current_locale and 'ru' in current_locale.lower() else 'en'

            metadata_description = self.portproton_api.get_autoinstall_description(script_name, lang_code)
            if metadata_description:
                description = metadata_description

        # Function to load image and restore effect
        def load_image_and_restore_effect():
            # Check if detail page still exists and is valid
            if not detailPage or detailPage.isHidden() or detailPage.parent() is None:
                logger.warning("Detail page is None, hidden, or no longer valid, skipping image load")
                return

            try:
                detailPage.setWindowOpacity(1.0)
            except RuntimeError:
                logger.warning("Detail page is None, hidden, or no longer valid, skipping opacity set")
                return

            if cover_path:
                def on_pixmap_ready(pixmap):
                    # Check if detail page still exists and is valid
                    if not detailPage or detailPage.isHidden() or detailPage.parent() is None:
                        logger.warning("Detail page is None, hidden, or no longer valid, skipping pixmap update")
                        return
                    try:
                        rounded = round_corners(pixmap, 10)
                        imageLabel.setPixmap(rounded)
                        logger.debug("Pixmap set for imageLabel")

                        def on_palette_ready(palette):
                            # Check if detail page still exists and is valid
                            if not detailPage or detailPage.isHidden() or detailPage.parent() is None:
                                logger.warning("Detail page is None, hidden, or no longer valid, skipping palette update")
                                return
                            try:
                                dark_palette = [self.main_window.darkenColor(color, factor=200) for color in palette]
                                stops = ",\n".join(
                                    [f"stop:{i/(len(dark_palette)-1):.2f} {dark_palette[i].name()}" for i in range(len(dark_palette))]
                                )
                                detailPage.setStyleSheet(self.main_window.theme.detail_page_style(stops))
                                detailPage.update()
                                logger.debug("Stylesheet updated with palette")
                            except RuntimeError:
                                logger.warning("Detail page already deleted, skipping palette stylesheet update")
                        self.main_window.getColorPalette_async(cover_path, num_colors=5, callback=on_palette_ready)
                    except RuntimeError:
                        logger.warning("Detail page already deleted, skipping pixmap update")
                load_pixmap_async(cover_path, 300, 450, on_pixmap_ready)
            else:
                try:
                    detailPage.setStyleSheet(self.main_window.theme.DETAIL_PAGE_NO_COVER_STYLE)
                    detailPage.update()
                except RuntimeError:
                    logger.warning("Detail page already deleted, skipping no-cover stylesheet update")

        def cleanup_animation():
            if detailPage in self._animations:
                del self._animations[detailPage]

        mainLayout = QVBoxLayout(detailPage)
        mainLayout.setContentsMargins(30, 30, 30, 30)
        mainLayout.setSpacing(20)

        backButton = AutoSizeButton(_("Back"), icon=self.main_window.theme_manager.get_icon("back"))
        backButton.setFixedWidth(100)
        backButton.setStyleSheet(self.main_window.theme.ADDGAME_BACK_BUTTON_STYLE)
        backButton.clicked.connect(lambda: self.goBackDetailPage(detailPage))
        mainLayout.addWidget(backButton, alignment=Qt.AlignmentFlag.AlignLeft)

        contentFrame = QFrame()
        contentFrame.setStyleSheet(self.main_window.theme.DETAIL_CONTENT_FRAME_STYLE)
        contentFrameLayout = QHBoxLayout(contentFrame)
        contentFrameLayout.setContentsMargins(20, 20, 20, 20)
        contentFrameLayout.setSpacing(40)
        mainLayout.addWidget(contentFrame)

        # Cover (at left)
        coverFrame = QFrame()
        coverFrame.setFixedSize(300, 450)
        coverFrame.setStyleSheet(self.main_window.theme.COVER_FRAME_STYLE)
        shadow = QGraphicsDropShadowEffect(coverFrame)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 0)
        coverFrame.setGraphicsEffect(shadow)
        coverLayout = QVBoxLayout(coverFrame)
        coverLayout.setContentsMargins(0, 0, 0, 0)

        coverLayout.addWidget(imageLabel)

        # No favorite icon for auto-install games

        # No badges for auto-install detail page
        contentFrameLayout.addWidget(coverFrame)

        # Game details (at right) - minimal version without time info
        detailsWidget = QWidget()
        detailsWidget.setStyleSheet(self.main_window.theme.DETAILS_WIDGET_STYLE)
        detailsLayout = QVBoxLayout(detailsWidget)
        detailsLayout.setContentsMargins(20, 20, 20, 20)
        detailsLayout.setSpacing(15)

        titleLabel = QLabel(name)
        titleLabel.setStyleSheet(self.main_window.theme.DETAIL_PAGE_TITLE_STYLE)
        detailsLayout.addWidget(titleLabel)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(self.main_window.theme.DETAIL_PAGE_LINE_STYLE)
        detailsLayout.addWidget(line)

        descLabel = QLabel(description)
        descLabel.setWordWrap(True)
        descLabel.setStyleSheet(self.main_window.theme.DETAIL_PAGE_DESC_STYLE)
        detailsLayout.addWidget(descLabel)

        # No HLTB data, playtime, or launch info for auto install
        detailsLayout.addStretch(1)

        buttons_layout = QHBoxLayout()

        # The script_name was already extracted at the beginning of the function
        # Determine if game is already installed based on whether .desktop files exist for the script
        game_installed = self.is_autoinstall_game_installed(script_name, name) if script_name else False

        install_button_text = _("Reinstall") if game_installed else _("Install")
        # Use update icon for reinstall, save icon for initial install
        install_button_icon = self.main_window.theme_manager.get_icon("update" if game_installed else "save")

        installButton = AutoSizeButton(install_button_text, icon=install_button_icon)
        installButton.setFixedSize(120, 40)
        installButton.setStyleSheet(self.main_window.theme.PLAY_BUTTON_STYLE)
        installButton.clicked.connect(lambda: self.main_window.launch_autoinstall(script_name))
        buttons_layout.addWidget(installButton, alignment=Qt.AlignmentFlag.AlignLeft)
        buttons_layout.addStretch()
        detailsLayout.addLayout(buttons_layout)

        contentFrameLayout.addWidget(detailsWidget)
        mainLayout.addStretch()

        self.main_window.stackedWidget.addWidget(detailPage)
        self.main_window.stackedWidget.setCurrentWidget(detailPage)
        self.main_window.currentDetailPage = detailPage

        # Animation
        detail_animations = DetailPageAnimations(self.main_window, self.main_window.theme)
        detail_animations.animate_detail_page(detailPage, load_image_and_restore_effect, cleanup_animation)

        # Update page reference
        self.main_window.currentDetailPage = detailPage

        original_load = load_image_and_restore_effect

        def enhanced_load():
            original_load()
            QTimer.singleShot(50, try_set_focus)

        def try_set_focus():
            if not (installButton and not installButton.isHidden()):
                return

            # Ensure page is active
            self.main_window.stackedWidget.setCurrentWidget(detailPage)
            detailPage.setFocus(Qt.FocusReason.OtherFocusReason)
            installButton.setFocus(Qt.FocusReason.OtherFocusReason)
            installButton.update()
            detailPage.raise_()
            self.main_window.activateWindow()

            if installButton.hasFocus():
                logger.debug("Install button successfully received focus")
            else:
                logger.debug("Retrying focus...")
                QTimer.singleShot(20, retry_focus)

        def retry_focus():
            if not (installButton and not installButton.isHidden() and not installButton.hasFocus()):
                return

            # Process events to ensure UI state is updated
            QApplication.processEvents()
            self.main_window.activateWindow()
            self.main_window.stackedWidget.setCurrentWidget(detailPage)
            detailPage.raise_()
            installButton.setFocus(Qt.FocusReason.OtherFocusReason)
            installButton.update()

            if not installButton.hasFocus():
                logger.debug("Final retry...")
                installButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                installButton.setFocus(Qt.FocusReason.OtherFocusReason)
                QApplication.processEvents()

                if installButton.hasFocus():
                    logger.debug("Install button received focus after final retry")
                else:
                    logger.debug("Install button still doesn't have focus")

        detail_animations.animate_detail_page(
            detailPage,
            enhanced_load,
            cleanup_animation
        )

    def is_autoinstall_game_installed(self, script_name, game_name):
        """Check if an auto-install game is already installed by looking for .desktop files."""
        if not self.main_window.portproton_location:
            return False

        # Look for .desktop files that might match this game/script
        try:
            desktop_files = os.listdir(self.main_window.portproton_location)
            for file in desktop_files:
                if file.endswith('.desktop'):
                    # Check if the desktop file contains references to the script or game name
                    try:
                        with open(os.path.join(self.main_window.portproton_location, file), encoding='utf-8') as f:
                            content = f.read()
                            if script_name.lower() in content.lower() or game_name.lower() in content.lower():
                                return True
                    except (OSError, UnicodeDecodeError):
                        continue
        except (OSError, AttributeError):
            pass
        return False

    def toggleFavoriteInDetailPage(self, game_name, label):
        favorites = read_favorites()
        if game_name in favorites:
            favorites.remove(game_name)
            label.setText("☆")
        else:
            favorites.append(game_name)
            label.setText("★")
        save_favorites(favorites)
        self.main_window.game_library_manager.update_game_grid()

    def goBackDetailPage(self, page: QWidget | None) -> None:
        if page is None or page != self.main_window.stackedWidget.currentWidget() or getattr(self, '_exit_animation_in_progress', False):
            return
        self._exit_animation_in_progress = True
        self._detail_page_active = False
        self._current_detail_page = None

        def cleanup():
            """Helper function to clean up after animation."""
            try:
                # Stop and clean up any existing animations for this page
                if hasattr(self, '_animations') and page in self._animations:
                    try:
                        animation = self._animations[page]
                        if isinstance(animation, QAbstractAnimation):
                            if animation.state() == QAbstractAnimation.State.Running:
                                animation.stop()
                            # Since animation is set to delete when stopped, we don't manually delete it
                            del self._animations[page]
                    except (KeyError, RuntimeError):
                        pass  # Animation already deleted or not found

                # Ensure page is still valid before trying to remove it
                # Check if page is still in the stacked widget by iterating through all widgets
                page_found = False
                for i in range(self.main_window.stackedWidget.count()):
                    if self.main_window.stackedWidget.widget(i) is page:
                        page_found = True
                        break

                if page_found:
                    # Remove the detail page widget
                    self.main_window.stackedWidget.removeWidget(page)
                    # Go back to the tab where the detail page was opened from
                    return_tab_index = getattr(self, '_return_to_tab_index', 0)  # Default to library tab
                    self.main_window.stackedWidget.setCurrentIndex(return_tab_index)

                    # Ensure proper layout update after returning to the tab
                    # This is important when a refresh happened while detail page was open
                    if return_tab_index == 0:  # Library tab
                        if hasattr(self.main_window, 'game_library_manager'):
                            QTimer.singleShot(10, lambda: self.main_window.game_library_manager.update_game_grid())
                    elif return_tab_index == 1:  # Auto Install tab
                        # Force update of the auto install container layout
                        if hasattr(self.main_window, 'autoInstallContainer'):
                            QTimer.singleShot(10, lambda: self.main_window.autoInstallContainer.updateGeometry())
                            if hasattr(self.main_window, 'autoInstallContainerLayout'):
                                QTimer.singleShot(15, lambda: self.main_window.autoInstallContainerLayout.update())
                else:
                    logger.debug("Page not found in stacked widget, may have been removed already")

                # Clear references to avoid dangling references
                if hasattr(self.main_window, 'currentDetailPage'):
                    self.main_window.currentDetailPage = None
                if hasattr(self.main_window, 'current_exec_line'):
                    self.main_window.current_exec_line = None
                if hasattr(self.main_window, 'current_play_button'):
                    self.main_window.current_play_button = None

                self._exit_animation_in_progress = False
            except RuntimeError:
                # Widget was already deleted, which is expected after deleteLater()
                logger.debug("Detail page already deleted during cleanup")
                self._exit_animation_in_progress = False
            except Exception as e:
                logger.error(f"Unexpected error in cleanup: {e}", exc_info=True)
                self._exit_animation_in_progress = False

        # Start exit animation
        try:
            # Check if the page is still valid before starting animation
            if page and not page.isHidden() and page.parent() is not None:
                detail_animations = DetailPageAnimations(self.main_window, self.main_window.theme)
                detail_animations.animate_detail_page_exit(page, cleanup)
            else:
                logger.warning("Detail page not valid, bypassing animation and cleaning up directly")
                self._exit_animation_in_progress = False
                cleanup()
        except RuntimeError:
            logger.debug("Page deleted before animation could start")
            self._exit_animation_in_progress = False
        except Exception as e:
            logger.error(f"Error starting exit animation: {e}", exc_info=True)
            self._exit_animation_in_progress = False

    def open_portproton_forum_topic(self, name):
        result = self.portproton_api.get_forum_topic_slug(name)
        base_url = "https://linux-gaming.ru/"
        if result.startswith("search?q="):
            url = QUrl(f"{base_url}{result}")
        else:
            url = QUrl(f"{base_url}t/{result}")
        QDesktopServices.openUrl(url)
