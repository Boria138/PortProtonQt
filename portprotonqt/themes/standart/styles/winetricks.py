from .constants import *

WINETRICKS_TAB_STYLE = f"""
QTabWidget::pane {{
    border-top: 1px solid {color_c};
    background: {color_h};
}}
QTabBar::tab {{
    background: {color_c};
    color: {color_f};
    padding: 8px 16px;
    border-top-left-radius: {border_radius_a};
    border-top-right-radius: {border_radius_a};
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {color_a};
    color: {color_f};
}}
QTabBar::tab:hover {{
    background: {color_a};
}}
"""

WINETRICKS_TABBLE_STYLE = f"""
QComboBox {{
    background: {color_c};
    border: {border_c} {color_g};
    border-radius: {border_radius_a};
    padding-left: 12px;
    color: {color_f};
    font-family: '{font_family}';
    font-size: {font_size_a};
    min-width: 120px;
    combobox-popup: 0;
}}
QComboBox:on {{
    background: {color_b};
    border: {border_c} {color_a};
    border-bottom-style: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    border-bottom-left-radius: 0px;
    border-bottom-right-radius: 0px;
}}
QComboBox:hover {{
    border: {border_c} {color_a};
    background: {color_a};
}}
/* Состояние фокуса */
QComboBox:focus {{
    border: {border_c} {color_a};
    background-color: {color_a};
}}
QComboBox:disabled {{
    background: #2a2c35;
    border: {border_c} #2a2c35;
    color: #777a84;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    border-left: {border_b} rgba(255, 255, 255, 0.05);
    padding: 12px;
    height: 12px;
    width: 12px;
}}
QComboBox::down-arrow {{
    image: url({theme_manager.get_icon("down", current_theme_name, as_path=True)});
    padding: 12px;
    height: 12px;
    width: 12px;
}}
QComboBox::down-arrow:on {{
    image: url({theme_manager.get_icon("up", current_theme_name, as_path=True)});
    padding: 12px;
    height: 12px;
    width: 12px;
}}
/* Список при открытом комбобоксе */
QComboBox QAbstractItemView {{
    outline: none;
    background: {color_c};
    border: {border_c} {color_a};
    border-top-style: none;
    border-top-left-radius: 0px;
    border-top-right-radius: 0px;
    border-bottom-left-radius: 10px;
    border-bottom-right-radius: 10px;
}}
QListView {{
    background: {color_c};
}}
QListView::item {{
    padding: 7px 7px 7px 12px;
    margin: 3px;
    border-radius: {border_radius_a};
    color: {color_f};
}}
QListView::item:hover {{
    background: {color_b};
}}
QListView::item:selected {{
    background: {color_b};
}}
/* Выделение в списке при фокусе на элементе */
QListView::item:focus {{
    background: {color_a};
    color: {color_f};
}}
QLineEdit {{
    background: {color_c};
    border: {border_c} rgba(255, 255, 255, 0.01);
    border-radius: {border_radius_a};
    height: 34px;
    padding-left: 12px;
    color: {color_f};
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QLineEdit:hover {{
    background: {color_c};
    border: {border_c} {color_a};
}}
QLineEdit:focus {{
    border: {border_c} {color_a};
    background-color: {color_e};
}}
QTableWidget {{
    background: {color_h};
    color: {color_f};
    gridline-color: {color_h};
    alternate-background-color: {color_d};
    border: {border_a};
    border-radius: {border_radius_a};
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QHeaderView::section {{
    background: {color_d};
    color: {color_f};
    padding: 5px;
    border: {border_a};
    font-weight: bold;
}}
QTableWidget::item {{
    padding: 8px;
    border-bottom: {border_a } {color_c};
    height: 36px;
}}
QTableWidget::item:selected,
QTableWidget::item:focus,
QTableWidget::item:selected:focus {{
    background: {color_a};
    color: {color_f};
    selection-background-color: {color_a};
}}
QTableWidget::item:hover {{
    background: {color_h};
}}
QTableWidget::indicator {{
    width: 24px;
    height: 24px;
    border: {border_c} {color_h};
    border-radius: {border_radius_a};
    background: {color_b};
}}
QTableWidget::indicator:unchecked {{
    background: rgba(255, 255, 255, 0.1);
    image: none;
}}
QTableWidget::indicator:checked {{
    background: {color_b};
    image: url({theme_manager.get_icon("check", current_theme_name, as_path=True)});
    border: {border_c} {color_a};
}}
QTableWidget::indicator:hover {{
    background: rgba(255, 255, 255, 0.2);
    border: {border_c} {color_a};
}}
QTableWidget::indicator:focus {{
    background: rgba(255, 255, 255, 0.2);
    border: {border_c} {color_a};
}}
QScrollBar:vertical {{
    width: 10px;
    border:  {border_a};
    border-radius: 5px;
    background: rgba(20, 20, 20, 0.30);
}}
QScrollBar::handle:vertical {{
    background: #bebebe;
    border:  {border_a};
    border-radius: 5px;
}}
QScrollBar::add-line:vertical {{
    border:  {border_a};
    background: none;
}}
QScrollBar::sub-line:vertical {{
    border:  {border_a};
    background: none;
}}
QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
    border:  {border_a};
    width: 3px;
    height: 3px;
    background: none;
}}
QScrollBar:horizontal {{
    height: 10px;
    border:  {border_a};
    border-radius: 5px;
    background: rgba(20, 20, 20, 0.30);
}}
QScrollBar::handle:horizontal {{
    background: #bebebe;
    border:  {border_a};
    border-radius: 5px;
}}
QScrollBar::add-line:horizontal {{
    border:  {border_a};
    background: none;
}}
QScrollBar::sub-line:horizontal {{
    border:  {border_a};
    background: none;
}}
QScrollBar::up-arrow:horizontal, QScrollBar::down-arrow:horizontal {{
    border:  {border_a};
    width: 3px;
    height: 3px;
    background: none;
}}
"""

