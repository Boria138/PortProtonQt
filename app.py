import sys
import os
import glob
import configparser
import shlex
import requests
import subprocess
from io import BytesIO
from PySide6 import QtWidgets, QtCore, QtGui

def load_pixmap(cover, width, height):
    """
    Загружает изображение из локального файла или по URL и масштабирует его.
    Если загрузка не удалась, создаёт резервное изображение.
    Если ссылка ведёт на Steam CDN, обложка кешируется локально в папке images.
    """
    pixmap = QtGui.QPixmap()

    # Если ссылка на обложку ведёт на Steam CDN
    if cover.startswith("https://steamcdn-a.akamaihd.net/steam/apps/"):
        try:
            parts = cover.split("/")
            if "apps" in parts:
                idx = parts.index("apps")
                appid = parts[idx + 1]
            else:
                appid = None

            if appid:
                images_folder = "images"
                if not os.path.exists(images_folder):
                    os.makedirs(images_folder)
                local_path = os.path.join(images_folder, f"{appid}.jpg")
                if os.path.exists(local_path):
                    pixmap.load(local_path)
                else:
                    response = requests.get(cover)
                    if response.status_code == 200:
                        with open(local_path, "wb") as f:
                            f.write(response.content)
                        pixmap.load(local_path)
        except Exception as e:
            print("Ошибка загрузки обложки из Steam CDN:", e)
    elif cover.startswith("http"):
        try:
            response = requests.get(cover)
            if response.status_code == 200:
                pixmap.loadFromData(response.content)
        except Exception as e:
            print("Ошибка загрузки обложки из URL:", e)
    elif QtCore.QFile.exists(cover):
        pixmap.load(cover)

    if not pixmap or pixmap.isNull():
        pixmap = QtGui.QPixmap(width, height)
        pixmap.fill(QtGui.QColor("#333333"))
        painter = QtGui.QPainter(pixmap)
        painter.setPen(QtGui.QPen(QtGui.QColor("white")))
        painter.setFont(QtGui.QFont("Poppins", 12))
        painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, "No Image")
        painter.end()
    return pixmap.scaled(width, height, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)

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

