from portprotonqt.theme_manager import ThemeManager
from portprotonqt.config import ui_config

theme_manager = ThemeManager()
current_theme_name = ui_config.get_theme()

# CONSTANTS
favoriteLabelSize = 48, 48
autoSizeButtonPadding = 16
detailCompactCoverFrameSize = 128
detailCompactCoverImageSize = 108
detailCompactContentSpacing = 15
detailCompactHeaderSpacing = 16
detailCompactTitleMargins = (0, 0, 0, 0)
detailCompactDescriptionMargins = (3, 3, 3, 3)
portProtonPageMargins = (15, 15, 15, 15)
portProtonPageHorizontalSpacing = 15
portProtonPageVerticalSpacing = 10
portProtonPageSectionHeaderSpacing = 10
wineSettingsSetSpacing = 10
mangoHudSwitchesColumns = 4
mangoHudSwitchesVerticalSpacing = 10
mangoHudFpsColumns = 4
mangoHudFpsVerticalSpacing = 10
mangoHudPresetsColumns = 2
exeSettingsGroupBoxBlockSpacing = 14
exeSettingsGroupBoxElementVerticalSpacing = 10
exeSettingsGroupBoxElementHorizontalSpacing = 10

# VARS
font_family = "Play"
font_size_a = "16px"
font_size_b = "24px"
border_a = "0px solid"
border_b = "1px solid"
border_c = "2px solid"
border_radius_a = "10px"
border_radius_b = "15px"
color_a = "#70b8ff"
color_b = "#F8F9FC"
color_c = "#F0F2F5"
color_d = "#E9ECEF"
color_e = "#DEE2E6"
color_f = "#ffffff"
color_g = "rgba(0, 0, 0, 0)"
color_h = "transparent"
color_i = "rgba(40, 42, 51, 0.9)"
color_j = "#d2d3db"
color_k = "#9394a5"
color_l = "#212529"

# QColor constants for programmatic use
color_shadow_card = "#00000096"  # rgba(0, 0, 0, 150)
color_shadow_detail = "#000000c8"  # rgba(0, 0, 0, 200)
color_placeholder_bg = "#333333"
color_default_fallback = "#1a1a1a"
color_disabled_bg = "#f0f0f0"
color_disabled_text = "#777a84"
color_text_muted = "#bbbbbb"
color_accent_blue = "#007AFF"
color_gamepad_supported = "#00ff00"
color_white = "#ffffff"
missing_exe_cover_opacity = 0.45

# Shadow constants
shadow_blur_radius = 20
shadow_offset = (0, 0)
settings_tooltip_offset_x = 28
settings_tooltip_offset_y = 4
virtual_keyboard_slide_animation_duration = 160
virtual_keyboard_fade_animation_duration = 140
virtual_keyboard_slide_fade_animation_duration = 180
virtual_keyboard_slide_bounce_animation_duration = 220
virtual_keyboard_animation_type = "slide"

