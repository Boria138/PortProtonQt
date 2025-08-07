📘  Эта документация также доступна на [русском](README.ru.md)

---

## 📋 Contents
- [Overview](#-overview)
- [Creating the Theme Folder](#-creating-the-theme-folder)
- [Style File](#-style-file-stylespy)
- [Animation configuration](#-animation-configuration)
- [Metadata](#-metadata-metainfoini)
- [Screenshots](#-screenshots)
- [Fonts and Icons](#-fonts-and-icons-optional)

---

## 📖 Overview

Themes in `PortProtonQT` allow customizing the UI appearance. Themes are stored under:

- `~/.local/share/PortProtonQT/themes`.

---

## 📁 Creating the Theme Folder

```bash
mkdir -p ~/.local/share/PortProtonQT/themes/my_custom_theme
```

---

## 🎨 Style File (`styles.py`)

Create a `styles.py` in the theme root. It should define variables or functions that return CSS.

**Example:**
```python
def custom_button_style(color1, color2):
    return f"""
    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 {color1}, stop:1 {color2});
    }}
    """
```

---

## 🎥 Animation configuration

The `GAME_CARD_ANIMATION` dictionary controls all animation parameters for game cards:

```python
GAME_CARD_ANIMATION = {
    # Type of animation when entering and exiting the detail page
    # Possible values: "fade", "slide_left", "slide_right", "slide_up", "slide_down", "bounce"
    "detail_page_animation_type": "fade",

    # Border width of the card in idle state (no hover or focus).
    # Affects the thickness of the border when the card is not highlighted.
    # Value in pixels.
    "default_border_width": 2,

    # Border width on hover.
    # Increases the border thickness when the cursor is over the card.
    # Value in pixels.
    "hover_border_width": 8,

    # Border width on focus (e.g., selected via keyboard).
    # Increases the border thickness when the card is focused.
    # Value in pixels.
    "focus_border_width": 12,

    # Minimum border width during pulsing animation.
    # Sets the minimum border thickness during the "breathing" animation.
    # Value in pixels.
    "pulse_min_border_width": 8,

    # Maximum border width during pulsing animation.
    # Sets the maximum border thickness during pulsing.
    # Value in pixels.
    "pulse_max_border_width": 10,

    # Duration of the border thickness animation (e.g., on hover or focus).
    # Affects the speed of transition between different border widths.
    # Value in milliseconds.
    "thickness_anim_duration": 300,

    # Duration of one pulsing animation cycle.
    # Defines how fast the border "pulses" between min and max values.
    # Value in milliseconds.
    "pulse_anim_duration": 800,

    # Duration of the gradient rotation animation.
    # Affects how fast the gradient border rotates around the card.
    # Value in milliseconds.
    "gradient_anim_duration": 3000,

    # Starting angle of the gradient (in degrees).
    # Defines the initial rotation point of the gradient when the animation starts.
    "gradient_start_angle": 360,

    # Ending angle of the gradient (in degrees).
    # Defines the end rotation point of the gradient.
    # A value of 0 means a full 360-degree rotation.
    "gradient_end_angle": 0,

    # Easing curve type for border expansion animation (on hover/focus).
    # Affects the "feel" of the animation (e.g., smooth acceleration or deceleration).
    # Possible values: strings corresponding to QEasingCurve.Type (e.g., "OutBack", "InOutQuad").
    "thickness_easing_curve": "OutBack",

    # Easing curve type for border contraction animation (on mouse leave/focus loss).
    # Affects the "feel" of returning to the original border width.
    "thickness_easing_curve_out": "InBack",

    # Gradient colors for the animated border.
    # A list of dictionaries where each defines a position (0.0–1.0) and color in hex format.
    # Affects the appearance of the border on hover or focus.
    "gradient_colors": [
        {"position": 0, "color": "#00fff5"},    # Start color (cyan)
        {"position": 0.33, "color": "#FF5733"}, # 33% color (orange)
        {"position": 0.66, "color": "#9B59B6"}, # 66% color (purple)
        {"position": 1, "color": "#00fff5"}     # End color (back to cyan)
    ],

    # Duration of the fade animation when entering the detail page
    "detail_page_fade_duration": 350,

    # Duration of the slide animation when entering the detail page
    "detail_page_slide_duration": 500,

    # Duration of the bounce animation when entering the detail page
    "detail_page_bounce_duration": 400,

    # Duration of the fade animation when exiting the detail page
    "detail_page_fade_duration_exit": 350,

    # Duration of the slide animation when exiting the detail page
    "detail_page_slide_duration_exit": 500,

    # Duration of the bounce animation when exiting the detail page
    "detail_page_bounce_duration_exit": 400,

    # Easing curve type for animation when entering the detail page
    # Applies to slide and bounce animations
    "detail_page_easing_curve": "OutCubic",

    # Easing curve type for animation when exiting the detail page
    # Applies to slide and bounce animations
    "detail_page_easing_curve_exit": "InCubic"
}
```

---

## 📝 Metadata (`metainfo.ini`)

```ini
[Metainfo]
name = My Custom Theme
author = Your Name
author_link = https://example.com
description = Description of your theme.
```

---

## 🖼 Screenshots

Folder: `images/screenshots/` — place UI screenshots there.

---

## 🔡 Fonts and Icons (optional)

- Fonts: `fonts/*.ttf` or `.otf`
- Icons: `images/icons/*.svg/.png`

---
