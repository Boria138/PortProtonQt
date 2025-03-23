from PySide6 import QtCore, QtGui, QtWidgets
import portprotonqt.themes.standart_lite.styles as default_styles
from portprotonqt.image_utils import load_pixmap, round_corners
from portprotonqt.localization import _

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

        # Задаём размеры карточки
        self.setFixedSize(card_width, int(card_width * 1.6))
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setStyleSheet(self.theme.GAME_CARD_WINDOW_STYLE)

        self._borderWidth = 1
        self._gradientAngle = 0.0
        self._hovered = False

        self.thickness_anim = QtCore.QPropertyAnimation(self, b"borderWidth")
        self.thickness_anim.setDuration(300)

        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QtGui.QColor(0, 0, 0, 150))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Создаём контейнер для обложки с наложением (Stacked Layout)
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

        # Создаем ProtonDB бейдж
        tier_text = self.getProtonDBText(protondb_tier)
        self.protondbLabel = ClickableLabel(coverWidget)
        if tier_text:
            self.protondbLabel.setText(tier_text)
            self.protondbLabel.setStyleSheet(self.theme.PROTONDB_BADGE_STYLE)
            protondb_visible = True
        else:
            self.protondbLabel.setVisible(False)
            protondb_visible = False

        # Создаем Steam бейдж
        self.steamLabel = QtWidgets.QLabel(coverWidget)
        self.steamLabel.setText("Steam")
        self.steamLabel.setStyleSheet(self.theme.STEAM_BADGE_STYLE)
        steam_visible = (str(steam_game).lower() == "true")
        self.steamLabel.setVisible(steam_visible)
        self.steamLabel.adjustSize()

        # Позиционирование бейджей у правого края
        right_margin = 8     # Отступ от правого края
        badge_spacing = 5    # Вертикальный отступ между бейджами
        top_y = 10           # Стартовая позиция сверху

        # Если оба бейджа видны, Steam располагается сверху, ProtonDB ниже
        if steam_visible and protondb_visible:
            steam_width = self.steamLabel.width()
            steam_x = card_width - steam_width - right_margin
            self.steamLabel.move(steam_x, top_y)

            protondb_width = self.protondbLabel.width()
            protondb_x = card_width - protondb_width - right_margin
            protondb_y = top_y + self.steamLabel.height() + badge_spacing
            self.protondbLabel.move(protondb_x, protondb_y)
        # Если виден только Steam – позиционируем его вверху
        elif steam_visible:
            steam_width = self.steamLabel.width()
            steam_x = card_width - steam_width - right_margin
            self.steamLabel.move(steam_x, top_y)
        # Если виден только ProtonDB – позиционируем его вверху
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
        # Открываем URL отчёта с использованием QDesktopServices
        url = QtCore.QUrl(f"https://www.protondb.com/app/{self.appid}")
        QtGui.QDesktopServices.openUrl(url)

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
            gradient.setColorAt(0.5, QtGui.QColor("#9B59B6"))
            gradient.setColorAt(1, QtGui.QColor("#00fff5"))
            pen.setBrush(QtGui.QBrush(gradient))
        else:
            pen.setColor(QtGui.QColor(0, 0, 0, 0))
        painter.setPen(pen)
        rect = self.rect().adjusted(self._borderWidth / 2, self._borderWidth / 2,
                                     -self._borderWidth / 2, -self._borderWidth / 2)
        painter.drawRoundedRect(rect, 15, 15)

    def enterEvent(self, event):
        self._hovered = True
        self.thickness_anim.stop()
        self.thickness_anim.setStartValue(self._borderWidth)
        self.thickness_anim.setEndValue(4)
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
        if hasattr(self, "gradient_anim"):
            self.gradient_anim.stop()
            del self.gradient_anim
        self.thickness_anim.stop()
        self.thickness_anim.setStartValue(self._borderWidth)
        self.thickness_anim.setEndValue(1)
        self.thickness_anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.select_callback(self.name, self.description, self.cover_path, self.appid,
                             self.controller_support, self.exec_line, self.last_launch,
                             self.formatted_playtime, self.protondb_tier)

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.select_callback(self.name, self.description, self.cover_path, self.appid,
                                 self.controller_support, self.exec_line, self.last_launch,
                                 self.formatted_playtime, self.protondb_tier)
        else:
            super().keyPressEvent(event)