GAME_CARD_ANIMATION = {
    # Animation type for entering/exiting detail page
    # Possible values: "fade", "slide_left", "slide_right", "slide_up", "slide_down", "bounce"
    # Defines how the detail page appears and disappears
    "detail_page_animation_type": "fade",

    # Border width of card in idle state (no hover or focus)
    # Affects border thickness around card when not highlighted
    # Value in pixels
    "default_border_width": 2,

    # Border width on hover
    # Increases border thickness when cursor is over card
    # Value in pixels
    "hover_border_width": 8,

    # Border width on focus (e.g., keyboard selection)
    # Increases border thickness when card is focused
    # Value in pixels
    "focus_border_width": 12,

    # Minimum border width during pulse animation
    # Defines minimum border thickness during pulse (breathing) animation
    # Value in pixels
    "pulse_min_border_width": 8,

    # Maximum border width during pulse animation
    # Defines maximum border thickness during pulse
    # Value in pixels
    "pulse_max_border_width": 10,

    # Duration of border thickness change animation (e.g., on hover or focus)
    # Affects speed of transition between border widths
    # Value in milliseconds
    "thickness_anim_duration": 300,

    # Duration of one pulse animation cycle
    # Defines how fast border "pulses" between min and max values
    # Value in milliseconds
    "pulse_anim_duration": 800,

    # Duration of gradient rotation animation
    # Affects speed of gradient border rotation around card
    # Value in milliseconds
    "gradient_anim_duration": 3000,

    # Starting gradient angle (in degrees)
    # Defines starting point of gradient rotation
    "gradient_start_angle": 360,

    # Ending gradient angle (in degrees)
    # Defines ending point of gradient rotation
    # Value 0 means full 360 degree rotation
    "gradient_end_angle": 0,

    # Animation type for card on hover or focus
    # Possible values: "gradient", "scale", "fill", "stripe", "glow", "scale_fill"
    # "gradient" enables rotating gradient border, "scale" increases card size, "fill" applies accent overlay,
    # "stripe" applies static accent border, "glow" applies pulsing accent border,
    # "scale_fill" combines scale animation with fill overlay
    "card_animation_type": "gradient",

    # Overlay color for "fill" card animation type
    # Any valid Qt color string (hex/rgb/rgba)
    "fill_color": color_a,

    # Overlay opacity for "fill" card animation type (0-255)
    "fill_alpha": 90,

    # Border color for "stripe" card animation type
    # Any valid Qt color string (hex/rgb/rgba)
    "stripe_color": color_a,

    # Border opacity for "stripe" card animation type (0-255)
    "stripe_alpha": 255,

    # Base opacity for "glow" card animation type (0-255)
    "glow_base_alpha": 120,

    # Additional pulse opacity for "glow" card animation type (0-255)
    "glow_pulse_alpha": 80,

    # Card scale in idle state
    # Defines base card size (1.0 = 100% of original size)
    # Value as fraction (e.g., 1.0 for normal size)
    "default_scale": 1.0,

    # Card scale on hover
    # Increases card size on hover
    # Value as fraction (e.g., 1.1 = 110% of original size)
    "hover_scale": 1.1,

    # Card scale on focus (e.g., keyboard selection)
    # Increases card size on focus
    # Value as fraction (e.g., 1.05 = 105% of original size)
    "focus_scale": 1.05,

    # Duration of scale animation
    # Affects speed of card size change on hover or focus
    # Value in milliseconds
    "scale_anim_duration": 200,

    # Easing curve type for border thickness increase animation (on hover/focus)
    # Affects animation "feel" (e.g., smooth acceleration or deceleration)
    # Possible values: strings matching QEasingCurve.Type (e.g., "OutBack", "InOutQuad")
    "thickness_easing_curve": "OutBack",

    # Easing curve type for border thickness decrease animation (on hover/focus loss)
    # Affects "feel" of return to original border width
    "thickness_easing_curve_out": "InBack",

    # Easing curve type for scale increase animation (on hover/focus)
    # Affects scale animation "feel" (e.g., with "bounce" effect)
    # Possible values: strings matching QEasingCurve.Type
    "scale_easing_curve": "OutBack",

    # Easing curve type for scale decrease animation (on hover/focus loss)
    # Affects "feel" of return to original scale
    "scale_easing_curve_out": "InBack",

    # Gradient colors for animated border
    # List of dicts, each specifying position (0.0–1.0) and hex color
    # Affects border appearance on hover or focus if card_animation_type="gradient"
    "gradient_colors": [
        {"position": 0, "color": "#00fff5"},    # Start color (cyan)
        {"position": 0.33, "color": "#FF5733"}, # Color at 33% (orange)
        {"position": 0.66, "color": "#9B59B6"}, # Color at 66% (purple)
        {"position": 1, "color": "#00fff5"}     # End color (return to cyan)
    ],

    # Fade animation duration on detail page enter
    # Affects page appearance speed for fade animation
    # Value in milliseconds
    "detail_page_fade_duration": 350,

    # Slide animation duration on detail page enter
    # Affects page sliding speed for slide animation
    # Value in milliseconds
    "detail_page_slide_duration": 500,

    # Bounce animation duration on detail page enter
    # Affects page "bounce" speed for bounce animation
    # Value in milliseconds
    "detail_page_bounce_duration": 400,

    # Fade animation duration on detail page exit
    # Affects page disappearance speed for fade animation
    # Value in milliseconds
    "detail_page_fade_duration_exit": 350,

    # Slide animation duration on detail page exit
    # Affects page sliding speed for slide animation
    # Value in milliseconds
    "detail_page_slide_duration_exit": 500,

    # Bounce animation duration on detail page exit
    # Affects page "squeeze" speed for bounce animation
    # Value in milliseconds
    "detail_page_bounce_duration_exit": 400,

    # Easing curve type for detail page enter animation
    # Applied to slide and bounce animations, affects movement "feel"
    # Possible values: strings matching QEasingCurve.Type
    "detail_page_easing_curve": "OutCubic",

    # Easing curve type for detail page exit animation
    # Applied to slide and bounce animations, affects movement "feel"
    # Possible values: strings matching QEasingCurve.Type
    "detail_page_easing_curve_exit": "InCubic"
}

MAIN_WINDOW_STYLE = f"""
    QWidget {{
        background: {color_j};
    }}
    QLabel {{
        color: {color_l};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QPushButton {{
        background: {color_c};
        border: {border_c} rgba(255, 255, 255, 0.01);
        border-radius: {border_radius_a};
        color: {color_l};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 8px 16px;
    }}
    QPushButton:hover {{
        background: {color_a};
        border: {border_c} {color_a};
    }}
    QPushButton:pressed {{
        background: {color_b};
    }}
    QPushButton:focus {{
        border: {border_c} {color_a};
        background-color: {color_a};
    }}
"""

# Favorite Star
FAVORITE_LABEL_STYLE = f"color: gold; font-size: 32px; background: {color_h};"

# Transparent background style
TRANSPARENT_BACKGROUND_STYLE = f"""
    QWidget {{
        background: {color_h};
    }}
"""

