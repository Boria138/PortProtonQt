import orjson
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup, Tag
from portprotonqt.config_utils import read_proxy_config


class SearchModifiers(Enum):
    """Модификаторы поиска для фильтрации результатов."""
    NONE = ""
    ONLY_DLC = "only_dlc"
    ONLY_MODS = "only_mods"
    ONLY_HACKS = "only_hacks"
    HIDE_DLC = "hide_dlc"


@dataclass
class GameEntry:
    """Информация об игре из HowLongToBeat."""
    # Основная информация
    game_id: int = -1
    game_name: str | None = None
    game_alias: str | None = None
    game_type: str | None = None
    game_image_url: str | None = None
    game_web_link: str | None = None
    review_score: float | None = None
    developer: str | None = None
    platforms: list[str] = field(default_factory=list)
    release_year: int | None = None
    similarity: float = -1.0

    # Времена прохождения (в часах)
    main_story: float | None = None
    main_extra: float | None = None
    completionist: float | None = None
    all_styles: float | None = None
    coop_time: float | None = None
    multiplayer_time: float | None = None

    # Флаги сложности
    has_single_player: bool = False
    has_coop: bool = False
    has_multiplayer: bool = False
    has_combined_complexity: bool = False

    # Исходные данные JSON
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchConfig:
    """Конфигурация для поиска."""
    api_key: str | None = None
    search_url: str | None = None


class APIKeyExtractor:
    """Извлекает API ключ и URL поиска из скриптов сайта."""

    @staticmethod
    def extract_from_script(script_content: str) -> SearchConfig:
        """Извлекает конфигурацию из содержимого скрипта."""
        config = SearchConfig()
        config.api_key = APIKeyExtractor._extract_api_key(script_content)
        config.search_url = APIKeyExtractor._extract_search_url(script_content, config.api_key)
        return config

    @staticmethod
    def _extract_api_key(script_content: str) -> str | None:
        """Извлекает API ключ из скрипта."""
        # Паттерн для поиска user ID
        user_id_pattern = r'users\s*:\s*{\s*id\s*:\s*"([^"]+)"'
        matches = re.findall(user_id_pattern, script_content)
        if matches:
            return ''.join(matches)

        # Паттерн для поиска конкатенированного API ключа
        concat_pattern = r'\/api\/\w+\/"(?:\.concat\("[^"]*"\))+'
        matches = re.findall(concat_pattern, script_content)
        if matches:
            parts = str(matches).split('.concat')
            cleaned_parts = [re.sub(r'["\(\)\[\]\']', '', part) for part in parts[1:]]
            return ''.join(cleaned_parts)

        return None

    @staticmethod
    def _extract_search_url(script_content: str, api_key: str | None) -> str | None:
        """Извлекает URL поиска из скрипта."""
        if not api_key:
            return None

        pattern = re.compile(
            r'fetch\(\s*["\'](\/api\/[^"\']*)["\']'
            r'((?:\s*\.concat\(\s*["\']([^"\']*)["\']\s*\))+)'
            r'\s*,',
            re.DOTALL
        )

        for match in pattern.finditer(script_content):
            endpoint = match.group(1)
            concat_calls = match.group(2)
            concat_strings = re.findall(r'\.concat\(\s*["\']([^"\']*)["\']\s*\)', concat_calls)
            concatenated_str = ''.join(concat_strings)

            if concatenated_str == api_key:
                return endpoint

        return None


