"""GOG authentication, library and gogdl process helpers."""

import hashlib
import os
import platform
import re
import shutil
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import orjson
import requests

from portprotonqt.localization import get_metadata_language
from portprotonqt.logger import get_logger

logger = get_logger(__name__)
GOG_LOGIN_URL = (
    "https://auth.gog.com/auth?client_id=46899977096215655&"
    "redirect_uri=https%3A%2F%2Fembed.gog.com%2Fon_login_success%3Forigin%3Dclient&"
    "response_type=code&layout=galaxy"
)
GOGDL_RELEASE_URL = "https://api.github.com/repos/Heroic-Games-Launcher/heroic-gogdl/releases/latest"
GOGDL_AUTH_TIMEOUT = 60
GOG_METADATA_WORKERS = 4
GOG_PRODUCT_LOCALES = {
    "bg": "bg-BG", "cs": "cs-CZ", "da": "da-DK", "de": "de-DE",
    "el": "el-GR", "en": "en-US", "es": "es-ES", "fi": "fi-FI",
    "fr": "fr-FR", "hu": "hu-HU", "it": "it-IT", "ja": "ja-JP",
    "ko": "ko-KR", "nl": "nl-NL", "no": "no-NO", "pl": "pl-PL",
    "pt": "pt-BR", "ro": "ro-RO", "ru": "ru-RU", "sv": "sv-SE",
    "th": "th-TH", "tr": "tr-TR", "uk": "uk-UA", "zh": "zh-Hans",
    "zh_hant": "zh-Hant",
}


