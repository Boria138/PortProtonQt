from typing import Protocol
from portprotonqt.game_card import GameCard
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QSlider, QScroller
from PySide6.QtCore import Qt, QTimer
from portprotonqt.custom_widgets import FlowLayout
from portprotonqt.config_utils import read_favorites, read_sort_method, read_card_size, save_card_size
from portprotonqt.image_utils import load_pixmap_async
from portprotonqt.context_menu_manager import ContextMenuManager, CustomLineEdit

class MainWindowProtocol(Protocol):
    """Protocol defining the interface that MainWindow must implement for GameLibraryManager."""

    def openGameDetailPage(
        self,
        name: str,
        description: str,
        cover_path: str | None = None,
        appid: str = "",
        exec_line: str = "",
        controller_support: str = "",
        last_launch: str = "",
        formatted_playtime: str = "",
        protondb_tier: str = "",
        game_source: str = "",
        anticheat_status: str = "",
    ) -> None: ...

    def createSearchWidget(self) -> tuple[QWidget, CustomLineEdit]: ...

    def on_slider_released(self) -> None: ...

    # Required attributes
    searchEdit: CustomLineEdit
    _last_card_width: int
    current_hovered_card: GameCard | None
    current_focused_card: GameCard | None

class GameLibraryManager:
    def __init__(self, main_window: MainWindowProtocol, theme, context_menu_manager: ContextMenuManager | None):
        self.main_window = main_window
        self.theme = theme
        self.context_menu_manager: ContextMenuManager | None = context_menu_manager
        self.games: list[tuple] = []
        self.filtered_games: list[tuple] = []
        self.game_card_cache = {}
        self.pending_images = {}
        self.card_width = read_card_size()
        self.gamesListWidget: QWidget | None = None
        self.gamesListLayout: FlowLayout | None = None
        self.sizeSlider: QSlider | None = None

    def create_games_library_widget(self):
        """Creates the games library widget with search, grid, and slider."""
        self.gamesLibraryWidget = QWidget()
        self.gamesLibraryWidget.setStyleSheet(self.theme.LIBRARY_WIDGET_STYLE)
        layout = QVBoxLayout(self.gamesLibraryWidget)
        layout.setSpacing(15)

        # Search widget
        searchWidget, self.searchEdit = self.main_window.createSearchWidget()
        layout.addWidget(searchWidget)

        # Scroll area for game grid
        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet(self.theme.SCROLL_AREA_STYLE)
        QScroller.grabGesture(scrollArea.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)

        self.gamesListWidget = QWidget()
        self.gamesListWidget.setStyleSheet(self.theme.LIST_WIDGET_STYLE)
        self.gamesListLayout = FlowLayout(self.gamesListWidget)
        self.gamesListWidget.setLayout(self.gamesListLayout)

        scrollArea.setWidget(self.gamesListWidget)
        layout.addWidget(scrollArea)

        # Slider for card size
        sliderLayout = QHBoxLayout()
        sliderLayout.addStretch()

        self.sizeSlider = QSlider(Qt.Orientation.Horizontal)
        self.sizeSlider.setMinimum(200)
        self.sizeSlider.setMaximum(250)
        self.sizeSlider.setValue(self.card_width)
        self.sizeSlider.setTickInterval(10)
        self.sizeSlider.setFixedWidth(150)
        self.sizeSlider.setToolTip(f"{self.card_width} px")
        self.sizeSlider.setStyleSheet(self.theme.SLIDER_SIZE_STYLE)
        self.sizeSlider.sliderReleased.connect(self.main_window.on_slider_released)
        sliderLayout.addWidget(self.sizeSlider)

        layout.addLayout(sliderLayout)

        # Calculate initial card width
        def calculate_card_width():
            if self.gamesListLayout is None:
                return
            available_width = scrollArea.width() - 20
            spacing = self.gamesListLayout._spacing
            target_cards_per_row = 8
            calculated_width = (available_width - spacing * (target_cards_per_row - 1)) // target_cards_per_row
            calculated_width = max(200, min(calculated_width, 250))

        QTimer.singleShot(0, calculate_card_width)

        # Connect scroll event for lazy loading
        scrollArea.verticalScrollBar().valueChanged.connect(self.load_visible_images)

        return self.gamesLibraryWidget

    def on_slider_released(self):
        """Handles slider release to update card size."""
        if self.sizeSlider is None:
            return
        self.card_width = self.sizeSlider.value()
        self.sizeSlider.setToolTip(f"{self.card_width} px")
        save_card_size(self.card_width)
        for card in self.game_card_cache.values():
            card.update_card_size(self.card_width)
        self.update_game_grid()

    def load_visible_images(self):
        """Loads images for visible game cards."""
        if self.gamesListWidget is None:
            return
        visible_region = self.gamesListWidget.visibleRegion()
        max_concurrent_loads = 5
        loaded_count = 0
        for card_key, card in self.game_card_cache.items():
            if card_key in self.pending_images and visible_region.contains(card.pos()) and loaded_count < max_concurrent_loads:
                cover_path, width, height, callback = self.pending_images.pop(card_key)
                load_pixmap_async(cover_path, width, height, callback)
                loaded_count += 1

    def _on_card_focused(self, game_name: str, is_focused: bool):
        """Handles card focus events."""
        card_key = None
        for key, card in self.game_card_cache.items():
            if card.name == game_name:
                card_key = key
                break

        if not card_key:
            return

        card = self.game_card_cache[card_key]

        if is_focused:
            if self.main_window.current_hovered_card and self.main_window.current_hovered_card != card:
                self.main_window.current_hovered_card._hovered = False
                self.main_window.current_hovered_card.leaveEvent(None)
                self.main_window.current_hovered_card = None
            if self.main_window.current_focused_card and self.main_window.current_focused_card != card:
                self.main_window.current_focused_card._focused = False
                self.main_window.current_focused_card.clearFocus()
            self.main_window.current_focused_card = card
        else:
            if self.main_window.current_focused_card == card:
                self.main_window.current_focused_card = None

    def _on_card_hovered(self, game_name: str, is_hovered: bool):
        """Handles card hover events."""
        card_key = None
        for key, card in self.game_card_cache.items():
            if card.name == game_name:
                card_key = key
                break

        if not card_key:
            return

        card = self.game_card_cache[card_key]

        if is_hovered:
            if self.main_window.current_focused_card and self.main_window.current_focused_card != card:
                self.main_window.current_focused_card._focused = False
                self.main_window.current_focused_card.clearFocus()
            if self.main_window.current_hovered_card and self.main_window.current_hovered_card != card:
                self.main_window.current_hovered_card._hovered = False
                self.main_window.current_hovered_card.leaveEvent(None)
            self.main_window.current_hovered_card = card
        else:
            if self.main_window.current_hovered_card == card:
                self.main_window.current_hovered_card = None

    def update_game_grid(self, games_list: list[tuple] | None = None):
        """Updates the game grid with the provided or current game list."""
        if self.gamesListLayout is None or self.gamesListWidget is None:
            return
        games_list = games_list if games_list is not None else self.games
        search_text = self.main_window.searchEdit.text().strip().lower()
        favorites = read_favorites()
        sort_method = read_sort_method()

        def sort_key(game):
            name = game[0]
            fav_order = 0 if name in favorites else 1
            if sort_method == "playtime":
                return (fav_order, -game[11], -game[10])
            elif sort_method == "alphabetical":
                return (fav_order, name.lower())
            elif sort_method == "favorites":
                return (fav_order,)
            else:
                return (fav_order, -game[10], -game[11])

        sorted_games = sorted(games_list, key=sort_key)
        new_card_order = []

        for game_data in sorted_games:
            game_name = game_data[0]
            exec_line = game_data[4]
            game_key = (game_name, exec_line)
            should_be_visible = not search_text or search_text in game_name.lower()

            if game_key in self.game_card_cache:
                card = self.game_card_cache[game_key]
                card.setVisible(should_be_visible)
                new_card_order.append((game_key, card))
                continue

            if self.context_menu_manager is None:
                continue  # Skip card creation if context_menu_manager is None

            card = GameCard(
                *game_data,
                select_callback=self.main_window.openGameDetailPage,
                theme=self.theme,
                card_width=self.card_width,
                context_menu_manager=self.context_menu_manager
            )

            card.hoverChanged.connect(self._on_card_hovered)
            card.focusChanged.connect(self._on_card_focused)

            card.editShortcutRequested.connect(self.context_menu_manager.edit_game_shortcut)
            card.deleteGameRequested.connect(self.context_menu_manager.delete_game)
            card.addToMenuRequested.connect(self.context_menu_manager.add_to_menu)
            card.removeFromMenuRequested.connect(self.context_menu_manager.remove_from_menu)
            card.addToDesktopRequested.connect(self.context_menu_manager.add_to_desktop)
            card.removeFromDesktopRequested.connect(self.context_menu_manager.remove_from_desktop)
            card.addToSteamRequested.connect(self.context_menu_manager.add_to_steam)
            card.removeFromSteamRequested.connect(self.context_menu_manager.remove_from_steam)
            card.openGameFolderRequested.connect(self.context_menu_manager.open_game_folder)

            self.game_card_cache[game_key] = card
            new_card_order.append((game_key, card))
            card.setVisible(should_be_visible)

        while self.gamesListLayout.count():
            child = self.gamesListLayout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        for _game_key, card in new_card_order:
            self.gamesListLayout.addWidget(card)
            if card.isVisible():
                self.load_visible_images()

        existing_keys = {game_key for game_key, card in new_card_order}
        for card_key in list(self.game_card_cache.keys()):
            if card_key not in existing_keys:
                card = self.game_card_cache.pop(card_key)
                card.deleteLater()
                if card_key in self.pending_images:
                    del self.pending_images[card_key]

        self.gamesListLayout.update()
        self.gamesListWidget.updateGeometry()
        self.gamesListWidget.update()

        self.main_window._last_card_width = self.card_width

    def clear_layout(self, layout):
        """Clears all widgets from the layout."""
        if layout is None:
            return
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                widget = child.widget()
                for key, card in list(self.game_card_cache.items()):
                    if card == widget:
                        del self.game_card_cache[key]
                        if key in self.pending_images:
                            del self.pending_images[key]
                widget.deleteLater()

    def set_games(self, games: list[tuple]):
        """Sets the games list and updates the filtered games."""
        self.games = games
        self.filtered_games = self.games
        self.update_game_grid()

    def filter_games_delayed(self):
        """Filters games based on search text and updates the grid."""
        text = self.main_window.searchEdit.text().strip().lower()
        if text == "":
            self.filtered_games = self.games
        else:
            self.filtered_games = [game for game in self.games if text in game[0].lower()]
        self.update_game_grid(self.filtered_games)
