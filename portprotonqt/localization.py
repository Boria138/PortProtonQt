import gettext
import configparser
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

def get_screenshot_caption(base_filename, metainfo_file, language_code=None):
    """
    Возвращает перевод названия скриншота на основе языка пользователя.

    Args:
        base_filename: Имя файла без расширения
        metainfo_file: Путь к файлу metainfo.ini
        language_code: Код языка (если None, будет определен автоматически)

    Returns:
        Переведенное название скриншота
    """
    if language_code is None:
        system_locale = get_system_locale()
        language_code = system_locale.split('_')[0] if '_' in system_locale else system_locale

    # Загружаем переводы из metainfo.ini
    screenshot_translations = {}
    if metainfo_file and os.path.exists(metainfo_file):
        cp = configparser.ConfigParser()
        cp.read(metainfo_file, encoding="utf-8")
        if "Screenshots" in cp:
            for key in cp.options("Screenshots"):
                screenshot_translations[key] = cp.get("Screenshots", key)

    # Ищем перевод в формате: base_filename_languagecode
    caption = base_filename  # По умолчанию используем базовое имя файла

    if screenshot_translations:
        # Попробуем перевод для конкретного языка (например, "library_ru")
        lang_specific_key = f"{base_filename}_{language_code}"
        # Попробуем английский перевод (например, "library_en")
        english_key = f"{base_filename}_en"

        if lang_specific_key in screenshot_translations:
            caption = screenshot_translations[lang_specific_key]
        elif english_key in screenshot_translations:
            caption = screenshot_translations[english_key]
        elif base_filename in screenshot_translations:
            caption = screenshot_translations[base_filename]  # fallback to untranslated key

    return caption

def get_theme_translations(metainfo_file, language_code=None):
    """
    Возвращает переводы названия и описания темы на основе языка пользователя.

    Args:
        metainfo_file: Путь к файлу metainfo.ini
        language_code: Код языка (если None, будет определен автоматически)

    Returns:
        Словарь с полями 'name' и 'description' с переведенными значениями
    """
    if language_code is None:
        system_locale = get_system_locale()
        language_code = system_locale.split('_')[0] if '_' in system_locale else system_locale

    # Загружаем переводы из metainfo.ini
    translations = {'name': '', 'description': ''}

    if metainfo_file and os.path.exists(metainfo_file):
        cp = configparser.ConfigParser()
        cp.read(metainfo_file, encoding="utf-8")

        if "Metainfo" in cp:
            # Попробуем перевод названия для конкретного языка (например, "name_ru")
            lang_specific_name_key = f"name_{language_code}"
            # Попробуем английский перевод названия (например, "name_en")
            english_name_key = "name_en"

            # Ищем перевод названия
            if cp.has_option("Metainfo", lang_specific_name_key):
                translations['name'] = cp.get("Metainfo", lang_specific_name_key)
            elif cp.has_option("Metainfo", english_name_key):
                translations['name'] = cp.get("Metainfo", english_name_key)
            elif cp.has_option("Metainfo", "name"):
                translations['name'] = cp.get("Metainfo", "name")

            # Попробуем перевод описания для конкретного языка (например, "description_ru")
            lang_specific_desc_key = f"description_{language_code}"
            # Попробуем английский перевод описания (например, "description_en")
            english_desc_key = "description_en"

            # Ищем перевод описания
            if cp.has_option("Metainfo", lang_specific_desc_key):
                translations['description'] = cp.get("Metainfo", lang_specific_desc_key)
            elif cp.has_option("Metainfo", english_desc_key):
                translations['description'] = cp.get("Metainfo", english_desc_key)
            elif cp.has_option("Metainfo", "description"):
                translations['description'] = cp.get("Metainfo", "description")

    return translations
