import gettext
from pathlib import Path
import locale
from babel import Locale

LOCALE_MAP = {
    'ru': 'russian',
    'en': 'english',
    'fr': 'french',
    'de': 'german',
    'es': 'spanish',
    'it': 'italian',
    'zh': 'schinese',
    'zh_Hant': 'tchinese',
    'ja': 'japanese',
    'ko': 'koreana',
    'pt': 'brazilian',
    'pl': 'polish',
    'nl': 'dutch',
    'sv': 'swedish',
    'no': 'norwegian',
    'da': 'danish',
    'fi': 'finnish',
    'cs': 'czech',
    'hu': 'hungarian',
    'tr': 'turkish',
    'ro': 'romanian',
    'th': 'thai',
    'uk': 'ukrainian',
    'bg': 'bulgarian',
    'el': 'greek',
}

translate = gettext.translation(
    domain="messages",
    localedir = Path(__file__).parent / "locales",
    fallback=True,
)
_ = translate.gettext

def get_system_locale():
    """Возвращает системную локаль, например, 'ru_RU'. Если не удаётся определить – возвращает 'en'."""
    loc = locale.getdefaultlocale()[0]
    return loc if loc else 'en'

def get_steam_language():
    try:
        # Babel автоматически разбирает сложные локали, например, 'zh_Hant_HK' → 'zh_Hant'
        system_locale = get_system_locale()
        if system_locale:
            locale = Locale.parse(system_locale)
            # Используем только языковой код ('ru', 'en', и т.д.)
            language_code = locale.language
            return LOCALE_MAP.get(language_code, 'english')
    except Exception as e:
        print(f"Failed to detect locale: {e}")

    # Если что-то пошло не так — используем английский по умолчанию
    return 'english'

def get_egs_language():
    try:
        # Babel автоматически разбирает сложные локали, например, 'zh_Hant_HK' → 'zh_Hant'
        system_locale = get_system_locale()
        if system_locale:
            locale = Locale.parse(system_locale)
            # Используем только языковой код ('ru', 'en', и т.д.)
            language_code = locale.language
            return language_code
    except Exception as e:
        print(f"Failed to detect locale: {e}")

    # Если что-то пошло не так — используем английский по умолчанию
    return 'en'
