from .constants import *

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
"""

FILE_EXPLORER_PATH_LABEL_STYLE = f"""
    QLabel {{
        color: {color_a};
        font-size: {font_size_a};
        font-family: {font_family};
    }}
"""