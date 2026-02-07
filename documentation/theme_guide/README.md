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

Create a `styles.py` in the theme root. It should define variables or functions that return QSS (Qt Style Sheets). For better organization, you can split your theme into multiple submodules by creating a subdirectory (e.g., `styles`, `components`, etc.) with separate Python files for different components, and import them in `styles.py`.

**Example of modular structure:**
```
my_custom_theme/
├── styles.py
├── metainfo.ini
├── fonts/
├── images/
└── styles/  # This can be named anything (e.g., components, modules, etc.)
    ├── __init__.py  # This empty file makes the directory a Python package
    ├── constants.py
    ├── base.py
    ├── game_card.py
    ├── detail_page.py
    ├── settings.py
    ├── winetricks.py
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
font_size_a = "16px"
font_size_b = "24px"
border_radius_a = "10px"
color_a = "#409EFF"
color_b = "#282a33"
# ... other constants
```

---

## 🎥 Animation configuration

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
    # Possible values: "gradient", "scale"
    # "gradient" enables a rotating gradient for the border, "scale" enlarges the card
    "card_animation_type": "gradient",

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

---

## 📝 Metadata (`metainfo.ini`)

```ini
[Metainfo]
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

---

## 🖼 Screenshots

Folder: `images/screenshots/` — place UI screenshots there.

### Screenshot Translation Support

You can provide translations for screenshot captions by adding entries to the `[Screenshots]` section in your `metainfo.ini` file:

```ini
[Screenshots]
auto_installs_en = Auto-installs
auto_installs_ru = Автоустановки
library_en = Library
library_ru = Библиотека
game_card_en = Game Card
game_card_ru = Карточка
context_menu_en = Context Menu
context_menu_ru = Контекстное меню
portproton_settings_en = PortProton Settings
portproton_settings_ru = Настройки PortProton
wine_settings_en = Wine Settings
wine_settings_ru = Настройки Wine
themes_en = Themes
themes_ru = Темы
```

Screenshot files should be named in English (without spaces), and the application will display the appropriate translated caption based on the user's system language, falling back to English if translations are not available.

---

## 🔡 Fonts and Icons (optional)

- Fonts: `fonts/*.ttf` or `.otf`
- Icons and Images: `images/` directory for all visual assets:
  - `images/icons/` - Main application icons (organized in subdirectories like actions/, navigation/, platforms/, etc.)
  - `images/icons/buttons/` - Button icons for UI elements
  - `images/icons/keyboards/` - Keyboard key icons (key_+, key_enter, etc.)
  - `images/icons/controllers/` - Controller button icons
  - `images/icons/controllers/xbox/` - Xbox controller button icons (xbox_a, xbox_b, etc.)
  - `images/icons/controllers/playstation/` - PlayStation controller button icons (ps_circle, ps_cross, etc.)
  - `images/ui_elements/` - UI elements (placeholder images, etc.)
  - `images/screenshots/` - Theme preview screenshots
  
Icons and images can be referenced by name without specifying the subdirectory, as the system will search through all subdirectories automatically. Theme creators can organize images in any logical subdirectory structure.

---
