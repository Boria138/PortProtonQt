# Улучшенный тёмный стиль glassmorphism, вдохновлённый Apple Vision Pro – доработанный вариант

# СТИЛЬ ШАПКИ ГЛАВНОГО ОКНА
MAIN_WINDOW_HEADER_STYLE = """
    QFrame {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(20, 20, 20, 0.50),
            stop:1 rgba(30, 30, 30, 0.45));
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-bottom: 1px solid rgba(255, 255, 255, 0.20);
        border-top-left-radius: 20px;
        border-top-right-radius: 20px;
        box-shadow: 0 12px 48px rgba(0, 0, 0, 0.5);
    }
"""

# СТИЛЬ ЗАГОЛОВКА (ЛОГО) В ШАПКЕ
TITLE_LABEL_STYLE = """
    QLabel {
        font-family: 'RASKHAL';
        font-size: 36px;
        color: #007AFF;
        text-shadow: 0 0 15px rgba(0,122,255,0.8);
    }
"""

# СТИЛЬ ОБЛАСТИ НАВИГАЦИИ (КНОПКИ ВКЛАДОК)
NAV_WIDGET_STYLE = """
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(20, 20, 20, 0.50),
            stop:1 rgba(30, 30, 30, 0.45));
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 15px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45);
    }
"""

# СТИЛЬ КНОПОК ВКЛАДОК НАВИГАЦИИ
NAV_BUTTON_STYLE = """
    QPushButton {
        background: transparent;
        padding: 14px 24px;
        color: #ffffff;
        font-family: 'Poppins';
        text-transform: uppercase;
        border: none;
    }
    QPushButton:checked {
        background: rgba(0,122,255,0.25);
        color: #007AFF;
        font-weight: bold;
        border-radius: 5px;
    }
    QPushButton:hover {
        color: #007AFF;
    }
"""

# ГЛОБАЛЬНЫЙ СТИЛЬ ДЛЯ ОКНА (ФОН) И QLabel
MAIN_WINDOW_STYLE = """
    QMainWindow {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #141414,
            stop:1 #1f1f1f);
    }
    QLabel {
        color: #ffffff;
    }
"""

# СТИЛЬ ПОЛЯ ПОИСКА
SEARCH_EDIT_STYLE = """
    QLineEdit {
        background-color: rgba(30, 30, 30, 0.70);
        border: 1px solid rgba(255, 255, 255, 0.35);
        border-radius: 20px;
        padding-left: 35px;
        padding-right: 10px;
        font-family: 'Poppins';
        font-size: 16px;
        color: #ffffff;
    }
    QLineEdit:focus {
        border: 1px solid #007AFF;
    }
"""

# ОТКЛЮЧАЕМ РАМКУ У QScrollArea
SCROLL_AREA_STYLE = "border: none;"

# СТИЛЬ ОБЛАСТИ ДЛЯ КАРТОЧЕК ИГР (QWidget)
LIST_WIDGET_STYLE = """
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(20, 20, 20, 0.50),
            stop:1 rgba(20, 20, 20, 0.40));
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 15px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45);
    }
"""

# ЗАГОЛОВОК "БИБЛИОТЕКА" НА ВКЛАДКЕ
INSTALLED_TAB_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 28px; color: #007AFF;"

# СТИЛЬ КНОПКИ "ДОБАВИТЬ ИГРУ"
ADD_GAME_BUTTON_STYLE = """
    QPushButton {
        background: rgba(20, 20, 20, 0.50);
        border: 1px solid rgba(255, 255, 255, 0.30);
        border-radius: 10px;
        color: #ffffff;
        font-size: 16px;
        padding: 12px 24px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45);
    }
    QPushButton:hover {
        background: rgba(20, 20, 20, 0.60);
    }
    QPushButton:pressed {
        background: rgba(20, 20, 20, 0.70);
        border: 1px solid rgba(255, 255, 255, 0.35);
    }
"""

# ТЕКСТОВЫЕ СТИЛИ: ЗАГОЛОВКИ И ОСНОВНОЙ КОНТЕНТ
TAB_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 24px; color: #ffffff;"
CONTENT_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #ffffff;"

# ФОН ДЛЯ ДЕТАЛЬНОЙ СТРАНИЦЫ, ЕСЛИ ОБЛОЖКА НЕ ЗАГРУЖЕНА
DETAIL_PAGE_NO_COVER_STYLE = "background: rgba(20,20,20,0.95);"

# СТИЛЬ КНОПКИ "НАЗАД" НА ДЕТАЛЬНОЙ СТРАНИЦЕ
BACK_BUTTON_STYLE = """
    QPushButton {
        background: rgba(20, 20, 20, 0.50);
        border: 1px solid rgba(255, 255, 255, 0.30);
        border-radius: 8px;
        color: #ffffff;
        font-size: 16px;
        padding: 8px 16px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45);
    }
    QPushButton:hover {
        background: rgba(20, 20, 20, 0.60);
    }
    QPushButton:pressed {
        background: rgba(20, 20, 20, 0.70);
        border: 1px solid rgba(255, 255, 255, 0.35);
    }
"""