# QMessageBox STYLES (MESSAGE BOXES)
MESSAGE_BOX_STYLE = f"""
    QMessageBox {{
        background: {color_j};
        border: {border_a};
    }}
    QMessageBox QLabel {{
        color: {color_l};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QMessageBox QPushButton {{
        background: {color_c};
        border: {border_a} {color_h};
        border-radius: {border_radius_a};
        color: {color_l};
        font-family: '{font_family}';
        padding: 8px 20px;
        min-width: 80px;
    }}
    QMessageBox QPushButton:hover {{
        background: {color_a};
        border-color: border: {border_b} {color_a};
    }}
    QMessageBox QPushButton:focus {{
        border: {border_c} {color_a};
        background: {color_a};
    }}
"""

# PROGRESS BAR STYLE
PROGRESS_BAR_STYLE = f"""
    QProgressBar {{
        color: {color_l};
        background-color: {color_c};
        text-align: center;
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QProgressBar::chunk {{
        background-color: {color_a};
    }}
"""

# STATUS BAR STYLE
STATUS_BAR_STYLE = f"""
    QStatusBar {{
        color: {color_l};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
"""

TAB_TITLE_STYLE = f"font-family: '{font_family}'; font-size: {font_size_b}; color: {color_l}; background-color: none;"

# PARAMS_TITLE_STYLE
PARAMS_TITLE_STYLE = f"""
    QLabel {{
        color: {color_l};
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        height: 34px;
        padding: 7px;
        background: {color_d};
        border-radius: {border_radius_a};
        min-width: 150px;
    }}
"""

THEME_TAB_FOCUS_STYLE = f"""
    QComboBox#themeTabCombo:focus {{
        border: {border_b} {color_l};
        background-color: {color_a};
    }}
    QPushButton#themeApplyButton:focus {{
        border: {border_b} {color_l};
    }}
    QGraphicsView#themeScreenshotsCarousel {{
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
    }}
    QGraphicsView#themeScreenshotsCarousel:focus {{
        border: {border_b} {color_a};
    }}
"""

PREVIEW_WIDGET_STYLE = f"""
    QWidget {{
        margin-top: 3px;
        background-color: {color_e};
        border-radius: {border_radius_a};
    }}
"""

CONTENT_STYLE = f"""
    QLabel {{
        font-family: '{font_family}';
        font-size: {font_size_a};
        color: {color_l};
        background-color: none;
        border-bottom: {border_b} rgba(255, 255, 255, 0.2);
        padding-bottom: 15px;
    }}
"""

LIBRARY_WIDGET_STYLE = f"""
    QWidget {{
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 #cea2fa,
            stop:1 #70b8ff
    );
        border-radius: 0px;
    }}
"""

# CONTAINER_STYLE
CONTAINER_STYLE= """
    QWidget {
        background-color: none;
    }
"""

# OTHER_PAGES_WIDGET_STYLE
OTHER_PAGES_WIDGET_STYLE= f"""
    QWidget {{
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 {color_j},
            stop:1 {color_k}
    );
        border-radius: 0px;
    }}
"""

# CAROUSEL_WIDGET_STYLE
CAROUSEL_WIDGET_STYLE= f"""
    QWidget {{
        background: {color_k};
        border-radius: 0px;
    }}
"""

SETTINGS_FRAME_STYLE = f"""
    QFrame {{
        background: {color_h};
        border:  {border_b} {color_c};
        border-radius: {border_radius_b};
    }}
"""

SETTINGS_FRAME_TITLE_STYLE = f"""
    QLabel {{
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        color: {color_l};
        background: {color_h};
        border:  {border_a} {color_c};
    }}
"""

SETTINGS_TITLE_STYLE = f"""
    QLabel {{
        color: {color_l};
        height: 34px;
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        padding: 7px;
        background: {color_b};
        border-radius: {border_radius_a};
        border:  {border_a} {color_c};
        min-width: 320px;
    }}
"""

SETTINGS_TITLE_CHECKBOX_STYLE = f"""
    QLabel {{
        color: {color_l};
        height: 34px;
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        padding: 7px;
        background: {color_h};
        border-radius: {border_radius_a};
        border:  {border_a} {color_c};
        min-width: 180px;
    }}
"""

# Disabled line edit style
SETTINGS_DISABLED_INPUT_STYLE = f"background-color: {color_disabled_bg};"

# DRIVES BUTTONS STYLE (FILE MANAGER)
DRIVES_BUTTON_STYLE = f"""
    QPushButton {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        color: {color_l};
        font-size: {font_size_a};
        font-family: '{font_family}';
        min-width: 90px;
    }}
    QPushButton:hover {{
        background: {color_a};
        border: {border_c} {color_a};
    }}
    QPushButton:pressed {{
        background: {color_b};
    }}
    QPushButton:focus {{
        border: {border_c} {color_a};
        background-color: {color_a};
    }}
"""

# OVERLAY STYLE
OVERLAY_WINDOW_STYLE = f"background: {color_b};"
OVERLAY_BUTTON_STYLE = f"""
    QPushButton {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        color: {color_l};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 8px 16px;
    }}
    QPushButton:hover {{
        background: {color_a};
        border: {border_c} {color_a};
    }}
    QPushButton:pressed {{
        background: {color_b};
    }}
    QPushButton:focus {{
        border: {border_c} {color_a};
        background-color: {color_a};
    }}
"""

