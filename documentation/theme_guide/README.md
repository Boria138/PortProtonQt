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
    # Animation type when transitioning to a detailed page
    # Available values: "fade", "slide_left", "slide_right", "slide_up", "slide_down", "bounce"
    "detail_page_animation_type": "fade",

    # Border width settings (in pixels)
    "default_border_width": 2,
    "hover_border_width": 8,
    "focus_border_width": 12,
    "pulse_min_border_width": 8,
    "pulse_max_border_width": 10,

    # Animation duration (in milliseconds)
    "thickness_anim_duration": 300,
    "pulse_anim_duration": 800,
    "gradient_anim_duration": 3000,

    # Gradient animation angles (in degrees)
    "gradient_start_angle": 360,
    "gradient_end_angle": 0,

    # Smoothing curves for smooth animations
    "thickness_easing_curve": "OutBack",
    "thickness_easing_curve_out": "InBack",

    # Gradient colors for animated stroke
    "gradient_colors": [
        {"position": 0, "color": "#00fff5"},
        {"position": 0.33, "color": "#FF5733"},
        {"position": 0.66, "color": "#9B59B6"},
        {"position": 1, "color": "#00fff5"}
    ],

    # Duration of transitions to the detailed page
    "detail_page_fade_duration": 350,
    "detail_page_slide_duration": 500,
    "detail_page_zoom_duration": 400
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
