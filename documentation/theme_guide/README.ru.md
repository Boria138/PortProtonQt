📘 This documentation is also available in [English](README.md)

---

## 📋 Содержание
- [Обзор](#обзор)
- [Создание папки темы](#создание-папки-темы)
- [Файл стилей](#файл-стилей)
- [Конфигурация анимации](#конфигурация-анимации)
- [Метаинформация](#метаинформация)
- [Скриншоты](#скриншоты)
- [Шрифты и иконки](#шрифты-и-иконки)

---

## 📖 Обзор

Темы в `PortProtonQT` позволяют изменить внешний вид интерфейса. Все темы хранятся в папке:

- `~/.local/share/PortProtonQT/themes`.

---

## 📁 Создание папки темы

```bash
mkdir -p ~/.local/share/PortProtonQT/themes/my_custom_theme
```

---

## 🎨 Файл стилей (`styles.py`)

Создайте `styles.py` в корне темы. В нём определите переменные и/или функции, возвращающие CSS-оформление.

**Пример функции:**
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

## 🎥 Конфигурация анимации

Словарь `GAME_CARD_ANIMATION` управляет всеми параметрами анимации для карточек игр:

```python
GAME_CARD_ANIMATION = {
    # Тип анимации при переходе на детальную страницу
    # Доступные значения: "fade", "slide_left", "slide_right", "slide_up", "slide_down", "bounce", "none"
    "detail_page_animation_type": "fade",

    # Настройки ширины обводки (в пикселях)
    "default_border_width": 2,
    "hover_border_width": 8,
    "focus_border_width": 12,
    "pulse_min_border_width": 8,
    "pulse_max_border_width": 10,

    # Длительности анимаций (в миллисекундах)
    "thickness_anim_duration": 300,
    "pulse_anim_duration": 800,
    "gradient_anim_duration": 3000,

    # Углы анимации градиента (в градусах)
    "gradient_start_angle": 360,
    "gradient_end_angle": 0,

    # Кривые сглаживания для плавных анимаций
    "thickness_easing_curve": "OutBack",
    "thickness_easing_curve_out": "InBack",

    # Цвета градиента для анимированной обводки
    "gradient_colors": [
        {"position": 0, "color": "#00fff5"},
        {"position": 0.33, "color": "#FF5733"},
        {"position": 0.66, "color": "#9B59B6"},
        {"position": 1, "color": "#00fff5"}
    ],

    # Длительности переходов на детальную страницу
    "detail_page_fade_duration": 350,
    "detail_page_slide_duration": 500,
    "detail_page_zoom_duration": 400
}
```

---

## 📝 Метаинформация (`metainfo.ini`)

```ini
[Metainfo]
name = My Custom Theme
author = Ваше имя
author_link = https://example.com
description = Описание вашей темы.
```

---

## 🖼 Скриншоты

Папка: `images/screenshots/` — любые изображения оформления темы.

---

## 🔡 Шрифты и иконки (опционально)

- Шрифты: `fonts/*.ttf` или `.otf`
- Иконки: `images/icons/*.svg/.png`

---