# QGroupBox STYLES
QGROUP_BOX_STYLE = f"""
    QGroupBox {{
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        color: {color_l};
        border: {border_b} {color_c};
        border-radius: {border_radius_a};
        margin-top: 10px;
        margin-right: 10px;
        padding-top: 5px;
        background: {color_h};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }}
"""

# GAME CARD STYLE (GAMECARD)
GAME_CARD_WINDOW_STYLE = f"""
    QFrame {{
        border-radius: 25px;
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 rgba(255, 255, 255, 1),
            stop:1 rgba(210, 211, 219, 0.5)
    );
        border: {border_a} {color_h};
    }}
"""

# GAME NAME LABEL IN CARD (QLabel)
GAME_CARD_NAME_LABEL_STYLE = f"""
    QLabel {{
        color: {color_l};
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        background-color: {color_h};
        border: {border_a} {color_h};
        padding: 14px, 7px, 3px, 7px;
        qproperty-wordWrap: true;
    }}
"""

# PROTONDB BADGE STYLES ON CARD
def get_protondb_badge_style(tier):
    tier = tier.lower()
    tier_colors = {
        "platinum": {"background": "rgba(255,255,255,0.9)", "color": "black"},
        "gold": {"background": "rgba(253,185,49,0.7)", "color": "black"},
        "silver": {"background": "rgba(169,169,169,0.8)", "color": "black"},
        "bronze": {"background": "rgba(205,133,63,0.7)", "color": "black"},
        "borked": {"background": "rgba(255,0,0,0.7)", "color": "black"},
        "pending": {"background": "rgba(160,82,45,0.7)", "color": "black"}
    }
    colors = tier_colors.get(tier, {"background": "rgba(0, 0, 0, 0.5)", "color": "white"})
    return f"""
        qproperty-alignment: AlignCenter;
        background-color: {colors["background"]};
        color: {colors["color"]};
        border-radius: 5px;
        font-family: '{font_family}';
        font-weight: bold;
    """

# WEANTICHEATYET BADGE STYLES
def get_anticheat_badge_style(status):
    status = status.lower()
    status_colors = {
        "supported": {"background": "rgba(102, 168, 15, 0.7)", "color": "black"},
        "running": {"background": "rgba(25, 113, 194, 0.7)", "color": "black"},
        "planned": {"background": "rgba(156, 54, 181, 0.7)", "color": "black"},
        "broken": {"background": "rgba(232, 89, 12, 0.7)", "color": "black"},
        "denied": {"background": "rgba(224, 49, 49, 0.7)", "color": "black"}
    }
    colors = status_colors.get(status, {"background": "rgba(0, 0, 0, 0.5)", "color": "white"})
    return f"""
        qproperty-alignment: AlignCenter;
        background-color: {colors["background"]};
        color: {colors["color"]};
        font-size: {font_size_a};
        border-radius: 5px;
        font-weight: bold;
    """

# STEAM BADGE STYLES
STEAM_BADGE_STYLE= f"""
    qproperty-alignment: AlignCenter;
    background: rgba(0, 0, 0, 0.5);
    color: white;
    border-radius: 5px;
    font-family: '{font_family}';
    font-weight: bold;
"""

# MAIN FRAME FOR GAME DETAILS
DETAIL_CONTENT_FRAME_STYLE = f"""
    QFrame {{
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 {color_j},
            stop:1 {color_k}
        );
        border:  {border_a} {color_g};
        border-radius: {border_radius_b};
    }}
"""

# FRAME UNDER COVER
COVER_FRAME_STYLE = f"""
    QFrame {{
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 #E9ECEF,
            stop:1 {color_j}
        );
        border-radius: {border_radius_b};
        border:  {border_a} {color_g};
    }}
"""

# COVER WIDGET
COVER_WIDGET_STYLE = f"""
    QWidget {{
        background: {color_h};
        border:  {border_a} {color_h};
    }}
"""

# COVER LABEL BORDER RADIUS
COVER_LABEL_STYLE = f"border-radius: {border_radius_b};"

# DETAILS WIDGET (TEXT, DESCRIPTION)
DETAILS_WIDGET_STYLE = f"""
        QFrame {{
            background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
                stop:0 #E9ECEF,
                stop:1 {color_j}
            );
            border-radius: {border_radius_b};
            padding: 10px;
        }}
        QWidget#child {{
            background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
                stop:0 #E9ECEF,
                stop:1 {color_j}
            );
            border-radius: {border_radius_b};
            padding: 10px;
        }}
"""

COMPACT_DETAILS_WIDGET_STYLE = f"""
        QFrame, QWidget {{
            background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
                stop:0 #E9ECEF,
                stop:1 {color_j}
            );
            border-radius: {border_radius_b};
            padding: 10px;
        }}
"""

# TITLE (HEADER) ON DETAIL PAGE
DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 32px; color: {color_l}; background: {color_h};"
COMPACT_DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 32px; color: {color_l}; background: {color_h};"

# DIVIDER LINE
DETAIL_PAGE_LINE_STYLE = f"background: {color_j}; margin: 0 0;"