class HTTPClient:
    """HTTP клиент для работы с API HowLongToBeat."""

    BASE_URL = 'https://howlongtobeat.com/'
    GAME_URL = BASE_URL + "game"
    SEARCH_URL = BASE_URL + "api/s/"

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'referer': self.BASE_URL
        })
        # Apply proxy settings from config
        proxy_config = read_proxy_config()
        if proxy_config:
            self.session.proxies.update(proxy_config)

    def get_search_config(self, parse_all_scripts: bool = False) -> SearchConfig | None:
        """Получает конфигурацию поиска с главной страницы."""
        try:
            response = self.session.get(self.BASE_URL, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            scripts = soup.find_all('script', src=True)

            # Filter for Tag objects and ensure src is a string
            if parse_all_scripts:
                script_urls = []
                for script in scripts:
                    if isinstance(script, Tag):
                        src = script.get('src')
                        if src is not None and isinstance(src, str):
                            script_urls.append(src)
            else:
                script_urls = []
                for script in scripts:
                    if isinstance(script, Tag):
                        src = script.get('src')
                        if src is not None and isinstance(src, str) and '_app-' in src:
                            script_urls.append(src)

            for script_url in script_urls:
                full_url = self.BASE_URL + script_url
                script_response = self.session.get(full_url, timeout=self.timeout)
                if script_response.status_code == 200:
                    config = APIKeyExtractor.extract_from_script(script_response.text)
                    if config.api_key:
                        return config
        except requests.RequestException:
            pass
        return None

    def search_games(self, game_name: str, search_modifiers: SearchModifiers = SearchModifiers.NONE,
                    page: int = 1, config: SearchConfig | None = None) -> str | None:
        """Выполняет поиск игр."""
        if not config:
            config = self.get_search_config()
            if not config:
                config = self.get_search_config(parse_all_scripts=True)

        if not config or not config.api_key:
            return None

        search_url = self.SEARCH_URL
        if config.search_url:
            search_url = self.BASE_URL + config.search_url.lstrip('/')

        payload = self._build_search_payload(game_name, search_modifiers, page, config)
        headers = {
            'content-type': 'application/json',
            'accept': '*/*'
        }

        # Попытка с API ключом в URL
        try:
            response = self.session.post(
                search_url + config.api_key,
                headers=headers,
                data=orjson.dumps(payload),
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.text
        except requests.RequestException:
            pass

        # Попытка с API ключом в payload
        try:
            response = self.session.post(
                search_url,
                headers=headers,
                data=orjson.dumps(payload),
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.text
        except requests.RequestException:
            pass

        return None

    def get_game_title(self, game_id: int) -> str | None:
        """Получает название игры по ID."""
        try:
            params = {'id': str(game_id)}
            response = self.session.get(self.GAME_URL, params=params, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.title

            if title_tag and title_tag.string:
                # Обрезаем стандартные части заголовка
                title = title_tag.string[12:-17].strip()
                return title

        except requests.RequestException:
            pass

        return None

    def _build_search_payload(self, game_name: str, search_modifiers: SearchModifiers,
                             page: int, config: SearchConfig) -> dict[str, Any]:
        """Строит payload для поискового запроса."""
        payload = {
            'searchType': "games",
            'searchTerms': game_name.split(),
            'searchPage': page,
            'size': 20,
            'searchOptions': {
                'games': {
                    'userId': 0,
                    'platform': "",
                    'sortCategory': "popular",
                    'rangeCategory': "main",
                    'rangeTime': {'min': 0, 'max': 0},
                    'gameplay': {
                        'perspective': "",
                        'flow': "",
                        'genre': "",
                        "difficulty": ""
                    },
                    'rangeYear': {'max': "", 'min': ""},
                    'modifier': search_modifiers.value,
                },
                'users': {'sortCategory': "postcount"},
                'lists': {'sortCategory': "follows"},
                'filter': "",
                'sort': 0,
                'randomizer': 0
            },
            'useCache': True
        }

        if config.api_key:
            payload['searchOptions']['users']['id'] = config.api_key

        return payload


class ResultParser:
    """Парсер результатов поиска."""

    IMAGE_URL_PREFIX = "https://howlongtobeat.com/games/"
    GAME_URL_PREFIX = "https://howlongtobeat.com/game/"

    def __init__(self, search_query: str, minimum_similarity: float = 0.4,
                 case_sensitive: bool = True, auto_filter_times: bool = False):
        self.search_query = search_query
        self.minimum_similarity = minimum_similarity
        self.case_sensitive = case_sensitive
        self.auto_filter_times = auto_filter_times
        self.search_numbers = self._extract_numbers(search_query)

    def parse_results(self, json_response: str, target_game_id: int | None = None) -> list[GameEntry]:
        """Парсит JSON ответ и возвращает список игр."""
        try:
            data = orjson.loads(json_response)
            games = []

            for game_data in data.get("data", []):
                game = self._parse_game_entry(game_data)

                if target_game_id is not None:
                    if game.game_id == target_game_id:
                        games.append(game)
                elif self.minimum_similarity == 0.0 or game.similarity >= self.minimum_similarity:
                    games.append(game)

            return games

        except (orjson.JSONDecodeError, KeyError):
            return []

    def _parse_game_entry(self, game_data: dict[str, Any]) -> GameEntry:
        """Парсит данные одной игры."""
        game = GameEntry()

        # Основная информация
        game.game_id = game_data.get("game_id", -1)
        game.game_name = game_data.get("game_name")
        game.game_alias = game_data.get("game_alias")
        game.game_type = game_data.get("game_type")
        game.review_score = game_data.get("review_score")
        game.developer = game_data.get("profile_dev")
        game.release_year = game_data.get("release_world")
        game.raw_data = game_data

        # URL изображения
        if "game_image" in game_data:
            game.game_image_url = self.IMAGE_URL_PREFIX + game_data["game_image"]

        # Ссылка на игру
        game.game_web_link = f"{self.GAME_URL_PREFIX}{game.game_id}"

        # Платформы
        if "profile_platform" in game_data:
            game.platforms = game_data["profile_platform"].split(", ")

        # Времена прохождения (конвертация из секунд в часы)
        time_fields = [
            ("comp_main", "main_story"),
            ("comp_plus", "main_extra"),
            ("comp_100", "completionist"),
            ("comp_all", "all_styles"),
            ("invested_co", "coop_time"),
            ("invested_mp", "multiplayer_time")
        ]

        for json_field, attr_name in time_fields:
            if json_field in game_data:
                time_hours = round(game_data[json_field] / 3600, 2)
                setattr(game, attr_name, time_hours)

        # Флаги сложности
        game.has_combined_complexity = bool(game_data.get("comp_lvl_combine", 0))
        game.has_single_player = bool(game_data.get("comp_lvl_sp", 0))
        game.has_coop = bool(game_data.get("comp_lvl_co", 0))
        game.has_multiplayer = bool(game_data.get("comp_lvl_mp", 0))

        # Автофильтрация времен
        if self.auto_filter_times:
            if not game.has_single_player:
                game.main_story = None
                game.main_extra = None
                game.completionist = None
                game.all_styles = None
            if not game.has_coop:
                game.coop_time = None
            if not game.has_multiplayer:
                game.multiplayer_time = None

        # Вычисление similarity
        game.similarity = self._calculate_similarity(game)

        return game

    def _calculate_similarity(self, game: GameEntry) -> float:
        """Вычисляет similarity между поисковым запросом и игрой."""
        name_similarity = self._compare_strings(self.search_query, game.game_name)
        alias_similarity = self._compare_strings(self.search_query, game.game_alias)

        return max(name_similarity, alias_similarity)

    def _compare_strings(self, a: str | None, b: str | None) -> float:
        """Сравнивает две строки и возвращает коэффициент similarity."""
        if not a or not b:
            return 0.0

        if self.case_sensitive:
            similarity = SequenceMatcher(None, a, b).ratio()
        else:
            similarity = SequenceMatcher(None, a.lower(), b.lower()).ratio()

        # Штраф за отсутствие чисел из оригинального запроса
        if self.search_numbers and not self._contains_numbers(b, self.search_numbers):
            similarity -= 0.1

        return max(0.0, similarity)

    @staticmethod
    def _extract_numbers(text: str) -> list[str]:
        """Извлекает числа из текста."""
        return [word for word in text.split() if word.isdigit()]

    @staticmethod
    def _contains_numbers(text: str, numbers: list[str]) -> bool:
        """Проверяет, содержит ли текст указанные числа."""
        if not numbers:
            return True

        cleaned_text = re.sub(r'([^\s\w]|_)+', '', text)
        text_numbers = [word for word in cleaned_text.split() if word.isdigit()]

        return any(num in text_numbers for num in numbers)


class HowLongToBeat:
    """Основной класс для работы с API HowLongToBeat."""

    def __init__(self, minimum_similarity: float = 0.4, auto_filter_times: bool = False,
                 timeout: int = 60):
        self.minimum_similarity = minimum_similarity
        self.auto_filter_times = auto_filter_times
        self.http_client = HTTPClient(timeout)

    def search(self, game_name: str, search_modifiers: SearchModifiers = SearchModifiers.NONE,
               case_sensitive: bool = True) -> list[GameEntry] | None:
        """Ищет игры по названию."""
        if not game_name or not game_name.strip():
            return None

        json_response = self.http_client.search_games(game_name, search_modifiers)
        if not json_response:
            return None

        parser = ResultParser(
            game_name,
            self.minimum_similarity,
            case_sensitive,
            self.auto_filter_times
        )

        return parser.parse_results(json_response)

    def search_by_id(self, game_id: int) -> GameEntry | None:
        """Ищет игру по ID."""
        if not game_id or game_id <= 0:
            return None

        game_title = self.http_client.get_game_title(game_id)
        if not game_title:
            return None

        json_response = self.http_client.search_games(game_title)
        if not json_response:
            return None

        parser = ResultParser(game_title, 0.0, False, self.auto_filter_times)
        results = parser.parse_results(json_response, target_game_id=game_id)

        return results[0] if results else None
