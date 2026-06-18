from .constants import *

# GAME CARD STYLE (GAMECARD)
GAME_CARD_WINDOW_STYLE = f"""
    QFrame {{
        border-radius: 20px;
        background: rgba(20, 20, 20, 0.40);
        border:  {border_a} {color_g};
    }}
"""

# GAME NAME LABEL IN CARD (QLabel)
GAME_CARD_NAME_LABEL_STYLE = f"""
    QLabel {{
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        background-color: {color_g};
        border-bottom-left-radius: 20px;
        border-bottom-right-radius: 20px;
        padding: 14px, 7px, 3px, 7px;
        qproperty-wordWrap: true;
    }}
"""

# PROTONDB BADGE STYLES ON CARD
def get_protondb_badge_style(tier):
    tier = tier.lower()
    tier_colors = {
        "platinum": {"background": "rgba(255,255,255,0.9)", "color": "black"},
        "gold": {"background": "rgba(253,185,49,0.7)", "color": "black"},
        "silver": {"background": "rgba(169,169,169,0.8)", "color": "black"},
        "bronze": {"background": "rgba(205,133,63,0.7)", "color": "black"},
        "borked": {"background": "rgba(255,0,0,0.7)", "color": "black"},
        "pending": {"background": "rgba(160,82,45,0.7)", "color": "black"}
    }
    colors = tier_colors.get(tier, {"background": "rgba(0, 0, 0, 0.5)", "color": "white"})
    return f"""
        qproperty-alignment: AlignCenter;
        background-color: {colors["background"]};
        color: {colors["color"]};
        border-radius: 5px;
        font-family: '{font_family}';
        font-weight: bold;
    """

# PPDB BADGE STYLES
def get_ppdb_badge_style(tier):
    tier = tier.lower()
    tier_colors = {
        "platinum": {"background": color_ppdb_platinum, "color": "black"},
        "gold": {"background": color_ppdb_gold, "color": "black"},
        "silver": {"background": color_ppdb_silver, "color": "black"},
        "bronze": {"background": color_ppdb_bronze, "color": "black"},
        "broken": {"background": color_ppdb_broken, "color": "black"}
    }
    colors = tier_colors.get(tier, {"background": "rgba(0, 0, 0, 0.5)", "color": "white"})
    return f"""
        qproperty-alignment: AlignCenter;
        background-color: {colors["background"]};
        color: {colors["color"]};
        border-radius: 5px;
        font-family: '{font_family}';
        font-weight: bold;
    """

# WEANTICHEATYET BADGE STYLES
def get_anticheat_badge_style(status):
    status = status.lower()
    status_colors = {
        "supported": {"background": "rgba(102, 168, 15, 0.7)", "color": "black"},
        "running": {"background": "rgba(25, 113, 194, 0.7)", "color": "black"},
        "planned": {"background": "rgba(156, 54, 181, 0.7)", "color": "black"},
        "broken": {"background": "rgba(232, 89, 12, 0.7)", "color": "black"},
        "denied": {"background": "rgba(224, 49, 49, 0.7)", "color": "black"}
    }
    colors = status_colors.get(status, {"background": "rgba(0, 0, 0, 0.5)", "color": "white"})
    return f"""
        qproperty-alignment: AlignCenter;
        background-color: {colors["background"]};
        color: {colors["color"]};
        font-size: {font_size_a};
        border-radius: 5px;
        font-weight: bold;
    """

# STEAM BADGE STYLES
STEAM_BADGE_STYLE= f"""
    qproperty-alignment: AlignCenter;
    background: rgba(0, 0, 0, 0.5);
    color: white;
    border-radius: 5px;
    font-family: '{font_family}';
    font-weight: bold;
"""

# ADDITIONAL INFO STYLES ON GAMES PAGE
LAST_LAUNCH_TITLE_STYLE = f"max-height: 16px; background: rgba(20,20,20,0.40);font-family: '{font_family}'; font-size: 11px; color: {color_f}; text-transform: uppercase; letter-spacing: 0.75px;"
LAST_LAUNCH_VALUE_STYLE = f"height: 16px; background: rgba(20,20,20,0.40);font-family: '{font_family}'; font-size: 13px; color: {color_f}; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE = f"max-height: 16px; background: rgba(20,20,20,0.40);font-family: '{font_family}'; font-size: 11px; color: {color_f}; text-transform: uppercase; letter-spacing: 0.75px;"
PLAY_TIME_VALUE_STYLE = f"height: 16px; background: rgba(20,20,20,0.40);font-family: '{font_family}'; font-size: 13px; color: {color_f}; font-weight: 600; letter-spacing: 0.75px;"
GAMEPAD_SUPPORT_VALUE_STYLE = f"""
    font-family: '{font_family}'; font-size: {font_size_a}; color: {color_gamepad_supported};
    font-weight: bold; background: {color_g};
    border-radius: 5px; padding: 4px 8px;
"""
