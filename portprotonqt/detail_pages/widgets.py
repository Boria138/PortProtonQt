"""Detail page widgets for PortProtonQt."""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QWidget,
    QScrollArea,
    QBoxLayout,
    QSizePolicy,
    QScroller,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices

from portprotonqt.custom_widgets import ClickableLabel, AutoSizeButton
from portprotonqt.game_card import GameCard
from portprotonqt.localization import _


COVER_WIDTH = 300
COVER_HEIGHT = 450
BADGE_WIDTH = int(COVER_WIDTH * 2 / 3)
BADGE_RIGHT_MARGIN = 8
BADGE_SPACING = 5
BADGE_TOP_Y = 10


def create_scroll_area(parent: QWidget, theme) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    """Create scroll area with content widget and main layout."""
    page_layout = QVBoxLayout(parent)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.setSpacing(0)

    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    scroll_area.setStyleSheet(theme.SCROLL_AREA_STYLE)
    QScroller.grabGesture(scroll_area.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)

    scroll_content = QWidget()
    scroll_area.setWidget(scroll_content)
    page_layout.addWidget(scroll_area)

    main_layout = QVBoxLayout(scroll_content)
    main_layout.setContentsMargins(30, 30, 30, 30)
    main_layout.setSpacing(20)

    return scroll_area, scroll_content, main_layout


def create_back_button(
    parent_layout: QVBoxLayout,
    theme,
    theme_manager,
    on_click: Callable[..., None],
) -> AutoSizeButton:
    """Create back button with standard styling."""
    back_button = AutoSizeButton(_("Back"), icon=theme_manager.get_icon("back"))
    back_button.setFixedWidth(100)
    back_button.setStyleSheet(theme.ADDGAME_BACK_BUTTON_STYLE)
    back_button.clicked.connect(on_click)
    parent_layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignLeft)
    return back_button


def create_content_frame(
    parent_layout: QVBoxLayout,
    theme,
) -> tuple[QFrame, QBoxLayout]:
    """Create content frame with adaptive layout."""
    content_frame = QFrame()
    content_frame.setStyleSheet(theme.DETAIL_CONTENT_FRAME_STYLE)
    content_frame_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, content_frame)
    content_frame_layout.setContentsMargins(20, 20, 20, 20)
    content_frame_layout.setSpacing(40)
    parent_layout.addWidget(content_frame)
    return content_frame, content_frame_layout


def setup_adaptive_layout(
    detail_page: QWidget,
    content_frame_layout: QBoxLayout,
) -> None:
    """Setup adaptive layout switching on resize."""

    def on_detail_page_resize(event) -> None:
        if detail_page.width() < 900:
            if content_frame_layout.direction() != QBoxLayout.Direction.TopToBottom:
                content_frame_layout.setDirection(QBoxLayout.Direction.TopToBottom)
                content_frame_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            if content_frame_layout.direction() != QBoxLayout.Direction.LeftToRight:
                content_frame_layout.setDirection(QBoxLayout.Direction.LeftToRight)
                content_frame_layout.setAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                )
        QWidget.resizeEvent(detail_page, event)

    detail_page.resizeEvent = on_detail_page_resize


def create_cover_frame(
    parent: QWidget,
    theme,
    image_label: QLabel,
    favorite_label_text: str | None = None,
    on_favorite_click: Callable[..., None] | None = None,
    badges: list | None = None,
) -> QFrame:
    """Create cover frame with image, favorite icon, and badges."""
    cover_frame = QFrame()
    cover_frame.setFixedSize(COVER_WIDTH, COVER_HEIGHT)
    cover_frame.setStyleSheet(theme.COVER_FRAME_STYLE)

    _setup_cover_shadow(cover_frame)

    cover_layout = QVBoxLayout(cover_frame)
    cover_layout.setContentsMargins(0, 0, 0, 0)
    cover_layout.addWidget(image_label)

    if favorite_label_text and on_favorite_click:
        _add_favorite_label(cover_frame, favorite_label_text, theme, on_favorite_click)

    if badges:
        _position_badges(cover_frame, badges)

    return cover_frame


