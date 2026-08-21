import os
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from portprotonqt.config import load_theme_metainfo, ui_config, window_config
from portprotonqt.custom_widgets import AutoSizeButton, CustomComboBox
from portprotonqt.image_utils import ImageCarousel
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.tabs.theme_store import THEME_STORE_ITEM, ThemeStoreMixin
from portprotonqt.theme_manager import load_theme_screenshots
from portprotonqt.tray_manager import restart_application_process

logger = get_logger(__name__)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow

    _MainWindowTypingBase = QMainWindow
else:
    _MainWindowTypingBase = object


class MainWindowThemeTabMixin(ThemeStoreMixin, _MainWindowTypingBase):
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def createThemeTab(self):
        """Themes tab"""
        self.themeTabWidget = QWidget()
        self.themeTabWidget.setStyleSheet(self.theme.OTHER_PAGES_WIDGET_STYLE + self.theme.THEME_TAB_FOCUS_STYLE)
        self.themeTabWidget.setObjectName("otherPage")
        mainLayout = QVBoxLayout(self.themeTabWidget)
        mainLayout.setContentsMargins(10, 14, 10, 10)
        mainLayout.setSpacing(10)

        # 1. Top line: Title and theme list
        self.themeTabHeaderLayout = QHBoxLayout()

        self.themeTabTitleLabel = QLabel(_("Select Theme:"))
        self.themeTabTitleLabel.setObjectName("tabTitle")
        self.themeTabTitleLabel.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.themeTabTitleLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.themeTabHeaderLayout.addWidget(self.themeTabTitleLabel)

        self.themesCombo = CustomComboBox(theme=self.theme)
        self.themesCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.themesCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.themesCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.themesCombo.setObjectName("themeTabCombo")
        self.themesCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        theme_names = self.theme_manager.get_available_themes()
        available_themes = ui_config.get_theme_bases(theme_names)
        current_theme_base = ui_config.get_theme_base()
        if current_theme_base in available_themes:
            available_themes.remove(current_theme_base)
            available_themes.insert(0, current_theme_base)
        self.themesCombo.addItems(available_themes)
        if ui_config.get_enable_theme_store():
            self.themesCombo.addItem(_(THEME_STORE_ITEM), THEME_STORE_ITEM)
        self.themeTabHeaderLayout.addWidget(self.themesCombo)

        self.themeVariantCombo = CustomComboBox(theme=self.theme)
        self.themeVariantCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.themeVariantCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.themeVariantCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.themeVariantCombo.setObjectName("themeVariantCombo")
        self.themeVariantCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.themeVariantCombo.addItem(_("Dark"), "dark")
        self.themeVariantCombo.addItem(_("Light"), "light")
        self.themeVariantCombo.addItem(_("Auto"), "auto")
        current_variant = ui_config.get_theme_variant()
        variant_index = self.themeVariantCombo.findData(current_variant)
        if variant_index >= 0:
            self.themeVariantCombo.setCurrentIndex(variant_index)
        self.themeTabHeaderLayout.addWidget(self.themeVariantCombo)
        self.themeTabHeaderLayout.addStretch(1)

        mainLayout.addLayout(self.themeTabHeaderLayout)

        self.themeContentStack = QStackedWidget()
        self.themeInstalledPage = QWidget()
        installedLayout = QVBoxLayout(self.themeInstalledPage)
        installedLayout.setContentsMargins(0, 0, 0, 0)
        installedLayout.setSpacing(10)

        def hasThemeVariants(theme_name: str) -> bool:
            if theme_name == _(THEME_STORE_ITEM):
                return False
            return ui_config.resolve_theme(theme_name, "dark") != ui_config.resolve_theme(theme_name, "light")

        def updateThemeVariantVisibility(*_args: object) -> None:
            self.themeVariantCombo.setVisible(hasThemeVariants(self.themesCombo.currentText()))

        # 2. Screenshots carousel
        self.screenshotsCarousel = ImageCarousel([])
        self.screenshotsCarousel.setStyleSheet(self.theme.CAROUSEL_WIDGET_STYLE)
        self.screenshotsCarousel.setObjectName("themeScreenshotsCarousel")
        self.screenshotsCarousel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.screenshotsCarousel.prevArrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.screenshotsCarousel.nextArrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        installedLayout.addWidget(self.screenshotsCarousel, stretch=1)

        # 3. Theme info
        self.themeInfoLayout = QVBoxLayout()
        self.themeInfoLayout.setSpacing(10)

        self.themeMetainfoLabel = QLabel()
        self.themeMetainfoLabel.setWordWrap(True)
        self.themeMetainfoLabel.setOpenExternalLinks(True)
        self.themeMetainfoLabel.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.themeMetainfoLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.themeInfoLayout.addWidget(self.themeMetainfoLabel)

        self.applyButton = AutoSizeButton(_("Apply Theme"), icon=self.theme_manager.get_icon("apply", as_path=True))
        self.applyButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.applyButton.setObjectName("themeApplyButton")
        self.applyButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.themeInfoLayout.addWidget(self.applyButton)

        self.deleteThemeButton = AutoSizeButton(
            _("Delete Theme"),
            icon=self.theme_manager.get_icon("delete", as_path=True),
        )
        self.deleteThemeButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.deleteThemeButton.setObjectName("themeDeleteButton")
        self.deleteThemeButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.themeInfoLayout.addWidget(self.deleteThemeButton)

        installedLayout.addLayout(self.themeInfoLayout)
        self.themeContentStack.addWidget(self.themeInstalledPage)
        self.themeStorePage = self._create_theme_store_page()
        self.themeContentStack.addWidget(self.themeStorePage)
        mainLayout.addWidget(self.themeContentStack, stretch=1)

        # Preview update function
        def updateThemePreview(*_args: object) -> None:
            if self.themesCombo.currentData() == THEME_STORE_ITEM:
                self._show_theme_store()
                return
            self.themeContentStack.setCurrentWidget(self.themeInstalledPage)
            updateThemeVariantVisibility()
            base_theme = self.themesCombo.currentText()
            variant = self.themeVariantCombo.currentData() or "light"
            theme_name = ui_config.resolve_theme(base_theme, variant)
            custom_themes = self._get_selected_custom_themes()
            self.deleteThemeButton.setVisible(bool(custom_themes))
            meta = load_theme_metainfo(theme_name)
            link = meta.get("author_link", "")
            link_html = f'<a href="{link}">{link}</a>' if link else _("No link")
            unknown_author = _("Unknown")

            preview_text = (
                "<b>" + _("Name:") + "</b> " + meta.get('name', theme_name) + "<br>" +
                "<b>" + _("Description:") + "</b> " + meta.get('description', '') + "<br>" +
                "<b>" + _("Author:") + "</b> " + meta.get('author', unknown_author) + "<br>" +
                "<b>" + _("Link:") + "</b> " + link_html
            )
            self.themeMetainfoLabel.setText(preview_text)
            self.themeMetainfoLabel.setStyleSheet(self.theme.CONTENT_STYLE)

            screenshots = load_theme_screenshots(theme_name)
            if screenshots:
                self.screenshotsCarousel.update_images([
                    (pixmap, caption)
                    for pixmap, caption in screenshots
                ])
                self.screenshotsCarousel.show()
            else:
                self.screenshotsCarousel.hide()

        updateThemePreview()
        self.themesCombo.currentTextChanged.connect(updateThemePreview)
        self.themeVariantCombo.currentTextChanged.connect(updateThemePreview)

        # Theme apply logic
        def on_apply() -> None:
            selected_theme = ui_config.resolve_theme(
                self.themesCombo.currentText(),
                self.themeVariantCombo.currentData() or "light",
            )
            if selected_theme:
                self._apply_theme_and_restart(
                    selected_theme,
                    self.themeVariantCombo.currentData() or "light",
                )

        self.applyButton.clicked.connect(on_apply)
        self.deleteThemeButton.clicked.connect(self._delete_selected_theme)

        # Add widget to stackedWidget
        self.theme_tab_index = self.stackedWidget.addWidget(self.themeTabWidget)

    def _get_selected_custom_themes(self) -> list[str]:
        base_theme = self.themesCombo.currentText()
        variants = {
            ui_config.resolve_theme(base_theme, "dark"),
            ui_config.resolve_theme(base_theme, "light"),
        }
        return [name for name in variants if self.theme_manager.is_custom_theme(name)]

    def _delete_selected_theme(self) -> None:
        theme_names = self._get_selected_custom_themes()
        if not theme_names:
            return
        message = _("Delete theme '{0}'?").format(self.themesCombo.currentText())
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle(_("Confirm Deletion"))
        message_box.setText(message)
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.No)
        message_box.setButtonText(QMessageBox.StandardButton.Yes, _("Yes"))
        message_box.setButtonText(QMessageBox.StandardButton.No, _("No"))
        if message_box.exec() != QMessageBox.StandardButton.Yes:
            return
        removal_results = [
            self.theme_manager.remove_custom_theme(name) for name in theme_names
        ]
        if not all(removal_results):
            QMessageBox.warning(self, _("Error"), _("Failed to delete theme."))
            return
        active_theme_deleted = ui_config.get_theme_base() == self.themesCombo.currentText()
        self._refresh_theme_combo("standart")
        if active_theme_deleted:
            self._apply_theme_and_restart("standart", self.themeVariantCombo.currentData() or "light")
            return
        self.themesCombo.setCurrentIndex(-1)
        self.themesCombo.setCurrentIndex(0)

    def _refresh_theme_store_visibility(self) -> None:
        store_index = self.themesCombo.findData(THEME_STORE_ITEM)
        if ui_config.get_enable_theme_store():
            if store_index < 0:
                self.themesCombo.addItem(_(THEME_STORE_ITEM), THEME_STORE_ITEM)
            return
        if store_index < 0:
            return
        if self.themesCombo.currentIndex() == store_index:
            self.themesCombo.setCurrentIndex(0)
        self.themesCombo.removeItem(store_index)

    def restart_application(self):
        """Restart application."""
        if not self.isFullScreen():
            window_config.set_geometry(self.width(), self.height())
        restart_application_process()

    def _refresh_theme_combo(self, selected_theme: str) -> None:
        theme_names = self.theme_manager.get_available_themes()
        available_themes = ui_config.get_theme_bases(theme_names)
        selected_base = ui_config.get_theme_bases([selected_theme])[0]
        if selected_base in available_themes:
            available_themes.remove(selected_base)
            available_themes.insert(0, selected_base)
        self.themesCombo.blockSignals(True)
        self.themesCombo.clear()
        self.themesCombo.addItems(available_themes)
        if ui_config.get_enable_theme_store():
            self.themesCombo.addItem(_(THEME_STORE_ITEM), THEME_STORE_ITEM)
        self.themesCombo.blockSignals(False)

    def _apply_theme_and_restart(self, theme_name: str, variant: str) -> None:
        theme_module = self.theme_manager.apply_theme(theme_name)
        if not theme_module:
            return
        ui_config.set_theme(theme_name)
        ui_config.set_theme_variant(variant)
        self._save_theme_tab_state()
        QTimer.singleShot(500, lambda: self.restart_application())

    def _save_theme_tab_state(self) -> None:
        xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
        state_file = os.path.join(xdg_data_home, "PortProtonQt", "state.txt")
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                f.write("theme_tab\n")
            logger.info(f"State saved to {state_file}")
        except OSError as e:
            logger.error(f"Failed to save state to {state_file}: {e}")

    def restore_state(self):
        """Restore application state after restart."""
        xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
        state_file = os.path.join(xdg_data_home, "PortProtonQt", "state.txt")
        logger.info(f"Checking for state file: {state_file}")
        if os.path.exists(state_file):
            try:
                with open(state_file, encoding="utf-8") as f:
                    state = f.read().strip()
                    logger.info(f"State file contents: '{state}'")
                    if state == "theme_tab":
                        logger.info("Restoring to theme tab")
                        theme_index = getattr(self, "theme_tab_index", -1)
                        if theme_index >= 0 and self.stackedWidget.count() > theme_index:
                            self.switchTab(theme_index)
                        else:
                            logger.warning("Theme tab is not available yet")
                    else:
                        logger.warning(f"Unexpected state value: '{state}'")
                os.remove(state_file)
                logger.info(f"State file {state_file} removed")
            except Exception as e:
                logger.error(f"Failed to read or process state file {state_file}: {e}")
        else:
            logger.info(f"State file {state_file} does not exist")
