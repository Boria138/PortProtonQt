import concurrent.futures
import os
import shlex
import signal
import subprocess

import portprotonqt.themes.standart.styles as default_styles
import psutil
import requests

from portprotonqt.dialogs import AddGameDialog
from portprotonqt.game_card import GameCard
from portprotonqt.flow_layout import FlowLayout
from portprotonqt.gamepad_support import GamepadSupport
from portprotonqt.image_utils import load_pixmap, round_corners, ImageCarousel
from portprotonqt.steam_api import get_steam_game_info, get_full_steam_game_info, get_steam_installed_games
from portprotonqt.theme_manager import ThemeManager, load_theme_screenshots
from portprotonqt.time_utils import save_last_launch, get_last_launch, parse_playtime_file, format_playtime, get_last_launch_timestamp, format_last_launch
from portprotonqt.config_utils import get_portproton_location, read_theme_from_config, save_theme_to_config, parse_desktop_entry, load_theme_metainfo, read_time_config, read_card_size, save_card_size, read_sort_method, read_display_filter
from portprotonqt.localization import _
from portprotonqt.logger import get_logger

from PySide6 import QtCore, QtGui, QtWidgets
from datetime import datetime

logger = get_logger(__name__)

class MainWindow(QtWidgets.QMainWindow):
    """Main window of PortProtonQT."""

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
        self.card_width = read_card_size()
        self.gamepad_support = GamepadSupport(self)
        self.setWindowTitle("PortProtonQT")
        self.resize(1280, 720)
        self.setMinimumSize(800, 600)

        self.requests_session = requests.Session()
        self.games = self.loadGames()
        self.game_processes = []
        self.target_exe = None
        self.current_running_button = None

        # Статус-бар
        self.setStatusBar(QtWidgets.QStatusBar(self))

        centralWidget = QtWidgets.QWidget()
        self.setCentralWidget(centralWidget)
        mainLayout = QtWidgets.QVBoxLayout(centralWidget)
        mainLayout.setSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        # 1. ШАПКА (HEADER)
        self.header = QtWidgets.QWidget()
        self.header.setFixedHeight(80)
        self.header.setStyleSheet(self.theme.MAIN_WINDOW_HEADER_STYLE)
        headerLayout = QtWidgets.QVBoxLayout(self.header)
        headerLayout.setContentsMargins(0, 0, 0, 0)

        # Текст "PortProton" слева
        self.titleLabel = QtWidgets.QLabel()
        pixmap = self.theme_manager.current_theme_logo
        self.titleLabel.setPixmap(pixmap)
        self.titleLabel.setFixedSize(pixmap.size())
        self.titleLabel.setStyleSheet(self.theme.TITLE_LABEL_STYLE)
        headerLayout.addStretch()
        scaled_pixmap = pixmap.scaled(60, 60, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                      QtCore.Qt.TransformationMode.SmoothTransformation)
        self.titleLabel.setPixmap(scaled_pixmap)
        self.titleLabel.setFixedSize(scaled_pixmap.size())

        # 2. НАВИГАЦИЯ (КНОПКИ ВКЛАДОК)
        self.navWidget = QtWidgets.QWidget()
        self.navWidget.setStyleSheet(self.theme.NAV_WIDGET_STYLE)
        navLayout = QtWidgets.QHBoxLayout(self.navWidget)
        navLayout.setContentsMargins(10, 0, 10, 0)
        navLayout.setSpacing(0)

        navLayout.addWidget(self.titleLabel)

        self.tabButtons = {}
        # Список вкладок
        tabs = [
            _("Library"),              # индекс 0
            _("Auto Install"),         # индекс 1
            _("Emulators"),            # индекс 2
            _("Wine Settings"),        # индекс 3
            _("PortProton Settings"),  # индекс 4
            _("Themes")                # индекс 5
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
        # Обновление логотипа
        pixmap = self.theme_manager.get_theme_logo(self.current_theme_name)
        scaled_pixmap = pixmap.scaled(60, 60, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                      QtCore.Qt.TransformationMode.SmoothTransformation)
        self.titleLabel.setPixmap(scaled_pixmap)
        self.titleLabel.setFixedSize(scaled_pixmap.size())
        self.gamesListWidget.setStyleSheet(self.theme.LIST_WIDGET_STYLE)

        # Принудительное обновление базовых стилей
        self.header.setStyleSheet(self.theme.MAIN_WINDOW_HEADER_STYLE)
        self.titleLabel.setStyleSheet(self.theme.TITLE_LABEL_STYLE)
        self.navWidget.setStyleSheet(self.theme.NAV_WIDGET_STYLE)
        for btn in self.tabButtons.values():
            btn.setStyleSheet(self.theme.NAV_BUTTON_STYLE)
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE)

        # Обновление виджетов на вкладках
        self._updateTabStyles()

        # Перезагрузка карточек
        self.updateGameGrid()

    def _updateTabStyles(self):
        # Вкладка "Библиотека"
        self.addGameButton.setStyleSheet(self.theme.ADD_GAME_BUTTON_STYLE)
        self.searchEdit.setStyleSheet(self.theme.SEARCH_EDIT_STYLE)

        # Вкладка "Темы"
        self.themesCombo.setStyleSheet(self.theme.COMBO_BOX_STYLE)
        self.applyButton.setStyleSheet(self.theme.ADD_GAME_BUTTON_STYLE)

        # Список заголовков, которые нужно обновить
        for title_label in self.findChildren(QtWidgets.QLabel, "tabTitle"):
            title_label.setStyleSheet(self.theme.TAB_TITLE_STYLE)

        # Обновляем контент с objectName="tabContent"
        for content_label in self.findChildren(QtWidgets.QLabel, "tabContent"):
            content_label.setStyleSheet(self.theme.CONTENT_STYLE)

    def loadGames(self):
        portproton_games = self._load_portproton_games()
        steam_games = self._load_steam_games()

        # Объединение и удаление дубликатов
        seen = set()
        games = []
        for game in portproton_games + steam_games:
            name = game[0]
            if name not in seen:
                seen.add(name)
                games.append(game)

        sort_method = read_sort_method()
        if sort_method == "playtime":
            games.sort(key=lambda g: (g[11], g[10]), reverse=True)
        else:
            games.sort(key=lambda g: (g[10], g[11]), reverse=True)

        # Фильтрация по параметру display_filter
        display_filter = read_display_filter()
        if display_filter == "portproton":
            games = [game for game in games if game[11] == "false"]
        elif display_filter == "steam":
            games = [game for game in games if game[11] == "true"]

        return games


    def _load_portproton_games(self):
        # Перенос оригинальной логики загрузки .desktop файлов
        games = []
        portproton_location = get_portproton_location()
        self.portproton_location = portproton_location

        if not portproton_location:
            return games

        desktop_files = [entry.path for entry in os.scandir(portproton_location)
                        if entry.name.endswith(".desktop")]

        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(self._process_desktop_file, desktop_files))

        return [res for res in results if res is not None]

    def _load_steam_games(self):
        steam_games = []
        for name, appid, last_played, playtime_seconds in get_steam_installed_games():
            steam_info = get_full_steam_game_info(appid)
            last_launch = format_last_launch(datetime.fromtimestamp(last_played)) if last_played else _("Never")
            steam_game = "true"

            steam_games.append((
                name,
                steam_info.get('description', ''),
                steam_info.get('cover', ''),
                appid,
                f"steam://rungameid/{appid}",
                steam_info.get('controller_support', ''),
                last_launch,
                format_playtime(playtime_seconds),
                steam_info.get('protondb_tier', ''),
                last_played,
                playtime_seconds,
                steam_game,
            ))
        return steam_games

    def _process_desktop_file(self, file_path):
        """Обрабатывает .desktop файл и возвращает данные игры"""
        entry = parse_desktop_entry(file_path)
        if not entry:
            return None

        desktop_name = entry.get("Name", _("Unknown Game"))
        if desktop_name.lower() == "portproton" or desktop_name.lower() == "readme":
            return None

        exec_line = entry.get("Exec", "")
        steam_info = {}
        game_exe = ""
        exe_name = ""
        playtime_seconds = 0
        formatted_playtime = ""

        # Обработка Exec строки
        if exec_line:
            parts = shlex.split(exec_line)
            game_exe = os.path.expanduser(parts[3] if len(parts) >= 4 else exec_line)

            # Получение Steam-данных
            steam_info = get_steam_game_info(
                desktop_name,
                exec_line,
                self.requests_session
            )

        # Получение пользовательских данных
        xdg_data_home = os.getenv("XDG_DATA_HOME",
            os.path.join(os.path.expanduser("~"), ".local", "share"))

        custom_cover = ""
        custom_name = None
        custom_desc = None

        if game_exe:
            exe_name = os.path.splitext(os.path.basename(game_exe))[0]
            custom_folder = os.path.join(
                xdg_data_home,
                "PortProtonQT",
                "custom_data",
                exe_name
            )
            os.makedirs(custom_folder, exist_ok=True)

            # Чтение пользовательских файлов
            custom_files = set(os.listdir(custom_folder))
            for ext in [".jpg", ".png", ".jpeg", ".bmp"]:
                candidate = f"cover{ext}"
                if candidate in custom_files:
                    custom_cover = os.path.join(custom_folder, candidate)
                    break

            name_file = os.path.join(custom_folder, "name.txt")
            desc_file = os.path.join(custom_folder, "desc.txt")

            if "name.txt" in custom_files:
                with open(name_file, encoding="utf-8") as f:
                    custom_name = f.read().strip()

            if "desc.txt" in custom_files:
                with open(desc_file, encoding="utf-8") as f:
                    custom_desc = f.read().strip()

            # Статистика времени игры
            statistics_file = os.path.join(
                self.portproton_location,
                "data",
                "tmp",
                "statistics"
            )
            playtime_data = parse_playtime_file(statistics_file)
            matching_key = next(
                (key for key in playtime_data
                 if os.path.basename(key).split('.')[0] == exe_name),
                None
            )
            if matching_key:
                playtime_seconds = playtime_data[matching_key]
                formatted_playtime = format_playtime(playtime_seconds)

        # Формирование финальных данных
        steam_game = "false"
        return (
            custom_name or desktop_name,
            custom_desc or steam_info.get("description", ""),
            custom_cover or steam_info.get("cover", "") or entry.get("Icon", ""),
            steam_info.get("appid", ""),
            exec_line,
            steam_info.get("controller_support", ""),
            get_last_launch(exe_name) if exe_name else _("Never"),
            formatted_playtime,
            steam_info.get("protondb_tier", ""),
            get_last_launch_timestamp(exe_name) if exe_name else 0,
            playtime_seconds,
            steam_game
        )

    # ВКЛАДКИ
    def switchTab(self, index):
        """Устанавливает активную вкладку по индексу."""
        for i, btn in self.tabButtons.items():
            btn.setChecked(i == index)
        self.stackedWidget.setCurrentIndex(index)

    def createSearchWidget(self):
        """Создаёт виджет добавить игру + поиск."""
        self.container = QtWidgets.QWidget()
        self.container.setStyleSheet(self.theme.CONTAINER_STYLE)
        layout = QtWidgets.QHBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title = QtWidgets.QLabel(_("Game Library"))
        title.setStyleSheet(self.theme.INSTALLED_TAB_TITLE_STYLE)
        layout.addWidget(title)

        self.addGameButton = QtWidgets.QPushButton(_("Add Game"))
        self.addGameButton.setStyleSheet(self.theme.ADD_GAME_BUTTON_STYLE)
        self.addGameButton.clicked.connect(self.openAddGameDialog)
        layout.addWidget(self.addGameButton, alignment=QtCore.Qt.AlignRight)

        searchEdit = QtWidgets.QLineEdit()
        searchEdit.setPlaceholderText(_("Find Games ..."))
        searchEdit.setClearButtonEnabled(True)
        searchEdit.setStyleSheet(self.theme.SEARCH_EDIT_STYLE)

        layout.addWidget(searchEdit)
        layout.setStretch(1, 1)
        return self.container, searchEdit

    def filterGames(self, text):
        """Фильтрует список игр по подстроке text."""
        text = text.strip().lower()
        if text == "":
            filtered = self.games
        else:
            filtered = [game for game in self.games if text in game[0].lower()]
        self.populateGamesGrid(filtered)

    def createInstalledTab(self):
        """Вкладка 'Game Library'."""
        self.gamesLibraryWidget = QtWidgets.QWidget()
        self.gamesLibraryWidget.setStyleSheet(self.theme.LIBRARY_WIDGET_STYLE)
        layout = QtWidgets.QVBoxLayout(self.gamesLibraryWidget)
        layout.setSpacing(15)

        searchWidget, self.searchEdit = self.createSearchWidget()
        self.searchEdit.textChanged.connect(self.filterGames)
        layout.addWidget(searchWidget)

        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet(self.theme.SCROLL_AREA_STYLE)

        self.gamesListWidget = QtWidgets.QWidget()
        self.gamesListWidget.setStyleSheet(self.theme.LIST_WIDGET_STYLE)
        # Используем FlowLayout вместо QGridLayout:
        self.gamesListLayout = FlowLayout(self.gamesListWidget)
        self.gamesListWidget.setLayout(self.gamesListLayout)

        scrollArea.setWidget(self.gamesListWidget)
        layout.addWidget(scrollArea)

        # Слайдер для изменения размера карточек:
        sliderLayout = QtWidgets.QHBoxLayout()
        sliderLayout.addStretch()  # сдвигаем ползунок вправо
        self.sizeSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.sizeSlider.setMinimum(200)
        self.sizeSlider.setMaximum(300)
        self.sizeSlider.setValue(self.card_width)
        self.sizeSlider.setTickInterval(10)
        self.sizeSlider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.sizeSlider.setFixedWidth(150)
        self.sizeSlider.setToolTip(f"{self.card_width} px")
        self.sizeSlider.setStyleSheet(self.theme.SLIDER_SIZE_STYLE)
        sliderLayout.addWidget(self.sizeSlider)
        layout.addLayout(sliderLayout)

        self.sliderDebounceTimer = QtCore.QTimer(self)
        self.sliderDebounceTimer.setSingleShot(True)
        self.sliderDebounceTimer.setInterval(40)

        def on_slider_value_changed():
            self.setUpdatesEnabled(False)
            self.card_width = self.sizeSlider.value()
            self.sizeSlider.setToolTip(f"{self.card_width} px")
            self.updateGameGrid()  # обновляем карточки
            self.setUpdatesEnabled(True)
        self.sizeSlider.valueChanged.connect(lambda val: self.sliderDebounceTimer.start())
        self.sliderDebounceTimer.timeout.connect(on_slider_value_changed)

        self.stackedWidget.addWidget(self.gamesLibraryWidget)

        # Первичная отрисовка карточек:
        self.updateGameGrid()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sliderDebounceTimer.start()

    def updateGameGrid(self):
        """Перестраивает карточки с учетом FlowLayout."""
        if not self.games:
            return
        self.clearLayout(self.gamesListLayout)
        # Получаем доступную ширину виджета (без внутренних отступов)
        available_width = self.gamesListWidget.width() -40  # можно скорректировать отступы
        spacing = self.gamesListLayout.spacing()
        # Определяем количество карточек, которые должны поместиться (минимальная ширина задаётся слайдером)
        columns = max(1, available_width // (self.card_width + spacing))
        # Пересчитываем оптимальную ширину карточки так, чтобы карточки заполнили всю строку равномерно
        new_card_width = (available_width - (columns - 1) * spacing) // columns

        for game_data in self.games:
            card = GameCard(*game_data,
                            select_callback=self.openGameDetailPage,
                            theme=self.theme,
                            card_width=new_card_width)
            self.gamesListLayout.addWidget(card)
        self.gamesListWidget.updateGeometry()


    def populateGamesGrid(self, games_list, columns=4):
        self.clearLayout(self.gamesListLayout)
        for idx, game_data in enumerate(games_list):
            card = GameCard(*game_data, select_callback=self.openGameDetailPage, theme=self.theme, card_width=self.card_width)
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
        """Открывает диалоговое окно 'Add Game' с текущей темой."""
        dialog = AddGameDialog(self, self.theme)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            name = dialog.nameEdit.text().strip()
            desc = dialog.descEdit.toPlainText().strip()
            cover = dialog.coverEdit.text().strip()
            self.games.append((name, desc, cover, "stub", "stub", "stub", _("Never"), "stub", "stub", "stub", "stub", "stub"))
            self.populateGamesGrid(self.games)

    def createAutoInstallTab(self):
        """Вкладка 'Auto Install'."""
        self.autoInstallWidget = QtWidgets.QWidget()
        self.autoInstallWidget.setStyleSheet(self.theme.AUTOINSTALL_WIDGET_STYLE)
        layout = QtWidgets.QVBoxLayout(self.autoInstallWidget)
        layout.setContentsMargins(20, 20, 20, 20)

        self.autoInstallTitle = QtWidgets.QLabel(_("Auto Install"))
        self.autoInstallTitle.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.autoInstallTitle.setObjectName("tabTitle")
        layout.addWidget(self.autoInstallTitle)

        self.autoInstallContent = QtWidgets.QLabel(_("Here you can configure automatic game installation..."))
        self.autoInstallContent.setStyleSheet(self.theme.CONTENT_STYLE)
        self.autoInstallContent.setObjectName("tabContent")
        layout.addWidget(self.autoInstallContent)
        layout.addStretch(1)

        self.stackedWidget.addWidget(self.autoInstallWidget)

    def createEmulatorsTab(self):
        """Вкладка 'Emulators'."""
        self.emulatorsWidget = QtWidgets.QWidget()
        self.emulatorsWidget.setStyleSheet(self.theme.EMULATORS_WIDGET_STYLE)
        layout = QtWidgets.QVBoxLayout(self.emulatorsWidget)
        layout.setContentsMargins(20, 20, 20, 20)

        self.emulatorsTitle = QtWidgets.QLabel(_("Emulators"))
        self.emulatorsTitle.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.emulatorsTitle.setObjectName("tabTitle")
        layout.addWidget(self.emulatorsTitle)

        self.emulatorsContent = QtWidgets.QLabel(_("List of available emulators and their configuration..."))
        self.emulatorsContent.setStyleSheet(self.theme.CONTENT_STYLE)
        self.emulatorsContent.setObjectName("tabContent")
        layout.addWidget(self.emulatorsContent)
        layout.addStretch(1)

        self.stackedWidget.addWidget(self.emulatorsWidget)

    def createWineTab(self):
        """Вкладка 'Wine Settings'."""
        self.wineWidget = QtWidgets.QWidget()
        self.wineWidget.setStyleSheet(self.theme.WINE_SETTINGS_WIDGET_STYLE)
        layout = QtWidgets.QVBoxLayout(self.wineWidget)
        layout.setContentsMargins(20, 20, 20, 20)

        self.wineTitle = QtWidgets.QLabel(_("Wine Settings"))
        self.wineTitle.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.wineTitle.setObjectName("tabTitle")
        layout.addWidget(self.wineTitle)

        self.wineContent = QtWidgets.QLabel(_("Various Wine parameters and versions..."))
        self.wineContent.setStyleSheet(self.theme.CONTENT_STYLE)
        self.wineContent.setObjectName("tabContent")
        layout.addWidget(self.wineContent)
        layout.addStretch(1)

        self.stackedWidget.addWidget(self.wineWidget)

    def createPortProtonTab(self):
        """Вкладка 'PortProton Settings'."""
        self.portProtonWidget = QtWidgets.QWidget()
        self.portProtonWidget.setStyleSheet(self.theme.PORTPROTON_SETTINGS_WIDGET_STYLE)
        layout = QtWidgets.QVBoxLayout(self.portProtonWidget)
        layout.setContentsMargins(20, 20, 20, 20)

        self.portProtonTitle = QtWidgets.QLabel(_("PortProton Settings"))
        self.portProtonTitle.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.portProtonTitle.setObjectName("tabTitle")
        layout.addWidget(self.portProtonTitle)

        self.portProtonContent = QtWidgets.QLabel(_("Main PortProton parameters..."))
        self.portProtonContent.setStyleSheet(self.theme.CONTENT_STYLE)
        self.portProtonContent.setObjectName("tabContent")
        layout.addWidget(self.portProtonContent)
        layout.addStretch(1)

        self.stackedWidget.addWidget(self.portProtonWidget)

    def createThemeTab(self):
        """Вкладка 'Themes'"""
        self.themeTabWidget = QtWidgets.QWidget()
        self.themeTabWidget.setStyleSheet(self.theme.THEMES_WIDGET_STYLE)
        mainLayout = QtWidgets.QVBoxLayout(self.themeTabWidget)
        mainLayout.setContentsMargins(20, 20, 20, 20)
        mainLayout.setSpacing(10)

        # 1. Верхняя строка: Заголовок и список тем
        self.themeTabHeaderLayout = QtWidgets.QHBoxLayout()

        self.themeTabTitleLabel = QtWidgets.QLabel(_("Select Theme:"))
        self.themeTabTitleLabel.setObjectName("tabTitle")
        self.themeTabTitleLabel.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.themeTabHeaderLayout.addWidget(self.themeTabTitleLabel)

        self.themesCombo = QtWidgets.QComboBox()
        self.themesCombo.setStyleSheet(self.theme.COMBO_BOX_STYLE)
        available_themes = self.theme_manager.get_available_themes()
        if self.current_theme_name in available_themes:
            available_themes.remove(self.current_theme_name)
            available_themes.insert(0, self.current_theme_name)
        self.themesCombo.addItems(available_themes)
        self.themeTabHeaderLayout.addWidget(self.themesCombo)
        self.themeTabHeaderLayout.addStretch(1)

        mainLayout.addLayout(self.themeTabHeaderLayout)

        # 2. Карусель скриншотов
        self.screenshotsCarousel = ImageCarousel([])
        mainLayout.addWidget(self.screenshotsCarousel, stretch=1)

        # 3. Информация о теме
        self.themeInfoLayout = QtWidgets.QVBoxLayout()
        self.themeInfoLayout.setSpacing(10)

        self.themeMetainfoLabel = QtWidgets.QLabel()
        self.themeMetainfoLabel.setWordWrap(True)
        self.themeInfoLayout.addWidget(self.themeMetainfoLabel)

        self.applyButton = QtWidgets.QPushButton(_("Apply Theme"))
        self.applyButton.setStyleSheet(self.theme.ADD_GAME_BUTTON_STYLE)
        self.themeInfoLayout.addWidget(self.applyButton)

        self.themeStatusLabel = QtWidgets.QLabel()
        self.themeInfoLayout.addWidget(self.themeStatusLabel)

        mainLayout.addLayout(self.themeInfoLayout)

        # Функция обновления превью
        def updateThemePreview(theme_name):
            meta = load_theme_metainfo(theme_name)
            link = meta.get("author_link", "")
            link_html = f'<a href="{link}">{link}</a>' if link else _("No link")

            preview_text = (
                f"<b>{_('Name:')}</b> {meta.get('name', theme_name)}<br>"
                f"<b>{_('Description:')}</b> {meta.get('description', '')}<br>"
                f"<b>{_('Author:')}</b> {meta.get('author', _('Unknown'))}<br>"
                f"<b>{_('Link:')}</b> {link_html}"
            )
            self.themeMetainfoLabel.setText(preview_text)
            self.themeMetainfoLabel.setStyleSheet(self.theme.CONTENT_STYLE)  # Обновление стиля

            screenshots = load_theme_screenshots(theme_name)
            if screenshots:
                self.screenshotsCarousel.update_images([
                    (pixmap, os.path.splitext(filename)[0])
                    for pixmap, filename in screenshots
                ])
                self.screenshotsCarousel.show()
            else:
                self.screenshotsCarousel.hide()

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
                    self.themeStatusLabel.setText(_("Theme '{0}' applied successfully").format(selected_theme))
                    self.updateUIStyles()
                    save_theme_to_config(selected_theme)
                    updateThemePreview(selected_theme)
                else:
                    self.themeStatusLabel.setText(_("Error applying theme '{0}'").format(selected_theme))
            else:
                self.themeStatusLabel.setText(_("No available themes to apply"))

        self.applyButton.clicked.connect(on_apply)

        # Добавляем виджет в stackedWidget
        self.stackedWidget.addWidget(self.themeTabWidget)

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
        for _unused, (r_sum, g_sum, b_sum, count) in histogram.items():
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

    def openGameDetailPage(self, name, description, cover_path=None, appid="", exec_line="", controller_support="", last_launch="", formatted_playtime="", protondb_tier="", steam_game=""):
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

        backButton = QtWidgets.QPushButton(_("Back"))
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

        infoLayout = QtWidgets.QHBoxLayout()
        infoLayout.setSpacing(10)

        lastLaunchTitle = QtWidgets.QLabel(_("LAST LAUNCH"))
        lastLaunchTitle.setStyleSheet(self.theme.LAST_LAUNCH_TITLE_STYLE)
        lastLaunchValue = QtWidgets.QLabel(last_launch)
        lastLaunchValue.setStyleSheet(self.theme.LAST_LAUNCH_VALUE_STYLE)

        playTimeTitle = QtWidgets.QLabel(_("PLAY TIME"))
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
            cs = controller_support.lower()
            translated_cs=""
            if cs == "full":
                translated_cs = _("full")
            elif cs == "partial":
                translated_cs = _("partial")
            elif cs == "none":
                translated_cs = _("none")
            gamepadSupportLabel = QtWidgets.QLabel(_("Gamepad Support: {0}").format(translated_cs))
            gamepadSupportLabel.setAlignment(QtCore.Qt.AlignCenter)
            gamepadSupportLabel.setStyleSheet(self.theme.GAMEPAD_SUPPORT_VALUE_STYLE)
            detailsLayout.addWidget(gamepadSupportLabel, alignment=QtCore.Qt.AlignCenter)

        detailsLayout.addStretch(1)

        # Определяем текущий идентификатор игры по exec_line для корректного отображения кнопки
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

        # Если для этой игры уже запущен процесс, выставляем кнопку "✕ Stop"
        if self.target_exe is not None and current_exe == self.target_exe:
            play_text = f"✕ { _('Stop') }"
        else:
            play_text = f"▷ { _('Play') }"

        playButton = QtWidgets.QPushButton(play_text)
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

    def is_target_exe_running(self):
        """Проверяет, запущен ли процесс с именем self.target_exe через psutil."""
        if not self.target_exe:
            return False
        for proc in psutil.process_iter(attrs=["name"]):
            if proc.info["name"].lower() == self.target_exe.lower():
                return True
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
        if exec_line.startswith("steam://"):
            subprocess.Popen(["steam", exec_line],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
            self.statusBar().showMessage(_("Launching via Steam..."), 3000)
            return

        entry_exec_split = shlex.split(exec_line)
        if entry_exec_split[0] == "env":
            if len(entry_exec_split) < 3:
                QtWidgets.QMessageBox.warning(self, _("Error"), _("Invalid command format (native)"))
                return
            file_to_check = entry_exec_split[2]
        elif entry_exec_split[0] == "flatpak":
            if len(entry_exec_split) < 4:
                QtWidgets.QMessageBox.warning(self, _("Error"), _("Invalid command format (flatpak)"))
                return
            file_to_check = entry_exec_split[3]
        else:
            file_to_check = entry_exec_split[0]
        if not os.path.exists(file_to_check):
            QtWidgets.QMessageBox.warning(self, _("Error"), _("File not found: {0}").format(file_to_check))
            return
        current_exe = os.path.basename(file_to_check)

        if self.game_processes and self.target_exe is not None and self.target_exe != current_exe:
            QtWidgets.QMessageBox.warning(self, _("Error"), _("Cannot launch game while another game is running"))
            return

        # Если игра уже запущена для этого exe – останавливаем её
        if self.game_processes and self.target_exe == current_exe:
            for proc in self.game_processes:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            self.game_processes = []
            if hasattr(self, '_typewriter_timer') and self._typewriter_timer is not None:
                self._typewriter_timer.stop()
                self._typewriter_timer.deleteLater()
                self._typewriter_timer = None
            self.statusBar().showMessage(_("Game stopped"), 2000)
            QtCore.QTimer.singleShot(1500, self.clearGameStatus)
            button.setText(f"▷ { _('Play') }")
            if hasattr(self, 'checkProcessTimer') and self.checkProcessTimer is not None:
                self.checkProcessTimer.stop()
                self.checkProcessTimer.deleteLater()
                self.checkProcessTimer = None
            self.target_exe = None
        else:
            self.target_exe = current_exe
            exe_name = os.path.splitext(current_exe)[0]
            env_vars = os.environ.copy()
            if entry_exec_split[0] == "env" and len(entry_exec_split) > 1 and 'data/scripts/start.sh' in entry_exec_split[1]:
                env_vars['START_FROM_STEAM'] = '1'
            elif entry_exec_split[0] == "flatpak":
                env_vars['START_FROM_STEAM'] = '1'
            process = subprocess.Popen(entry_exec_split, env=env_vars, shell=False)
            self.game_processes.append(process)
            save_last_launch(exe_name, datetime.now())
            self.startTypewriterEffect(_("Launching {0}").format(game_name))
            self.checkProcessTimer = QtCore.QTimer(self)
            self.checkProcessTimer.timeout.connect(self.checkTargetExe)
            self.checkProcessTimer.start(500)
            button.setText(f"✕ { _('Stop') }")

    def closeEvent(self, event):
        for proc in self.game_processes:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        save_card_size(self.card_width)
        event.accept()
