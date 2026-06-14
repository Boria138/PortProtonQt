"""Shared fixtures for PortProtonQt tests."""
import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Generator[Path, None, None]:
    os.environ["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    os.environ["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    os.environ["XDG_DATA_HOME"] = str(tmp_path / "data")
    yield tmp_path / "config"
    for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"):
        os.environ.pop(key, None)


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    cache_dir = tmp_path / "cache" / "PortProtonQt"
    cache_dir.mkdir(parents=True)
    return cache_dir


@pytest.fixture
def sample_steam_apps() -> list[dict]:
    return [
        {"appid": 730, "name": "Counter-Strike 2", "normalized_name": "counter strike 2"},
        {"appid": 570, "name": "Dota 2", "normalized_name": "dota 2"},
        {"appid": 440, "name": "Team Fortress 2", "normalized_name": "team fortress 2"},
        {"appid": 1091500, "name": "Cyberpunk 2077™", "normalized_name": "cyberpunk 2077"},
        {"appid": 1174180, "name": "Red Dead Redemption 2: Ultimate Edition", "normalized_name": "red dead redemption 2"},
    ]


@pytest.fixture
def sample_anticheat_apps() -> list[dict]:
    return [
        {"normalized_name": "fortnite", "status": "Broken", "slug": "fortnite"},
        {"normalized_name": "apex legends", "status": "Running", "slug": "apex-legends"},
        {"normalized_name": "pubg battlegrounds", "status": "Running", "slug": "pubg"},
    ]
