from .constants import *

FILE_EXPLORER_STYLE = f"""
    QListView {{
        font-size: {font_size_normal};
        font-family: {font_family};
        background: {color_surface};
        alternate-background-color: {color_surface};
        color: {color_text};
        border-top-left-radius: 5px;
        border-bottom-left-radius: 5px;
    }}
    QListView::item {{
        padding: 8px;
        margin: 0px 5px;
    }}
    QListView::item:alternate {{
        margin: 0px 5px;
        background: {color_surface_elevated};
    }}
    QListView::item:selected {{
        background: {color_accent};
        color: {color_text};
        border-radius: {border_radius_small};
    }}
    QListView::item:hover {{
        background: {color_accent};
        color: {color_text};
        border-radius: {border_radius_small};
    }}
    QListView::item:focus {{
        background: {color_accent};
        color: {color_text};
        border-radius: {border_radius_small};
    }}
"""

FILE_EXPLORER_PATH_LABEL_STYLE = f"""
    QLabel {{
        color: {color_accent};
        font-size: {font_size_normal};
        font-family: {font_family};
    }}
"""
