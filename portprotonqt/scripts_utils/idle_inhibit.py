import asyncio
import os
import sys

from portprotonqt.logger import get_logger
from portprotonqt.localization import _
from portprotonqt.scripts_utils.dbus_tools import (
    release_idle_inhibit,
    request_idle_inhibit,
)


logger = get_logger(__name__)

APPLICATION_NAME = "ru.linux_gaming.PortProtonQt"
INHIBIT_REASON = _("Launched")
WINE_WAIT_INTERVAL = 5
WINE_PROCESS_NAMES = {"wine-preloader", "wine64-preloader", "wineserver"}


def _get_inhibit_reason() -> str:
    game_name = os.getenv("PW_INHIBIT_NAME", "").strip()
    if not game_name:
        game_name = os.getenv("PORTPROTON_NAME", "").strip()
    if not game_name:
        return INHIBIT_REASON

    return f"{INHIBIT_REASON} {game_name}"


async def _run_command(command: list[str]) -> int:
    process = await asyncio.create_subprocess_exec(*command)
    return_code = await process.wait()
    await _wait_wine_processes()
    return return_code


def _has_wine_process() -> bool:
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            exe_path = os.readlink(os.path.join("/proc", pid, "exe"))
        except OSError:
            continue
        if _is_portproton_wine_process(exe_path):
            return True
    return False


def _is_portproton_wine_process(exe_path: str) -> bool:
    lower_path = exe_path.lower()
    if "portproton" not in lower_path:
        return False
    return os.path.basename(lower_path) in WINE_PROCESS_NAMES


async def _wait_wine_processes() -> None:
    while _has_wine_process():
        await asyncio.sleep(WINE_WAIT_INTERVAL)


async def _inhibit_and_run(command: list[str]) -> int:
    try:
        bus, kind, payload = await request_idle_inhibit(
            APPLICATION_NAME,
            _get_inhibit_reason(),
        )
    except (ImportError, TimeoutError) as err:
        logger.warning("Screensaver inhibit failed: %s", err)
        return await _run_command(command)
    except Exception as err:
        logger.warning("Screensaver inhibit failed: %s", err)
        return await _run_command(command)

    try:
        return await _run_command(command)
    finally:
        await release_idle_inhibit(bus, kind, payload)


async def _main(command: list[str]) -> int:
    if not command:
        return 2

    return await _inhibit_and_run(command)


def main() -> int:
    return asyncio.run(_main(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