# DESCRIPTION TEXT
DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_a}; color: {color_l}; line-height: 1.5;"
COMPACT_DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_a}; color: {color_l}; line-height: 1.5; background: {color_h};"

# PLAYTIME WIDGET (PLAYTIME)
COMPACT_PLAYTIME_WIDGET_STYLE = f"background: {color_h}; border-radius: {border_radius_b}; padding: 10px;"

# ADDITIONAL INFO STYLES ON GAMES PAGE
LAST_LAUNCH_TITLE_STYLE = f"max-height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 {color_j}); font-family: '{font_family}'; font-size: 11px; color: {color_l}; text-transform: uppercase; letter-spacing: 0.75px;"
LAST_LAUNCH_VALUE_STYLE = f"height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 {color_j}); font-family: '{font_family}'; font-size: 13px; color: {color_l}; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE = f"max-height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 {color_j}); font-family: '{font_family}'; font-size: 11px; color: {color_l}; text-transform: uppercase; letter-spacing: 0.75px;"
PLAY_TIME_VALUE_STYLE = f"height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 {color_j}); font-family: '{font_family}'; font-size: 13px; color: {color_l}; font-weight: 600; letter-spacing: 0.75px;"
GAMEPAD_SUPPORT_VALUE_STYLE = f"""
    font-family: '{font_family}'; font-size: {font_size_a}; color: {color_gamepad_supported};
    font-weight: bold; background: {color_g};
    border-radius: 5px; padding: 4px 8px;
"""

# PLAY BUTTON STYLE
PLAY_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 #E9ECEF,
            stop:1 {color_j}
        );
        border: {border_b} {color_f};
        border-radius: {border_radius_a};
        font-size: {font_size_a};
        margin-top: 15px;
        color: {color_l};
        font-weight: bold;
        font-family: '{font_family}';
        padding: 8px 16px;
        margin-top: 15px;
        min-width: 120px;
        min-height: 30px;
    }}
    QPushButton:hover {{
        background: {color_a};
    }}
    QPushButton:pressed {{
        background: {color_a};
    }}
    QPushButton:focus {{
        background: {color_a};
    }}
"""

# BACKGROUND FOR DETAIL PAGE IF COVER NOT LOADED
DETAIL_PAGE_NO_COVER_STYLE = f"background: rgba(20,20,20,0.95); border-radius: {border_radius_b};"

# STYLE FOR "ADD GAME" AND "BACK" BUTTONS ON DETAIL PAGE AND LIBRARY
ADDGAME_BACK_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 #E9ECEF,
            stop:1 {color_j}
        );
        border: {border_b} {color_f};
        border-radius: {border_radius_a};
        color: {color_l};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 5px 10px;
        min-width: 120px;
        min-height: 25px;
    }}
    QPushButton:hover {{
        background: {color_a};
    }}
    QPushButton:pressed {{
        background: {color_a};
    }}
    QPushButton:focus {{
        background: {color_a};
        border: {border_b} {color_a};
    }}
"""

# SEARCH FIELD STYLE
SEARCH_EDIT_STYLE = f"""
    QLineEdit {{
        background: {color_b};
        border: {border_a};
        border-radius: {border_radius_a};
        padding: 7px 14px;
        font-family: '{font_family}';
        font-size: {font_size_a};
        color: {color_l};
        min-height: 24px;
    }}
    QLineEdit:hover {{
        border: {border_b} {color_a};
    }}
    QLineEdit:focus {{
        border: {border_b} {color_a};
    }}
"""

# SLIDER_SIZE_STYLE
SLIDER_SIZE_STYLE= f"""
    QWidget {{
        background: {color_h};
        height: 25px;
    }}
    QSlider::groove:horizontal {{
        border:  {border_a};
        border-radius: 3px;
        height: 6px; /* the groove expands to the size of the slider by default. by giving it a height, it has a fixed size */
        background: rgba(20, 20, 20, 0.30);
        margin: 6px 0;
    }}
    QSlider::handle:horizontal {{
        background: {color_c};
        border:  {border_a};
        width: 18px;
        height: 18px;
        margin: -6px 0; /* handle is placed by default on the contents rect of the groove. Expand outside the groove */
        border-radius: 9px;
    }}
"""

# GAME CARD AREA STYLE (QWidget)
LIST_WIDGET_STYLE = """
    QWidget {
        background: none;
        border:  {border_a} {color_g};
        border-radius: 25px;
    }
"""

# NAVIGATION TAB BUTTON STYLE
NAV_BUTTON_STYLE = f"""
    NavLabel {{
        background: {color_h};
        padding: 6px 3px;
        margin: 10px 0 10px 10px;
        color: {color_i};
        font-family: '{font_family}';
        font-size: {font_size_a};
        text-transform: uppercase;
        border: {color_a};
        border-radius: 0px;
    }}
    NavLabel[checked = true] {{
        background: {color_h};
        color: {color_l};
        font-weight: normal;
        text-decoration: none;
        border-bottom: {border_c} {color_a};
        border-radius: 0px;
    }}
    NavLabel:hover {{
        background: {color_h};
        color: {color_l};
        border-bottom: {border_c} #7f7f7f;
    }}
    NavLabel[checked = true]:hover {{
        background: {color_h};
        color: {color_l};
        border-bottom: {border_c} {color_a};
    }}
"""

