import orjson
import re
import os
from dataclasses import dataclass, field
from typing import Any
from difflib import SequenceMatcher
from threading import Thread
import requests
from bs4 import BeautifulSoup, Tag
from portprotonqt.config_utils import read_proxy_config
from portprotonqt.time_utils import format_playtime
from PySide6.QtCore import QObject, Signal

@dataclass
class GameEntry:
    """Game information from HowLongToBeat."""
    game_id: int = -1
    game_name: str | None = None
    main_story: float | None = None
    main_extra: float | None = None
    completionist: float | None = None
    similarity: float = -1.0
    raw_data: dict[str, Any] = field(default_factory=dict)

@dataclass
class SearchConfig:
    """Search configuration."""
    api_key: str | None = None
    search_url: str | None = None

class APIKeyExtractor:
    """Extract API key and search URL from site scripts."""
    @staticmethod
    def extract_from_script(script_content: str) -> SearchConfig:
        config = SearchConfig()
        config.api_key = APIKeyExtractor._extract_api_key(script_content)
        config.search_url = APIKeyExtractor._extract_search_url(script_content, config.api_key)
        return config

    @staticmethod
    def _extract_api_key(script_content: str) -> str | None:
        user_id_pattern = r'users\s*:\s*{\s*id\s*:\s*"([^"]+)"'
        matches = re.findall(user_id_pattern, script_content)
        if matches:
            return ''.join(matches)
        concat_pattern = r'\/api\/\w+\/"(?:\.concat\("[^"]*"\))+'
        matches = re.findall(concat_pattern, script_content)
        if matches:
            parts = str(matches).split('.concat')
            cleaned_parts = [re.sub(r'["\(\)\[\]\']', '', part) for part in parts[1:]]
            return ''.join(cleaned_parts)
        return None

    @staticmethod
    def _extract_search_url(script_content: str, api_key: str | None) -> str | None:
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
    """HTTP client for HowLongToBeat API."""
    BASE_URL = 'https://howlongtobeat.com/'
    SEARCH_URL = BASE_URL + "api/s/"

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'referer': self.BASE_URL
        })
        proxy_config = read_proxy_config()
        if proxy_config:
            self.session.proxies.update(proxy_config)

    def get_search_config(self, parse_all_scripts: bool = False) -> SearchConfig | None:
        try:
            response = self.session.get(self.BASE_URL, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            scripts = soup.find_all('script', src=True)
            script_urls = []
            for script in scripts:
                if isinstance(script, Tag):
                    src = script.get('src')
                    if src is not None and isinstance(src, str):
                        if parse_all_scripts or '_app-' in src:
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

    def search_games(self, game_name: str, page: int = 1, config: SearchConfig | None = None) -> str | None:
        if not config:
            config = self.get_search_config()
            if not config:
                config = self.get_search_config(parse_all_scripts=True)
        if not config or not config.api_key:
            return None
        search_url = self.SEARCH_URL
        if config.search_url:
            search_url = self.BASE_URL + config.search_url.lstrip('/')
        payload = self._build_search_payload(game_name, page, config)
        headers = {
            'content-type': 'application/json',
            'accept': '*/*'
        }
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

    def _build_search_payload(self, game_name: str, page: int, config: SearchConfig) -> dict[str, Any]:
        payload = {
            'searchType': "games",
            'searchTerms': game_name.split(),
            'searchPage': page,
            'size': 1,  # Limit to 1 result
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
                    'modifier': ""  # Hardcoded to empty string for SearchModifiers.NONE
                },
                'users': {'sortCategory': "postcount"},
                'lists': {'sortCategory': "follows"},
                'filter': "",
                'sort': 0,
                'randomizer': 0
            },
            'useCache': True,
            'fields': ["game_id", "game_name", "comp_main", "comp_plus", "comp_100"]  # Request only needed fields
        }
        if config.api_key:
            payload['searchOptions']['users']['id'] = config.api_key
        return payload

