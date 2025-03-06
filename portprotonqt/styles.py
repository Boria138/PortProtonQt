MAIN_WINDOW_HEADER_STYLE = """
    QFrame {
        background: rgba(0, 0, 0, 0.6);
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }
"""

TITLE_LABEL_STYLE = """
    font-family: 'RASKHAL';
    font-size: 32px;
    color: #00fff5;
    text-shadow: 0 0 5px #00fff5, 0 0 7px #9B59B6;
"""

VIRTUAL_KEYBOARD_KEYS_STYLE = """
    QPushButton {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 10px;
        color: white;
        font-size: 16px;
        padding: 10px 20px;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
"""

NAV_WIDGET_STYLE = """
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 10px;
"""

NAV_BUTTON_STYLE = """
    QPushButton {
        background: transparent;
        padding: 12px 20px;
        color: #fff;
        font-family: 'Poppins';
        text-transform: uppercase;
        border: none;
    }
    QPushButton:checked {
        background: linear-gradient(45deg, rgba(0,255,255,0.15), rgba(155,89,182,0.25));
        color: #00fff5;
        font-weight: bold;
        border-radius: 5px;
    }
    QPushButton:hover {
        color: #00fff5;
    }
"""

MAIN_WINDOW_STYLE = """
    QMainWindow {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                     stop:0 #1a1a1a, stop:1 #333333);
    }
    QLabel {
        color: #ffffff;
    }
"""

SEARCH_EDIT_STYLE = """
    QLineEdit {
        background-color: #222;
        border: 2px solid #444;
        border-radius: 15px;
        padding-left: 35px;
        padding-right: 10px;
        font-family: 'Poppins';
        font-size: 16px;
        color: white;
    }
    QLineEdit:focus {
        border: 2px solid #00fff5;
    }
"""

SCROLL_AREA_STYLE="border: none;"

LIST_WIDGET_STYLE= """
    background-color: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 15px;
"""

INSTALLED_TAB_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 28px; color: #f5f5f5;"

ADD_GAME_BUTTON_STYLE = """
    QPushButton {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 10px;
        color: white;
        font-size: 16px;
        padding: 10px 20px;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
"""

TAB_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 24px; color: #f5f5f5;"
CONTENT_STYLE = "font-family: 'Poppins'; font-size: 16px;"

DETAIL_PAGE_NO_COVER_STYLE = "background: #1a1a1a;"

BACK_BUTTON_STYLE = """
    QPushButton {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 5px;
        color: white;
        font-size: 16px;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
"""

DETAIL_CONTENT_FRAME_STYLE = """
    QFrame {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
    }
"""

COVER_FRAME_STYLE = """
    QFrame {
        background: #222222;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.1);
    }
"""

COVER_LABEL_STYLE = "border-radius: 15px;"

DETAILS_WIDGET_STYLE = "background: rgba(255,255,255,0.05); border-radius: 10px;"

DETAIL_PAGE_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 32px; color: #00fff5;"
DETAIL_PAGE_LINE_STYLE = "color: rgba(255,255,255,0.2);"
DETAIL_PAGE_DESC_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #ffffff;"
STEAM_APPID_LABEL_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #ffffff;"

PLAY_BUTTON_STYLE = """
    QPushButton {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 5px;
        font-size: 16px;
        color: white;
        font-weight: bold;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
"""

DIALOG_BROWSE_BUTTON_STYLE = """
    QPushButton {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 10px;
        color: white;
        font-size: 16px;
        padding: 5px 10px;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
"""

GAME_CARD_WINDOW_STYLE = """
    QFrame {
        border-radius: 15px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #141414, stop:1 #2a2a2a);
    }
"""

GAME_CARD_NAME_LABEL_STYLE= """
    color: white;
    font-family: 'Orbitron';
    font-size: 18px;
    font-weight: bold;
    background-color: #111;
    border-bottom-left-radius: 15px;
    border-bottom-right-radius: 15px;
    padding: 14px;
"""

# Функция для динамической генерации стиля страницы деталей с градиентным фоном
def detail_page_style(stops):
    return f"""
    QWidget {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    {stops});
    }}
"""
