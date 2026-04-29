from portprotonqt.theme_manager import ThemeManager
from portprotonqt.config import ui_config

theme_manager = ThemeManager()
current_theme_name = ui_config.get_theme()

# CONSTANTS
favoriteLabelSize = 48, 48

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
