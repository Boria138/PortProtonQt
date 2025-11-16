from PySide6.QtGui import QPainter, QColor, QDesktopServices
from PySide6.QtCore import Signal, Property, Qt, QUrl, QTimer
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QVBoxLayout, QWidget, QStackedLayout, QLabel
from collections.abc import Callable
from portprotonqt.image_utils import load_pixmap_async, round_corners
from portprotonqt.localization import _
from portprotonqt.config_utils import read_favorites, save_favorites, read_display_filter, read_theme_from_config
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.custom_widgets import ClickableLabel
from portprotonqt.portproton_api import PortProtonAPI
from portprotonqt.downloader import Downloader
from portprotonqt.animations import GameCardAnimations
from typing import cast


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
                 select_callback, theme=None, card_width=250, parent=None, context_menu_manager=None):
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
        self.current_theme_name = read_theme_from_config()
        self.downloader = Downloader(max_workers=4)
        self.portproton_api = PortProtonAPI(self.downloader)

        self.steam_visible = (str(game_source).lower() == "steam" and self.display_filter in ("all", "favorites"))
        self.egs_visible = (str(game_source).lower() == "epic" and self.display_filter in ("all", "favorites"))
        self.portproton_visible = (str(game_source).lower() == "portproton" and self.display_filter in ("all", "favorites"))

        self.base_extra_margin = 20
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
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(QColor(0, 0, 0, 150))
        self.shadow.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow)

        self.layout_ = QVBoxLayout(self)
        self.layout_.setSpacing(5)
        self.layout_.setContentsMargins(self.base_extra_margin // 2, self.base_extra_margin // 2, self.base_extra_margin // 2, self.base_extra_margin // 2)

        self.coverWidget = QWidget()
        coverLayout = QStackedLayout(self.coverWidget)
        coverLayout.setContentsMargins(0, 0, 0, 0)
        coverLayout.setStackingMode(QStackedLayout.StackingMode.StackAll)

        self.coverLabel = QLabel()
        self.coverLabel.setStyleSheet(self.theme.COVER_LABEL_STYLE)
        coverLayout.addWidget(self.coverLabel)

        load_pixmap_async(cover_path or "", self.base_card_width, int(self.base_card_width * 1.5), self.on_cover_loaded)

        self.favoriteLabel = ClickableLabel(self.coverWidget)
        self.favoriteLabel.clicked.connect(self.toggle_favorite)
        self.is_favorite = self.name in set(read_favorites())
        self.update_favorite_icon()
        self.favoriteLabel.raise_()

        tier_text = self.getProtonDBText(protondb_tier)
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
        self.portprotonLabel.clicked.connect(self.open_portproton_forum_topic)

        anticheat_text = self.getAntiCheatText(anticheat_status)
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
        self.nameLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nameLabel.setStyleSheet(self.theme.GAME_CARD_NAME_LABEL_STYLE)
        self.layout_.addWidget(self.nameLabel)

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
        if self.base_pixmap:
            scaled_width = int(self.base_card_width * self._scale)
            scaled_pixmap = self.base_pixmap.scaled(scaled_width, int(scaled_width * 1.5), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            rounded_pixmap = round_corners(scaled_pixmap, int(15 * self._scale))
            self.coverLabel.setPixmap(rounded_pixmap)

    def _position_badges(self, current_width):
        right_margin = int(8 * self._scale)
        badge_spacing = int(current_width * 0.02)
        top_y = int(10 * self._scale)
        badge_y_positions = []
        badge_width = int(current_width * 2/3)

        badges = [
            (self.steam_visible, self.steamLabel),
            (self.egs_visible, self.egsLabel),
            (self.portproton_visible, self.portprotonLabel),
            (bool(self.getProtonDBText(self.protondb_tier)), self.protondbLabel),
            (bool(self.getAntiCheatText(self.anticheat_status)), self.anticheatLabel),
        ]

        for is_visible, badge in badges:
            if is_visible:
                badge_x = current_width - badge_width - right_margin
                badge_y = badge_y_positions[-1] + badge_spacing if badge_y_positions else top_y
                badge.move(int(badge_x), int(badge_y))
                badge_y_positions.append(badge_y + badge.height())

        self.anticheatLabel.raise_()
        self.protondbLabel.raise_()
        self.portprotonLabel.raise_()
        self.egsLabel.raise_()
        self.steamLabel.raise_()

    def update_scale(self):
        scaled_width = int(self.base_card_width * self._scale)
        scaled_height = int(self.base_card_width * 1.8 * self._scale)
        scaled_extra = int(self.base_extra_margin * self._scale)
        self.setFixedSize(scaled_width + scaled_extra, scaled_height + scaled_extra)
        self.layout_.setContentsMargins(scaled_extra // 2, scaled_extra // 2, scaled_extra // 2, scaled_extra // 2)

        self.coverWidget.setFixedSize(scaled_width, int(scaled_width * 1.5))
        self.coverLabel.setFixedSize(scaled_width, int(scaled_width * 1.5))

        self.update_cover_pixmap()

        favorite_size = (int(self.theme.favoriteLabelSize[0] * self._scale), int(self.theme.favoriteLabelSize[1] * self._scale))
        self.favoriteLabel.setFixedSize(*favorite_size)
        self.favoriteLabel.move(int(8 * self._scale), int(8 * self._scale))

        badge_width = int(scaled_width * 2/3)
        icon_size = int(scaled_width * 0.06)
        icon_space = int(scaled_width * 0.012)
        for label in [self.steamLabel, self.egsLabel, self.portprotonLabel, self.protondbLabel, self.anticheatLabel]:
            if label is not None:
                label.setFixedWidth(badge_width)
                label.setIconSize(icon_size, icon_space)
                label.setCardWidth(scaled_width)

        self._position_badges(scaled_width)

        if self.base_font_size is not None:
            font = self.nameLabel.font()
            new_font_size = self.base_font_size * self._scale
            if new_font_size > 0:
                font.setPointSizeF(new_font_size)
                self.nameLabel.setFont(font)

        self.shadow.setBlurRadius(int(20 * self._scale))

        self.updateGeometry()
        self.update()

        # Ensure parent layout is updated safely
        parent = self.parentWidget()
        if parent:
            layout = parent.layout()
            if layout:
                layout.invalidate()
                layout.activate()
                layout.update()
            parent.updateGeometry()

    def update_card_size(self, new_width: int):
        self.base_card_width = new_width
        load_pixmap_async(self.cover_path or "", new_width, int(new_width * 1.5), self.on_cover_loaded)
        self.update_scale()

    def update_badge_visibility(self, display_filter: str):
        self.display_filter = display_filter
        self.steam_visible = (str(self.game_source).lower() == "steam" and self.display_filter in ("all", "favorites"))
        self.egs_visible = (str(self.game_source).lower() == "epic" and self.display_filter in ("all", "favorites"))
        self.portproton_visible = (str(self.game_source).lower() == "portproton" and self.display_filter in ("all", "favorites"))
        protondb_visible = bool(self.getProtonDBText(self.protondb_tier))
        anticheat_visible = bool(self.getAntiCheatText(self.anticheat_status))

        self.steamLabel.setVisible(self.steam_visible)
        self.egsLabel.setVisible(self.egs_visible)
        self.portprotonLabel.setVisible(self.portproton_visible)
        self.protondbLabel.setVisible(protondb_visible)
        self.anticheatLabel.setVisible(anticheat_visible)

        scaled_width = int(self.base_card_width * self._scale)
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

    def open_portproton_forum_topic(self):
        result = self.portproton_api.get_forum_topic_slug(self.name)
        base_url = "https://linux-gaming.ru/"
        if result.startswith("search?q="):
            url = QUrl(f"{base_url}{result}")
        else:
            url = QUrl(f"{base_url}t/{result}")
        QDesktopServices.openUrl(url)

    def open_protondb_report(self):
        url = QUrl(f"https://www.protondb.com/app/{self.appid}")
        QDesktopServices.openUrl(url)

    def open_steam_page(self):
        url = QUrl(f"https://steamcommunity.com/app/{self.appid}")
        QDesktopServices.openUrl(url)

    def open_weanticheatyet_page(self):
        formatted_name = self.name.lower().replace(" ", "-")
        url = QUrl(f"https://areweanticheatyet.com/game/{formatted_name}")
        QDesktopServices.openUrl(url)

    def update_favorite_icon(self):
        if self.is_favorite:
            self.favoriteLabel.setText("★")
        else:
            self.favoriteLabel.setText("☆")
        self.favoriteLabel.setStyleSheet(self.theme.FAVORITE_LABEL_STYLE)

        parent = self.parent()
        while parent:
            if hasattr(parent, 'game_library_manager'):
                QTimer.singleShot(0, parent.game_library_manager.update_game_grid) # type: ignore[attr-defined]
                break
            parent = parent.parent()

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

    borderWidth = Property(int, getBorderWidth, setBorderWidth, None, "", notify=cast(Callable[[], None], borderWidthChanged))
    gradientAngle = Property(float, getGradientAngle, setGradientAngle, None, "", notify=cast(Callable[[], None], gradientAngleChanged))
    scale = Property(float, getScale, setScale, None, "", notify=cast(Callable[[], None], scaleChanged))


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
            self.select_callback(
                self.name,
                self.description,
                self.cover_path,
                self.appid,
                self.controller_support,
                self.exec_line,
                self.last_launch,
                self.formatted_playtime,
                self.protondb_tier,
                self.game_source,
                self.anticheat_status
            )
        super().mousePressEvent(event)


    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.select_callback(
                self.name,
                self.description,
                self.cover_path,
                self.appid,
                self.controller_support,
                self.exec_line,
                self.last_launch,
                self.formatted_playtime,
                self.protondb_tier,
                self.game_source,
                self.anticheat_status
            )
        else:
            super().keyPressEvent(event)