class ResultParser:
    """Search results parser."""
    def __init__(self, search_query: str, minimum_similarity: float = 0.4, case_sensitive: bool = True):
        self.search_query = search_query
        self.minimum_similarity = minimum_similarity
        self.case_sensitive = case_sensitive
        self.search_numbers = self._extract_numbers(search_query)

    def parse_results(self, json_response: str, target_game_id: int | None = None) -> list[GameEntry]:
        try:
            data = orjson.loads(json_response)
            games = []
            # Only process the first result
            if data.get("data"):
                game_data = data["data"][0]
                game = self._parse_game_entry(game_data)
                if target_game_id is not None:
                    if game.game_id == target_game_id:
                        games.append(game)
                elif self.minimum_similarity == 0.0 or game.similarity >= self.minimum_similarity:
                    games.append(game)
            return games
        except (orjson.JSONDecodeError, KeyError, IndexError):
            return []

    def _parse_game_entry(self, game_data: dict[str, Any]) -> GameEntry:
        game = GameEntry()
        game.game_id = game_data.get("game_id", -1)
        game.game_name = game_data.get("game_name")
        game.raw_data = game_data
        time_fields = [
            ("comp_main", "main_story"),
            ("comp_plus", "main_extra"),
            ("comp_100", "completionist")
        ]
        all_zero = all(game_data.get(json_field, 0) == 0 for json_field, _ in time_fields)
        for json_field, attr_name in time_fields:
            if json_field in game_data:
                time_seconds = game_data[json_field]
                time_hours = None if all_zero else round(time_seconds / 3600, 2)
                setattr(game, attr_name, time_hours)
        game.similarity = self._calculate_similarity(game)
        return game

    def _calculate_similarity(self, game: GameEntry) -> float:
        return self._compare_strings(self.search_query, game.game_name)

    def _compare_strings(self, a: str | None, b: str | None) -> float:
        if not a or not b:
            return 0.0
        if self.case_sensitive:
            similarity = SequenceMatcher(None, a, b).ratio()
        else:
            similarity = SequenceMatcher(None, a.lower(), b.lower()).ratio()
        if self.search_numbers and not self._contains_numbers(b, self.search_numbers):
            similarity -= 0.1
        return max(0.0, similarity)

    @staticmethod
    def _extract_numbers(text: str) -> list[str]:
        return [word for word in text.split() if word.isdigit()]

    @staticmethod
    def _contains_numbers(text: str, numbers: list[str]) -> bool:
        if not numbers:
            return True
        cleaned_text = re.sub(r'([^\s\w]|_)+', '', text)
        text_numbers = [word for word in cleaned_text.split() if word.isdigit()]
        return any(num in text_numbers for num in numbers)

def get_cache_dir():
    """Return cache directory path, creating it if necessary."""
    xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    cache_dir = os.path.join(xdg_cache_home, "PortProtonQt")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

class HowLongToBeat(QObject):
    """Main class for HowLongToBeat API."""
    searchCompleted = Signal(list)

    def __init__(self, minimum_similarity: float = 0.4, timeout: int = 60, parent=None):
        super().__init__(parent)
        self.minimum_similarity = minimum_similarity
        self.http_client = HTTPClient(timeout)
        self.cache_dir = get_cache_dir()

    def _get_cache_file_path(self, game_name: str) -> str:
        """Return cache file path for given game name."""
        safe_game_name = re.sub(r'[^\w\s-]', '', game_name).replace(' ', '_').lower()
        cache_file = f"hltb_{safe_game_name}.json"
        return os.path.join(self.cache_dir, cache_file)

    def _load_from_cache(self, game_name: str) -> str | None:
        """Try to load data from cache if it exists."""
        cache_file = self._get_cache_file_path(game_name)
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'rb') as f:
                    return f.read().decode('utf-8')
        except (OSError, UnicodeDecodeError):
            pass
        return None

    def _save_to_cache(self, game_name: str, json_response: str):
        """Save data to cache, storing only first game and required fields."""
        cache_file = self._get_cache_file_path(game_name)
        try:
            # Parse JSON and take only the first game
            data = orjson.loads(json_response)
            if data.get("data"):
                first_game = data["data"][0]
                simplified_data = {
                    "data": [{
                        "game_id": first_game.get("game_id", -1),
                        "game_name": first_game.get("game_name"),
                        "comp_main": first_game.get("comp_main", 0),
                        "comp_plus": first_game.get("comp_plus", 0),
                        "comp_100": first_game.get("comp_100", 0)
                    }]
                }
                with open(cache_file, 'wb') as f:
                    f.write(orjson.dumps(simplified_data))
        except (OSError, orjson.JSONDecodeError, IndexError):
            pass

    def search(self, game_name: str, case_sensitive: bool = True) -> list[GameEntry] | None:
        if not game_name or not game_name.strip():
            return None
        # Check cache
        cached_response = self._load_from_cache(game_name)
        if cached_response:
            try:
                cached_data = orjson.loads(cached_response)
                full_json = {
                    "data": [
                        {
                            "game_id": game["game_id"],
                            "game_name": game["game_name"],
                            "comp_main": game["comp_main"],
                            "comp_plus": game["comp_plus"],
                            "comp_100": game["comp_100"]
                        }
                        for game in cached_data.get("data", [])
                    ]
                }
                parser = ResultParser(
                    game_name,
                    self.minimum_similarity,
                    case_sensitive
                )
                return parser.parse_results(orjson.dumps(full_json).decode('utf-8'))
            except orjson.JSONDecodeError:
                pass
        # If not in cache, make request
        json_response = self.http_client.search_games(game_name)
        if not json_response:
            return None
        # Save only first game to cache
        self._save_to_cache(game_name, json_response)
        parser = ResultParser(
            game_name,
            self.minimum_similarity,
            case_sensitive
        )
        return parser.parse_results(json_response)

    def format_game_time(self, game_entry: GameEntry, time_field: str = "main_story") -> str | None:
        time_value = getattr(game_entry, time_field, None)
        if time_value is None:
            return None
        time_seconds = int(time_value * 3600)
        return format_playtime(time_seconds)

    def search_with_callback(self, game_name: str, case_sensitive: bool = True):
        """Search for game in background thread and emit signal with results."""
        def search_thread():
            try:
                results = self.search(game_name, case_sensitive)
                self.searchCompleted.emit(results if results else [])
            except Exception as e:
                print(f"Error in search_with_callback: {e}")
                self.searchCompleted.emit([])

        thread = Thread(target=search_thread)
        thread.daemon = True
        thread.start()
