from typing import Protocol
from portprotonqt.game_card import GameCard
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QSlider, QScroller
from PySide6.QtCore import Qt, QTimer
from portprotonqt.custom_widgets import FlowLayout
from portprotonqt.config_utils import read_favorites, read_sort_method, read_card_size, save_card_size
from portprotonqt.image_utils import load_pixmap_async
from portprotonqt.context_menu_manager import ContextMenuManager, CustomLineEdit
from collections import deque

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
    gamesListWidget: QWidget | None

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
        self._update_timer: QTimer | None = None
        self._pending_update = False
        self.pending_deletions = deque()
        self.is_filtering = False
        self.dirty = False

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

        # Initialize update timer
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(100)  # 100ms debounce
        self._update_timer.timeout.connect(self._perform_update)

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

    def _perform_update(self):
        """Performs the actual grid update."""
        if not self._pending_update:
            return
        self._pending_update = False
        self._update_game_grid_immediate()

    def update_game_grid(self, games_list: list[tuple] | None = None, is_filter: bool = False):
        """Schedules a game grid update with debouncing."""
        if not is_filter:
            if games_list is not None:
                self.filtered_games = games_list
            self.dirty = True  # Full rebuild only for non-filter
        self.is_filtering = is_filter
        self._pending_update = True

        if self._update_timer is not None:
            self._update_timer.start()
        else:
            self._update_game_grid_immediate()

    def _update_game_grid_immediate(self):
        """Updates the game grid with the provided or current game list."""
        if self.gamesListLayout is None or self.gamesListWidget is None:
            return

        search_text = self.main_window.searchEdit.text().strip().lower()

        if self.is_filtering:
            # Filter mode: do not change layout, only hide/show cards
            self._apply_filter_visibility(search_text)
        else:
            # Full update: sorting, removal/addition, reorganization
            games_list = self.filtered_games if self.filtered_games else self.games
            favorites = read_favorites()
            sort_method = read_sort_method()

            # Batch layout updates (extended scope)
            self.gamesListWidget.setUpdatesEnabled(False)
            if self.gamesListLayout is not None:
                self.gamesListLayout.setEnabled(False)  # Disable layout during batch

            try:
                # Optimized sorting: Partition favorites first, then sort subgroups
                def partition_sort_key(game):
                    name = game[0]
                    is_fav = name in favorites
                    fav_order = 0 if is_fav else 1
                    if sort_method == "playtime":
                        return (fav_order, -game[11] if game[11] else 0, -game[10] if game[10] else 0)
                    elif sort_method == "alphabetical":
                        return (fav_order, name.lower())
                    elif sort_method == "favorites":
                        return (fav_order,)
                    else:
                        return (fav_order, -game[10] if game[10] else 0, -game[11] if game[11] else 0)

                # Quick partition: Sort favorites and non-favorites separately, then merge
                fav_games = [g for g in games_list if g[0] in favorites]
                non_fav_games = [g for g in games_list if g[0] not in favorites]
                sorted_fav = sorted(fav_games, key=partition_sort_key)
                sorted_non_fav = sorted(non_fav_games, key=partition_sort_key)
                sorted_games = sorted_fav + sorted_non_fav

                # Build set of current game keys for faster lookup
                current_game_keys = {(game[0], game[4]) for game in sorted_games}

                # Remove cards that no longer exist (batch)
                cards_to_remove = []
                for card_key in list(self.game_card_cache.keys()):
                    if card_key not in current_game_keys:
                        cards_to_remove.append(card_key)

                for card_key in cards_to_remove:
                    card = self.game_card_cache.pop(card_key)
                    if self.gamesListLayout is not None:
                        self.gamesListLayout.removeWidget(card)
                    self.pending_deletions.append(card)  # Defer
                    if card_key in self.pending_images:
                        del self.pending_images[card_key]

                # Track current layout order (only if dirty/full update needed)
                if self.dirty and self.gamesListLayout is not None:
                    current_layout_order = []
                    for i in range(self.gamesListLayout.count()):
                        item = self.gamesListLayout.itemAt(i)
                        if item is not None:
                            widget = item.widget()
                            if widget:
                                for key, card in self.game_card_cache.items():
                                    if card == widget:
                                        current_layout_order.append(key)
                                        break
                else:
                    current_layout_order = None  # Skip reorg if not dirty

                new_card_order = []
                cards_to_add = []

                for game_data in sorted_games:
                    game_name = game_data[0]
                    exec_line = game_data[4]
                    game_key = (game_name, exec_line)
                    should_be_visible = not search_text or search_text in game_name.lower()

                    if game_key in self.game_card_cache:
                        card = self.game_card_cache[game_key]
                        if card.isVisible() != should_be_visible:
                            card.setVisible(should_be_visible)
                        new_card_order.append(game_key)
                    else:
                        if self.context_menu_manager is None:
                            continue

                        card = self._create_game_card(game_data)
                        self.game_card_cache[game_key] = card
                        card.setVisible(should_be_visible)
                        new_card_order.append(game_key)
                        cards_to_add.append((game_key, card))

                # Only reorganize if order changed AND dirty
                if self.dirty and self.gamesListLayout is not None and (current_layout_order is None or new_card_order != current_layout_order):
                    # Remove all widgets from layout (batch)
                    while self.gamesListLayout.count():
                        self.gamesListLayout.takeAt(0)

                    # Add widgets in new order (batch)
                    for game_key in new_card_order:
                        card = self.game_card_cache[game_key]
                        self.gamesListLayout.addWidget(card)

                self.dirty = False  # Reset flag

                # Deferred deletions (run in timer to avoid stack overflow)
                if self.pending_deletions:
                    QTimer.singleShot(0, lambda: self._flush_deletions())

                # Load visible images for new cards only
                if cards_to_add:
                    self.load_visible_images()

            finally:
                if self.gamesListLayout is not None:
                    self.gamesListLayout.setEnabled(True)
                self.gamesListWidget.setUpdatesEnabled(True)
                if self.gamesListLayout is not None:
                    self.gamesListLayout.update()
                self.gamesListWidget.updateGeometry()
                self.main_window._last_card_width = self.card_width

        self.is_filtering = False  # Reset flag in any case

    def _apply_filter_visibility(self, search_text: str):
        """Applies visibility to cards based on search, without changing the layout."""
        visible_count = 0
        for game_key, card in self.game_card_cache.items():
            game_name = card.name  # Assume GameCard has 'name' attribute
            should_be_visible = not search_text or search_text in game_name.lower()
            if card.isVisible() != should_be_visible:
                card.setVisible(should_be_visible)
            if should_be_visible:
                visible_count += 1
                # Load image only for newly visible cards
                if game_key in self.pending_images:
                    cover_path, width, height, callback = self.pending_images.pop(game_key)
                    load_pixmap_async(cover_path, width, height, callback)

        # Force full relayout after visibility changes
        if self.gamesListLayout is not None:
            self.gamesListLayout.invalidate()  # Принудительно инвалидируем для пересчёта
            self.gamesListLayout.update()
        if self.gamesListWidget is not None:
            self.gamesListWidget.updateGeometry()
        self.main_window._last_card_width = self.card_width

        # If search is empty, load images for visible ones
        if not search_text:
            self.load_visible_images()

    def _create_game_card(self, game_data: tuple) -> GameCard:
        """Creates a new game card with all necessary connections."""
        card = GameCard(
            *game_data,
            select_callback=self.main_window.openGameDetailPage,
            theme=self.theme,
            card_width=self.card_width,
            context_menu_manager=self.context_menu_manager
        )

        card.hoverChanged.connect(self._on_card_hovered)
        card.focusChanged.connect(self._on_card_focused)

        if self.context_menu_manager:
            card.editShortcutRequested.connect(self.context_menu_manager.edit_game_shortcut)
            card.deleteGameRequested.connect(self.context_menu_manager.delete_game)
            card.addToMenuRequested.connect(self.context_menu_manager.add_to_menu)
            card.removeFromMenuRequested.connect(self.context_menu_manager.remove_from_menu)
            card.addToDesktopRequested.connect(self.context_menu_manager.add_to_desktop)
            card.removeFromDesktopRequested.connect(self.context_menu_manager.remove_from_desktop)
            card.addToSteamRequested.connect(self.context_menu_manager.add_to_steam)
            card.removeFromSteamRequested.connect(self.context_menu_manager.remove_from_steam)
            card.openGameFolderRequested.connect(self.context_menu_manager.open_game_folder)

        return card

    def _flush_deletions(self):
        """Delete pending widgets off the main update cycle."""
        for card in list(self.pending_deletions):
            card.deleteLater()
            self.pending_deletions.remove(card)

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
        self.dirty = True  # Full resort needed
        self.update_game_grid()

    def add_game_incremental(self, game_data: tuple):
        """Add a single game without full reload."""
        self.games.append(game_data)
        self.filtered_games.append(game_data)  # Assume no filter active; adjust if needed
        self.dirty = True
        self.update_game_grid()

    def remove_game_incremental(self, game_name: str, exec_line: str):
        """Remove a single game without full reload."""
        key = (game_name, exec_line)
        self.games = [g for g in self.games if (g[0], g[4]) != key]
        self.filtered_games = [g for g in self.filtered_games if (g[0], g[4]) != key]
        if key in self.game_card_cache and self.gamesListLayout is not None:
            card = self.game_card_cache.pop(key)
            self.gamesListLayout.removeWidget(card)
            self.pending_deletions.append(card)  # Defer deleteLater
            if key in self.pending_images:
                del self.pending_images[key]
        self.dirty = True
        self.update_game_grid()

    def filter_games_delayed(self):
        """Filters games based on search text and updates the grid."""
        self.update_game_grid(is_filter=True)

    def calculate_columns(self, card_width: int) -> int:
        """Calculate the number of columns based on card width and assumed container width."""
        # Assuming a typical container width; adjust as needed
        available_width = 1200  # Example width, can be dynamic if widget access is added
        spacing = 15  # Assumed spacing between cards
        columns = max(1, (available_width - spacing) // (card_width + spacing))
        return min(columns, 8)  # Cap at reasonable max
