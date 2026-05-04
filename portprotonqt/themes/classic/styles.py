LIBRARY_LAYOUT_MODE = "list"

GAME_CARD_ANIMATION = {
    "detail_page_animation_type": "fade",
    "default_border_width": 1,
    "hover_border_width": 3,
    "focus_border_width": 4,
    "pulse_min_border_width": 2,
    "pulse_max_border_width": 3,
    "thickness_anim_duration": 300,
    "pulse_anim_duration": 800,
    "gradient_anim_duration": 3000,
    "gradient_start_angle": 360,
    "gradient_end_angle": 0,
    "card_animation_type": "glow",
    "fill_color": "#409EFF",
    "fill_alpha": 90,
    "stripe_color": "#409EFF",
    "stripe_alpha": 255,
    "default_scale": 1.0,
    "hover_scale": 1.08,
    "focus_scale": 1.05,
    "scale_anim_duration": 200,
    "thickness_easing_curve": "OutBack",
    "thickness_easing_curve_out": "InBack",
    "scale_easing_curve": "OutBack",
    "scale_easing_curve_out": "InBack",
    "gradient_colors": [
        {"position": 0, "color": "#9ca3af"},
        {"position": 0.5, "color": "#6b7280"},
        {"position": 1, "color": "#9ca3af"},
    ],
    "detail_page_fade_duration": 350,
    "detail_page_slide_duration": 500,
    "detail_page_bounce_duration": 400,
    "detail_page_fade_duration_exit": 350,
    "detail_page_slide_duration_exit": 500,
    "detail_page_bounce_duration_exit": 400,
    "detail_page_easing_curve": "OutCubic",
    "detail_page_easing_curve_exit": "InCubic",
}

# VARS
font_family = "Play"
font_size_a = "16px"
font_size_b = "24px"
border_a = "0px solid"
border_b = "1px solid"
border_c = "2px solid"
border_radius_a = "10px"
border_radius_b = "15px"
color_a = "#409EFF"
color_b = "#282a33"
color_c = "#3f424d"
color_d = "#32343d"
color_e = "#404554"
color_f = "#ffffff"
color_g = "rgba(0, 0, 0, 0)"
color_h = "transparent"
color_i = "rgba(40, 42, 51, 0.9)"

LIBRARY_WIDGET_STYLE = """
    QWidget {
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 #22242b,
            stop:1 #1a1b21
        );
        border-radius: 0px;
    }
"""

# GAME CARD STYLE (GAMECARD)
GAME_CARD_WINDOW_STYLE = """
    QFrame {
        border-radius: 20px;
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 #404554,
            stop:1 #30323d
        );
        border:  0px solid;
    }
"""

# PLAY BUTTON STYLE
PLAY_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 #404554,
            stop:1 #30323d
        );
        border: {border_a} rgba(255, 255, 255, 0.5);
        border-radius: {border_radius_a};
        font-size: 16px;
        color: {color_f};
        font-weight: bold;
        font-family: '{font_family}';
        padding: 5px 10px;
        min-width: 50px;
        min-height: 20px;
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
# STYLE FOR "ADD GAME" AND "BACK" BUTTONS ON DETAIL PAGE AND LIBRARY
ADDGAME_BACK_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 #404554,
            stop:1 #30323d
        );
        border: {border_a};
        border-radius: {border_radius_a};
        color: {color_f};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 5px 10px;
    }}
    QPushButton:hover {{
        background: {color_a};
    }}
    QPushButton:pressed {{
        background: {color_a};
    }}
"""

# SEARCH FIELD STYLE
SEARCH_EDIT_STYLE = f"""
    QLineEdit {{
        background: {color_b};
        border: {border_a};
        border-radius: {border_radius_a};
        padding: 5px 10px;
        font-family: '{font_family}';
        font-size: {font_size_a};
        color: {color_f};
        min-height: 28px;
    }}
    QLineEdit:hover {{
        border: {border_b} {color_a};
    }}
    QLineEdit:focus {{
        border: {border_b} {color_a};
    }}
"""