class GOGAPI:
    """Provide the local GOG backend used by the Qt UI."""

    def __init__(self) -> None:
        data_home = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share"))
        self.data_dir = data_home / "PortProtonQt" / "gog"
        self.auth_path = self.data_dir / "auth.json"
        self.config_dir = self.data_dir / "gogdl"
        self.library_path = self.data_dir / "library.json"
        self.installed_path = self.data_dir / "installed.json"
        self.sizes_path = self.data_dir / "sizes.json"
        self.games_dir = Path.home() / "Games"

    def get_gogdl_path(self) -> str | None:
        """Return an available gogdl executable."""
        bundled = self.data_dir / "bin/gogdl"
        if bundled.is_file() and os.access(bundled, os.X_OK):
            return str(bundled)
        return shutil.which("gogdl")

    def build_command(self, arguments: list[str]) -> list[str]:
        """Build a gogdl command with private configuration paths."""
        gogdl = self.get_gogdl_path()
        if not gogdl:
            raise FileNotFoundError("gogdl executable not found")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.chmod(0o700)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        return [gogdl, "--auth-config-path", str(self.auth_path), *arguments]

    def ensure_gogdl(self) -> str:
        """Download and verify the latest official Heroic gogdl binary."""
        existing = self.get_gogdl_path()
        if existing:
            return existing
        architecture = {"x86_64": "x86_64", "aarch64": "arm64"}.get(platform.machine())
        if not architecture:
            raise OSError(f"Unsupported gogdl architecture: {platform.machine()}")
        response = requests.get(GOGDL_RELEASE_URL, timeout=15)
        response.raise_for_status()
        asset_name = f"gogdl_linux_{architecture}"
        asset = next(
            (item for item in response.json().get("assets", []) if item.get("name") == asset_name),
            None,
        )
        if not asset:
            raise OSError(f"gogdl release asset not found: {asset_name}")
        return self._download_gogdl_asset(asset)

    def _download_gogdl_asset(self, asset: dict) -> str:
        target = self.data_dir / "bin/gogdl"
        temporary = target.with_suffix(".part")
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        try:
            with requests.get(asset["browser_download_url"], stream=True, timeout=30) as response:
                response.raise_for_status()
                with open(temporary, "wb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            output.write(chunk)
                            digest.update(chunk)
            expected = str(asset.get("digest", "")).removeprefix("sha256:")
            if not expected or digest.hexdigest() != expected:
                raise OSError("gogdl checksum verification failed")
            temporary.chmod(0o755)
            temporary.replace(target)
            return str(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def get_environment(self) -> dict[str, str]:
        """Return the environment required by gogdl."""
        environment = os.environ.copy()
        environment["GOGDL_CONFIG_PATH"] = str(self.config_dir)
        return environment

    def authenticate(self, code: str) -> tuple[bool, str]:
        """Exchange an OAuth code through gogdl."""
        self.ensure_gogdl()
        result = subprocess.run(
            self.build_command(["auth", "--code", code]),
            env=self.get_environment(), capture_output=True, check=False,
            timeout=GOGDL_AUTH_TIMEOUT,
        )
        if result.returncode != 0:
            error = result.stderr.decode(errors="replace").strip()
            logger.error("gogdl authentication failed: %s", error)
            return False, error or f"gogdl exited with code {result.returncode}"
        try:
            data = orjson.loads(result.stdout)
        except orjson.JSONDecodeError:
            return False, "gogdl returned an invalid authentication response"
        if not isinstance(data, dict) or data.get("error"):
            return False, "GOG rejected the authorization code"
        if self.auth_path.is_file():
            self.auth_path.chmod(0o600)
        return True, ""

    def get_credentials(self) -> dict:
        """Return refreshed GOG credentials through gogdl."""
        try:
            self.ensure_gogdl()
            result = subprocess.run(
                self.build_command(["auth"]), env=self.get_environment(),
                capture_output=True, check=False,
            )
            data = orjson.loads(result.stdout) if result.returncode == 0 else {}
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, orjson.JSONDecodeError):
            return {}

    def is_authenticated(self) -> bool:
        """Return whether gogdl provides usable account credentials."""
        credentials = self.get_credentials()
        return bool(credentials.get("access_token") and credentials.get("user_id"))

    def refresh_library(
        self, progress_callback: Callable[[int, int], None] | None = None
    ) -> list[dict]:
        """Fetch and cache the user's GOG library."""
        credentials = self.get_credentials()
        token = credentials.get("access_token")
        user_id = credentials.get("user_id")
        if not token or not user_id:
            return []
        entries = self._get_library_entries(str(user_id), str(token))
        gog_entries = [entry for entry in entries if entry.get("platform_id") == "gog"]
        games = self._get_games_parallel(gog_entries, str(token), progress_callback)
        self._save_json(self.library_path, games)
        return games

    def _get_games_parallel(
        self, entries: list[dict], token: str,
        progress_callback: Callable[[int, int], None] | None,
    ) -> list[dict]:
        cached = {str(game.get("app_id")): game for game in self.load_library()}
        games = []
        worker_count = min(GOG_METADATA_WORKERS, os.cpu_count() or 1)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(self._get_game, entry, token): entry for entry in entries}
            for completed, future in enumerate(as_completed(futures), 1):
                entry = futures[future]
                app_id = str(entry.get("external_id", ""))
                try:
                    game = future.result()
                except requests.RequestException as error:
                    logger.warning("Failed to load GOG metadata for %s: %s", app_id, error)
                    game = cached.get(app_id, {})
                if game:
                    game.setdefault("steam_appid", "")
                    games.append(game)
                if progress_callback:
                    progress_callback(completed, len(entries))
        return games

    def load_library(self) -> list[dict]:
        """Load the cached GOG library."""
        data = self._load_json(self.library_path, [])
        return data if isinstance(data, list) else []

    def load_installed(self) -> dict[str, dict]:
        """Load installed GOG game records."""
        data = self._load_json(self.installed_path, {})
        return data if isinstance(data, dict) else {}

    def save_installed_game(self, app_id: str, game: dict) -> None:
        """Persist one installed GOG game record."""
        installed = self.load_installed()
        installed[app_id] = game
        self._save_json(self.installed_path, installed)

    def remove_installed_game(self, app_id: str) -> None:
        """Remove one installed GOG game record."""
        installed = self.load_installed()
        installed.pop(app_id, None)
        self._save_json(self.installed_path, installed)

    def get_cached_download_sizes(self, app_id: str) -> tuple[int, int] | None:
        """Return cached download and disk sizes for a game."""
        cache = self._load_json(self.sizes_path, {})
        if not isinstance(cache, dict):
            return None
        cached = cache.get(app_id)
        if not isinstance(cached, list) or len(cached) != 2:
            return None
        return int(cached[0]), int(cached[1])

    def save_download_sizes(self, app_id: str, sizes: tuple[int, int]) -> None:
        """Cache download and disk sizes for a game."""
        cached = self._load_json(self.sizes_path, {})
        if not isinstance(cached, dict):
            cached = {}
        cached[app_id] = list(sizes)
        self._save_json(self.sizes_path, cached)

    def is_game_installed(
        self, app_id: str, installed_games: dict[str, dict] | None = None
    ) -> bool:
        """Return whether a complete gogdl installation is available."""
        return self.get_installed_path(app_id, installed_games) is not None

    def get_installed_path(
        self, app_id: str, installed_games: dict[str, dict] | None = None
    ) -> Path | None:
        """Return a recorded or discoverable gogdl installation path."""
        records = installed_games if installed_games is not None else self.load_installed()
        installed = records.get(app_id, {})
        install_path = Path(str(installed.get("install_path", "")))
        if (install_path / f"goggame-{app_id}.info").is_file():
            return install_path
        return self.find_install_path(app_id, self.games_dir)

    def get_install_path(self, app_id: str, title: str) -> Path:
        """Return the default parent directory for GOG installations."""
        return self.games_dir

    def find_install_path(self, app_id: str, parent: Path) -> Path | None:
        """Find the directory created by gogdl for an installed game."""
        metadata_name = f"goggame-{app_id}.info"
        if (parent / metadata_name).is_file():
            return parent
        try:
            return next(
                (path.parent for path in parent.glob(f"*/{metadata_name}")),
                None,
            )
        except OSError as error:
            logger.warning("Failed to inspect GOG installation path %s: %s", parent, error)
            return None

    def get_launch_target(self, app_id: str) -> str | None:
        """Return the primary executable from gogdl installation metadata."""
        primary, install_path = self._get_primary_task(app_id)
        if primary is None or install_path is None:
            return None
        target = install_path
        parts = str(primary.get("path", "")).replace("\\", "/").split("/")
        for part in parts:
            exact_path = target / part
            if exact_path.exists():
                target = exact_path
                continue
            try:
                target = next(
                    child for child in target.iterdir()
                    if child.name.casefold() == part.casefold()
                )
            except (OSError, StopIteration):
                return None
        return str(target) if target.is_file() else None

    def ensure_launch_parameters(self, app_id: str) -> None:
        """Add GOG task arguments to the executable PPDB when absent."""
        primary, install_path = self._get_primary_task(app_id)
        target = self.get_launch_target(app_id)
        if primary is None or install_path is None or not target:
            return
        arguments = str(primary.get("arguments", "")).replace("\r", " ").replace("\n", " ").strip()
        if not arguments:
            return
        ppdb_path = Path(f"{target}.ppdb")
        try:
            current = ppdb_path.read_text(encoding="utf-8") if ppdb_path.exists() else ""
            base_value = arguments.replace('"', "").replace("\\", "/")
            normalized = base_value
            support_dir = (
                self.config_dir / "heroic_gogdl" / "gog-support" / app_id / "app"
            )
            if support_dir.is_dir():
                for support_file in support_dir.rglob("*"):
                    if not support_file.is_file():
                        continue
                    relative_path = os.path.relpath(support_file, Path(target).parent)
                    normalized = normalized.replace(
                        f"../{support_file.name}", relative_path.replace(os.sep, "/")
                    )
            safe_value = normalized.replace("$", "\\$").replace("`", "\\`")
            launch_line = f'export LAUNCH_PARAMETERS="{safe_value}"'
            lines = current.splitlines()
            existing = next(
                (line for line in lines if line.startswith("export LAUNCH_PARAMETERS=")),
                "",
            )
            if existing:
                value = existing.removeprefix('export LAUNCH_PARAMETERS="').removesuffix('"')
                comparable = re.sub(r"\\+", "/", value.replace('\\"', "").replace('"', ""))
                if comparable not in (base_value, normalized):
                    return
                lines[lines.index(existing)] = launch_line
                ppdb_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return
            separator = "" if not current or current.endswith("\n") else "\n"
            ppdb_path.write_text(
                f"{current}{separator}{launch_line}\n",
                encoding="utf-8",
            )
        except OSError as error:
            logger.warning("Failed to add GOG launch parameters to %s: %s", ppdb_path, error)

    def _get_primary_task(self, app_id: str) -> tuple[dict | None, Path | None]:
        """Return the primary GOG launch task and installation path."""
        install_path = self.get_installed_path(app_id)
        if install_path is None:
            return None, None
        info = self._load_json(install_path / f"goggame-{app_id}.info", {})
        tasks = info.get("playTasks", []) if isinstance(info, dict) else []
        primary = next((task for task in tasks if task.get("isPrimary")), None)
        if primary is None and tasks:
            primary = tasks[0]
        if not isinstance(primary, dict) or primary.get("type") != "FileTask":
            return None, install_path
        return primary, install_path

    def _get_library_entries(self, user_id: str, token: str) -> list[dict]:
        entries = []
        page_token = ""
        headers = {"Authorization": f"Bearer {token}"}
        while True:
            url = f"https://galaxy-library.gog.com/users/{user_id}/releases"
            response = requests.get(url, headers=headers, params={"page_token": page_token} if page_token else {}, timeout=15)
            response.raise_for_status()
            data = response.json()
            entries.extend(data.get("items", []))
            page_token = data.get("next_page_token", "")
            if not page_token:
                return entries

    def _get_game(self, entry: dict, token: str) -> dict:
        if entry.get("platform_id") != "gog" or not entry.get("external_id"):
            return {}
        app_id = str(entry["external_id"])
        headers = {"Authorization": f"Bearer {token}"}
        if entry.get("certificate"):
            headers["X-GOG-Library-Cert"] = str(entry["certificate"])
        response = requests.get(
            f"https://gamesdb.gog.com/platforms/gog/external_releases/{app_id}",
            headers=headers, timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        game = data.get("game", {})
        if not game.get("visible_in_library", True):
            return {}
        steam_release = next(
            (
                release for release in game.get("releases", [])
                if release.get("platform_id") == "steam"
            ),
            {},
        )
        description = self._localized_value(data.get("summary"))
        language = get_metadata_language().lower()
        try:
            product_response = requests.get(
                f"https://api.gog.com/products/{app_id}",
                params={
                    "expand": "description",
                    "locale": GOG_PRODUCT_LOCALES.get(language, language),
                },
                timeout=15,
            )
            product_response.raise_for_status()
            product_description = product_response.json().get("description", {})
            localized_lead = str(product_description.get("lead") or "")
            if localized_lead:
                paragraphs = re.split(
                    r"(?:<br\s*/?>\s*){2,}", localized_lead, flags=re.IGNORECASE
                )
                paragraph_count = (
                    2 if re.match(r"\s*<(?:b|strong)>", paragraphs[0], re.IGNORECASE)
                    else 1
                )
                description = "<br><br>".join(
                    paragraph.strip() for paragraph in paragraphs[:paragraph_count]
                )
        except requests.RequestException as error:
            logger.warning(
                "Failed to load localized GOG description for %s: %s",
                app_id, error,
            )
        return {
            "app_id": app_id,
            "title": (
                self._localized_value(data.get("title"))
                or self._localized_value(game.get("title"))
                or app_id
            ).strip(),
            "description": description,
            "cover": self._format_image(game.get("vertical_cover") or game.get("logo") or game.get("background")),
            "steam_appid": str(steam_release.get("external_id", "")),
        }

    @staticmethod
    def _localized_value(values: dict | None) -> str:
        if not isinstance(values, dict):
            return ""
        language = get_metadata_language().lower()
        for key in (language, language.replace("_", "-")):
            if values.get(key):
                return str(values[key])
        localized = next(
            (value for key, value in values.items() if key.lower().startswith(language)),
            None,
        )
        return str(localized or values.get("*", ""))

    @staticmethod
    def _format_image(image: dict | None) -> str:
        template = image.get("url_format", "") if isinstance(image, dict) else ""
        return template.replace("{formatter}", "").replace("{ext}", "jpg")

    @staticmethod
    def parse_download_sizes(output: bytes) -> tuple[int, int]:
        """Return download and disk sizes from gogdl info output."""
        data = orjson.loads(output)
        sizes = data.get("size", {}) if isinstance(data, dict) else {}
        languages = data.get("languages", []) if isinstance(data, dict) else []
        selected = [sizes.get("*", {})]
        if languages:
            selected.append(sizes.get(str(languages[0]), {}))
        download_size = sum(int(item.get("download_size", 0)) for item in selected)
        disk_size = sum(int(item.get("disk_size", 0)) for item in selected)
        return download_size, disk_size

    @staticmethod
    def extract_auth_code(url: str) -> str:
        """Extract the OAuth code from GOG's redirect URL."""
        values = parse_qs(urlparse(url).query)
        return values.get("code", [""])[0]

    @staticmethod
    def _load_json(path: Path, fallback):
        try:
            return orjson.loads(path.read_bytes())
        except (OSError, orjson.JSONDecodeError):
            return fallback

    @staticmethod
    def _save_json(path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
