📘  Эта документация также доступна на [русском](README.ru.md)

---

## 📋 Contents
- [Overview](#overview)
- [Creating the Theme Folder](#creating-the-theme-folder)
- [Style File](#style-file)
- [Metadata](#metadata)
- [Screenshots](#screenshots)
- [Fonts and Icons](#fonts-and-icons)

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
