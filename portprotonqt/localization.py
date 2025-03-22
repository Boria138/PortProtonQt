import gettext
from pathlib import Path

translate = gettext.translation(
    domain="messages",
    localedir = Path(__file__).parent / "locales",
    fallback=True,
)
_ = translate.gettext
