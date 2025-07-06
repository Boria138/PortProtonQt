import gettext
from pathlib import Path
import locale
import os
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

def read_metadata_translations(metadata_file, language_code):
    """
    Читает переводы из metadata.txt для указанного языка.
    Возвращает словарь с полями name и description.
    Для name: использует name_<language_code>, затем name_en, затем name, и наконец _('Unknown Game').
    Для description: использует description_<language_code>, затем description_en, затем description.
    """
    translations = {'name': _('Unknown Game'), 'description': ''}
    if not os.path.exists(metadata_file):
        return translations

    with open(metadata_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith(f'name_{language_code}='):
                translations['name'] = line[len(f'name_{language_code}='):].strip()
            elif line.startswith('name_en=') and translations['name'] == _('Unknown Game'):
                translations['name'] = line[len('name_en='):].strip()
            elif line.startswith('name=') and translations['name'] == _('Unknown Game'):
                translations['name'] = line[len('name='):].strip()
            elif line.startswith(f'description_{language_code}='):
                translations['description'] = line[len(f'description_{language_code}='):].strip()
            elif line.startswith('description_en=') and not translations['description']:
                translations['description'] = line[len('description_en='):].strip()
            elif line.startswith('description=') and not translations['description']:
                translations['description'] = line[len('description='):].strip()

    return translations