def _setup_cover_shadow(cover_frame: QFrame) -> None:
    """Add shadow effect to cover frame."""
    shadow = QGraphicsDropShadowEffect(cover_frame)
    shadow.setBlurRadius(20)
    shadow.setColor(QColor(0, 0, 0, 200))
    shadow.setOffset(0, 0)
    cover_frame.setGraphicsEffect(shadow)


def _add_favorite_label(
    cover_frame: QFrame, favorite_label_text: str, theme, on_favorite_click: Callable[[], None] | None = None
) -> None:
    """Add favorite label to cover frame."""
    favorite_label = ClickableLabel(cover_frame)
    favorite_label.setFixedSize(*theme.favoriteLabelSize)
    favorite_label.setStyleSheet(theme.FAVORITE_LABEL_STYLE)
    favorite_label.setText(favorite_label_text)
    if on_favorite_click:
        favorite_label.clicked.connect(on_favorite_click)
    favorite_label.move(8, 8)
    favorite_label.raise_()


def _position_badges(cover_frame: QFrame, badges: list) -> None:
    """Position badges on cover frame."""
    badge_y_positions = []

    for badge_data in badges:
        badge = badge_data["label"]
        # Reparent badge to cover_frame
        badge.setParent(cover_frame)
        badge_x = COVER_WIDTH - BADGE_WIDTH - BADGE_RIGHT_MARGIN

        if badge_y_positions:
            badge_y = badge_y_positions[-1] + BADGE_SPACING
        else:
            badge_y = BADGE_TOP_Y

        badge.move(badge_x, badge_y)
        badge_y_positions.append(badge_y + badge.height())
        badge.raise_()


def create_protondb_badge(
    parent: QWidget,
    protondb_tier: str,
    appid: str,
    main_window,
) -> tuple[ClickableLabel | None, bool]:
    """Create ProtonDB badge."""
    protondb_text = GameCard.getProtonDBText(protondb_tier)
    if not protondb_text:
        return None, False

    icon_filename = GameCard.getProtonDBIconFilename(protondb_tier)
    icon = main_window.theme_manager.get_icon(icon_filename, main_window.current_theme_name)

    badge = ClickableLabel(
        protondb_text,
        icon=icon,
        parent=parent,
        icon_size=16,
        icon_space=3,
    )
    badge.setStyleSheet(main_window.theme.get_protondb_badge_style(protondb_tier))
    badge.setFixedWidth(BADGE_WIDTH)
    badge.clicked.connect(
        lambda: QDesktopServices.openUrl(QUrl(f"https://www.protondb.com/app/{appid}"))
    )
    return badge, True


def create_steam_badge(
    parent: QWidget,
    appid: str,
    main_window,
) -> ClickableLabel:
    """Create Steam badge."""
    steam_icon = main_window.theme_manager.get_icon("steam")
    badge = ClickableLabel(
        "Steam",
        icon=steam_icon,
        parent=parent,
        icon_size=16,
        icon_space=5,
    )
    badge.setStyleSheet(main_window.theme.STEAM_BADGE_STYLE)
    badge.setFixedWidth(BADGE_WIDTH)
    badge.clicked.connect(
        lambda: QDesktopServices.openUrl(QUrl(f"https://steamcommunity.com/app/{appid}"))
    )
    return badge


def create_egs_badge(
    parent: QWidget,
    main_window,
) -> ClickableLabel:
    """Create Epic Games Store badge."""
    egs_icon = main_window.theme_manager.get_icon("epic_games")
    badge = ClickableLabel(
        "Epic Games",
        icon=egs_icon,
        parent=parent,
        icon_size=16,
        icon_space=5,
        change_cursor=False,
    )
    badge.setStyleSheet(main_window.theme.STEAM_BADGE_STYLE)
    badge.setFixedWidth(BADGE_WIDTH)
    return badge


