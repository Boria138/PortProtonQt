import sys
import os
import glob
import configparser
from io import BytesIO
from PySide6 import QtWidgets, QtCore, QtGui

class AddGameDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить игру")
        self.setModal(True)
        layout = QtWidgets.QFormLayout(self)

        self.nameEdit = QtWidgets.QLineEdit(self)
        self.descEdit = QtWidgets.QTextEdit(self)
        self.coverEdit = QtWidgets.QLineEdit(self)

        browseButton = QtWidgets.QPushButton("Обзор...", self)
        browseButton.clicked.connect(self.browseCover)
        coverLayout = QtWidgets.QHBoxLayout()
        coverLayout.addWidget(self.coverEdit)
        coverLayout.addWidget(browseButton)

        layout.addRow("Название:", self.nameEdit)
        layout.addRow("Описание:", self.descEdit)
        layout.addRow("Путь к обложке:", coverLayout)

        buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addRow(buttonBox)

    def browseCover(self):
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Выберите обложку", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if fileName:
            self.coverEdit.setText(fileName)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PortProton Cyberpunk")
        self.resize(1280, 720)
        self.setMinimumSize(800, 600)

        self.games = self.loadGames()

        centralWidget = QtWidgets.QWidget()
        self.setCentralWidget(centralWidget)
        mainLayout = QtWidgets.QVBoxLayout(centralWidget)
        mainLayout.setSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        header = QtWidgets.QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QFrame {
                background: rgba(0, 0, 0, 0.6);
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }
        """)
        headerLayout = QtWidgets.QHBoxLayout(header)
        headerLayout.setContentsMargins(20, 0, 20, 0)
        titleLabel = QtWidgets.QLabel("PortProton")
        titleLabel.setStyleSheet("""
            font-family: 'Orbitron';
            font-size: 32px;
            color: #00fff5;
            text-shadow: 0 0 5px #00fff5, 0 0 7px #9B59B6;
        """)
        headerLayout.addWidget(titleLabel)
        headerLayout.addStretch()
        mainLayout.addWidget(header)

        navWidget = QtWidgets.QWidget()
        navWidget.setStyleSheet("""
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 10px;
        """)
        navLayout = QtWidgets.QHBoxLayout(navWidget)
        navLayout.setContentsMargins(10, 0, 10, 0)
        navLayout.setSpacing(5)
        self.tabButtons = {}

        tabs = [
            "Библиотека",
            "Автоустановка",
            "Эмуляторы",
            "Настройки wine",
            "Настройки PortProton"
        ]
        for i, tabName in enumerate(tabs):
            btn = QtWidgets.QPushButton(tabName)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, index=i: self.switchTab(index))
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    padding: 12px 20px;
                    color: #fff;
                    font-family: 'Poppins';
                    text-transform: uppercase;
                    border: none;
                }
                QPushButton:checked {
                    background: linear-gradient(45deg, rgba(0,255,255,0.15), rgba(155,89,182,0.25));
                    color: #00fff5;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    color: #00fff5;
                }
            """)
            navLayout.addWidget(btn)
            self.tabButtons[i] = btn

        self.tabButtons[0].setChecked(True)
        mainLayout.addWidget(navWidget)

        self.stackedWidget = QtWidgets.QStackedWidget()
        mainLayout.addWidget(self.stackedWidget)

        self.createInstalledTab()    # Вкладка 0
        self.createAutoInstallTab()  # Вкладка 1
        self.createEmulatorsTab()    # Вкладка 2
        self.createWineTab()         # Вкладка 3
        self.createPortProtonTab()   # Вкладка 4

        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                             stop:0 #1a1a1a, stop:1 #333333);
            }
            QLabel {
                color: #fff;
            }
        """)

    def loadGames(self):
        """
        Ищет desktop файлы с играми в пользовательском каталоге PortProton.
        Путь к каталогу берётся из конфигурационного файла (~/.config/PortProton.conf)
        или из симлинка ~/PortProton, если файла нет.
        Возвращает список кортежей (название, описание, путь к обложке).
        Пропускает desktop файл самого PortProton.
        """
        games = []
        home = os.path.expanduser("~")
        config_path = os.path.join(home, ".config", "PortProton.conf")
        portproton_location = ""
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as file:
                    portproton_location = file.read().strip()
                print(f"Current PortProton location from config: {portproton_location}")
            except Exception as e:
                print("Ошибка при чтении файла конфигурации PortProton:", e)
        else:
            fallback_dir = os.path.join(home, "PortProton")
            if os.path.exists(fallback_dir) and os.path.isdir(fallback_dir):
                portproton_location = os.path.realpath(fallback_dir)
                print(f"Using fallback PortProton location from symlink: {portproton_location}")
            else:
                print(f"Не найден конфигурационный файл {config_path} и симлинк ~/PortProton не существует.")
                return games

        portproton_files = glob.glob(os.path.join(portproton_location, "*.desktop"))
        for file_path in portproton_files:
            config = configparser.ConfigParser(interpolation=None)
            try:
                config.read(file_path, encoding="utf-8")
                if "Desktop Entry" in config:
                    entry = config["Desktop Entry"]
                    name = entry.get("Name", "Unknown Game")
                    if name.lower() == "portproton":
                        continue
                    desc = entry.get("Comment", "")
                    icon = entry.get("Icon", "")
                    games.append((name, desc, icon))
            except Exception as e:
                print(f"Ошибка чтения файла {file_path}: {e}")
        return games


    def switchTab(self, index):
        for i, btn in self.tabButtons.items():
            btn.setChecked(i == index)
        self.stackedWidget.setCurrentIndex(index)

    def createInstalledTab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        title = QtWidgets.QLabel("Список установленного")
        title.setStyleSheet("font-family: 'Orbitron'; font-size: 24px; color: #f5f5f5;")
        layout.addWidget(title)

        addGameButton = QtWidgets.QPushButton("Добавить игру")
        addGameButton.setStyleSheet("font-family: 'Poppins'; font-size: 16px; color: #00fff5;")
        addGameButton.clicked.connect(self.openAddGameDialog)
        layout.addWidget(addGameButton, alignment=QtCore.Qt.AlignLeft)

        gridWidget = QtWidgets.QWidget()
        self.gamesGridLayout = QtWidgets.QGridLayout(gridWidget)
        self.gamesGridLayout.setSpacing(20)
        for idx, (name, desc, cover) in enumerate(self.games):
            card = self.createGameCard(name, desc, cover)
            self.gamesGridLayout.addWidget(card, idx // 3, idx % 3)

        layout.addWidget(gridWidget)
        layout.addStretch(1)
        self.stackedWidget.addWidget(widget)

    def openAddGameDialog(self):
        dialog = AddGameDialog(self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            name = dialog.nameEdit.text().strip()
            desc = dialog.descEdit.toPlainText().strip()
            cover = dialog.coverEdit.text().strip()
            if name:
                self.games.append((name, desc, cover))
                new_card = self.createGameCard(name, desc, cover)
                index = len(self.games) - 1
                self.gamesGridLayout.addWidget(new_card, index // 3, index % 3)

    def createGameCard(self, name, description, cover_path=None):
        """
        Создаёт карточку игры с эффектом glassmorphism.
        Обложка берётся только из локального файла.
        Если локальный файл не найден, создаётся резервная картинка.
        """
        card = QtWidgets.QFrame()
        card.setFixedSize(180, 300)
        card.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.05);
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.1);
            }
            QFrame:hover {
                background: rgba(255,255,255,0.1);
            }
        """)
        shadow = QtWidgets.QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(15)
        shadow.setColor(QtGui.QColor(0, 255, 255, 100))
        shadow.setOffset(0, 0)
        card.setGraphicsEffect(shadow)

        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)

        imageLabel = QtWidgets.QLabel()
        imageLabel.setFixedSize(180, 250)

        # Используем локальный файл обложки, если он существует
        if cover_path and QtCore.QFile.exists(cover_path):
            pixmap = QtGui.QPixmap(cover_path)
            pixmap = pixmap.scaled(180, 250, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)
        else:
            # Создаем резервную картинку с фоном и текстом
            pixmap = QtGui.QPixmap(180, 250)
            pixmap.fill(QtGui.QColor("#333333"))
            painter = QtGui.QPainter(pixmap)
            painter.setPen(QtGui.QPen(QtGui.QColor("white")))
            painter.setFont(QtGui.QFont("Poppins", 12))
            painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, name)
            painter.end()
        imageLabel.setPixmap(pixmap)
        layout.addWidget(imageLabel)

        titleLabel = QtWidgets.QLabel(name)
        titleLabel.setAlignment(QtCore.Qt.AlignCenter)
        titleLabel.setStyleSheet("font-family: 'Poppins'; font-weight: 600; color: #00fff5;")
        layout.addWidget(titleLabel)

        card.mousePressEvent = lambda event: self.openGameDetailPage(name, description, cover_path)
        return card

    def createAutoInstallTab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QtWidgets.QLabel("Автоустановка")
        title.setStyleSheet("font-family: 'Orbitron'; font-size: 24px; color: #f5f5f5;")
        layout.addWidget(title)
        content = QtWidgets.QLabel("Здесь можно настроить автоматическую установку игр...")
        content.setStyleSheet("font-family: 'Poppins'; font-size: 16px;")
        layout.addWidget(content)
        layout.addStretch(1)
        self.stackedWidget.addWidget(widget)

    def createEmulatorsTab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QtWidgets.QLabel("Эмуляторы")
        title.setStyleSheet("font-family: 'Orbitron'; font-size: 24px; color: #f5f5f5;")
        layout.addWidget(title)
        content = QtWidgets.QLabel("Список доступных эмуляторов и их настройка...")
        content.setStyleSheet("font-family: 'Poppins'; font-size: 16px;")
        layout.addWidget(content)
        layout.addStretch(1)
        self.stackedWidget.addWidget(widget)

    def createWineTab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QtWidgets.QLabel("Настройки wine")
        title.setStyleSheet("font-family: 'Orbitron'; font-size: 24px; color: #f5f5f5;")
        layout.addWidget(title)
        content = QtWidgets.QLabel("Различные параметры и версии wine...")
        content.setStyleSheet("font-family: 'Poppins'; font-size: 16px;")
        layout.addWidget(content)
        layout.addStretch(1)
        self.stackedWidget.addWidget(widget)

    def createPortProtonTab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QtWidgets.QLabel("Настройки PortProton")
        title.setStyleSheet("font-family: 'Orbitron'; font-size: 24px; color: #f5f5f5;")
        layout.addWidget(title)
        content = QtWidgets.QLabel("Основные параметры PortProton...")
        content.setStyleSheet("font-family: 'Poppins'; font-size: 16px;")
        layout.addWidget(content)
        layout.addStretch(1)
        self.stackedWidget.addWidget(widget)

    def getColorPalette(self, cover_path, num_colors=5, sample_step=10):
        """
        Извлекает палитру из нескольких доминирующих цветов обложки.
        """

        pixmap = QtGui.QPixmap(cover_path)
        if pixmap.isNull():
            return [QtGui.QColor("#1a1a1a")] * num_colors
        image = pixmap.toImage()
        width, height = image.width(), image.height()
        histogram = {}
        for x in range(0, width, sample_step):
            for y in range(0, height, sample_step):
                color = image.pixelColor(x, y)
                key = (color.red() // 32, color.green() // 32, color.blue() // 32)
                if key in histogram:
                    histogram[key][0] += color.red()
                    histogram[key][1] += color.green()
                    histogram[key][2] += color.blue()
                    histogram[key][3] += 1
                else:
                    histogram[key] = [color.red(), color.green(), color.blue(), 1]
        avg_colors = []
        for key, (r_sum, g_sum, b_sum, count) in histogram.items():
            avg_r = r_sum // count
            avg_g = g_sum // count
            avg_b = b_sum // count
            avg_colors.append((count, QtGui.QColor(avg_r, avg_g, avg_b)))
        avg_colors.sort(key=lambda x: x[0], reverse=True)
        palette = [color for count, color in avg_colors[:num_colors]]
        if len(palette) < num_colors:
            palette += [palette[-1]] * (num_colors - len(palette))
        return palette

    def darkenColor(self, color, factor=200):
        return color.darker(factor)

    def openGameDetailPage(self, name, description, cover_path=None):
        detailPage = QtWidgets.QWidget()
        if cover_path and QtCore.QFile.exists(cover_path):
            palette = self.getColorPalette(cover_path, num_colors=5)
            dark_palette = [self.darkenColor(color, factor=200) for color in palette]
            stops = ",\n".join(
                [f"stop:{i/(len(dark_palette)-1):.2f} {dark_palette[i].name()}" for i in range(len(dark_palette))]
            )
            detailPage.setStyleSheet(f"""
                QWidget {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                                {stops});
                }}
            """)
        else:
            detailPage.setStyleSheet("background: #1a1a1a;")

        mainLayout = QtWidgets.QVBoxLayout(detailPage)
        mainLayout.setContentsMargins(30, 30, 30, 30)
        mainLayout.setSpacing(20)

        backButton = QtWidgets.QPushButton("Назад")
        backButton.setFixedWidth(100)
        backButton.setStyleSheet("""
            QPushButton {
                background: linear-gradient(45deg, rgba(0,255,255,0.15), rgba(155,89,182,0.25));
                border: none;
                padding: 10px 20px;
                color: #00fff5;
                font-family: 'Poppins';
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: linear-gradient(45deg, rgba(0,255,255,0.25), rgba(155,89,182,0.35));
            }
        """)
        backButton.clicked.connect(lambda: self.goBackDetailPage(detailPage))
        mainLayout.addWidget(backButton, alignment=QtCore.Qt.AlignLeft)

        contentFrame = QtWidgets.QFrame()
        contentFrame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 10px;
            }
        """)
        contentFrameLayout = QtWidgets.QHBoxLayout(contentFrame)
        contentFrameLayout.setContentsMargins(20, 20, 20, 20)
        contentFrameLayout.setSpacing(40)
        mainLayout.addWidget(contentFrame)

        coverFrame = QtWidgets.QFrame()
        coverFrame.setFixedSize(300, 400)
        coverFrame.setStyleSheet("""
            QFrame {
                background: #222222;
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.1);
            }
        """)
        shadow = QtWidgets.QGraphicsDropShadowEffect(coverFrame)
        shadow.setBlurRadius(20)
        shadow.setColor(QtGui.QColor(0, 0, 0, 200))
        shadow.setOffset(0, 0)
        coverFrame.setGraphicsEffect(shadow)
        coverLayout = QtWidgets.QVBoxLayout(coverFrame)
        coverLayout.setContentsMargins(0, 0, 0, 0)
        imageLabel = QtWidgets.QLabel()
        imageLabel.setFixedSize(300, 400)
        if cover_path and QtCore.QFile.exists(cover_path):
            pixmap = QtGui.QPixmap(cover_path)
            pixmap = pixmap.scaled(300, 400, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)
        else:
            pixmap = QtGui.QPixmap(300, 400)
            pixmap.fill(QtGui.QColor("#333333"))
            painter = QtGui.QPainter(pixmap)
            painter.setPen(QtGui.QPen(QtGui.QColor("white")))
            painter.setFont(QtGui.QFont("Poppins", 14))
            painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, name)
            painter.end()
        imageLabel.setPixmap(pixmap)
        coverLayout.addWidget(imageLabel)
        contentFrameLayout.addWidget(coverFrame)

        detailsWidget = QtWidgets.QWidget()
        detailsWidget.setStyleSheet("background: rgba(255,255,255,0.05); border-radius: 10px;")
        detailsLayout = QtWidgets.QVBoxLayout(detailsWidget)
        detailsLayout.setContentsMargins(20, 20, 20, 20)
        detailsLayout.setSpacing(15)

        titleLabel = QtWidgets.QLabel(name)
        titleLabel.setStyleSheet("font-family: 'Orbitron'; font-size: 32px; color: #00fff5;")
        detailsLayout.addWidget(titleLabel)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet("color: rgba(255,255,255,0.2);")
        detailsLayout.addWidget(line)

        descLabel = QtWidgets.QLabel(description)
        descLabel.setWordWrap(True)
        descLabel.setStyleSheet("font-family: 'Poppins'; font-size: 16px; color: #fff;")
        detailsLayout.addWidget(descLabel)

        detailsLayout.addStretch(1)
        playButton = QtWidgets.QPushButton("Играть")
        playButton.setFixedSize(120, 40)
        playButton.setStyleSheet("""
            QPushButton {
                background: linear-gradient(45deg, rgba(0,255,255,0.15), rgba(155,89,182,0.25));
                border: none;
                border-radius: 5px;
                font-family: 'Poppins';
                font-size: 16px;
                color: #00fff5;
                font-weight: bold;
            }
            QPushButton:hover {
                background: linear-gradient(45deg, rgba(0,255,255,0.25), rgba(155,89,182,0.35));
            }
        """)
        detailsLayout.addWidget(playButton, alignment=QtCore.Qt.AlignLeft)
        contentFrameLayout.addWidget(detailsWidget)

        mainLayout.addStretch()

        self.stackedWidget.addWidget(detailPage)
        self.stackedWidget.setCurrentWidget(detailPage)

        opacityEffect = QtWidgets.QGraphicsOpacityEffect(detailPage)
        detailPage.setGraphicsEffect(opacityEffect)
        animation = QtCore.QPropertyAnimation(opacityEffect, b"opacity")
        animation.setDuration(800)
        animation.setStartValue(0)
        animation.setEndValue(1)
        animation.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        detailPage.animation = animation
        animation.finished.connect(lambda: detailPage.setGraphicsEffect(None))

    def goBackDetailPage(self, page):
        self.stackedWidget.setCurrentIndex(0)
        self.stackedWidget.removeWidget(page)
        page.deleteLater()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