# NAVIGATION AREA STYLE (TAB BUTTONS)
NAV_WIDGET_STYLE = f"""
    QWidget {{
        background: {color_h};
        border:  {border_a};
    }}
"""

WINETRICKS_TABBLE_STYLE = f"""
QTableWidget {{
    background: {color_h};
    color: {color_l};
    gridline-color: {color_h};
    alternate-background-color: {color_e};
    border: {border_a};
    border-radius: {border_radius_a};
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QHeaderView::section {{
    background: {color_d};
    color: {color_l};
    padding: 2px;
    border: {border_a};
    font-weight: bold;
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QTableWidget::item {{
    padding: 3px;
    border-bottom: {border_a } {color_c};
    height: 32px;
}}
QTableWidget::item:selected,
QTableWidget::item:focus,
QTableWidget::item:selected:focus {{
    background: {color_a};
    color: {color_l};
    selection-background-color: {color_a};
}}
QTableWidget::item:hover {{
    background: {color_h};
}}
"""

SCROLL_STYLE = f"""
    QScrollBar:vertical {{
        width: 10px;
        border:  {border_a};
        border-radius: 5px;
        background: rgba(20, 20, 20, 0.20);
    }}
    QScrollBar::handle:vertical {{
        background: {color_c};
        border:  {border_a};
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical {{
        border:  {border_a};
        background: none;
    }}
    QScrollBar::sub-line:vertical {{
        border:  {border_a};
        background: none;
    }}
    QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
        border:  {border_a};
        width: 3px;
        height: 3px;
        background: none;
    }}
    QScrollBar:horizontal {{
        height: 10px;
        border:  {border_a};
        border-radius: 5px;
        background: rgba(20, 20, 20, 0.20);
    }}
    QScrollBar::handle:horizontal {{
        background: {color_c};
        border:  {border_a};
        border-radius: 5px;
    }}
    QScrollBar::add-line:horizontal {{
        border:  {border_a};
        background: none;
    }}
    QScrollBar::sub-line:horizontal {{
        border:  {border_a};
        background: none;
    }}
    QScrollBar::up-arrow:horizontal, QScrollBar::down-arrow:horizontal {{
        border:  {border_a};
        width: 3px;
        height: 3px;
        background: none;
    }}
"""

# COMBOBOX
COMBOBOX_STYLE = f"""
    QComboBox {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        padding-left: 12px;
        height: 34px;
        color: {color_l};
        font-family: '{font_family}';
        font-size: {font_size_a};
        min-width: 120px;
        combobox-popup: 0;
    }}
    QComboBox:on {{
        background: {color_b};
        border: {border_c} {color_a};
        border-bottom-style: none;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
    }}
    QComboBox:hover {{
        border: {border_c} {color_a};
        background: {color_a};
    }}
    /* Focus state */
    QComboBox:focus {{
        border: {border_c} {color_a};
        background-color: {color_a};
    }}
    QComboBox:disabled {{
        background: {color_e};
        border: {border_c} {color_e};
        color: #777a84;
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        border-left: {border_b} rgba(255, 255, 255, 0.05);
        padding: 12px;
        height: 12px;
        width: 12px;
    }}
    QComboBox::down-arrow {{
        image: url({theme_manager.get_icon("down", current_theme_name, as_path=True)});
        padding: 12px;
        height: 12px;
        width: 12px;
    }}
    QComboBox::down-arrow:on {{
        image: url({theme_manager.get_icon("up", current_theme_name, as_path=True)});
        padding: 12px;
        height: 12px;
        width: 12px;
    }}
/* List when combobox is open */
    QComboBox QAbstractItemView {{
        outline: none;
        background: {color_c};
        border: {border_c} {color_a};
        border-top-style: none;
        border-top-left-radius: 0px;
        border-top-right-radius: 0px;
        border-bottom-left-radius: 10px;
        border-bottom-right-radius: 10px;
    }}
    QComboBox:editable {{
        background: {color_c};
    }}
    QComboBox::drop-down:editable:focus {{
        background: {color_a};
        border-top-left-radius: 0px;
        border-top-right-radius: 10px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 10px;
    }}
    QListView {{
        background: {color_c};
    }}
    QListView::item {{
        padding: 7px 7px 7px 12px;
        margin: 3px;
        min-height: 24px;
        border-radius: {border_radius_a};
        color: {color_l};
    }}
    QListView::item:hover {{
        background: {color_b};
    }}
    QListView::item:selected {{
        background: {color_b};
    }}
    /* Selection in list when item is focused */
    QListView::item:focus {{
        background: {color_a};
        color: {color_l};
    }}
"""