class GameCard(QtWidgets.QFrame):
    def __init__(self, name, description, cover_path, appid, exec_line, select_callback, parent=None):
        super().__init__(parent)
        self.name = name
        self.description = description
        self.cover_path = cover_path
        self.appid = appid
        self.exec_line = exec_line
        self.select_callback = select_callback

        self.setFixedSize(250, 400)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setStyleSheet("""
            QFrame {
                border-radius: 15px;
                background-color: #000;
            }
            QFrame:focus {
                border: 2px solid #00fff5;
            }
        """)
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QtGui.QColor(0, 0, 0, 150))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        coverLabel = QtWidgets.QLabel()
        coverLabel.setFixedSize(250, 300)
        pixmap = load_pixmap(cover_path, 250, 300) if cover_path else load_pixmap("", 250, 300)
        coverLabel.setPixmap(pixmap)
        coverLabel.setScaledContents(True)
        coverLabel.setStyleSheet("border-top-left-radius: 15px; border-top-right-radius: 15px;")
        layout.addWidget(coverLabel)

        nameLabel = QtWidgets.QLabel(name)
        nameLabel.setAlignment(QtCore.Qt.AlignCenter)
        nameLabel.setStyleSheet("""
            color: white;
            font-family: 'Orbitron';
            font-size: 18px;
            font-weight: bold;
            background-color: #111;
            border-bottom-left-radius: 15px;
            border-bottom-right-radius: 15px;
            padding: 8px;
        """)
        layout.addWidget(nameLabel)

    def mousePressEvent(self, event):
        self.select_callback(self.name, self.description, self.cover_path, self.appid, self.exec_line)

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.select_callback(self.name, self.description, self.cover_path, self.appid, self.exec_line)
        else:
            super().keyPressEvent(event)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PortProton Cyberpunk")
        self.resize(1280, 720)
        self.setMinimumSize(800, 600)

        self.requests_session = requests.Session()
        self.steam_apps = None
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

    def load_steam_apps(self):
        if self.steam_apps is None:
            app_list_url = "http://api.steampowered.com/ISteamApps/GetAppList/v2/"
            try:
                response = self.requests_session.get(app_list_url)
                if response.status_code == 200:
                    data = response.json()
                    self.steam_apps = data.get("applist", {}).get("apps", [])
                else:
                    self.steam_apps = []
            except Exception as e:
                print("Ошибка загрузки списка приложений Steam:", e)
                self.steam_apps = []
        return self.steam_apps

    def get_steam_game_info(self, desktop_name, exec_line):
        """
        Поиск Steam‑информации производится по трем вариантам:
          1. Имя из desktop файла,
          2. Имя папки (из пути к exe),
          3. Имя исполняемого файла.
        Если найден appid, то в качестве обложки используется ссылка вида:
          https://steamcdn-a.akamaihd.net/steam/apps/<appid>/library_600x900_2x.jpg
        При наличии объекта fullgame сразу используется её информация (так как нас не волнуют DLC и саундтреки).
        """
        try:
            parts = shlex.split(exec_line)
            game_exe = parts[3] if len(parts) >= 4 else exec_line
            folder_name = os.path.basename(os.path.dirname(game_exe)) if os.path.dirname(game_exe) else ""
            exe_name = os.path.splitext(os.path.basename(game_exe))[0]
            candidates = [desktop_name, folder_name, exe_name]

            steam_apps = self.load_steam_apps()
            if not hasattr(self, 'steam_apps_index'):
                self.steam_apps_index = {app["name"].lower(): app for app in steam_apps}

            matching_app = None
            for candidate in candidates:
                candidate_lower = candidate.lower()
                if candidate_lower in self.steam_apps_index:
                    matching_app = self.steam_apps_index[candidate_lower]
                    break
                matching_app = next((app for app in steam_apps if candidate_lower in app["name"].lower()), None)
                if matching_app:
                    break

            if matching_app:
                appid = matching_app["appid"]

                if not hasattr(self, 'steam_details_cache'):
                    self.steam_details_cache = {}

                if appid in self.steam_details_cache:
                    app_info = self.steam_details_cache[appid]
                else:
                    details_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=russian"
                    details_response = self.requests_session.get(details_url)
                    if details_response.status_code != 200:
                        return {"appid": "", "name": exe_name.capitalize(), "description": "", "cover": ""}
                    details_data = details_response.json()
                    app_details = details_data.get(str(appid), {})
                    if not app_details.get("success"):
                        return {"appid": "", "name": exe_name.capitalize(), "description": "", "cover": ""}
                    app_info = app_details.get("data", {})

                    # Если есть информация о fullgame, сразу используем её,
                    # поскольку нас не волнуют DLC и саундтреки.
                    if app_info.get("fullgame", {}).get("appid"):
                        fullgame_appid = app_info["fullgame"]["appid"]
                        if fullgame_appid in self.steam_details_cache:
                            app_info = self.steam_details_cache[fullgame_appid]
                            appid = fullgame_appid
                        else:
                            details_url = f"https://store.steampowered.com/api/appdetails?appids={fullgame_appid}&l=russian"
                            details_response = self.requests_session.get(details_url)
                            if details_response.status_code == 200:
                                fullgame_details = details_response.json().get(str(fullgame_appid), {})
                                if fullgame_details.get("success"):
                                    app_info = fullgame_details.get("data", {})
                                    appid = fullgame_appid
                                    self.steam_details_cache[fullgame_appid] = app_info
                    self.steam_details_cache[matching_app["appid"]] = app_info

                title = app_info.get("name", exe_name.capitalize())
                description = app_info.get("short_description", "")
                # Формируем URL обложки по appid
                if appid:
                    cover = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"
                else:
                    cover = app_info.get("capsule_image", "")
                return {"appid": appid, "name": title, "description": description, "cover": cover}

            return {"appid": "", "name": exe_name.capitalize(), "description": "", "cover": ""}
        except Exception as e:
            print(f"Ошибка получения данных из Steam API: {e}")
            return {"appid": "", "name": exe_name.capitalize(), "description": "", "cover": ""}

    def loadGames(self):
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
                    desktop_name = entry.get("Name", "Unknown Game")
                    if desktop_name.lower() == "portproton":
                        continue
                    exec_line = entry.get("Exec", "")
                    steam_info = {}
                    if exec_line:
                        steam_info = self.get_steam_game_info(desktop_name, exec_line)
                        if steam_info is None:
                            continue
                    if steam_info.get("appid"):
                        name = steam_info.get("name")
                        desc = steam_info.get("description")
                        cover = steam_info.get("cover")
                        appid = steam_info.get("appid")
                    else:
                        name = desktop_name
                        desc = entry.get("Comment", "")
                        cover = entry.get("Icon", "")
                        appid = ""
                    games.append((name, desc, cover, appid, exec_line))
            except Exception as e:
                print(f"Ошибка чтения файла {file_path}: {e}")
        return games

    def switchTab(self, index):
        for i, btn in self.tabButtons.items():
            btn.setChecked(i == index)
        self.stackedWidget.setCurrentIndex(index)

    def createSearchWidget(self):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        searchIconLabel = QtWidgets.QLabel()
        searchIconLabel.setFixedSize(30, 30)
        style = QtWidgets.QApplication.style()
        icon = style.standardIcon(QtWidgets.QStyle.SP_FileDialogContentsView)
        searchIconLabel.setPixmap(icon.pixmap(20, 20))
        searchIconLabel.setAlignment(QtCore.Qt.AlignCenter)
        searchEdit = QtWidgets.QLineEdit()
        searchEdit.setPlaceholderText("Поиск игр...")
        searchEdit.setClearButtonEnabled(True)
        searchEdit.setStyleSheet("""
            QLineEdit {
                background-color: #222;
                border: 2px solid #444;
                border-radius: 15px;
                padding-left: 35px;
                padding-right: 10px;
                font-family: 'Poppins';
                font-size: 16px;
                color: white;
            }
            QLineEdit:focus {
                border: 2px solid #00fff5;
            }
        """)
        layout.addWidget(searchIconLabel)
        layout.addWidget(searchEdit)
        layout.setStretch(1, 1)
        return container, searchEdit

    def filterGames(self, text):
        text = text.strip().lower()
        if text == "":
            filtered = self.games
        else:
            filtered = [game for game in self.games if text in game[0].lower()]
        self.populateGamesGrid(filtered)

    def createInstalledTab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QtWidgets.QLabel("Библиотека игр")
        title.setStyleSheet("font-family: 'Orbitron'; font-size: 28px; color: #f5f5f5;")
        layout.addWidget(title)

        addGameButton = QtWidgets.QPushButton("Добавить игру")
        addGameButton.setStyleSheet("font-family: 'Poppins'; font-size: 16px; color: #00fff5;")
        addGameButton.clicked.connect(self.openAddGameDialog)
        layout.addWidget(addGameButton, alignment=QtCore.Qt.AlignLeft)

        searchWidget, self.searchEdit = self.createSearchWidget()
        self.searchEdit.textChanged.connect(self.filterGames)
        layout.addWidget(searchWidget)

        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet("border: none;")
        scrollArea.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        listWidget = QtWidgets.QWidget()
        listWidget.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 15px;
        """)
        self.gamesListLayout = QtWidgets.QGridLayout(listWidget)
        self.gamesListLayout.setSpacing(20)
        self.gamesListLayout.setContentsMargins(10, 10, 10, 10)
        scrollArea.setWidget(listWidget)
        layout.addWidget(scrollArea)

        self.stackedWidget.addWidget(widget)
        self.populateGamesGrid(self.games)

    def populateGamesGrid(self, games_list):
        self.clearLayout(self.gamesListLayout)
        columns = 4
        for idx, (name, desc, cover, appid, exec_line) in enumerate(games_list):
            card = GameCard(name, desc, cover, appid, exec_line, self.openGameDetailPage)
            row = idx // columns
            col = idx % columns
            self.gamesListLayout.addWidget(card, row, col)

    def clearLayout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def openAddGameDialog(self):
        dialog = AddGameDialog(self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            name = dialog.nameEdit.text().strip()
            desc = dialog.descEdit.toPlainText().strip()
            cover = dialog.coverEdit.text().strip()
            self.games.append((name, desc, cover, "", ""))
            self.populateGamesGrid(self.games)

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
        pixmap = load_pixmap(cover_path, 180, 250)
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

    def openGameDetailPage(self, name, description, cover_path=None, appid="", exec_line=""):
        detailPage = QtWidgets.QWidget()
        if cover_path:
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
        pixmap = load_pixmap(cover_path, 300, 400) if cover_path else load_pixmap("", 300, 400)
        imageLabel.setPixmap(pixmap)
        imageLabel.setScaledContents(True)
        coverLayout.addWidget(imageLabel)
        contentFrameLayout.addWidget(coverFrame)
        detailPage._coverPixmap = pixmap

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

        if appid:
            appidLabel = QtWidgets.QLabel(f"Steam AppID: {appid}")
            appidLabel.setStyleSheet("font-family: 'Poppins'; font-size: 16px; color: #fff;")
            detailsLayout.addWidget(appidLabel)

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
        playButton.clicked.connect(lambda: self.launchGame(exec_line))
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

    def launchGame(self, exec_line):
        if not exec_line:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Команда запуска не указана!")
            return
        try:
            entry_exec_split = shlex.split(exec_line)
            if len(entry_exec_split) > 1 and ('data/scripts/start.sh' in entry_exec_split[1]):
                exec_line = f"env START_FROM_STEAM=1 {exec_line[4:]}"
            elif len(entry_exec_split) > 0 and ('flatpak' in entry_exec_split[0]):
                exec_line = f"flatpak run --env=START_FROM_STEAM=1 {exec_line[12:]}"
            subprocess.Popen(exec_line, shell=True)
        except Exception as e:
            print("Ошибка запуска игры:", e)
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Не удалось запустить игру: {e}")

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
