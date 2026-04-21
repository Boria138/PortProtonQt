from PySide6.QtGui import QPainter, QColor, QDesktopServices
from PySide6.QtCore import Signal, Property, Qt, QUrl, QTimer
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QVBoxLayout, QHBoxLayout, QWidget, QStackedLayout, QLabel
from portprotonqt.image_utils import load_pixmap_async, round_corners
from portprotonqt.localization import _
from portprotonqt.config_utils import (
    read_favorites,
    save_favorites,
    read_display_filter,
    read_theme_from_config,
    read_badge_view_mode,
    read_economy_mode,
)
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.custom_widgets import ClickableLabel
from portprotonqt.portproton_api import PortProtonAPI
from portprotonqt.downloader import Downloader
from portprotonqt.animations import GameCardAnimations

class GameCard(QFrame):
    borderWidthChanged = Signal()
    gradientAngleChanged = Signal()
    scaleChanged = Signal()
    editShortcutRequested = Signal(str, str, str)
    deleteGameRequested = Signal(str, str)
    addToMenuRequested = Signal(str, str)
    removeFromMenuRequested = Signal(str)
    addToDesktopRequested = Signal(str, str)
    removeFromDesktopRequested = Signal(str)
    addToSteamRequested = Signal(str, str, str)
    removeFromSteamRequested = Signal(str, str)
    openGameFolderRequested = Signal(str, str)
    hoverChanged = Signal(str, bool)
    focusChanged = Signal(str, bool)

    def __init__(self, name, description, cover_path, appid, controller_support, exec_line,
                 last_launch, formatted_playtime, protondb_tier, anticheat_status, last_launch_ts, playtime_seconds, game_source,
                 anticheat_slug="", *, select_callback, theme=None, card_width=250, parent=None, context_menu_manager=None):
        super().__init__(parent)
        self.name = name
        self.description = description
        self.cover_path = cover_path
        self.appid = appid
        self.controller_support = controller_support
        self.exec_line = exec_line
        self.last_launch = last_launch
        self.formatted_playtime = formatted_playtime
        self.protondb_tier = protondb_tier
        self.anticheat_status = anticheat_status
        self.anticheat_slug = anticheat_slug or ""
        self.game_source = game_source
        self.last_launch_ts = last_launch_ts
        self.playtime_seconds = playtime_seconds
        self.base_card_width = card_width
        self.base_pixmap = None
        self.base_font_size = None

        self.select_callback = select_callback
        self.context_menu_manager = context_menu_manager
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.theme_manager = ThemeManager()
        self.theme = theme if theme is not None else self.theme_manager.apply_theme(read_theme_from_config())

        self.display_filter = read_display_filter()
        self.badge_view_mode = read_badge_view_mode()
        self.current_theme_name = read_theme_from_config()
        self.layout_mode = str(getattr(self.theme, "LIBRARY_LAYOUT_MODE", "grid")).lower()
        self.list_layout = self.layout_mode == "list"
        self.economy_mode = read_economy_mode()
        self.downloader = Downloader(max_workers=4)
        self.portproton_api = PortProtonAPI(self.downloader)

        self.steam_visible = (str(game_source).lower() == "steam" and self.display_filter in ("all", "favorites") and not self.economy_mode)
        self.egs_visible = (str(game_source).lower() == "epic" and self.display_filter in ("all", "favorites") and not self.economy_mode)
        self.portproton_visible = (str(game_source).lower() == "portproton" and self.display_filter in ("all", "favorites") and not self.economy_mode)

        self.base_extra_margin = 8 if self.list_layout else 20
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(self.theme.GAME_CARD_WINDOW_STYLE)

        self._borderWidth = self.theme.GAME_CARD_ANIMATION["default_border_width"]
        self._gradientAngle = self.theme.GAME_CARD_ANIMATION["gradient_start_angle"]
        self._scale = self.theme.GAME_CARD_ANIMATION["default_scale"]
        self._hovered = False
        self._focused = False

        self.animations = GameCardAnimations(self, self.theme)
        self.animations.setup_animations()

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(self.theme.shadow_blur_radius)
        self.shadow.setColor(QColor(self.theme.color_shadow_card))
        self.shadow.setOffset(*self.theme.shadow_offset)
        self.setGraphicsEffect(self.shadow)

        if self.list_layout:
            self.layout_ = QHBoxLayout(self)
            self.layout_.setSpacing(12)
        else:
            self.layout_ = QVBoxLayout(self)
            self.layout_.setSpacing(5)
        self.layout_.setContentsMargins(self.base_extra_margin // 2, self.base_extra_margin // 2, self.base_extra_margin // 2, self.base_extra_margin // 2)

        self.coverWidget = QWidget()
        coverLayout = QStackedLayout(self.coverWidget)
        coverLayout.setContentsMargins(0, 0, 0, 0)
        coverLayout.setStackingMode(QStackedLayout.StackingMode.StackAll)

        self.coverLabel = QLabel()
        self.coverLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.coverLabel.setStyleSheet(self.theme.COVER_LABEL_STYLE)
        coverLayout.addWidget(self.coverLabel)

        if self.list_layout:
            load_pixmap_async(cover_path or "", 64, 64, self.on_cover_loaded)
        else:
            load_pixmap_async(cover_path or "", self.base_card_width, int(self.base_card_width * 1.5), self.on_cover_loaded)

        self.favoriteLabel = ClickableLabel(self.coverWidget)
        self.favoriteLabel.clicked.connect(self.toggle_favorite)
        self.is_favorite = self.name in set(read_favorites())
        self.update_favorite_icon()
        self.favoriteLabel.raise_()
        if self.list_layout:
            self.favoriteLabel.setVisible(False)

        tier_text = "" if self.economy_mode else self.getProtonDBText(protondb_tier)
        if tier_text:
            icon_filename = self.getProtonDBIconFilename(protondb_tier)
            icon = self.theme_manager.get_icon(icon_filename, self.current_theme_name)
            self.protondbLabel = ClickableLabel(
                tier_text,
                icon=icon,
                parent=self.coverWidget,
                font_scale_factor=0.06
            )
            self.protondbLabel.setStyleSheet(self.theme.get_protondb_badge_style(protondb_tier))
            self.protondbLabel.setCardWidth(card_width)
        else:
            self.protondbLabel = ClickableLabel("", parent=self.coverWidget)
            self.protondbLabel.setVisible(False)

        steam_icon = self.theme_manager.get_icon("steam")
        self.steamLabel = ClickableLabel(
            "Steam",
            icon=steam_icon,
            parent=self.coverWidget,
            font_scale_factor=0.06
        )
        self.steamLabel.setStyleSheet(self.theme.STEAM_BADGE_STYLE)
        self.steamLabel.setCardWidth(card_width)
        self.steamLabel.setVisible(self.steam_visible)
        if self.economy_mode:
            self.steamLabel.setVisible(False)

        egs_icon = self.theme_manager.get_icon("epic_games")
        self.egsLabel = ClickableLabel(
            "Epic Games",
            icon=egs_icon,
            parent=self.coverWidget,
            font_scale_factor=0.06,
            change_cursor=False
        )
        self.egsLabel.setStyleSheet(self.theme.STEAM_BADGE_STYLE)
        self.egsLabel.setCardWidth(card_width)
        self.egsLabel.setVisible(self.egs_visible)
        if self.economy_mode:
            self.egsLabel.setVisible(False)

        portproton_icon = self.theme_manager.get_icon("portproton")
        self.portprotonLabel = ClickableLabel(
            "PortProton",
            icon=portproton_icon,
            parent=self.coverWidget,
            font_scale_factor=0.06
        )
        self.portprotonLabel.setStyleSheet(self.theme.STEAM_BADGE_STYLE)
        self.portprotonLabel.setCardWidth(card_width)
        self.portprotonLabel.setVisible(self.portproton_visible)
        self.portprotonLabel.clicked.connect(self.open_ppdb_page)
        if self.economy_mode:
            self.portprotonLabel.setVisible(False)

        anticheat_text = "" if self.economy_mode else self.getAntiCheatText(anticheat_status)
        if anticheat_text:
            icon_filename = self.getAntiCheatIconFilename(anticheat_status)
            icon = self.theme_manager.get_icon(icon_filename, self.current_theme_name)
            self.anticheatLabel = ClickableLabel(
                anticheat_text,
                icon=icon,
                parent=self.coverWidget,
                font_scale_factor=0.06
            )
            self.anticheatLabel.setStyleSheet(self.theme.get_anticheat_badge_style(anticheat_status))
            self.anticheatLabel.setCardWidth(card_width)
        else:
            self.anticheatLabel = ClickableLabel("", parent=self.coverWidget)
            self.anticheatLabel.setVisible(False)

        self.protondbLabel.clicked.connect(self.open_protondb_report)
        self.steamLabel.clicked.connect(self.open_steam_page)
        self.anticheatLabel.clicked.connect(self.open_weanticheatyet_page)

        self.layout_.addWidget(self.coverWidget)

        self.nameLabel = QLabel(name)
        if self.list_layout:
            self.nameLabel.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        else:
            self.nameLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nameLabel.setStyleSheet(self.theme.GAME_CARD_NAME_LABEL_STYLE)
        self.layout_.addWidget(self.nameLabel)
        if self.list_layout:
            self.layout_.addStretch()

        font_size = self.nameLabel.font().pointSizeF()
        self.base_font_size = font_size if font_size > 0 else 10.0

        self.update_scale()

        # Force initial layout update to ensure correct geometry
        self.updateGeometry()
        parent = self.parentWidget()
        if parent:
            layout = parent.layout()
            if layout:
                layout.invalidate()
            parent.updateGeometry()

    def on_cover_loaded(self, pixmap):
        self.base_pixmap = pixmap
        self.update_cover_pixmap()

    def update_cover_pixmap(self):
        # Check if the coverLabel still exists before trying to update it
        # This prevents the "Internal C++ object already deleted" error when
        # the widget has been destroyed but the async callback still executes
        if not hasattr(self, 'coverLabel') or self.coverLabel is None:
            return

        if self.base_pixmap and not self.base_pixmap.isNull():
            if self.list_layout:
                target_width = self.coverLabel.width() if self.coverLabel.width() > 0 else 56
                target_height = self.coverLabel.height() if self.coverLabel.height() > 0 else 56
                radius = max(8, int(10 * self._scale))
                aspect_mode = Qt.AspectRatioMode.KeepAspectRatio
            else:
                target_width = int(self.base_card_width * self._scale)
                target_height = int(target_width * 1.5)
                radius = int(15 * self._scale)
                aspect_mode = Qt.AspectRatioMode.KeepAspectRatioByExpanding
            scaled_pixmap = self.base_pixmap.scaled(
                target_width,
                target_height,
                aspect_mode,
                Qt.TransformationMode.SmoothTransformation,
            )
            rounded_pixmap = round_corners(scaled_pixmap, radius)
            try:
                self.coverLabel.setPixmap(rounded_pixmap)
            except RuntimeError:
                # Handle the case where the Qt object was deleted between the check and the call
                pass

    def _position_badges(self, current_width):
        # Check if the card has been destroyed before updating
        if not hasattr(self, 'coverLabel') or self.coverLabel is None:
            return

        right_margin = int(8 * self._scale)
        badge_spacing = int(current_width * 0.02)
        top_y = int(10 * self._scale)
        badge_y_positions = []
        badges = [
            (self.steam_visible, self.steamLabel),
            (self.egs_visible, self.egsLabel),
            (self.portproton_visible, self.portprotonLabel),
            (bool(self.getProtonDBText(self.protondb_tier)), self.protondbLabel),
            (bool(self.getAntiCheatText(self.anticheat_status)), self.anticheatLabel),
        ]

        for is_visible, badge in badges:
            if is_visible:
                badge_x = current_width - badge.width() - right_margin
                badge_y = badge_y_positions[-1] + badge_spacing if badge_y_positions else top_y
                try:
                    badge.move(int(badge_x), int(badge_y))
                    badge_y_positions.append(badge_y + badge.height())
                except RuntimeError:
                    # Handle the case where the Qt object was deleted
                    pass

        try:
            self.anticheatLabel.raise_()
            self.protondbLabel.raise_()
            self.portprotonLabel.raise_()
            self.egsLabel.raise_()
            self.steamLabel.raise_()
        except RuntimeError:
            # Handle the case where the Qt object was deleted
            pass

    def update_scale(self):
        # Check if the card has been destroyed before updating
        if not hasattr(self, 'coverLabel') or self.coverLabel is None:
            return

        scaled_width = int(self.base_card_width * self._scale)
        scaled_extra = int(self.base_extra_margin * self._scale)
        self.layout_.setContentsMargins(scaled_extra // 2, scaled_extra // 2, scaled_extra // 2, scaled_extra // 2)
        if self.list_layout:
            row_height = max(68, int(72 * self._scale))
            icon_size = max(48, int(56 * self._scale))
            self.setFixedSize(scaled_width + scaled_extra, row_height + scaled_extra)
            self.coverWidget.setFixedSize(icon_size, icon_size)
            self.coverLabel.setFixedSize(icon_size, icon_size)
        else:
            scaled_height = int(self.base_card_width * 1.8 * self._scale)
            self.setFixedSize(scaled_width + scaled_extra, scaled_height + scaled_extra)
            self.coverWidget.setFixedSize(scaled_width, int(scaled_width * 1.5))
            self.coverLabel.setFixedSize(scaled_width, int(scaled_width * 1.5))

        self.update_cover_pixmap()

        favorite_size = (int(self.theme.favoriteLabelSize[0] * self._scale), int(self.theme.favoriteLabelSize[1] * self._scale))
        self.favoriteLabel.setFixedSize(*favorite_size)
        self.favoriteLabel.move(int(8 * self._scale), int(8 * self._scale))

        badge_width = int(scaled_width * 2/3)
        icon_size = int(scaled_width * 0.06)
        icon_space = int(scaled_width * 0.012)
        compact_badge_width = int(scaled_width * 0.12)
        compact_badge_width = max(compact_badge_width, icon_size + icon_space + 8)
        compact_badge = self.badge_view_mode == "compact"
        hidden_badges = self.badge_view_mode == "hidden"
        badge_visibility = [
            (self.steam_visible, self.steamLabel),
            (self.egs_visible, self.egsLabel),
            (self.portproton_visible, self.portprotonLabel),
            (bool(self.getProtonDBText(self.protondb_tier)), self.protondbLabel),
            (bool(self.getAntiCheatText(self.anticheat_status)), self.anticheatLabel),
        ]
        for is_visible, label in badge_visibility:
            if label is not None:
                try:
                    label.setIconSize(icon_size, icon_space)
                    label.setCardWidth(scaled_width)
                    label.setCompactMode(
                        compact_badge,
                        compact_badge_width,
                        badge_width,
                        self._on_badge_width_changed
                    )
                    label.setVisible(is_visible and not hidden_badges)
                except RuntimeError:
                    # Handle the case where the Qt object was deleted
                    pass

        if not self.list_layout:
            self._position_badges(scaled_width)

        if self.base_font_size is not None:
            try:
                font = self.nameLabel.font()
                new_font_size = self.base_font_size * self._scale
                if new_font_size > 0:
                    font.setPointSizeF(new_font_size)
                    self.nameLabel.setFont(font)
            except RuntimeError:
                # Handle the case where the Qt object was deleted
                pass

        try:
            self.shadow.setBlurRadius(int(20 * self._scale))
        except RuntimeError:
            # Handle the case where the Qt object was deleted
            pass

        try:
            self.updateGeometry()
            self.update()
        except RuntimeError:
            # Handle the case where the Qt object was deleted
            pass

        # Ensure parent layout is updated safely
        try:
            parent = self.parentWidget()
            if parent:
                layout = parent.layout()
                if layout:
                    layout.invalidate()
                    layout.activate()
                    layout.update()
                parent.updateGeometry()
        except RuntimeError:
            # Handle the case where the Qt object was deleted
            pass

    def update_card_size(self, new_width: int):
        """Update card size by scaling existing base_pixmap without reloading."""
        self.base_card_width = new_width
        self.update_cover_pixmap()
        self.update_scale()

    def update_badge_visibility(self, display_filter: str):
        # Check if the card has been destroyed before updating
        if not hasattr(self, 'coverLabel') or self.coverLabel is None:
            return

        self.display_filter = display_filter
        self.economy_mode = read_economy_mode()
        self.steam_visible = (str(self.game_source).lower() == "steam" and self.display_filter in ("all", "favorites") and not self.economy_mode)
        self.egs_visible = (str(self.game_source).lower() == "epic" and self.display_filter in ("all", "favorites") and not self.economy_mode)
        self.portproton_visible = (str(self.game_source).lower() == "portproton" and self.display_filter in ("all", "favorites") and not self.economy_mode)
        protondb_visible = bool(self.getProtonDBText(self.protondb_tier)) and not self.economy_mode
        anticheat_visible = bool(self.getAntiCheatText(self.anticheat_status)) and not self.economy_mode

        hidden_badges = self.badge_view_mode == "hidden"

        try:
            self.steamLabel.setVisible(self.steam_visible and not hidden_badges)
            self.egsLabel.setVisible(self.egs_visible and not hidden_badges)
            self.portprotonLabel.setVisible(self.portproton_visible and not hidden_badges)
            self.protondbLabel.setVisible(protondb_visible and not hidden_badges)
            self.anticheatLabel.setVisible(anticheat_visible and not hidden_badges)
        except RuntimeError:
            # Handle the case where the Qt object was deleted
            return

        scaled_width = int(self.base_card_width * self._scale)
        if not self.list_layout:
            self._position_badges(scaled_width)

        # Update layout after visibility changes
        self.updateGeometry()
        parent = self.parentWidget()
        if parent:
            layout = parent.layout()
            if layout:
                layout.invalidate()
                layout.update()
            parent.updateGeometry()

    def _on_badge_width_changed(self):
        if not hasattr(self, 'coverLabel') or self.coverLabel is None:
            return
        if self.list_layout:
            return
        scaled_width = int(self.base_card_width * self._scale)
        self._position_badges(scaled_width)

    def update_badge_view_mode(self, badge_view_mode: str):
        """Update badge rendering mode."""
        self.badge_view_mode = badge_view_mode if badge_view_mode in ("detailed", "compact", "hidden") else "detailed"
        self.update_scale()

    def _show_context_menu(self, pos):
        if self.context_menu_manager:
            self.context_menu_manager.show_context_menu(self, pos)

    @staticmethod
    def getAntiCheatText(status: str) -> str:
        if not status:
            return ""
        translations = {
            "supported": _("Supported"),
            "running": _("Running"),
            "planned": _("Planned"),
            "broken":  _("Broken"),
            "denied": _("Denied")
        }
        return translations.get(status.lower(), "")

    @staticmethod
    def getAntiCheatIconFilename(status: str) -> str:
        status = status.lower()
        if status in ("supported"):
            return "ac_supported"
        elif status in ("running"):
            return "ac_running"
        elif status in ("planned"):
            return "ac_planned"
        elif status in ("denied"):
            return "ac_denied"
        elif status in ("broken"):
            return "ac_broken"
        return ""

    @staticmethod
    def getProtonDBText(tier: str) -> str:
        if not tier:
            return ""
        translations = {
            "platinum": _("Platinum"),
            "gold": _("Gold"),
            "silver":  _("Silver"),
            "bronze": _("Bronze"),
            "borked": _("Broken"),
            "pending":  _("Pending")
        }
        return translations.get(tier.lower(), "")

    @staticmethod
    def getProtonDBIconFilename(tier: str) -> str:
        tier = tier.lower()
        if tier in ("platinum", "gold"):
            return "platinum-gold"
        elif tier in ("silver", "bronze"):
            return "silver-bronze"
        elif tier in ("borked", "pending"):
            return "broken"
        return ""

    def open_ppdb_page(self):
        self.portproton_api.open_ppdb_page(self.name, self.exec_line)

    def open_protondb_report(self):
        url = QUrl(f"https://www.protondb.com/app/{self.appid}")
        QDesktopServices.openUrl(url)

    def open_steam_page(self):
        url = QUrl(f"https://steamcommunity.com/app/{self.appid}")
        QDesktopServices.openUrl(url)

    def open_weanticheatyet_page(self):
        if self.anticheat_slug:
            url = QUrl(f"https://areweanticheatyet.com/game/{self.anticheat_slug}")
        else:
            formatted_name = self.name.lower().replace(" ", "-")
            url = QUrl(f"https://areweanticheatyet.com/game/{formatted_name}")
        QDesktopServices.openUrl(url)

    def update_favorite_icon(self):
        # Check if the card has been destroyed before updating
        if not hasattr(self, 'coverLabel') or self.coverLabel is None:
            return

        try:
            if self.is_favorite:
                self.favoriteLabel.setText("★")
            else:
                self.favoriteLabel.setText("☆")
            self.favoriteLabel.setStyleSheet(self.theme.FAVORITE_LABEL_STYLE)
        except RuntimeError:
            # Handle the case where the Qt object was deleted
            return

        try:
            parent = self.parent()
            while parent:
                if hasattr(parent, 'game_library_manager'):
                    # Access using getattr with default to avoid Ruff B009 warning
                    manager = getattr(parent, 'game_library_manager', None)
                    if manager is not None:
                        QTimer.singleShot(0, manager.update_game_grid)
                    break
                parent = parent.parent()
        except RuntimeError:
            # Handle the case where the Qt object was deleted
            pass

    def toggle_favorite(self):
        favorites = read_favorites()
        favorites_set = set(favorites)
        if self.is_favorite:
            if self.name in favorites_set:
                favorites.remove(self.name)
            self.is_favorite = False
        else:
            if self.name not in favorites_set:
                favorites.append(self.name)
            self.is_favorite = True
        save_favorites(favorites)
        self.update_favorite_icon()

    def getBorderWidth(self) -> int:
        return self._borderWidth

    def setBorderWidth(self, value: int):
        if self._borderWidth != value:
            self._borderWidth = value
            self.borderWidthChanged.emit()
            self.update()

    def getGradientAngle(self) -> float:
        return self._gradientAngle

    def setGradientAngle(self, value: float):
        if self._gradientAngle != value:
            self._gradientAngle = value
            self.gradientAngleChanged.emit()
            self.update()

    def getScale(self) -> float:
        return self._scale

    def setScale(self, value: float):
        if self._scale != value:
            self._scale = value
            self.update_scale()
            self.scaleChanged.emit()

    borderWidth = Property(int, fget=getBorderWidth, fset=setBorderWidth, notify=borderWidthChanged)
    gradientAngle = Property(float, fget=getGradientAngle, fset=setGradientAngle, notify=gradientAngleChanged)
    scale = Property(float, fget=getScale, fset=setScale, notify=scaleChanged)


    def paintEvent(self, event):
        super().paintEvent(event)
        self.animations.paint_border(QPainter(self))

    def enterEvent(self, event):
        self.animations.handle_enter_event()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animations.handle_leave_event()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self.animations.handle_focus_in_event()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.animations.handle_focus_out_event()
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            game_data = {
                "name": self.name,
                "description": self.description,
                "cover_path": self.cover_path,
                "appid": self.appid,
                "controller_support": self.controller_support,
                "exec_line": self.exec_line,
                "last_launch": self.last_launch,
                "formatted_playtime": self.formatted_playtime,
                "protondb_tier": self.protondb_tier,
                "game_source": self.game_source,
                "anticheat_status": self.anticheat_status,
                "anticheat_slug": self.anticheat_slug,
            }
            self.select_callback(game_data)
        super().mousePressEvent(event)

    def cleanup(self):
        """Clean up animations to prevent memory leaks when the card is destroyed."""
        if hasattr(self, 'animations') and self.animations:
            try:
                self.animations.cleanup()
            except RuntimeError:
                # Object already deleted
                pass

    def __del__(self):
        """Destructor to ensure cleanup happens."""
        try:
            self.cleanup()
        except RuntimeError:
            # Object already deleted
            pass


    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            game_data = {
                "name": self.name,
                "description": self.description,
                "cover_path": self.cover_path,
                "appid": self.appid,
                "controller_support": self.controller_support,
                "exec_line": self.exec_line,
                "last_launch": self.last_launch,
                "formatted_playtime": self.formatted_playtime,
                "protondb_tier": self.protondb_tier,
                "game_source": self.game_source,
                "anticheat_status": self.anticheat_status,
                "anticheat_slug": self.anticheat_slug,
            }
            self.select_callback(game_data)
        else:
            super().keyPressEvent(event)