CHECKBOX_STYLE = f"""
    QCheckBox {{
        height: 34px;
        color: {color_l};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QCheckBox::indicator {{
        width: 24px;
        height: 24px;
        border: {border_c} #bfbfbf;
        border-radius: {border_radius_a};
        background: {color_c};
    }}
    QCheckBox::indicator:hover {{
        background: {color_c};
        border: {border_c} {color_a};
    }}
    QCheckBox::indicator:focus {{
        border: {border_c} {color_a};
    }}
    QCheckBox::indicator:checked {{
        image: url({theme_manager.get_icon("check", current_theme_name, as_path=True)});
        border: {border_c} {color_a};
    }}
    QCheckBox::indicator:disabled {{
        background: {color_e};
        border: {border_c} {color_e};
    }}
    QCheckBox::indicator:checked:disabled {{
        image: url({theme_manager.get_icon("check", current_theme_name, as_path=True)});
        background: {color_e};
        border: {border_c} {color_e};
    }}

    QTableWidget::indicator {{
        width: 24px;
        height: 24px;
        border: {border_c} #bfbfbf;
        border-radius: {border_radius_a};
        background: {color_c};
    }}
    QTableWidget::indicator:unchecked {{
        background: {color_c};
        border: {border_c} #bfbfbf;
        image: none;
    }}
    QTableWidget::indicator:checked {{
        background: {color_b};
        image: url({theme_manager.get_icon("check", current_theme_name, as_path=True)});
        border: {border_c} {color_a};
    }}
    QTableWidget::indicator:hover {{
        background: rgba(255, 255, 255, 0.2);
        border: {border_c} {color_a};
    }}
    QTableWidget::indicator:focus {{
        background: rgba(255, 255, 255, 0.2);
        border: {border_c} {color_a};
    }}
    QTableWidget::indicator:disabled {{
        background: {color_b};
        border: {border_c} {color_d};
    }}
    QTableWidget::indicator:checked:disabled {{
        image: url({theme_manager.get_icon("check", current_theme_name, as_path=True)});
        background: {color_b};
        border: {border_c} {color_d};
    }}
"""

LINE_EDIT_STYLE = f"""
    QLineEdit {{
        background: {color_c};
        border: {border_c} rgba(255, 255, 255, 0.01);
        border-radius: {border_radius_a};
        height: 34px;
        padding-left: 12px;
        color: {color_l};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QLineEdit:hover {{
        background: {color_c};
        border: {border_c} {color_a};
    }}
    QLineEdit:focus {{
        border: {border_c} {color_a};
        background-color: {color_e};
    }}
"""

ADDGAME_INPUT_STYLE = f"""
    QLineEdit {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        height: 34px;
        padding-left: 12px;
        color: {color_l};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QLineEdit:hover {{
        background: {color_c};
        border: {border_c} {color_a};
    }}
    QLineEdit:focus {{
        border: {border_c} {color_a};
        background-color: {color_e};
    }}
"""

TAB_STYLE = f"""
    QTabWidget::pane {{
        border-top: 1px solid {color_c};
        background: {color_h};
    }}
    QTabBar::tab {{
        background: {color_c};
        color: {color_l};
        padding: 8px 16px;
        border-top-left-radius: {border_radius_a};
        border-top-right-radius: {border_radius_a};
        margin-right: 2px;
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QTabBar::tab:selected {{
        background: {color_a};
        color: {color_l};
    }}
    QTabBar::tab:hover {{
        background: {color_a};
    }}
"""

# HINT BAR STYLE
HINT_BAR_STYLE = f"""
    QWidget {{
        max-height: 40px;
    }}
"""

# HINT LABEL STYLE
HINTS_LABEL_STYLE = f"""
    QWidget {{
        background: {color_h};
        font-family: '{font_family}';
        font-size: 13px;
        color: {color_l};
        font-weight: 600;
        letter-spacing: 0.75px;
    }}
"""

# MAIN WINDOW HEADER STYLE
MAIN_WINDOW_HEADER_STYLE = f"""
    QFrame {{
        background: {color_h};
        border: 10px solid {color_g};
        border-bottom: 0px solid {color_g};
        border-top-left-radius: 30px;
        border-top-right-radius: 30px;
        border: none;
    }}
"""

# ACTION BUTTONS STYLE (SAVE, APPLY, ETC.)
ACTION_BUTTON_STYLE = f"""
    QPushButton {{
        background: {color_b};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        color: {color_l};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 8px 16px;
    }}
    QPushButton:hover {{
        background: {color_a};
        border: {border_c} {color_a};
    }}
    QPushButton:pressed {{
        background: {color_b};
    }}
    QPushButton:focus {{
        border: {border_c} {color_a};
        background-color: {color_a};
    }}
"""

# ACTION BUTTON ACTIVE STYLE (MANGOHUD, GAMESCOPE ETC.)
ACTION_BUTTON_ACTIVE_STYLE = f"""
    QPushButton {{
        background: {color_c};
        border: {border_c} {color_a};
        border-radius: {border_radius_a};
        color: {color_l};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 8px 16px;
    }}
    QPushButton:hover {{
        background: {color_a};
        border: {border_c} {color_a};
    }}
    QPushButton:pressed {{
        background: {color_b};
    }}
    QPushButton:focus {{
        border: {border_c} {color_a};
        background-color: {color_a};
    }}
"""