def create_portproton_badge(
    parent: QWidget,
    on_click: Callable[..., None],
    main_window,
) -> ClickableLabel:
    """Create PortProton badge."""
    portproton_icon = main_window.theme_manager.get_icon("portproton")
    badge = ClickableLabel(
        "PortProton",
        icon=portproton_icon,
        parent=parent,
        icon_size=16,
        icon_space=5,
    )
    badge.setStyleSheet(main_window.theme.STEAM_BADGE_STYLE)
    badge.setFixedWidth(BADGE_WIDTH)
    badge.clicked.connect(on_click)
    return badge


def create_anticheat_badge(
    parent: QWidget,
    anticheat_status: str,
    game_name: str,
    main_window,
) -> tuple[ClickableLabel | None, bool]:
    """Create WeAntiCheatYet badge."""
    anticheat_text = GameCard.getAntiCheatText(anticheat_status)
    if not anticheat_text:
        return None, False

    icon_filename = GameCard.getAntiCheatIconFilename(anticheat_status)
    icon = main_window.theme_manager.get_icon(icon_filename, main_window.current_theme_name)

    badge = ClickableLabel(
        anticheat_text,
        icon=icon,
        parent=parent,
        icon_size=16,
        icon_space=3,
    )
    badge.setStyleSheet(main_window.theme.get_anticheat_badge_style(anticheat_status))
    badge.setFixedWidth(BADGE_WIDTH)
    badge.clicked.connect(
        lambda: QDesktopServices.openUrl(
            QUrl(f"https://areweanticheatyet.com/game/{game_name.lower().replace(' ', '-')}")
        )
    )
    return badge, True


def create_details_widget(
    parent: QWidget,
    main_window,
    title: str,
    description: str,
    game_info_layout: QVBoxLayout | None = None,
    controller_support: str | None = None,
    buttons_layout: QHBoxLayout | None = None,
) -> QWidget:
    """Create details widget with title, description, and optional content."""
    details_widget = QWidget()
    details_widget.setStyleSheet(main_window.theme.DETAILS_WIDGET_STYLE)
    details_widget.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
    )

    details_layout = QVBoxLayout(details_widget)
    details_layout.setContentsMargins(20, 20, 20, 20)
    details_layout.setSpacing(15)

    _add_details_header(details_layout, main_window.theme, title)
    _add_details_description(details_layout, main_window.theme, description)

    if game_info_layout:
        details_layout.addLayout(game_info_layout)

    if controller_support:
        _add_controller_support(details_layout, main_window.theme, controller_support)

    details_layout.addStretch(1)

    if buttons_layout:
        details_layout.addLayout(buttons_layout)

    return details_widget


def _add_details_header(layout: QVBoxLayout, theme, title: str) -> None:
    """Add title and divider line to details layout."""
    title_label = QLabel(title)
    title_label.setStyleSheet(theme.DETAIL_PAGE_TITLE_STYLE)
    layout.addWidget(title_label)

    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(theme.DETAIL_PAGE_LINE_STYLE)
    layout.addWidget(line)


def _add_details_description(layout: QVBoxLayout, theme, description: str) -> None:
    """Add description label to details layout."""
    desc_label = QLabel(description)
    desc_label.setWordWrap(True)
    desc_label.setStyleSheet(theme.DETAIL_PAGE_DESC_STYLE)
    layout.addWidget(desc_label)


def _add_controller_support(layout: QVBoxLayout, theme, controller_support: str) -> None:
    """Add controller support label to details layout."""
    cs = controller_support.lower()
    translated_cs = _get_controller_support_text(cs)
    gamepad_label = QLabel(_("Gamepad Support: {0}").format(translated_cs))
    gamepad_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    gamepad_label.setStyleSheet(theme.GAMEPAD_SUPPORT_VALUE_STYLE)
    layout.addWidget(gamepad_label, alignment=Qt.AlignmentFlag.AlignCenter)


def _get_controller_support_text(cs: str) -> str:
    """Get translated controller support text."""
    if cs == "full":
        return _("full")
    elif cs == "partial":
        return _("partial")
    elif cs == "none":
        return _("none")
    return ""