WINETRICKS_LOG_STYLE = f"""
QTextEdit {{
    background: {color_c};
    border: {border_a};
    border-radius: {border_radius_a};
    color: {color_f};
    font-family: '{font_family}';
    font-size: {font_size_a};
    padding: 5px;
}}
"""

FILE_EXPLORER_STYLE = f"""
    QListView {{
        font-size: {font_size_a};
        font-family: {font_family};
        background: {color_c};
        alternate-background-color: {color_c};
        color: {color_f};
        border-top-left-radius: 5px;
        border-bottom-left-radius: 5px;
    }}
    QListView::item {{
        padding: 8px;
        margin: 0px 5px;
    }}
    QListView::item:alternate {{
        margin: 0px 5px;
        background: {color_d};
    }}
    QListView::item:selected {{
        background: {color_a};
        color: {color_f};
        border-radius: {border_radius_a};
    }}
    QListView::item:hover {{
        background: {color_a};
        color: {color_f};
        border-radius: {border_radius_a};
    }}
    QListView::item:focus {{
        background: {color_a};
        color: {color_f};
        border-radius: {border_radius_a};
    }}
    QScrollBar:vertical {{
        width: 10px;
        border:  {border_a};
        border-radius: 5px;
        background: {color_c};
    }}
    QScrollBar::handle:vertical {{
        background: #bebebe;
        border:  {border_a};
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical {{
        border:  {border_a};
        background: {color_c};
        border-bottom-right-radius: 5px;
    }}
    QScrollBar::sub-line:vertical {{
        border:  {border_a};
        background: {color_c};
        border-top-right-radius: 5px;
    }}
    QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
        border:  {border_a};
        width: 3px;
        height: 3px;
        background: none;
    }}
"""

FILE_EXPLORER_PATH_LABEL_STYLE = f"""
    QLabel {{
        color: {color_a};
        font-size: {font_size_a};
        font-family: {font_family};
    }}
"""
