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


LIBRARY_WIDGET_STYLE = """
    QWidget {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #2b2d31,
            stop:1 #1f2125
        );
        border-radius: 0px;
    }
"""