GETWINE_WINDOW_STYLE = f"""
/* Table */
QHeaderView::section {{
    background: {color_d};
    color: {color_l};
    border: {border_a};
    font-weight: bold;
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QTableWidget {{
    background: {color_h};
    gridline-color: {color_h};
    color: {color_l};
    alternate-background-color: {color_d};
    border: {border_a};
    border-radius: {border_radius_a};
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QTableWidget::item:!enabled {{
    color: #7a7a7a;
}}
QTableWidget::item:selected,
QTableWidget::item:selected:!active,
QTableWidget::item:hover {{
    background: {color_a};
}}
/* LogArea */
QFrame {{
    background: {color_h};
}}
QTextEdit {{
    background: {color_e};
    border: {border_a};
    border-radius: {border_radius_a};
    color: {color_l};
    font-family: '{font_family}';
    font-size: {font_size_a};
    padding: 5px;
}}
QProgressBar {{
    color: {color_l};
    background-color: {color_c};
    height: 34px;
    text-align: center;
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QProgressBar::chunk {{
    background-color: {color_a};
}}
"""

# Empty state label style
GETWINE_EMPTY_LABEL_STYLE = f"font-size: {font_size_a}; padding: 50px;"

FILE_EXPLORER_STYLE = f"""
    QListView {{
        font-size: {font_size_a};
        font-family: {font_family};
        background: {color_e};
        alternate-background-color: {color_e};
        color: {color_l};
        border-top-left-radius: 5px;
        border-bottom-left-radius: 5px;
    }}
    QListView::item {{
        padding: 8px;
        margin: 0px 5px;
    }}
    QListView::item:alternate {{
        margin: 0px 5px;
        background: {color_d};
    }}
    QListView::item:selected {{
        background: {color_a};
        color: {color_l};
        border-radius: {border_radius_a};
    }}
    QListView::item:hover {{
        background: {color_a};
        color: {color_l};
        border-radius: {border_radius_a};
    }}
    QListView::item:focus {{
        background: {color_a};
        color: {color_l};
        border-radius: {border_radius_a};
    }}
"""

FILE_EXPLORER_PATH_LABEL_STYLE = f"""
    QLabel {{
        color: {color_l};
        font-size: {font_size_a};
        font-family: {font_family};
    }}
"""

CONTEXT_MENU_STYLE = f"""
    QMenu {{
        background: {color_b};
        color: {color_l};
        font-family: '{font_family}';
        font-size: {font_size_a};
        padding: 5px;
        min-width: 150px;
        border: {border_b} {color_a};
        border-radius: {border_radius_a};
    }}
    QMenu::icon {{
        margin-left: 15px;
    }}
    QMenu::item {{
        padding: 10px 20px 10px 10px;
        background: {color_h};
        border-radius: {border_radius_a};
        color: {color_l};
    }}
    QMenu::item:selected {{
        background: {color_a};
        color: {color_l};
    }}
    QMenu::item:disabled {{
            color: #7f7f7f;
        }}
    QMenu::item:hover {{
        background: {color_a};
        color: {color_l};
    }}
    QMenu::item:focus {{
        background: {color_a};
        color: {color_l};
        border: {border_b} rgba(255, 255, 255, 0.3);
        border-radius: {border_radius_a};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: #7f7f7f;
        margin: 3px 6px;
    }}
"""

VIRTUAL_KEYBOARD_STYLE = f"""
QWidget {{
    background: {color_k};
}}
QPushButton {{
    font-size: 14px;
    border: {border_a} {color_h};
    border-radius: {border_radius_a};
    min-width: 30px;
    min-height: 30px;
    padding: 5px;
    background-color: {color_e};
    color: {color_l};
}}
QPushButton:hover {{
    background-color: {color_a};
    border: {border_b} {color_a};
}}
QPushButton:focus {{
    border: {border_b} {color_a};
    background-color: {color_a};
}}
QPushButton[vk_selected="true"] {{
    border: {border_b} {color_a};
    background-color: {color_a};
}}
QPushButton:pressed {{
    background-color: {color_e};
    border: {border_a} {color_h};
}}
QPushButton[checked="true"] {{
    background-color: {color_a};
    color: {color_l};
    border: {border_a} {color_h};
}}
QPushButton[checked="true"]:focus {{
    border: {border_b} {color_l};
}}
"""

# FULLSCREEN THEME SCREENSHOT PREVIEW STYLES
PREV_BUTTON_STYLE="background-color: rgba(0, 0, 0, 0.5); color: white; border: none;"
NEXT_BUTTON_STYLE="background-color: rgba(0, 0, 0, 0.5); color: white; border: none;"

TOOLTIP_STYLE = f"""
    QLabel {{
        background-color: {color_b};
        border: {border_b} {color_c};
        border-radius: {border_radius_a};
        padding: 8px;
        color: {color_l};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
"""

# FUNCTION FOR DYNAMIC GRADIENT (GAME DETAILS)
# Functions from this theme always work regardless of selected theme, functions from other themes work only in those themes
def detail_page_style(stops):
    return f"""
    QWidget {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    {stops});
                                    border-radius: 0px;
    }}
"""
