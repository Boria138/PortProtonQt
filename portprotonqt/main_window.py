import concurrent.futures
import os
import shlex
import signal
import subprocess

import portprotonqt.themes.standart_lite.styles as default_styles
import psutil
import requests
from portprotonqt.dialogs import AddGameDialog
from portprotonqt.game_card import GameCard
from portprotonqt.gamepad_support import GamepadSupport
from portprotonqt.image_utils import load_pixmap, round_corners, ImageCarousel
from portprotonqt.steam_api import get_steam_game_info
from portprotonqt.theme_manager import ThemeManager, load_theme_screenshots
from portprotonqt.time_utils import save_last_launch, get_last_launch, parse_playtime_file, format_playtime
from portprotonqt.config_utils import get_portproton_location, read_theme_from_config, save_theme_to_config, parse_desktop_entry, load_theme_metainfo, read_time_config, read_file_content
from PySide6 import QtCore, QtGui, QtWidgets
from datetime import datetime

class MainWindow(QtWidgets.QMainWindow):
    """Основное окно PortProtonQT."""

    def __init__(self):
        super().__init__()

        read_time_config()

        # Создаём менеджер тем и читаем, какая тема выбрана
        self.theme_manager = ThemeManager()
        selected_theme = read_theme_from_config()
        self.current_theme_name = selected_theme
        self.theme = self.theme_manager.apply_theme(selected_theme)
        if not self.theme:
            # Если тема не загрузилась, fallback на стандартный стиль
            self.theme = default_styles

        self.gamepad_support = GamepadSupport(self)
        self.setWindowTitle("PortProtonQT")
        self.resize(1280, 720)
        self.setMinimumSize(800, 600)

        self.requests_session = requests.Session()
        self.games = self.loadGames()
        self.game_processes = []
        self.target_exe = None  # Для отслеживания конкретного exe

        # Статус-бар
        self.setStatusBar(QtWidgets.QStatusBar(self))

        centralWidget = QtWidgets.QWidget()
        self.setCentralWidget(centralWidget)
        mainLayout = QtWidgets.QVBoxLayout(centralWidget)
        mainLayout.setSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        # 1. ШАПКА (HEADER)
        self.header = QtWidgets.QFrame()
        self.header.setFixedHeight(80)
        self.header.setStyleSheet(self.theme.MAIN_WINDOW_HEADER_STYLE)
        headerLayout = QtWidgets.QHBoxLayout(self.header)
        headerLayout.setContentsMargins(20, 0, 20, 0)

        # Текст "PortProton" слева
        self.titleLabel = QtWidgets.QLabel("PortProton")
        self.titleLabel = QtWidgets.QLabel()
        pixmap = self.theme_manager.current_theme_logo
        self.titleLabel.setPixmap(pixmap)
        self.titleLabel.setFixedSize(pixmap.size())  # Фиксируем размер под изображение
        self.titleLabel.setStyleSheet(self.theme.TITLE_LABEL_STYLE)  # Оставляем стиль (если нужно)
        headerLayout.addWidget(self.titleLabel)
        headerLayout.addStretch()
        mainLayout.addWidget(self.header)
        scaled_pixmap = pixmap.scaled(80, 80, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.titleLabel.setPixmap(scaled_pixmap)
        self.titleLabel.setFixedSize(scaled_pixmap.size())

        # 2. НАВИГАЦИЯ (КНОПКИ ВКЛАДОК)
        self.navWidget = QtWidgets.QWidget()
        self.navWidget.setStyleSheet(self.theme.NAV_WIDGET_STYLE)
        navLayout = QtWidgets.QHBoxLayout(self.navWidget)
        navLayout.setContentsMargins(10, 0, 10, 0)
        navLayout.setSpacing(5)

        self.tabButtons = {}
        # Список вкладок
        tabs = [
            "Библиотека",         # индекс 0
            "Автоустановка",       # индекс 1
            "Эмуляторы",           # индекс 2
            "Настройки wine",      # индекс 3
            "Настройки PortProton",# индекс 4
            "Темы"                 # индекс 5
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

        # 3. QStackedWidget (ВКЛАДКИ)
        self.stackedWidget = QtWidgets.QStackedWidget()
        mainLayout.addWidget(self.stackedWidget)

        # Создаём все вкладки
        self.createInstalledTab()    # вкладка 0
        self.createAutoInstallTab()  # вкладка 1
        self.createEmulatorsTab()    # вкладка 2
        self.createWineTab()         # вкладка 3
        self.createPortProtonTab()   # вкладка 4
        self.createThemeTab()        # вкладка 5

        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE)

    def updateUIStyles(self):
        """Обновляет все стили после смены темы."""
        self.header.setStyleSheet(self.theme.MAIN_WINDOW_HEADER_STYLE)
        self.titleLabel.setStyleSheet(self.theme.TITLE_LABEL_STYLE)
        self.navWidget.setStyleSheet(self.theme.NAV_WIDGET_STYLE)
        for btn in self.tabButtons.values():
            btn.setStyleSheet(self.theme.NAV_BUTTON_STYLE)
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE)
        self.populateGamesGrid(self.games)

    def loadGames(self):
        games = []
        # Получаем путь к PortProton через модуль конфигов
        portproton_location = get_portproton_location()
        self.portproton_location = portproton_location

        if not portproton_location:
            return games

        # Определяем пути для XDG_DATA_HOME (используется для кастомных данных)
        xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))

        # Получаем список файлов с расширением .desktop в директории portproton_location
        desktop_files = [entry.path for entry in os.scandir(portproton_location)
                        if entry.is_file() and entry.name.endswith(".desktop")]

        def process_file(file_path):
            entry = parse_desktop_entry(file_path)
            if entry is None:
                return None

            desktop_name = entry.get("Name", "Unknown Game")
            if desktop_name.lower() == "portproton":
                return None

            exec_line = entry.get("Exec", "")
            steam_info = {}
            game_exe = ""
            controller_support = ""
            formatted_playtime = ""
            last_launch = "Никогда"

            if exec_line:
                try:
                    parts = shlex.split(exec_line)
                    game_exe = os.path.expanduser(parts[3] if len(parts) >= 4 else exec_line)
                except Exception as e:
                    print(f"Ошибка обработки Exec строки в {file_path}: {e}")
                    game_exe = os.path.expanduser(exec_line)
                steam_info = get_steam_game_info(desktop_name, exec_line, self.requests_session)
                if steam_info is None:
                    return None

            custom_cover = ""
            custom_name = None
            custom_desc = None
            if game_exe:
                exe_name = os.path.splitext(os.path.basename(game_exe))[0]
                custom_folder = os.path.join(xdg_data_home, "PortProtonQT", "custom_data", exe_name)
                os.makedirs(custom_folder, exist_ok=True)
                last_launch = get_last_launch(exe_name) if exe_name else "Никогда"

                playtime_seconds = 0
                statistics_file = os.path.join(self.portproton_location, "data", "tmp", "statistics")
                playtime_data = parse_playtime_file(statistics_file)
                matching_key = next((key for key in playtime_data if os.path.basename(key).split('.')[0] == exe_name), None)
                if matching_key:
                    playtime_seconds = playtime_data[matching_key]
                    formatted_playtime = format_playtime(playtime_seconds)
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
                controller_support = steam_info.get("controller_support", "")
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

            return (name, desc, cover, appid, exec_line, controller_support, last_launch, formatted_playtime)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(process_file, desktop_files))

        for res in results:
            if res is not None:
                games.append(res)
        return games


    # ВКЛАДКИ
    def switchTab(self, index):
        """Устанавливает активную вкладку по индексу."""
        for i, btn in self.tabButtons.items():
            btn.setChecked(i == index)
        self.stackedWidget.setCurrentIndex(index)

    def createSearchWidget(self):
        """Создаёт виджет поиска (иконка + QLineEdit)."""
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
        """Фильтрует список игр по подстроке text."""
        text = text.strip().lower()
        if text == "":
            filtered = self.games
        else:
            filtered = [game for game in self.games if text in game[0].lower()]
        self.populateGamesGrid(filtered)

    def createInstalledTab(self):
        """Вкладка 'Библиотека игр'."""
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateGameGridColumns()

    def updateGameGridColumns(self):
        if not self.games:
            return
        # Получаем ширину виджета
        available_width = self.stackedWidget.width()
        # Учитываем примерную ширину одной карточки + отступы:
        card_width = 300
        spacing = 20  # межкарточный отступ
        columns = max(1, (available_width // (card_width + spacing)))
        self.populateGamesGrid(self.games, columns=columns)

    def populateGamesGrid(self, games_list, columns=4):
        self.clearLayout(self.gamesListLayout)
        for idx, game_data in enumerate(games_list):
            card = GameCard(*game_data, select_callback=self.openGameDetailPage, theme=self.theme)
            row = idx // columns
            col = idx % columns
            self.gamesListLayout.addWidget(card, row, col)

    def clearLayout(self, layout):
        """Удаляет все виджеты из layout."""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def openAddGameDialog(self):
        """Открывает диалоговое окно 'Добавить игру' с текущей темой."""
        dialog = AddGameDialog(self, self.theme)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            name = dialog.nameEdit.text().strip()
            desc = dialog.descEdit.toPlainText().strip()
            cover = dialog.coverEdit.text().strip()
            self.games.append((name, desc, cover, "", "", "", "Никогда",""))
            self.populateGamesGrid(self.games)

    def createAutoInstallTab(self):
        """Вкладка 'Автоустановка'."""
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
        """Вкладка 'Эмуляторы'."""
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
        """Вкладка 'Настройки wine'."""
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
        """Вкладка 'Настройки PortProton'."""
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
        """Вкладка 'Темы'"""
        widget = QtWidgets.QWidget()
        mainLayout = QtWidgets.QVBoxLayout(widget)
        mainLayout.setContentsMargins(20, 20, 20, 20)
        mainLayout.setSpacing(10)

        # 1. Верхняя строка: Заголовок и список тем (QComboBox)
        topLayout = QtWidgets.QHBoxLayout()
        titleLabel = QtWidgets.QLabel("Выберите тему:")
        titleLabel.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        topLayout.addWidget(titleLabel)

        self.themesCombo = QtWidgets.QComboBox()
        self.themesCombo.setStyleSheet(self.theme.COMBO_BOX_STYLE)
        available_themes = self.theme_manager.get_available_themes()
        if self.current_theme_name in available_themes:
            available_themes.remove(self.current_theme_name)
            available_themes.insert(0, self.current_theme_name)
        self.themesCombo.addItems(available_themes)
        topLayout.addWidget(self.themesCombo)
        topLayout.addStretch(1)
        mainLayout.addLayout(topLayout)

        # 2. Центральная область: карусель изображений
        self.screenshotsCarousel = ImageCarousel([])  # Изначально пустая карусель
        mainLayout.addWidget(self.screenshotsCarousel, stretch=1)

        # 3. Нижняя часть: информация о теме и кнопка "Применить тему"
        bottomLayout = QtWidgets.QVBoxLayout()
        bottomLayout.setSpacing(10)

        self.themeMetainfoLabel = QtWidgets.QLabel("")
        self.themeMetainfoLabel.setWordWrap(True)
        bottomLayout.addWidget(self.themeMetainfoLabel)

        self.applyButton = QtWidgets.QPushButton("Применить тему")
        self.applyButton.setStyleSheet(self.theme.ADD_GAME_BUTTON_STYLE)
        bottomLayout.addWidget(self.applyButton)

        self.themeStatusLabel = QtWidgets.QLabel("")
        bottomLayout.addWidget(self.themeStatusLabel)
        mainLayout.addLayout(bottomLayout)

        def updateThemePreview(theme_name):
            meta = load_theme_metainfo(theme_name)  # Определена отдельно
            link = meta.get('author_link', '')
            link_html = f'<a href="{link}" target="_blank">{link}</a>' if link else 'Нет ссылки'

            preview_metainfo = (
                f"<b>Название:</b> {meta.get('name', theme_name)}<br>"
                f"<b>Описание:</b> {meta.get('description', '')}<br>"
                f"<b>Автор:</b> {meta.get('author', 'Unknown')}<br>"
                f"<b>Ссылка:</b> {link_html}"
            )
            self.themeMetainfoLabel.setTextFormat(QtCore.Qt.RichText)
            self.themeMetainfoLabel.setOpenExternalLinks(True)
            self.themeMetainfoLabel.setText(preview_metainfo)

            # Загружаем скриншоты для темы, возвращаем список кортежей (pixmap, filename)
            screenshots = load_theme_screenshots(theme_name)
            images = [(pixmap, os.path.splitext(filename)[0]) for pixmap, filename in screenshots] if screenshots else []
            self.screenshotsCarousel.update_images(images)

        updateThemePreview(self.current_theme_name)
        self.themesCombo.currentTextChanged.connect(updateThemePreview)

        # Логика применения темы
        def on_apply():
            selected_theme = self.themesCombo.currentText()
            if selected_theme:
                theme_module = self.theme_manager.apply_theme(selected_theme)
                if theme_module:
                    self.theme = theme_module
                    self.current_theme_name = selected_theme
                    self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE)
                    self.themeStatusLabel.setText(f"Тема '{selected_theme}' успешно применена")
                    self.updateUIStyles()
                    save_theme_to_config(selected_theme)
                    # Повторно обновляем превью, чтобы, если есть стили шрифтов и т.д., всё отобразилось
                    updateThemePreview(selected_theme)
                else:
                    self.themeStatusLabel.setText(f"Ошибка при применении темы '{selected_theme}'")
            else:
                self.themeStatusLabel.setText("Нет доступных тем для применения")

        self.applyButton.clicked.connect(on_apply)

        # Добавляем готовый виджет на вкладку
        self.stackedWidget.addWidget(widget)

    # ЛОГИКА ДЕТАЛЬНОЙ СТРАНИЦЫ ИГРЫ
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
        for _, (r_sum, g_sum, b_sum, count) in histogram.items():
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

    def openGameDetailPage(self, name, description, cover_path=None, appid="", exec_line="", controller_support="", last_launch="", formatted_playtime=""):
        """Переход на страницу с деталями игры."""
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

        # Обложка (слева)
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

        # Детали игры (справа)
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

        # Дополнительная информация (заглушки, как в Steam)
        infoLayout = QtWidgets.QHBoxLayout()
        infoLayout.setSpacing(10)

        lastLaunchTitle = QtWidgets.QLabel("ПОСЛЕДНИЙ ЗАПУСК")
        lastLaunchTitle.setStyleSheet(self.theme.LAST_LAUNCH_TITLE_STYLE)
        lastLaunchValue = QtWidgets.QLabel(last_launch)
        lastLaunchValue.setStyleSheet(self.theme.LAST_LAUNCH_VALUE_STYLE)

        playTimeTitle = QtWidgets.QLabel("ВЫ ИГРАЛИ")
        playTimeTitle.setStyleSheet(self.theme.PLAY_TIME_TITLE_STYLE)
        playTimeValue = QtWidgets.QLabel(formatted_playtime)
        playTimeValue.setStyleSheet(self.theme.PLAY_TIME_VALUE_STYLE)

        infoLayout.addWidget(lastLaunchTitle)
        infoLayout.addWidget(lastLaunchValue)
        infoLayout.addSpacing(30)
        infoLayout.addWidget(playTimeTitle)
        infoLayout.addWidget(playTimeValue)
        detailsLayout.addLayout(infoLayout)

        if controller_support:
            gamepadSupportLabel = QtWidgets.QLabel(f"Поддержка геймпада: {controller_support}")
            gamepadSupportLabel.setAlignment(QtCore.Qt.AlignCenter)
            gamepadSupportLabel.setStyleSheet(self.theme.GAMEPAD_SUPPORT_VALUE_STYLE)
            detailsLayout.addWidget(gamepadSupportLabel, alignment=QtCore.Qt.AlignCenter)

        detailsLayout.addStretch(1)

        playButton = QtWidgets.QPushButton("▷ Играть")
        playButton.setFixedSize(120, 40)
        playButton.setStyleSheet(self.theme.PLAY_BUTTON_STYLE)
        playButton.clicked.connect(lambda: self.toggleGame(exec_line, name, playButton))
        detailsLayout.addWidget(playButton, alignment=QtCore.Qt.AlignLeft)

        contentFrameLayout.addWidget(detailsWidget)
        mainLayout.addStretch()

        self.stackedWidget.addWidget(detailPage)
        self.stackedWidget.setCurrentWidget(detailPage)
        self.currentDetailPage = detailPage

        # Анимация плавного появления
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
        """Возврат из детальной страницы на вкладку 0 (Библиотека)."""
        self.stackedWidget.setCurrentIndex(0)
        self.stackedWidget.removeWidget(page)
        page.deleteLater()
        if hasattr(self, "currentDetailPage"):
            del self.currentDetailPage

    # ------------------------------------------------------------------------
    # ЗАПУСК/ОСТАНОВКА ИГРЫ
    # ------------------------------------------------------------------------
    def is_target_exe_running(self):
        """Проверяет, запущен ли процесс с именем self.target_exe через psutil."""
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
        """Эффект 'печатающегося текста' в статус-баре."""
        self._typewriter_text = message
        self._typewriter_index = 0
        self._typewriter_timer = QtCore.QTimer(self)
        self._typewriter_timer.timeout.connect(self._updateTypewriterText)
        self._typewriter_timer.start(interval)

    def _updateTypewriterText(self):
        if self._typewriter_index < len(self._typewriter_text):
            self.statusBar().showMessage(self._typewriter_text[:self._typewriter_index+1])
            self._typewriter_index += 1
        else:
            self._typewriter_index = 0  # сброс анимации, печатаем снова

    def clearGameStatus(self):
        """Очищает статус-бар."""
        self.statusBar().clearMessage()

    def checkTargetExe(self):
        """
        Если игра запущена (target_exe) или дочерний процесс завершился,
        останавливаем анимацию и очищаем статус-бар.
        """
        target_running = self.is_target_exe_running()
        child_running = any(proc.poll() is None for proc in self.game_processes)
        if (not child_running) or target_running:
            if hasattr(self, '_typewriter_timer'):
                self._typewriter_timer.stop()
                self._typewriter_timer.deleteLater()
                self._typewriter_timer = None
            QtCore.QTimer.singleShot(1500, self.clearGameStatus)
            if self.checkProcessTimer is not None:
                self.checkProcessTimer.stop()
                self.checkProcessTimer.deleteLater()
                self.checkProcessTimer = None


    def toggleGame(self, exec_line, game_name, button):
        """
        Запускает или останавливает игру:
          - Если уже запущена, убиваем процессы
          - Иначе, запускаем subprocess и контролируем статус
        """
        if self.game_processes:
            for proc in self.game_processes:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except Exception as e:
                    print("Ошибка при завершении процесса:", e)
            self.game_processes = []
            if hasattr(self, '_typewriter_timer') and self._typewriter_timer is not None:
                self._typewriter_timer.stop()
                self._typewriter_timer.deleteLater()
                self._typewriter_timer = None
            self.statusBar().showMessage("Игра остановлена", 2000)
            QtCore.QTimer.singleShot(1500, self.clearGameStatus)
            button.setText("▷ Играть")
            if hasattr(self, 'checkProcessTimer') and self.checkProcessTimer is not None:
                try:
                    self.checkProcessTimer.stop()
                    self.checkProcessTimer.deleteLater()
                except Exception as e:
                    print("Ошибка при удалении checkProcessTimer:", e)
                finally:
                    self.checkProcessTimer = None
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
                exe_name = os.path.splitext(os.path.basename(file_to_check))[0]
                env_vars = os.environ.copy()
                if entry_exec_split[0] == "env" and len(entry_exec_split) > 1 and 'data/scripts/start.sh' in entry_exec_split[1]:
                    env_vars['START_FROM_STEAM'] = '1'
                elif entry_exec_split[0] == "flatpak":
                    env_vars['START_FROM_STEAM'] = '1'
                process = subprocess.Popen(entry_exec_split, env=env_vars, shell=False)
                self.game_processes.append(process)
                save_last_launch(exe_name, datetime.now())
                self.startTypewriterEffect(f"Идёт запуск {game_name}")
                self.checkProcessTimer = QtCore.QTimer(self)
                self.checkProcessTimer.timeout.connect(self.checkTargetExe)
                self.checkProcessTimer.start(500)
                button.setText("✕ Остановить")
            except Exception as e:
                print("Ошибка запуска игры:", e)

    def closeEvent(self, event):
        for proc in self.game_processes:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception as e:
                print("Ошибка при завершении процесса:", e)
        event.accept()
