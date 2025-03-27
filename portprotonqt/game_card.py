from PySide6 import QtCore, QtGui, QtWidgets
import portprotonqt.themes.standart.styles as default_styles
from portprotonqt.image_utils import load_pixmap, round_corners
from portprotonqt.localization import _
from portprotonqt.config_utils import read_favorites, save_favorites  # импорт функций работы с избранным

class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

class GameCard(QtWidgets.QFrame):
    def __init__(self, name, description, cover_path, appid, controller_support, exec_line,
                 last_launch, formatted_playtime, protondb_tier, last_launch_ts, playtime_seconds, steam_game,
                 select_callback, theme=None, card_width=250, parent=None):
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
        self.steam_game = steam_game
        self.last_launch_ts = last_launch_ts
        self.playtime_seconds = playtime_seconds

        self.select_callback = select_callback
        self.theme = theme if theme is not None else default_styles

        # Дополнительное пространство для анимации
        extra_margin = 20
        self.setFixedSize(card_width + extra_margin, int(card_width * 1.6) + extra_margin)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setStyleSheet(self.theme.GAME_CARD_WINDOW_STYLE)

        # Параметры анимации обводки
        self._borderWidth = 2
        self._gradientAngle = 0.0
        self._hovered = False

        # Анимации
        self.thickness_anim = QtCore.QPropertyAnimation(self, b"borderWidth")
        self.thickness_anim.setDuration(300)
        self.gradient_anim = None
        self.pulse_anim = None

        # Флаг для отслеживания подключения слота startPulseAnimation
        self._isPulseAnimationConnected = False

        # Тень
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QtGui.QColor(0, 0, 0, 150))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

        # Отступы, чтобы анимация не перекрывалась
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(extra_margin // 2, extra_margin // 2, extra_margin // 2, extra_margin // 2)
        layout.setSpacing(5)

        # Контейнер обложки
        coverWidget = QtWidgets.QWidget()
        coverWidget.setFixedSize(card_width, int(card_width * 1.2))
        coverLayout = QtWidgets.QStackedLayout(coverWidget)
        coverLayout.setContentsMargins(0, 0, 0, 0)
        coverLayout.setStackingMode(QtWidgets.QStackedLayout.StackAll)

        # Обложка
        coverLabel = QtWidgets.QLabel()
        coverLabel.setFixedSize(card_width, int(card_width * 1.2))
        pixmap = load_pixmap(cover_path, card_width, int(card_width * 1.2)) if cover_path else load_pixmap("", card_width, int(card_width * 1.2))
        pixmap = round_corners(pixmap, 15)
        coverLabel.setPixmap(pixmap)
        coverLabel.setStyleSheet(self.theme.COVER_LABEL_STYLE)
        coverLayout.addWidget(coverLabel)

        # Значок избранного (звёздочка) в левом верхнем углу обложки
        self.favoriteLabel = ClickableLabel(coverWidget)
        self.favoriteLabel.setFixedSize(24, 24)
        self.favoriteLabel.move(8, 8)  # позиция: 8 пикселей от левого и верхнего края
        self.favoriteLabel.clicked.connect(self.toggle_favorite)
        # Определяем статус избранного по имени игры
        self.is_favorite = self.name in read_favorites()
        self.update_favorite_icon()
        self.favoriteLabel.raise_()

        # ProtonDB бейдж
        tier_text = self.getProtonDBText(protondb_tier)
        self.protondbLabel = ClickableLabel(coverWidget)
        if tier_text:
            self.protondbLabel.setText(tier_text)
            self.protondbLabel.setStyleSheet(self.theme.PROTONDB_BADGE_STYLE)
            protondb_visible = True
        else:
            self.protondbLabel.setVisible(False)
            protondb_visible = False

        # Steam бейдж
        self.steamLabel = QtWidgets.QLabel(coverWidget)
        self.steamLabel.setText("Steam")
        self.steamLabel.setStyleSheet(self.theme.STEAM_BADGE_STYLE)
        steam_visible = (str(steam_game).lower() == "true")
        self.steamLabel.setVisible(steam_visible)
        self.steamLabel.adjustSize()

        # Расположение бейджей
        right_margin = 8
        badge_spacing = 5
        top_y = 10
        if steam_visible and protondb_visible:
            steam_width = self.steamLabel.width()
            steam_x = card_width - steam_width - right_margin
            self.steamLabel.move(steam_x, top_y)

            protondb_width = self.protondbLabel.width()
            protondb_x = card_width - protondb_width - right_margin
            protondb_y = top_y + self.steamLabel.height() + badge_spacing
            self.protondbLabel.move(protondb_x, protondb_y)
        elif steam_visible:
            steam_width = self.steamLabel.width()
            steam_x = card_width - steam_width - right_margin
            self.steamLabel.move(steam_x, top_y)
        elif protondb_visible:
            protondb_width = self.protondbLabel.width()
            protondb_x = card_width - protondb_width - right_margin
            self.protondbLabel.move(protondb_x, top_y)

        self.protondbLabel.raise_()
        self.steamLabel.raise_()
        self.protondbLabel.clicked.connect(self.open_protondb_report)

        layout.addWidget(coverWidget)

        # Название игры
        nameLabel = QtWidgets.QLabel(name)
        nameLabel.setAlignment(QtCore.Qt.AlignCenter)
        nameLabel.setStyleSheet(self.theme.GAME_CARD_NAME_LABEL_STYLE)
        layout.addWidget(nameLabel)

    def getProtonDBText(self, tier):
        if not tier:
            return ""
        translations = {
            "platinum": _("Platinum"),
            "gold": _("Gold"),
            "silver": _("Silver"),
            "bronze": _("Bronze"),
            "borked": _("Borked"),
            "pending": _("Pending")
        }
        return translations.get(tier.lower(), "")

    def open_protondb_report(self):
        url = QtCore.QUrl(f"https://www.protondb.com/app/{self.appid}")
        QtGui.QDesktopServices.openUrl(url)

    def update_favorite_icon(self):
        """
        Обновляет отображение значка избранного.
        Если игра избранная – отображается заполненная звезда (★),
        иначе – пустая (☆).
        """
        if self.is_favorite:
            self.favoriteLabel.setText("★")
        else:
            self.favoriteLabel.setText("☆")
        self.favoriteLabel.setStyleSheet("color: gold; font-size: 18px; background: transparent;")

    def toggle_favorite(self):
        """
        Переключает статус избранного для данной игры и сохраняет изменения в конфиге.
        """
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
        # При необходимости можно уведомить родительский виджет об изменении порядка карточек.

    def getBorderWidth(self):
        return self._borderWidth

    def setBorderWidth(self, value):
        self._borderWidth = value
        self.update()

    borderWidth = QtCore.Property(int, getBorderWidth, setBorderWidth)

    def getGradientAngle(self):
        return self._gradientAngle

    def setGradientAngle(self, value):
        self._gradientAngle = value
        self.update()

    gradientAngle = QtCore.Property(float, getGradientAngle, setGradientAngle)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        pen = QtGui.QPen()
        pen.setWidth(self._borderWidth)
        if self._hovered:
            center = self.rect().center()
            gradient = QtGui.QConicalGradient(center, self._gradientAngle)
            gradient.setColorAt(0, QtGui.QColor("#00fff5"))
            gradient.setColorAt(0.33, QtGui.QColor("#FF5733"))
            gradient.setColorAt(0.66, QtGui.QColor("#9B59B6"))
            gradient.setColorAt(1, QtGui.QColor("#00fff5"))
            pen.setBrush(QtGui.QBrush(gradient))
        else:
            pen.setColor(QtGui.QColor(0, 0, 0, 0))

        painter.setPen(pen)
        radius = 5
        rect = self.rect().adjusted(
            self._borderWidth / 2,
            self._borderWidth / 2,
            -self._borderWidth / 2,
            -self._borderWidth / 2
        )
        painter.drawRoundedRect(rect, radius, radius)

    def startPulseAnimation(self):
        if not self._hovered:
            return
        self.pulse_anim = QtCore.QPropertyAnimation(self, b"borderWidth")
        self.pulse_anim.setDuration(800)
        self.pulse_anim.setLoopCount(-1)
        self.pulse_anim.setKeyValueAt(0, 8)
        self.pulse_anim.setKeyValueAt(0.5, 10)
        self.pulse_anim.setKeyValueAt(1, 8)
        self.pulse_anim.start()

    def enterEvent(self, event):
        self._hovered = True
        self.thickness_anim.stop()
        if self._isPulseAnimationConnected:
            self.thickness_anim.finished.disconnect(self.startPulseAnimation)
            self._isPulseAnimationConnected = False
        self.thickness_anim.setEasingCurve(QtCore.QEasingCurve.OutBack)
        self.thickness_anim.setStartValue(self._borderWidth)
        self.thickness_anim.setEndValue(8)
        self.thickness_anim.finished.connect(self.startPulseAnimation)
        self._isPulseAnimationConnected = True
        self.thickness_anim.start()

        self.gradient_anim = QtCore.QPropertyAnimation(self, b"gradientAngle")
        self.gradient_anim.setDuration(3000)
        self.gradient_anim.setStartValue(0)
        self.gradient_anim.setEndValue(360)
        self.gradient_anim.setLoopCount(-1)
        self.gradient_anim.start()

        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        if self.gradient_anim:
            self.gradient_anim.stop()
            self.gradient_anim = None

        self.thickness_anim.stop()
        if self._isPulseAnimationConnected:
            self.thickness_anim.finished.disconnect(self.startPulseAnimation)
            self._isPulseAnimationConnected = False

        if self.pulse_anim:
            self.pulse_anim.stop()
            self.pulse_anim = None

        self.thickness_anim.setEasingCurve(QtCore.QEasingCurve.InBack)
        self.thickness_anim.setStartValue(self._borderWidth)
        self.thickness_anim.setEndValue(2)
        self.thickness_anim.start()

        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.select_callback(
            self.name,
            self.description,
            self.cover_path,
            self.appid,
            self.controller_support,
            self.exec_line,
            self.last_launch,
            self.formatted_playtime,
            self.protondb_tier
        )

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.select_callback(
                self.name,
                self.description,
                self.cover_path,
                self.appid,
                self.controller_support,
                self.exec_line,
                self.last_launch,
                self.formatted_playtime,
                self.protondb_tier
            )
        else:
            super().keyPressEvent(event)