# ОСНОВНОЙ ФРЕЙМ ДЕТАЛЕЙ ИГРЫ
DETAIL_CONTENT_FRAME_STYLE = """
    QFrame {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(20, 20, 20, 0.50),
            stop:1 rgba(20, 20, 20, 0.45));
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 10px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45);
    }
"""

# ФРЕЙМ ПОД ОБЛОЖКОЙ
COVER_FRAME_STYLE = """
    QFrame {
        background: rgba(30, 30, 30, 0.85);
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.18);
    }
"""

# СКРУГЛЕНИЕ LABEL ПОД ОБЛОЖКУ
COVER_LABEL_STYLE = "border-radius: 15px;"

# ВИДЖЕТ ДЕТАЛЕЙ (ТЕКСТ, ОПИСАНИЕ)
DETAILS_WIDGET_STYLE = "background: rgba(20,20,20,0.45); border-radius: 10px; padding: 10px;"

# НАЗВАНИЕ (ЗАГОЛОВОК) НА ДЕТАЛЬНОЙ СТРАНИЦЕ
DETAIL_PAGE_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 32px; color: #007AFF;"

# ЛИНИЯ-РАЗДЕЛИТЕЛЬ
DETAIL_PAGE_LINE_STYLE = "color: rgba(255,255,255,0.12); margin: 10px 0;"

# ТЕКСТ ОПИСАНИЯ
DETAIL_PAGE_DESC_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #ffffff; line-height: 1.5;"

# ЛЕЙБЛ "STEAM APPID"
STEAM_APPID_LABEL_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #ffffff;"

# СТИЛЬ КНОПКИ "ИГРАТЬ"
PLAY_BUTTON_STYLE = """
    QPushButton {
        background: rgba(20, 20, 20, 0.50);
        border: 1px solid rgba(255, 255, 255, 0.30);
        border-radius: 8px;
        font-size: 16px;
        color: #ffffff;
        font-weight: bold;
        padding: 8px 16px;
        min-width: 120px;
        min-height: 40px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45);
    }
    QPushButton:hover {
        background: rgba(20, 20, 20, 0.60);
    }
    QPushButton:pressed {
        background: rgba(20, 20, 20, 0.70);
        border: 1px solid rgba(255, 255, 255, 0.35);
    }
"""

# СТИЛЬ КНОПКИ "ОБЗОР..." В ДИАЛОГЕ "ДОБАВИТЬ ИГРУ"
DIALOG_BROWSE_BUTTON_STYLE = """
    QPushButton {
        background: rgba(20, 20, 20, 0.50);
        border: 1px solid rgba(255, 255, 255, 0.30);
        border-radius: 10px;
        color: #ffffff;
        font-size: 16px;
        padding: 5px 10px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45);
    }
    QPushButton:hover {
        background: rgba(20, 20, 20, 0.60);
    }
    QPushButton:pressed {
        background: rgba(20, 20, 20, 0.70);
        border: 1px solid rgba(255, 255, 255, 0.35);
    }
"""

# СТИЛЬ КАРТОЧКИ ИГРЫ (GAMECARD)
GAME_CARD_WINDOW_STYLE = """
    QFrame {
        border-radius: 15px;
        background: rgba(20, 20, 20, 0.55);
        border: 1px solid rgba(255, 255, 255, 0.30);
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45);
    }
"""

# НАЗВАНИЕ В КАРТОЧКЕ (QLabel)
GAME_CARD_NAME_LABEL_STYLE = """
    QLabel {
        color: #ffffff;
        font-family: 'Orbitron';
        font-size: 18px;
        font-weight: bold;
        background-color: rgba(20, 20, 20, 0.85);
        border-bottom-left-radius: 15px;
        border-bottom-right-radius: 15px;
        padding: 14px;
        qproperty-wordWrap: true;
    }
"""

# ДОПОЛНИТЕЛЬНЫЕ СТИЛИ ИНФОРМАЦИИ НА СТРАНИЦЕ ИГР
LAST_LAUNCH_TITLE_STYLE = "font-family: 'Poppins'; font-size: 11px; color: #bbbbbb; text-transform: uppercase; letter-spacing: 0.75px; margin-bottom: 2px;"
LAST_LAUNCH_VALUE_STYLE = "font-family: 'Poppins'; font-size: 13px; color: #ffffff; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE   = "font-family: 'Poppins'; font-size: 11px; color: #bbbbbb; text-transform: uppercase; letter-spacing: 0.75px; margin-bottom: 2px;"
PLAY_TIME_VALUE_STYLE   = "font-family: 'Poppins'; font-size: 13px; color: #ffffff; font-weight: 600; letter-spacing: 0.75px;"

def detail_page_style(stops):
    return f"""
    QWidget {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    {stops});
    }}
"""

if __name__ == "__main__":
    # Пример применения стилей в PyQt/PySide приложении
    print("Обновлённый стиль для интерфейса страницы игры успешно определён!")
