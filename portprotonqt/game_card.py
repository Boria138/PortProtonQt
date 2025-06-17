from PySide6.QtGui import QPainter, QPen, QColor, QConicalGradient, QBrush, QDesktopServices
from PySide6.QtCore import QEasingCurve, Signal, Property, Qt, QPropertyAnimation, QByteArray, QUrl
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QVBoxLayout, QWidget, QStackedLayout, QLabel
from collections.abc import Callable
import portprotonqt.themes.standart.styles as default_styles
from portprotonqt.image_utils import load_pixmap_async, round_corners
from portprotonqt.localization import _
from portprotonqt.config_utils import read_favorites, save_favorites, read_display_filter
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.config_utils import read_theme_from_config
from portprotonqt.custom_widgets import ClickableLabel
import weakref
from typing import cast

class GameCard(QFrame):
    borderWidthChanged = Signal()
    gradientAngleChanged = Signal()
    # Signals for context menu actions
    editShortcutRequested = Signal(str, str, str) # name, exec_line, cover_path
    deleteGameRequested = Signal(str, str)        # name, exec_line
    addToMenuRequested = Signal(str, str)         # name, exec_line
    removeFromMenuRequested = Signal(str)         # name
    addToDesktopRequested = Signal(str, str)      # name, exec_line
    removeFromDesktopRequested = Signal(str)      # name
    addToSteamRequested = Signal(str, str, str)   # name, exec_line, cover_path
    removeFromSteamRequested = Signal(str, str)   # name, exec_line
    openGameFolderRequested = Signal(str, str)    # name, exec_line
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
        self.card_width = card_width

        self.select_callback = select_callback
        self.context_menu_manager = context_menu_manager
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.theme_manager = ThemeManager()
        self.theme = theme if theme is not None else default_styles

        self.display_filter = read_display_filter()
        self.current_theme_name = read_theme_from_config()

        self.steam_visible = (str(game_source).lower() == "steam" and self.display_filter in ("all", "favorites"))
        self.egs_visible = (str(game_source).lower() == "epic" and self.display_filter in ("all", "favorites"))
        self.portproton_visible = (str(game_source).lower() == "portproton" and self.display_filter in ("all", "favorites"))

        # Дополнительное пространство для анимации
        extra_margin = 20
        self.setFixedSize(card_width + extra_margin, int(card_width * 1.6) + extra_margin)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(self.theme.GAME_CARD_WINDOW_STYLE)

        # Параметры анимации обводки
        self._borderWidth = self.theme.GAME_CARD_ANIMATION["default_border_width"]
        self._gradientAngle = self.theme.GAME_CARD_ANIMATION["gradient_start_angle"]
        self._hovered = False
        self._focused = False

        # Анимации
        self.thickness_anim = QPropertyAnimation(self, QByteArray(b"borderWidth"))
        self.thickness_anim.setDuration(self.theme.GAME_CARD_ANIMATION["thickness_anim_duration"])
        self.gradient_anim = None
        self.pulse_anim = None

        # Флаг для отслеживания подключения слота startPulseAnimation
        self._isPulseAnimationConnected = False

        # Тень
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

        # Отступы
        layout = QVBoxLayout(self)
        layout.setContentsMargins(extra_margin // 2, extra_margin // 2, extra_margin // 2, extra_margin // 2)
        layout.setSpacing(5)

        # Контейнер обложки
        coverWidget = QWidget()
        coverWidget.setFixedSize(card_width, int(card_width * 1.2))
        coverLayout = QStackedLayout(coverWidget)
        coverLayout.setContentsMargins(0, 0, 0, 0)
        coverLayout.setStackingMode(QStackedLayout.StackingMode.StackAll)

        # Обложка
        self.coverLabel = QLabel()
        self.coverLabel.setFixedSize(card_width, int(card_width * 1.2))
        self.coverLabel.setStyleSheet(self.theme.COVER_LABEL_STYLE)
        coverLayout.addWidget(self.coverLabel)

        # создаём слабую ссылку на label
        label_ref = weakref.ref(self.coverLabel)

        def on_cover_loaded(pixmap):
            label = label_ref()
            if label is None:
                return
            label.setPixmap(round_corners(pixmap, 15))

        # асинхронная загрузка обложки (пустая строка даст placeholder внутри load_pixmap_async)
        load_pixmap_async(cover_path or "", card_width, int(card_width * 1.2), on_cover_loaded)

        # Значок избранного (звёздочка) в левом верхнем углу обложки
        self.favoriteLabel = ClickableLabel(coverWidget)
        self.favoriteLabel.setFixedSize(*self.theme.favoriteLabelSize)
        self.favoriteLabel.move(8, 8)
        self.favoriteLabel.clicked.connect(self.toggle_favorite)
        self.is_favorite = self.name in read_favorites()
        self.update_favorite_icon()
        self.favoriteLabel.raise_()

        # Определяем общие параметры для бейджей
        badge_width = int(card_width * 2/3)
        icon_size = int(card_width * 0.06)  # 6% от ширины карточки
        icon_space = int(card_width * 0.012)  # 1.2% от ширины карточки
        font_scale_factor = 0.06  # Шрифт будет 6% от card_width

        # ProtonDB бейдж
        tier_text = self.getProtonDBText(protondb_tier)
        if tier_text:
            icon_filename = self.getProtonDBIconFilename(protondb_tier)
            icon = self.theme_manager.get_icon(icon_filename, self.current_theme_name)
            self.protondbLabel = ClickableLabel(
                tier_text,
                icon=icon,
                parent=coverWidget,
                icon_size=icon_size,
                icon_space=icon_space,
                font_scale_factor=font_scale_factor
            )
            self.protondbLabel.setStyleSheet(self.theme.get_protondb_badge_style(protondb_tier))
            self.protondbLabel.setFixedWidth(badge_width)
            self.protondbLabel.setCardWidth(card_width)
        else:
            self.protondbLabel = ClickableLabel("", parent=coverWidget, icon_size=icon_size, icon_space=icon_space)
            self.protondbLabel.setFixedWidth(badge_width)
            self.protondbLabel.setVisible(False)

        # Steam бейдж
        steam_icon = self.theme_manager.get_icon("steam")
        self.steamLabel = ClickableLabel(
            "Steam",
            icon=steam_icon,
            parent=coverWidget,
            icon_size=icon_size,
            icon_space=icon_space,
            font_scale_factor=font_scale_factor
        )
        self.steamLabel.setStyleSheet(self.theme.STEAM_BADGE_STYLE)
        self.steamLabel.setFixedWidth(badge_width)
        self.steamLabel.setCardWidth(card_width)
        self.steamLabel.setVisible(self.steam_visible)

        # Epic Games Store бейдж
        egs_icon = self.theme_manager.get_icon("steam")
        self.egsLabel = ClickableLabel(
            "Epic Games",
            icon=egs_icon,
            parent=coverWidget,
            icon_size=icon_size,
            icon_space=icon_space,
            font_scale_factor=font_scale_factor,
            change_cursor=False
        )
        self.egsLabel.setStyleSheet(self.theme.STEAM_BADGE_STYLE)
        self.egsLabel.setFixedWidth(badge_width)
        self.egsLabel.setCardWidth(card_width)
        self.egsLabel.setVisible(self.egs_visible)

        # PortProton бейдж
        portproton_icon = self.theme_manager.get_icon("ppqt-tray")
        self.portprotonLabel = ClickableLabel(
            "PortProton",
            icon=portproton_icon,
            parent=coverWidget,
            icon_size=icon_size,
            icon_space=icon_space,
            font_scale_factor=font_scale_factor,
            change_cursor=False
        )
        self.portprotonLabel.setStyleSheet(self.theme.STEAM_BADGE_STYLE)
        self.portprotonLabel.setFixedWidth(badge_width)
        self.portprotonLabel.setCardWidth(card_width)
        self.portprotonLabel.setVisible(self.portproton_visible)

        # WeAntiCheatYet бейдж
        anticheat_text = self.getAntiCheatText(anticheat_status)
        if anticheat_text:
            icon_filename = self.getAntiCheatIconFilename(anticheat_status)
            icon = self.theme_manager.get_icon(icon_filename, self.current_theme_name)
            self.anticheatLabel = ClickableLabel(
                anticheat_text,
                icon=icon,
                parent=coverWidget,
                icon_size=icon_size,
                icon_space=icon_space,
                font_scale_factor=font_scale_factor
            )
            self.anticheatLabel.setStyleSheet(self.theme.get_anticheat_badge_style(anticheat_status))
            self.anticheatLabel.setFixedWidth(badge_width)
            self.anticheatLabel.setCardWidth(card_width)
        else:
            self.anticheatLabel = ClickableLabel("", parent=coverWidget, icon_size=icon_size, icon_space=icon_space)
            self.anticheatLabel.setFixedWidth(badge_width)
            self.anticheatLabel.setVisible(False)

        # Расположение бейджей
        self._position_badges(card_width)
        self.protondbLabel.clicked.connect(self.open_protondb_report)
        self.steamLabel.clicked.connect(self.open_steam_page)
        self.anticheatLabel.clicked.connect(self.open_weanticheatyet_page)

        layout.addWidget(coverWidget)

        # Название игры
        nameLabel = QLabel(name)
        nameLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nameLabel.setStyleSheet(self.theme.GAME_CARD_NAME_LABEL_STYLE)
        layout.addWidget(nameLabel)

    def _position_badges(self, card_width):
        """Позиционирует бейджи на основе ширины карточки."""
        right_margin = 8
        badge_spacing = int(card_width * 0.02)  # 2% от ширины карточки
        top_y = 10
        badge_y_positions = []
        badge_width = int(card_width * 2/3)

        badges = [
            (self.steam_visible, self.steamLabel),
            (self.egs_visible, self.egsLabel),
            (self.portproton_visible, self.portprotonLabel),
            (bool(self.getProtonDBText(self.protondb_tier)), self.protondbLabel),
            (bool(self.getAntiCheatText(self.anticheat_status)), self.anticheatLabel),
        ]

        for is_visible, badge in badges:
            if is_visible:
                badge_x = card_width - badge_width - right_margin
                badge_y = badge_y_positions[-1] + badge_spacing if badge_y_positions else top_y
                badge.move(badge_x, badge_y)
                badge_y_positions.append(badge_y + badge.height())

        # Поднимаем бейджи в правильном порядке (от нижнего к верхнему)
        self.anticheatLabel.raise_()
        self.protondbLabel.raise_()
        self.portprotonLabel.raise_()
        self.egsLabel.raise_()
        self.steamLabel.raise_()

    def update_card_size(self, new_width: int):
        """Обновляет размер карточки, обложки и бейджей."""
        self.card_width = new_width
        extra_margin = 20
        self.setFixedSize(new_width + extra_margin, int(new_width * 1.6) + extra_margin)

        if self.coverLabel is None:
            return

        coverWidget = self.coverLabel.parentWidget()
        if coverWidget is None:
            return

        coverWidget.setFixedSize(new_width, int(new_width * 1.2))
        self.coverLabel.setFixedSize(new_width, int(new_width * 1.2))

        label_ref = weakref.ref(self.coverLabel)
        def on_cover_loaded(pixmap):
            label = label_ref()
            if label:
                scaled_pixmap = pixmap.scaled(new_width, int(new_width * 1.2), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                rounded_pixmap = round_corners(scaled_pixmap, 15)
                label.setPixmap(rounded_pixmap)

        load_pixmap_async(self.cover_path or "", new_width, int(new_width * 1.2), on_cover_loaded)

        # Обновляем размеры и шрифты бейджей
        badge_width = int(new_width * 2/3)
        icon_size = int(new_width * 0.06)
        icon_space = int(new_width * 0.012)
        for label in [self.steamLabel, self.egsLabel, self.portprotonLabel, self.protondbLabel, self.anticheatLabel]:
            if label is not None:
                label.setFixedWidth(badge_width)
                label.setIconSize(icon_size, icon_space)
                label.setCardWidth(new_width)  # Пересчитываем размер шрифта

        # Перепозиционируем бейджи
        self._position_badges(new_width)

        self.update()

    def update_badge_visibility(self, display_filter: str):
        """Обновляет видимость бейджей на основе display_filter."""
        self.display_filter = display_filter
        self.steam_visible = (str(self.game_source).lower() == "steam" and display_filter in ("all", "favorites"))
        self.egs_visible = (str(self.game_source).lower() == "epic" and display_filter in ("all", "favorites"))
        self.portproton_visible = (str(self.game_source).lower() == "portproton" and display_filter in ("all", "favorites"))
        protondb_visible = bool(self.getProtonDBText(self.protondb_tier))
        anticheat_visible = bool(self.getAntiCheatText(self.anticheat_status))

        # Обновляем видимость бейджей
        self.steamLabel.setVisible(self.steam_visible)
        self.egsLabel.setVisible(self.egs_visible)
        self.portprotonLabel.setVisible(self.portproton_visible)
        self.protondbLabel.setVisible(protondb_visible)
        self.anticheatLabel.setVisible(anticheat_visible)

        # Перепозиционируем бейджи
        self._position_badges(self.card_width)

    def _show_context_menu(self, pos):
        """Delegate context menu display to ContextMenuManager."""
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

    def toggle_favorite(self):
        favorites = read_favorites()
        if self.is_favorite:
            if self.name in favorites:
                favorites.remove(self.name)
            self.is_favorite = False
        else:
            if self.name not in favorites:
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

    borderWidth = Property(int, getBorderWidth, setBorderWidth, None, "", notify=cast(Callable[[], None], borderWidthChanged))
    gradientAngle = Property(float, getGradientAngle, setGradientAngle, None, "", notify=cast(Callable[[], None], gradientAngleChanged))

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen()
        pen.setWidth(self._borderWidth)
        if self._hovered or self._focused:
            center = self.rect().center()
            gradient = QConicalGradient(center, self._gradientAngle)
            for stop in self.theme.GAME_CARD_ANIMATION["gradient_colors"]:
                gradient.setColorAt(stop["position"], QColor(stop["color"]))
            pen.setBrush(QBrush(gradient))
        else:
            pen.setColor(QColor(0, 0, 0, 0))

        painter.setPen(pen)
        radius = 18
        bw = round(self._borderWidth / 2)
        rect = self.rect().adjusted(bw, bw, -bw, -bw)
        painter.drawRoundedRect(rect, radius, radius)

    def startPulseAnimation(self):
        if not (self._hovered or self._focused):
            return
        if self.pulse_anim:
            self.pulse_anim.stop()
        self.pulse_anim = QPropertyAnimation(self, QByteArray(b"borderWidth"))
        self.pulse_anim.setDuration(self.theme.GAME_CARD_ANIMATION["pulse_anim_duration"])
        self.pulse_anim.setLoopCount(0)
        self.pulse_anim.setKeyValueAt(0, self.theme.GAME_CARD_ANIMATION["pulse_min_border_width"])
        self.pulse_anim.setKeyValueAt(0.5, self.theme.GAME_CARD_ANIMATION["pulse_max_border_width"])
        self.pulse_anim.setKeyValueAt(1, self.theme.GAME_CARD_ANIMATION["pulse_min_border_width"])
        self.pulse_anim.start()

    def enterEvent(self, event):
        self._hovered = True
        self.hoverChanged.emit(self.name, True)
        self.setFocus(Qt.FocusReason.MouseFocusReason)

        self.thickness_anim.stop()
        if self._isPulseAnimationConnected:
            self.thickness_anim.finished.disconnect(self.startPulseAnimation)
            self._isPulseAnimationConnected = False
        self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve"]]))
        self.thickness_anim.setStartValue(self._borderWidth)
        self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["hover_border_width"])
        self.thickness_anim.finished.connect(self.startPulseAnimation)
        self._isPulseAnimationConnected = True
        self.thickness_anim.start()

        if self.gradient_anim:
            self.gradient_anim.stop()
        self.gradient_anim = QPropertyAnimation(self, QByteArray(b"gradientAngle"))
        self.gradient_anim.setDuration(self.theme.GAME_CARD_ANIMATION["gradient_anim_duration"])
        self.gradient_anim.setStartValue(self.theme.GAME_CARD_ANIMATION["gradient_start_angle"])
        self.gradient_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["gradient_end_angle"])
        self.gradient_anim.setLoopCount(-1)
        self.gradient_anim.start()

        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.hoverChanged.emit(self.name, False)
        if not self._focused:
            if self.gradient_anim:
                self.gradient_anim.stop()
                self.gradient_anim = None
            if self.pulse_anim:
                self.pulse_anim.stop()
                self.pulse_anim = None
            if self.thickness_anim:
                self.thickness_anim.stop()
            if self._isPulseAnimationConnected:
                self.thickness_anim.finished.disconnect(self.startPulseAnimation)
                self._isPulseAnimationConnected = False
            self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve_out"]]))
            self.thickness_anim.setStartValue(self._borderWidth)
            self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["default_border_width"])
            self.thickness_anim.start()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        if not self._hovered:
            self._focused = True
            self.focusChanged.emit(self.name, True)

            self.thickness_anim.stop()
            if self._isPulseAnimationConnected:
                self.thickness_anim.finished.disconnect(self.startPulseAnimation)
                self._isPulseAnimationConnected = False
            self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve"]]))
            self.thickness_anim.setStartValue(self._borderWidth)
            self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["focus_border_width"])
            self.thickness_anim.finished.connect(self.startPulseAnimation)
            self._isPulseAnimationConnected = True
            self.thickness_anim.start()

            if self.gradient_anim:
                self.gradient_anim.stop()
            self.gradient_anim = QPropertyAnimation(self, QByteArray(b"gradientAngle"))
            self.gradient_anim.setDuration(self.theme.GAME_CARD_ANIMATION["gradient_anim_duration"])
            self.gradient_anim.setStartValue(self.theme.GAME_CARD_ANIMATION["gradient_start_angle"])
            self.gradient_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["gradient_end_angle"])
            self.gradient_anim.setLoopCount(-1)
            self.gradient_anim.start()

        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._focused = False
        self.focusChanged.emit(self.name, False)
        if not self._hovered:
            if self.gradient_anim:
                self.gradient_anim.stop()
                self.gradient_anim = None
            if self.pulse_anim:
                self.pulse_anim.stop()
                self.pulse_anim = None
            if self.thickness_anim:
                self.thickness_anim.stop()
            if self._isPulseAnimationConnected:
                self.thickness_anim.finished.disconnect(self.startPulseAnimation)
                self._isPulseAnimationConnected = False
            self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve_out"]]))
            self.thickness_anim.setStartValue(self._borderWidth)
            self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["default_border_width"])
            self.thickness_anim.start()
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
