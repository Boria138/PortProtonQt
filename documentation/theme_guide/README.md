  Эта документация также доступна на [русском](README.ru.md)

---

## Contents
- [Overview](#overview)
- [Creating the Theme Folder](#creating-the-theme-folder)
- [Theme Variants](#theme-variants)
- [Style File](#style-file-stylespy)
- [Style Inheritance](#style-inheritance)
  - [How Inheritance Works](#how-inheritance-works)
  - [Overriding QSS Styles](#overriding-qss-styles)
- [Library Layout Mode](#library-layout-mode)
- [Detail Page Layout Mode](#detail-page-layout-mode)
- [Detail Page Background Mode](#detail-page-background-mode)
  - [Custom Gradient Stops](#custom-gradient-stops)
  - [Wave Configuration](#wave-configuration)
- [Preloader](#preloader)
- [Source Corner (Ribbon)](#source-corner-ribbon)
- [Terminal Color Schemes](#terminal-color-schemes)
- [Animation configuration](#animation-configuration)
- [Metadata](#metadata-metainfoini)
  - [Translation Support](#translation-support)
- [Screenshots](#screenshots)
- [Fonts and Icons](#fonts-and-icons-optional)
  - [Recoloring SVG Icons](#recoloring-svg-icons)
  - [AutoSizeButton State Recoloring](#autosizebutton-state-recoloring)
  - [Non-Inherited Icon Colors](#non-inherited-icon-colors)

---

## Overview

Themes in `PortProtonQT` allow customizing the UI appearance. Themes are stored under:

- `~/.local/share/PortProtonQT/themes`.

---

## Creating the Theme Folder

```bash
mkdir -p ~/.local/share/PortProtonQT/themes/my_custom_theme
```

---

## Theme Variants

The theme tab groups light and dark variants under one base theme name.

Define the related theme folders in each variant's `metainfo.ini`:

```ini
[Metainfo]
dark_variant = my_custom_theme
light_variant = my_custom_theme_light
```

The folder names can be any valid theme folder names.

If both configured folders exist, the application shows a separate variant selector with `Dark`, `Light`, and `Auto`. If only one folder exists, the variant selector is hidden and the existing theme is used directly.

`Auto` is the default variant. It follows the system color scheme using the desktop portal first, then `gsettings`, and Qt color scheme detection as a fallback.

Both variants are regular themes and must contain their own `styles.py`. Use `THEME_INHERITS` if one variant should reuse missing style values from another theme.

---

## Style File (`styles.py`)

Create a `styles.py` in the theme root. It should define variables or functions that return QSS (Qt Style Sheets). For better organization, you can split your theme into multiple submodules by creating a `styles/` subdirectory with separate Python files for different components, and import them in `styles.py`.

**Example of modular structure:**
```
my_custom_theme/
├── styles.py
├── metainfo.ini
├── fonts/
├── images/
└── styles/
    ├── __init__.py  # This empty file makes the directory a Python package
    ├── constants.py
    ├── base.py
    ├── game_card.py
    ├── detail_page.py
    ├── settings.py
    ├── winetricks.py
    ├── get_wine.py
    ├── file_explorer.py
    └── theme_utils.py
```

**Main styles.py file:**

You can use either absolute imports (recommended for built-in themes):
```python
# Import from the theme's submodules using absolute paths relative to the package
# Replace 'my_custom_theme' with your actual theme folder name and 'styles' with your subdirectory name
from portprotonqt.themes.my_custom_theme.styles.constants import *
from portprotonqt.themes.my_custom_theme.styles.base import *
from portprotonqt.themes.my_custom_theme.styles.game_card import *
from portprotonqt.themes.my_custom_theme.styles.detail_page import *
from portprotonqt.themes.my_custom_theme.styles.settings import *
from portprotonqt.themes.my_custom_theme.styles.winetricks import *
from portprotonqt.themes.my_custom_theme.styles.theme_utils import *
```

Or you can use relative imports (recommended for custom user themes):
```python
# Import from the theme's submodules using relative paths
from .styles.constants import *
from .styles.base import *
from .styles.game_card import *
from .styles.detail_page import *
from .styles.settings import *
from .styles.winetricks import *
from .styles.theme_utils import *
```

**Example submodule (styles/constants.py):**
```python
# Theme constants
font_family = "Play"
font_size_normal = "16px"
font_size_header = "24px"
border_radius_small = "10px"
color_accent = "#409EFF"
color_bg = "#282a33"
# ... other constants
```

---

## Style Inheritance

Themes can inherit missing style variables and functions from another theme by defining `THEME_INHERITS` in `styles.py`:

```python
THEME_INHERITS = "classic"
```

If `THEME_INHERITS` is not defined, the theme inherits styles from `standart`.

Fonts, icons, and images also follow the inheritance chain — the first match found walking from child to `standart` wins. If your theme has a `fonts/` directory, it takes priority over the parent's. If it doesn't, the parent's fonts are loaded. Screenshots are the exception — they are loaded only from the current theme, not inherited.

### How Inheritance Works

The inheritance system uses **AST-based constant injection**. When a child theme loads, the engine walks the full inheritance chain (child → parent → grandparent → … → `standart`) and collects all constant assignments from each theme's `styles/constants.py` (or `styles.py` if no `styles/` directory exists).

Constants are collected in order from root to child. **Child theme constants override parent constants.** This means you can change any color, size, or layout value by simply redefining it in your theme — you do not need to copy entire QSS strings.

For parent themes with a `styles/` directory (like `standart`), the QSS styles are **regenerated** with your child constants. Each style file (e.g., `base.py`, `game_card.py`) is re-evaluated with `{**parent_constants, **child_constants}`, so all f-string QSS values reflect your overrides.

For parent themes with only a monolithic `styles.py`, assignments overridden by the child are stripped before re-execution, and the remaining code runs with your constants.

**Example — overriding colors and borders in a child theme:**
```python
# my_child_theme/styles.py
THEME_INHERITS = "standart"

# Override accent color — all QSS using color_accent will use this value
color_accent = "#3daee9"
color_bg = "#2c3746"
color_surface = "#323e4f"
color_text = "#fdfdfd"
```

**Example — overriding font and borders:**
```python
# my_child_theme/styles.py
THEME_INHERITS = "standart"

font_family = "Adwaita Sans"
border_radius_small = "12px"
border_radius_large = "18px"
border_radius_card = "12px"
border_radius_header = "24px"
border_radius_badge = "6px"
```

**Example — light theme variant:**
```python
# my_child_theme_light/styles.py
THEME_INHERITS = "standart-light"

color_accent = "#6c782e"
color_bg = "#fbf1c7"
color_surface = "#f4e8be"
color_text = "#3c3836"
```

**Inheritance chain examples:**
```
standart  (root, no parent)
  ├── standart-light  (defaults to "standart")
  │     └── classic-light  (THEME_INHERITS = "standart-light")
  └── classic  (THEME_INHERITS = "standart")
```

Only the **immediate parent's** `styles/` directory generates QSS for your child theme. Grandparent styles are inherited via attribute lookup fallback, not regenerated.

### Overriding QSS Styles

You can also override entire QSS style strings in your theme. This is useful when you need complete control over a widget's appearance:

```python
# my_child_theme/styles.py
THEME_INHERITS = "standart"

LIBRARY_WIDGET_STYLE = f"""
    QWidget {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {color_library_gradient_start},
            stop:1 {color_library_gradient_end});
        border-radius: 0px;
    }}
"""

NAV_BUTTON_STYLE = f"""
    NavLabel {{
        background: {color_transparent};
        border-radius: 0px;
        border-bottom: {border_thin} {color_accent};
    }}
"""
```

---

## Library Layout Mode

You can control the game library card layout directly from the theme via `styles.py`:

```python
# "grid" (default) or "list"
LIBRARY_LAYOUT_MODE = "grid"
```

- `grid`: multi-column card grid (classic behavior).
- `list`: horizontal row-style cards (launcher-style list).

This is a theme-level option and does not depend on app settings.

---

## Detail Page Layout Mode

You can control the detail page layout from the theme via `styles.py`:

```python
# "full" (default) or "compact"
DETAIL_PAGE_LAYOUT_MODE = "full"
```

- `full`: full cover size, description, badges, controller support, and HowLongToBeat data.
- `compact`: smaller cover and simplified detail content.

Economy mode also forces the compact detail page layout.

---

## Detail Page Background Mode

You can control the detail page background style from the theme via `styles.py`:

```python
# "gradient" (default), "static_waves", or "waves"
DETAIL_PAGE_BG_MODE = "gradient"
```

- `gradient`: diagonal linear gradient extracted from the cover image palette (default).
- `static_waves`: gradient background with static (non-animated) wave shapes overlaid.
- `waves`: gradient background with animated wave shapes that drift over time.

### Custom Gradient Stops

By default, the detail page gradient is generated from the cover image palette with evenly distributed positions. Define `DETAIL_PAGE_GRADIENT` in `styles.py` to override positions, colors, or both:

```python
# Custom positions — palette colors redistributed to these positions
DETAIL_PAGE_GRADIENT = [0, 0.3, 0.7, 1]

# Custom colors — position and color for each stop
DETAIL_PAGE_GRADIENT = [
    {"position": 0, "color": "#101010"},
    {"position": 0.5, "color": "#202020"},
    {"position": 1, "color": "#303030"},
]

# Raw QSS stop string
DETAIL_PAGE_GRADIENT = "stop:0 #101010, stop:0.5 #202020, stop:1 #303030"
```

### Wave Configuration

When `DETAIL_PAGE_BG_MODE` is `"static_waves"` or `"waves"`, you can customize the wave appearance via the `DETAIL_PAGE_WAVES` dictionary:

```python
DETAIL_PAGE_WAVES = {
    "layer_count": 4,              # Number of wave layers
    "wave_amplitude_ratio": 0.06,  # Wave height as ratio of page height
    "wave_frequency": 2.0,         # Number of wave cycles across the page
    "layer_spacing_ratio": 0.04,   # Vertical spacing between layers as ratio of page height
    "base_opacity": 0.45,          # Opacity of the first wave layer (0.0–1.0)
    "opacity_decay": 0.85,         # Opacity multiplier for each subsequent layer
    "animation_speed": 0.03,       # Phase increment per tick — "waves" mode only (higher = faster)
    "animation_interval_ms": 30,   # Timer interval in ms — "waves" mode only (lower = smoother)
}
```

Wave colors are derived from the darkened cover image palette. Each layer uses a different palette color with decreasing opacity. The `animation_speed` and `animation_interval_ms` parameters only affect the `"waves"` mode.

---

The `PRELOADER` dictionary controls the loading indicator style and animation. If not defined, the default spinner is used.

```python
PRELOADER = {
    # Style: "default" (spinning arc), "bat" (flying bat), "pulse" (expanding rings),
    #        "dots" (orbiting dots), "wave" (sine wave)
    "style": "bat",

    # --- Bat style options ---
    "bat_size": 80,           # Size of the bat in pixels
    "bat_flap_speed": 3.0,    # Wing flap speed
    "bat_alpha": 220,         # Opacity (0-255)
    "bat_color": color_accent,

    # --- Pulse style options ---
    "pulse_count": 3,         # Number of expanding rings
    "pulse_max_radius": 40,   # Maximum ring radius
    "pulse_speed": 2.0,       # Expansion speed
    "pulse_color": color_accent,

    # --- Dots style options ---
    "dots_count": 8,          # Number of orbiting dots
    "dots_radius": 38,        # Orbit radius
    "dots_dot_size": 5,       # Dot size
    "dots_speed": 3.0,        # Orbit speed
    "dots_color": color_accent,

    # --- Wave style options ---
    "wave_width": 80,         # Wave width in pixels
    "wave_amplitude": 15,     # Wave height
    "wave_speed": 3.0,        # Wave animation speed
    "wave_line_width": 3,     # Line thickness
    "wave_color": color_accent,
}
```

---

## Source Corner (Ribbon)

The `SOURCE_CORNER` dictionary controls the ribbon/corner badge that indicates the game source (Steam, EGS, etc.) on game cards.

```python
SOURCE_CORNER = {
    "ribbon_color": color_surface,         # Main ribbon background
    "ribbon_fold_color": "#00000096",      # Shadow of the folded corner
    "size_ratio": 0.28,                    # Ribbon size as ratio of card width
    "min_size": 54,                        # Minimum ribbon size in pixels
    "min_widget_size": 4,                  # Minimum widget size for ribbon to show
    "peel_start_ratio": 0.32,             # Peel effect start position
    "peel_mid_ratio": 0.58,               # Peel midpoint
    "peel_end_ratio": 0.82,               # Peel end position
    "peel_shadow_width": 3,               # Peel shadow thickness
    "fold_start_ratio": 0.60,             # Fold crease start
    "fold_end_ratio": 0.92,               # Fold crease end
    "icon_center_ratio": 0.84,            # Icon center position
    "icon_size_ratio": 0.25,              # Icon size relative to ribbon
    "min_icon_size": 8,                   # Minimum icon size
    "gradient_start": 0.0,                # Gradient start position
    "gradient_end": 1.0,                  # Gradient end position
    "gradient_lighter": 145,              # Lighter gradient stop (brightness)
    "gradient_darker": 112,               # Darker gradient stop (brightness)
    "fold_darker": 132,                   # Fold area brightness
}
```

---

## Terminal Color Schemes

Terminal color schemes are separate Kitty-style `.conf` files. Built-in schemes are stored in `portprotonqt/terminal_schemes/`. User schemes can be placed in:

```text
~/.local/share/PortProtonQt/terminal_schemes/
```

The filename without `.conf` is used as the scheme name. The terminal menu lists all available `.conf` files from the user directory and the built-in directory.

Example:

```conf
foreground #d4d4d4
background #1e1e1e
cursor #bbbbbb
selection_foreground #ffffff
selection_background #264f78
background_opacity 1.0
cursor_shape block
enable_audio_bell no

color0 #000000
color1 #cd3131
color2 #0dbc79
color3 #e5e510
color4 #2472c8
color5 #bc3fbc
color6 #11a8cd
color7 #e5e5e5

font_size 14
font_family Monospace
```

Supported terminal-specific options:

- `foreground`, `background`: default text and background colors.
- `selection_foreground`, `selection_background`: selected text colors.
- `cursor` or `cursor_color`: cursor color.
- `cursor_shape`: `block`, `beam`, or `underline`.
- `enable_audio_bell`: `yes`/`no`, `true`/`false`, `on`/`off`, or `1`/`0`.
- `background_opacity`: background opacity from `0.0` to `1.0`.
- `font_size`, `font_family`: terminal font settings.
- `color0` through `color255`: ANSI palette entries.

If `cursor_shape` is omitted, the terminal uses `beam`. If `enable_audio_bell` is omitted, audio bell is disabled.

---

## Animation configuration

The `GAME_CARD_ANIMATION` dictionary controls all animation parameters for game cards:

```python
GAME_CARD_ANIMATION = {
    # Type of animation when entering or exiting the detail page
    # Possible values: "fade", "slide_left", "slide_right", "slide_up", "slide_down", "bounce"
    # Determines how the detail page appears and disappears
    "detail_page_animation_type": "fade",

    # Border width of the card in idle state (no hover or focus)
    # Affects the thickness of the border around the card when it's not selected
    # Value in pixels
    "default_border_width": 2,

    # Border width on hover
    # Increases the border thickness when the cursor is over the card
    # Value in pixels
    "hover_border_width": 8,

    # Border width on focus (e.g., when selected via keyboard)
    # Increases the border thickness when the card is focused
    # Value in pixels
    "focus_border_width": 12,

    # Minimum border width during pulsing animation
    # Determines the minimum border thickness during the "breathing" animation
    # Value in pixels
    "pulse_min_border_width": 8,

    # Maximum border width during pulsing animation
    # Determines the maximum border thickness during pulsing
    # Value in pixels
    "pulse_max_border_width": 10,

    # Duration of the border thickness animation (e.g., on hover or focus)
    # Affects the speed of transition from one border width to another
    # Value in milliseconds
    "thickness_anim_duration": 300,

    # Duration of one pulsing animation cycle
    # Determines how fast the border "pulses" between min and max values
    # Value in milliseconds
    "pulse_anim_duration": 800,

    # Duration of the gradient rotation animation
    # Affects how fast the gradient border rotates around the card
    # Value in milliseconds
    "gradient_anim_duration": 3000,

    # Starting angle of the gradient (in degrees)
    # Determines the initial rotation point of the gradient at animation start
    "gradient_start_angle": 360,

    # Ending angle of the gradient (in degrees)
    # Determines the final rotation point of the gradient
    # Value 0 means a full 360° rotation
    "gradient_end_angle": 0,

    # Type of card animation on hover or focus
    # Possible values: "gradient", "scale", "fill", "stripe", "glow", "scale_fill"
    # "gradient" enables a rotating gradient border, "scale" enlarges the card,
    # "fill" applies a static overlay, "stripe" applies a static border color,
    # "glow" adds pulsing border glow, "scale_fill" combines scaling + fill
    "card_animation_type": "gradient",

    # Overlay color for "fill" animation type
    # Any valid Qt color string (hex/rgb/rgba)
    "fill_color": color_accent,

    # Overlay opacity for "fill" animation type (0-255)
    "fill_alpha": 90,

    # Border color for "stripe" animation type
    # Any valid Qt color string (hex/rgb/rgba)
    "stripe_color": color_accent,

    # Border opacity for "stripe" animation type (0-255)
    "stripe_alpha": 255,

    # Base opacity for "glow" animation type (0-255)
    "glow_base_alpha": 120,

    # Extra pulse opacity for "glow" animation type (0-255)
    "glow_pulse_alpha": 80,

    # Card scale in idle state
    # Determines the base size of the card (1.0 = 100% of original size)
    # Value as a fraction (e.g., 1.0 for normal size)
    "default_scale": 1.0,

    # Card scale on hover
    # Increases the card size on hover
    # Value as a fraction (e.g., 1.1 = 110% of original size)
    "hover_scale": 1.1,

    # Card scale on focus (e.g., when selected via keyboard)
    # Increases the card size on focus
    # Value as a fraction (e.g., 1.05 = 105% of original size)
    "focus_scale": 1.05,

    # Duration of scale animation
    # Affects how fast the card changes size on hover or focus
    # Value in milliseconds
    "scale_anim_duration": 200,

    # Easing curve type for border thickness increase animation (on hover/focus)
    # Affects the "feel" of the animation (e.g., smooth acceleration or deceleration)
    # Possible values: strings corresponding to QEasingCurve.Type (e.g., "OutBack", "InOutQuad")
    "thickness_easing_curve": "OutBack",

    # Easing curve type for border thickness decrease animation (on hover/focus exit)
    # Affects the "feel" of returning to the default border width
    "thickness_easing_curve_out": "InBack",

    # Easing curve type for scale increase animation (on hover/focus)
    # Affects the "feel" of the scaling animation (e.g., with a "bounce" effect)
    # Possible values: strings corresponding to QEasingCurve.Type
    "scale_easing_curve": "OutBack",

    # Easing curve type for scale decrease animation (on hover/focus exit)
    # Affects the "feel" of returning to the original scale
    "scale_easing_curve_out": "InBack",

    # Gradient colors for animated border
    # List of dictionaries, each specifying position (0.0–1.0) and color in hex format
    # Affects the appearance of the border on hover or focus if card_animation_type="gradient"
    "gradient_colors": [
        {"position": 0, "color": "#00fff5"},    # Starting color (cyan)
        {"position": 0.33, "color": "#FF5733"}, # Color at 33% (orange)
        {"position": 0.66, "color": "#9B59B6"}, # Color at 66% (purple)
        {"position": 1, "color": "#00fff5"}     # Ending color (back to cyan)
    ],

    # Duration of fade animation when entering the detail page
    # Affects the speed of page appearance with fade animation
    # Value in milliseconds
    "detail_page_fade_duration": 350,

    # Duration of slide animation when entering the detail page
    # Affects the speed of page sliding animation
    # Value in milliseconds
    "detail_page_slide_duration": 500,

    # Duration of bounce animation when entering the detail page
    # Affects the speed of page "bounce" animation
    # Value in milliseconds
    "detail_page_bounce_duration": 400,

    # Duration of fade animation when exiting the detail page
    # Affects the speed of page disappearance with fade animation
    # Value in milliseconds
    "detail_page_fade_duration_exit": 350,

    # Duration of slide animation when exiting the detail page
    # Affects the speed of page sliding animation
    # Value in milliseconds
    "detail_page_slide_duration_exit": 500,

    # Duration of bounce animation when exiting the detail page
    # Affects the speed of page "compression" animation
    # Value in milliseconds
    "detail_page_bounce_duration_exit": 400,

    # Easing curve type for animations when entering the detail page
    # Applied to slide and bounce animations; affects the "feel" of movement
    # Possible values: strings corresponding to QEasingCurve.Type
    "detail_page_easing_curve": "OutCubic",

    # Easing curve type for animations when exiting the detail page
    # Applied to slide and bounce animations; affects the "feel" of movement
    # Possible values: strings corresponding to QEasingCurve.Type
    "detail_page_easing_curve_exit": "InCubic"
}
```

Virtual keyboard animation options are configured with theme-level constants:

```python
virtual_keyboard_animation_type = "slide"  # "slide", "fade", "slide_fade", "slide_bounce"
virtual_keyboard_slide_animation_duration = 160
virtual_keyboard_fade_animation_duration = 140
virtual_keyboard_slide_fade_animation_duration = 180
virtual_keyboard_slide_bounce_animation_duration = 220
```

---

## Metadata (`metainfo.ini`)

```ini
[Metainfo]
dark_variant = my_custom_theme
light_variant = my_custom_theme_light
name_en = My Custom Theme
name_ru = Моя пользовательская тема
author = Your Name
author_link = https://example.com
description_en = Description of your theme.
description_ru = Описание вашей темы.
```

### Translation Support

You must provide translations for your theme's name and description by adding language-specific fields:
- `name_en`, `name_ru`, etc. for theme names
- `description_en`, `description_ru`, etc. for theme descriptions

The application will automatically select the appropriate translation based on the user's system language, falling back to English if translations are not available for the user's language.

`dark_variant` and `light_variant` are required when the theme has both variants. Add them to both variant folders so either selected folder can resolve back to the same variant pair.

---

## Screenshots

Folder: `images/screenshots/` — place UI screenshots there.
Screenshot files can have any convenient names.

---

## Fonts and Icons (optional)

- Fonts: `fonts/*.ttf` or `.otf`
- Icons and Images: `images/` directory for all visual assets. Supported formats: `.svg`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.jxl`.
  - `images/icons/` - Main application icons (organized in subdirectories like actions/, navigation/, platforms/, etc.)
  - `images/icons/buttons/` - Button icons for UI elements
  - `images/icons/keyboards/` - Keyboard key icons (key_+, key_enter, etc.)
  - `images/icons/controllers/` - Controller button icons
  - `images/icons/controllers/xbox/` - Xbox controller button icons (xbox_a, xbox_b, etc.)
  - `images/icons/controllers/playstation/` - PlayStation controller button icons (ps_circle, ps_cross, etc.)
  - `images/ui_elements/` - UI elements (placeholder images, etc.)
  - `images/screenshots/` - Theme preview screenshots

Icons and images can be referenced by name without specifying the subdirectory, as the system will search through all subdirectories automatically. Theme creators can organize images in any logical subdirectory structure.

### Recoloring SVG Icons

SVG icons can be recolored from theme constants without editing the SVG files. Define `ICON_COLORS` as a dictionary where the key is the icon file name without extension and the value is the target color:

```python
ICON_COLORS = {
    "tray_portproton": color_accent,
}
```

Only icons listed in `ICON_COLORS` are recolored. Icons without an entry keep their original file unchanged. The source SVG is never modified; PortProtonQt writes a recolored copy to the icon cache and uses that path.

The recoloring helper handles common SVG paint declarations: `fill`, `stroke`, `color`, `stop-color`, `flood-color`, `lighting-color`, inline `style` attributes, and CSS inside `<style>` blocks. It preserves non-color paint values such as `none`, `transparent`, `url(#...)`, `context-fill`, and `context-stroke`.

### AutoSizeButton State Recoloring

`AutoSizeButton` icons and text can be recolored automatically for button states. State-specific keys have priority over base icon keys. The lookup order is:

1. `{icon_name}_{state}`
2. `*_{state}`
3. `{icon_name}`

Supported states are `hover`, `pressed`, `focused`, and `disabled`. Use state wildcard keys to apply one color to all button icons in that state:

```python
ICON_COLORS = {
    "settings_hover": color_accent,
    "*_hover": color_text,
    "*_pressed": color_text,
    "*_focused": color_text,
    "*_disabled": color_text,
}
```

When no `ICON_COLORS` entry matches an `AutoSizeButton` state, the button falls back to theme colors: `color_disabled` for disabled, `color_accent_dark` or `color_accent` for pressed, and `color_accent` for hover/focus.

### Non-Inherited Icon Colors

`ICON_COLORS` is not inherited from parent themes. If a child theme needs SVG recoloring, define its own `ICON_COLORS` dictionary in that theme.

---
