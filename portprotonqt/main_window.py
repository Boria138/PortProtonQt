import os
import signal
import shlex
import configparser
import subprocess
import requests
import concurrent.futures
import psutil

from PySide6 import QtWidgets, QtCore, QtGui

import portprotonqt.themes.standart_lite.styles as default_styles
from portprotonqt.virtual_keyboard import VirtualKeyboard
from portprotonqt.dialogs import AddGameDialog
from portprotonqt.game_card import GameCard
from portprotonqt.image_utils import load_pixmap, round_corners
from portprotonqt.steam_api import get_steam_game_info
from portprotonqt.gamepad_support import GamepadSupport
from portprotonqt.theme_manager import ThemeManager

CONFIG_FILE = os.path.join(os.getenv("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")),
                           "PortProtonQT.conf")

def read_theme_from_config():
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE, encoding="utf-8")
            return config.get("Appearance", "theme", fallback="standart_lite")
        except Exception as e:
            print("Ошибка чтения конфигурации темы:", e)
    return "standart_lite"

def save_theme_to_config(theme_name):
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding="utf-8")
    if "Appearance" not in config:
        config["Appearance"] = {}
    config["Appearance"]["theme"] = theme_name
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
            config.write(configfile)
    except Exception as e:
        print("Ошибка сохранения конфигурации темы:", e)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # Создаём менеджер тем
        self.theme_manager = ThemeManager()
        selected_theme = read_theme_from_config()
        self.current_theme_name = selected_theme
        self.theme = self.theme_manager.apply_theme(selected_theme)
        if not self.theme:
            self.theme = default_styles

        self.gamepad_support = GamepadSupport(self)
        self.setWindowTitle("PortProtonQT")
        self.resize(1280, 720)
        self.setMinimumSize(800, 600)

        self.requests_session = requests.Session()
        self.games = self.loadGames()
        self.game_processes = []
        # Имя целевого exe, которое будем отслеживать
        self.target_exe = None

        # Создаём статус-бар
        self.setStatusBar(QtWidgets.QStatusBar(self))

        centralWidget = QtWidgets.QWidget()
        self.setCentralWidget(centralWidget)
        mainLayout = QtWidgets.QVBoxLayout(centralWidget)
        mainLayout.setSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        # Заголовок
        self.header = QtWidgets.QFrame()
        self.header.setFixedHeight(80)
        self.header.setStyleSheet(self.theme.MAIN_WINDOW_HEADER_STYLE)
        headerLayout = QtWidgets.QHBoxLayout(self.header)
        headerLayout.setContentsMargins(20, 0, 20, 0)
        self.titleLabel = QtWidgets.QLabel("PortProton")
        self.titleLabel.setStyleSheet(self.theme.TITLE_LABEL_STYLE)
        headerLayout.addWidget(self.titleLabel)
        headerLayout.addStretch()
        self.keyboardButton = QtWidgets.QPushButton("Клавиатура")
        self.keyboardButton.setStyleSheet(self.theme.VIRTUAL_KEYBOARD_KEYS_STYLE)
        self.keyboardButton.clicked.connect(self.toggleKeyboard)
        headerLayout.addWidget(self.keyboardButton)
        mainLayout.addWidget(self.header)

        # Навигация
        self.navWidget = QtWidgets.QWidget()
        self.navWidget.setStyleSheet(self.theme.NAV_WIDGET_STYLE)
        navLayout = QtWidgets.QHBoxLayout(self.navWidget)
        navLayout.setContentsMargins(10, 0, 10, 0)
        navLayout.setSpacing(5)
        self.tabButtons = {}
        tabs = [
            "Библиотека",
            "Автоустановка",
            "Эмуляторы",
            "Настройки wine",
            "Настройки PortProton",
            "Темы"
        ]
        for i, tabName in enumerate(tabs):
            btn = QtWidgets.QPushButton(tabName)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, index=i: self.switchTab(index))
            btn.setStyleSheet(self.theme.NAV_BUTTON_STYLE)
            navLayout.addWidget(btn)
            self.tabButtons[i] = btn

        self.tabButtons[0].setChecked(True)
        mainLayout.addWidget(self.navWidget)

        # Стек виджетов (вкладок)
        self.stackedWidget = QtWidgets.QStackedWidget()
        mainLayout.addWidget(self.stackedWidget)

        # Создаём вкладки
        self.createInstalledTab()    # вкладка 0
        self.createAutoInstallTab()  # вкладка 1
        self.createEmulatorsTab()    # вкладка 2
        self.createWineTab()         # вкладка 3
        self.createPortProtonTab()   # вкладка 4
        self.createThemeTab()        # вкладка 5

        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE)

        self.virtualKeyboard = VirtualKeyboard(self, target_widget=self.searchEdit)
        self.virtualKeyboard.hide()

    def updateUIStyles(self):
        self.header.setStyleSheet(self.theme.MAIN_WINDOW_HEADER_STYLE)
        self.titleLabel.setStyleSheet(self.theme.TITLE_LABEL_STYLE)
        self.keyboardButton.setStyleSheet(self.theme.VIRTUAL_KEYBOARD_KEYS_STYLE)
        self.navWidget.setStyleSheet(self.theme.NAV_WIDGET_STYLE)
        for btn in self.tabButtons.values():
            btn.setStyleSheet(self.theme.NAV_BUTTON_STYLE)
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE)
        if hasattr(self, 'searchEdit'):
            self.searchEdit.setStyleSheet(self.theme.SEARCH_EDIT_STYLE)

    def toggleKeyboard(self):
        if self.virtualKeyboard.isVisible():
            self.virtualKeyboard.hide()
        else:
            self.searchEdit.setFocus()
            global_bottom_center = self.mapToGlobal(QtCore.QPoint(self.width() // 2, self.height()))
            keyboard_x = global_bottom_center.x() - self.virtualKeyboard.width() // 2
            keyboard_y = global_bottom_center.y() + 10
            self.virtualKeyboard.move(keyboard_x, keyboard_y)
            self.virtualKeyboard.show()

    def loadGames(self):
        games = []
        xdg_config_home = os.getenv("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
        xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
        config_path = os.path.join(xdg_config_home, "PortProton.conf")

        def read_file_content(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception as e:
                print(f"Ошибка чтения файла {file_path}: {e}")
                return None

        portproton_location = None
        if os.path.exists(config_path):
            portproton_location = read_file_content(config_path)
            if portproton_location:
                print(f"Current PortProton location from config: {portproton_location}")
        else:
            fallback_dir = os.path.join(os.path.expanduser("~"), ".var", "app", "ru.linux_gaming.PortProton")
            if os.path.isdir(fallback_dir):
                portproton_location = fallback_dir
                print(f"Using fallback PortProton location from data directory: {portproton_location}")

        if not portproton_location:
            print(f"Не найден конфигурационный файл {config_path} и директория PortProton не существует.")
            return games

        desktop_files = []
        with os.scandir(portproton_location) as it:
            for entry in it:
                if entry.is_file() and entry.name.endswith(".desktop"):
                    desktop_files.append(entry.path)

        def process_file(file_path):
            config = configparser.ConfigParser(interpolation=None)
            try:
                config.read(file_path, encoding="utf-8")
            except Exception as e:
                print(f"Ошибка чтения файла {file_path}: {e}")
                return None

            if "Desktop Entry" not in config:
                return None

            entry = config["Desktop Entry"]
            desktop_name = entry.get("Name", "Unknown Game")
            if desktop_name.lower() == "portproton":
                return None

            exec_line = entry.get("Exec", "")
            steam_details_cache = {}
            steam_info = {}
            game_exe = ""
            if exec_line:
                try:
                    parts = shlex.split(exec_line)
                    game_exe = os.path.expanduser(parts[3] if len(parts) >= 4 else exec_line)
                except Exception as e:
                    print(f"Ошибка обработки Exec строки в {file_path}: {e}")
                    game_exe = os.path.expanduser(exec_line)
                steam_info = get_steam_game_info(desktop_name, exec_line, self.requests_session, steam_details_cache)
                if steam_info is None:
                    return None

            custom_cover = ""
            custom_name = None
            custom_desc = None
            if game_exe:
                exe_name = os.path.splitext(os.path.basename(game_exe))[0]
                custom_folder = os.path.join(xdg_data_home, "PortProtonQT", "custom_data", exe_name)
                os.makedirs(custom_folder, exist_ok=True)
                try:
                    custom_files = set(os.listdir(custom_folder))
                except Exception as e:
                    print(f"Ошибка доступа к папке {custom_folder}: {e}")
                    custom_files = set()

                for ext in [".jpg", ".png", ".jpeg", ".bmp"]:
                    candidate = "cover" + ext
                    candidate_path = os.path.join(custom_folder, candidate)
                    if candidate in custom_files and os.path.exists(candidate_path):
                        custom_cover = candidate_path
                        break

                name_file = os.path.join(custom_folder, "name.txt")
                desc_file = os.path.join(custom_folder, "desc.txt")
                if "name.txt" in custom_files:
                    custom_name = read_file_content(name_file)
                if "desc.txt" in custom_files:
                    custom_desc = read_file_content(desc_file)

            if steam_info.get("appid"):
                name = desktop_name
                desc = steam_info.get("description", "")
                cover = steam_info.get("cover", "")
                appid = steam_info.get("appid", "")
            else:
                name = desktop_name
                desc = entry.get("Comment", "")
                cover = entry.get("Icon", "")
                appid = ""

            if custom_name:
                name = custom_name
            if custom_desc:
                desc = custom_desc
            if custom_cover:
                cover = custom_cover

            return (name, desc, cover, appid, exec_line)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(process_file, desktop_files))

        for res in results:
            if res is not None:
                games.append(res)
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
        searchEdit.setStyleSheet(self.theme.SEARCH_EDIT_STYLE)
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
        title.setStyleSheet(self.theme.INSTALLED_TAB_TITLE_STYLE)
        layout.addWidget(title)

        addGameButton = QtWidgets.QPushButton("Добавить игру")
        addGameButton.setStyleSheet(self.theme.ADD_GAME_BUTTON_STYLE)
        addGameButton.clicked.connect(self.openAddGameDialog)
        layout.addWidget(addGameButton, alignment=QtCore.Qt.AlignLeft)

        searchWidget, self.searchEdit = self.createSearchWidget()
        self.searchEdit.textChanged.connect(self.filterGames)
        layout.addWidget(searchWidget)

        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet(self.theme.SCROLL_AREA_STYLE)
        listWidget = QtWidgets.QWidget()
        listWidget.setStyleSheet(self.theme.LIST_WIDGET_STYLE)
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
            card = GameCard(name, desc, cover, appid, exec_line, self.openGameDetailPage, theme=self.theme)
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
        title.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        layout.addWidget(title)
        content = QtWidgets.QLabel("Здесь можно настроить автоматическую установку игр...")
        content.setStyleSheet(self.theme.CONTENT_STYLE)
        layout.addWidget(content)
        layout.addStretch(1)
        self.stackedWidget.addWidget(widget)

    def createEmulatorsTab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QtWidgets.QLabel("Эмуляторы")
        title.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        layout.addWidget(title)
        content = QtWidgets.QLabel("Список доступных эмуляторов и их настройка...")
        content.setStyleSheet(self.theme.CONTENT_STYLE)
        layout.addWidget(content)
        layout.addStretch(1)
        self.stackedWidget.addWidget(widget)

    def createWineTab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QtWidgets.QLabel("Настройки wine")
        title.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        layout.addWidget(title)
        content = QtWidgets.QLabel("Различные параметры и версии wine...")
        content.setStyleSheet(self.theme.CONTENT_STYLE)
        layout.addWidget(content)
        layout.addStretch(1)
        self.stackedWidget.addWidget(widget)

    def createPortProtonTab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QtWidgets.QLabel("Настройки PortProton")
        title.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        layout.addWidget(title)
        content = QtWidgets.QLabel("Основные параметры PortProton...")
        content.setStyleSheet(self.theme.CONTENT_STYLE)
        layout.addWidget(content)
        layout.addStretch(1)
        self.stackedWidget.addWidget(widget)

    def createThemeTab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QtWidgets.QLabel("Управление темами")
        title.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        layout.addWidget(title)

        themesCombo = QtWidgets.QComboBox()
        available_themes = self.theme_manager.get_available_themes()
        if self.current_theme_name in available_themes:
            available_themes.remove(self.current_theme_name)
            available_themes.insert(0, self.current_theme_name)
        themesCombo.addItems(available_themes)
        layout.addWidget(themesCombo)

        applyButton = QtWidgets.QPushButton("Применить тему")
        applyButton.setStyleSheet(self.theme.ADD_GAME_BUTTON_STYLE)
        layout.addWidget(applyButton)

        self.themeStatusLabel = QtWidgets.QLabel("")
        layout.addWidget(self.themeStatusLabel)

        def on_apply():
            selected_theme = themesCombo.currentText()
            if selected_theme:
                theme_module = self.theme_manager.apply_theme(selected_theme)
                if theme_module:
                    self.theme = theme_module
                    self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE)
                    self.themeStatusLabel.setText(f"Тема '{selected_theme}' успешно применена")
                    self.updateUIStyles()
                    self.populateGamesGrid(self.games)
                    save_theme_to_config(selected_theme)
                else:
                    self.themeStatusLabel.setText(f"Ошибка при применении темы '{selected_theme}'")
            else:
                self.themeStatusLabel.setText("Нет доступных тем для применения")
        applyButton.clicked.connect(on_apply)

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
            pixmap = load_pixmap(cover_path, 300, 400)
            pixmap = round_corners(pixmap, 10)
            palette = self.getColorPalette(cover_path, num_colors=5)
            dark_palette = [self.darkenColor(color, factor=200) for color in palette]
            stops = ",\n".join(
                [f"stop:{i/(len(dark_palette)-1):.2f} {dark_palette[i].name()}" for i in range(len(dark_palette))]
            )
            detailPage.setStyleSheet(self.theme.detail_page_style(stops))
        else:
            detailPage.setStyleSheet(self.theme.DETAIL_PAGE_NO_COVER_STYLE)

        mainLayout = QtWidgets.QVBoxLayout(detailPage)
        mainLayout.setContentsMargins(30, 30, 30, 30)
        mainLayout.setSpacing(20)

        backButton = QtWidgets.QPushButton("Назад")
        backButton.setFixedWidth(100)
        backButton.setStyleSheet(self.theme.BACK_BUTTON_STYLE)
        backButton.clicked.connect(lambda: self.goBackDetailPage(detailPage))
        mainLayout.addWidget(backButton, alignment=QtCore.Qt.AlignLeft)

        contentFrame = QtWidgets.QFrame()
        contentFrame.setStyleSheet(self.theme.DETAIL_CONTENT_FRAME_STYLE)
        contentFrameLayout = QtWidgets.QHBoxLayout(contentFrame)
        contentFrameLayout.setContentsMargins(20, 20, 20, 20)
        contentFrameLayout.setSpacing(40)
        mainLayout.addWidget(contentFrame)

        coverFrame = QtWidgets.QFrame()
        coverFrame.setFixedSize(300, 400)
        coverFrame.setStyleSheet(self.theme.COVER_FRAME_STYLE)
        shadow = QtWidgets.QGraphicsDropShadowEffect(coverFrame)
        shadow.setBlurRadius(20)
        shadow.setColor(QtGui.QColor(0, 0, 0, 200))
        shadow.setOffset(0, 0)
        coverFrame.setGraphicsEffect(shadow)
        coverLayout = QtWidgets.QVBoxLayout(coverFrame)
        coverLayout.setContentsMargins(0, 0, 0, 0)
        imageLabel = QtWidgets.QLabel()
        imageLabel.setFixedSize(300, 400)
        pixmap_detail = load_pixmap(cover_path, 300, 400) if cover_path else load_pixmap("", 300, 400)
        pixmap_detail = round_corners(pixmap_detail, 10)
        imageLabel.setPixmap(pixmap_detail)
        coverLayout.addWidget(imageLabel)
        contentFrameLayout.addWidget(coverFrame)
        detailPage._coverPixmap = pixmap_detail

        detailsWidget = QtWidgets.QWidget()
        detailsWidget.setStyleSheet(self.theme.DETAILS_WIDGET_STYLE)
        detailsLayout = QtWidgets.QVBoxLayout(detailsWidget)
        detailsLayout.setContentsMargins(20, 20, 20, 20)
        detailsLayout.setSpacing(15)

        titleLabel = QtWidgets.QLabel(name)
        titleLabel.setStyleSheet(self.theme.DETAIL_PAGE_TITLE_STYLE)
        detailsLayout.addWidget(titleLabel)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet(self.theme.DETAIL_PAGE_LINE_STYLE)
        detailsLayout.addWidget(line)

        descLabel = QtWidgets.QLabel(description)
        descLabel.setWordWrap(True)
        descLabel.setStyleSheet(self.theme.DETAIL_PAGE_DESC_STYLE)
        detailsLayout.addWidget(descLabel)

        if appid:
            appidLabel = QtWidgets.QLabel(f"Steam AppID: {appid}")
            appidLabel.setStyleSheet(self.theme.STEAM_APPID_LABEL_STYLE)
            detailsLayout.addWidget(appidLabel)

        detailsLayout.addStretch(1)
        playButton = QtWidgets.QPushButton("Играть")
        playButton.setFixedSize(120, 40)
        playButton.setStyleSheet(self.theme.PLAY_BUTTON_STYLE)
        playButton.clicked.connect(lambda: self.toggleGame(exec_line, name, playButton))
        detailsLayout.addWidget(playButton, alignment=QtCore.Qt.AlignLeft)
        contentFrameLayout.addWidget(detailsWidget)

        mainLayout.addStretch()

        self.stackedWidget.addWidget(detailPage)
        self.stackedWidget.setCurrentWidget(detailPage)
        self.currentDetailPage = detailPage

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
        if hasattr(self, "currentDetailPage"):
            del self.currentDetailPage

    def is_target_exe_running(self):
        """Проверяет, запущен ли процесс с именем self.target_exe."""
        if not self.target_exe:
            return False
        for proc in psutil.process_iter(attrs=["name"]):
            try:
                if proc.info["name"].lower() == self.target_exe.lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def startTypewriterEffect(self, message, interval=100):
        """Запускает циклический эффект печатания текста в статус-баре."""
        self._typewriter_text = message
        self._typewriter_index = 0
        self._typewriter_timer = QtCore.QTimer(self)
        self._typewriter_timer.timeout.connect(self._updateTypewriterText)
        self._typewriter_timer.start(interval)

    def _updateTypewriterText(self):
        # Если достигли конца строки, сбрасываем индекс, чтобы начать заново
        if self._typewriter_index < len(self._typewriter_text):
            self.statusBar().showMessage(self._typewriter_text[:self._typewriter_index+1])
            self._typewriter_index += 1
        else:
            self._typewriter_index = 0  # сброс и повтор анимации

    def clearGameStatus(self):
        self.statusBar().clearMessage()

    def checkTargetExe(self):
        """Если игра запущена или дочерний процесс завершился, останавливаем анимацию и очищаем статус-бар с задержкой."""
        target_running = self.is_target_exe_running()
        child_running = any(proc.poll() is None for proc in self.game_processes)
        if (not child_running) or target_running:
            # Останавливаем эффект typewriter, если он работает
            if hasattr(self, '_typewriter_timer'):
                self._typewriter_timer.stop()
                self._typewriter_timer.deleteLater()
                del self._typewriter_timer
            # Очищаем статус-бар через задержку
            QtCore.QTimer.singleShot(1500, self.clearGameStatus)
            self.checkProcessTimer.stop()
            self.checkProcessTimer.deleteLater()

    def toggleGame(self, exec_line, game_name, button):
        if self.game_processes:
            # Если игра уже запущена, останавливаем все процессы
            for proc in self.game_processes:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except Exception as e:
                    print("Ошибка при завершении процесса:", e)
            self.game_processes = []

            # Останавливаем typewriter-эффект, если он работает
            if hasattr(self, '_typewriter_timer'):
                self._typewriter_timer.stop()
                self._typewriter_timer.deleteLater()
                del self._typewriter_timer

            self.statusBar().showMessage("Игра остановлена", 2000)
            QtCore.QTimer.singleShot(1500, self.clearGameStatus)
            button.setText("Играть")
            if hasattr(self, 'checkProcessTimer'):
                self.checkProcessTimer.stop()
                self.checkProcessTimer.deleteLater()
            self.target_exe = None
        else:
            try:
                entry_exec_split = shlex.split(exec_line)
                if entry_exec_split[0] == "env":
                    if len(entry_exec_split) < 3:
                        QtWidgets.QMessageBox.warning(self, "Ошибка", "Неверный формат команды (native)")
                        return
                    file_to_check = entry_exec_split[2]
                elif entry_exec_split[0] == "flatpak":
                    if len(entry_exec_split) < 4:
                        QtWidgets.QMessageBox.warning(self, "Ошибка", "Неверный формат команды (flatpak)")
                        return
                    file_to_check = entry_exec_split[3]
                else:
                    file_to_check = entry_exec_split[0]
                if not os.path.exists(file_to_check):
                    QtWidgets.QMessageBox.warning(self, "Ошибка", f"Указанный файл не найден: {file_to_check}")
                    return
                self.target_exe = os.path.basename(file_to_check)
                env_vars = os.environ.copy()
                if entry_exec_split[0] == "env" and len(entry_exec_split) > 1 and 'data/scripts/start.sh' in entry_exec_split[1]:
                    env_vars['START_FROM_STEAM'] = '1'
                elif entry_exec_split[0] == "flatpak":
                    env_vars['START_FROM_STEAM'] = '1'
                process = subprocess.Popen(entry_exec_split, env=env_vars, shell=False)
                self.game_processes.append(process)
                self.startTypewriterEffect(f"Идёт запуск {game_name}")
                self.checkProcessTimer = QtCore.QTimer(self)
                self.checkProcessTimer.timeout.connect(self.checkTargetExe)
                self.checkProcessTimer.start(500)
                button.setText("Остановить")
            except Exception as e:
                print("Ошибка запуска игры:", e)

    def closeEvent(self, event):
        for proc in self.game_processes:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception as e:
                print("Ошибка при завершении процесса:", e)
        event.accept()
