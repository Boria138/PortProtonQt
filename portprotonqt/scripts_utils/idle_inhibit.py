import asyncio
import contextlib
import os
import sys
from collections.abc import Awaitable
from typing import Any

from portprotonqt.logger import get_logger
from portprotonqt.localization import _


logger = get_logger(__name__)

BUS_NAME = "org.freedesktop.ScreenSaver"
BUS_PATH = "/org/freedesktop/ScreenSaver"
APPLICATION_NAME = "ru.linux_gaming.PortProtonQt"
INHIBIT_REASON = _("Launched")
DBUS_TIMEOUT = 10


def _get_inhibit_reason() -> str:
    game_name = os.getenv("PW_INHIBIT_NAME", "").strip()
    if not game_name:
        game_name = os.getenv("PORTPROTON_NAME", "").strip()
    if not game_name:
        return INHIBIT_REASON

    return f"{INHIBIT_REASON} {game_name}"


async def _run_command(command: list[str]) -> int:
    process = await asyncio.create_subprocess_exec(*command)
    return await process.wait()


async def _dbus_call(awaitable: Awaitable[Any]) -> Any:
    return await asyncio.wait_for(awaitable, timeout=DBUS_TIMEOUT)


async def _request_inhibit() -> tuple[Any, int, Any]:
    import dbus_fast
    import dbus_fast.aio

    bus = await _dbus_call(dbus_fast.aio.MessageBus().connect())
    introspection = await _dbus_call(bus.introspect(BUS_NAME, BUS_PATH))
    proxy = bus.get_proxy_object(BUS_NAME, BUS_PATH, introspection)
    iface = proxy.get_interface(BUS_NAME)
    cookie = await _dbus_call(iface.call_inhibit(APPLICATION_NAME, _get_inhibit_reason()))
    return iface, cookie, dbus_fast


async def _release_inhibit(iface: Any, cookie: int, dbus_fast: Any) -> None:
    with contextlib.suppress(dbus_fast.DBusError, asyncio.TimeoutError):
        await _dbus_call(iface.call_un_inhibit(cookie))


async def _inhibit_and_run(command: list[str]) -> int:
    try:
        iface, cookie, dbus_fast = await _request_inhibit()
    except TimeoutError as err:
        logger.warning("Screensaver inhibit failed: %s", err)
        return await _run_command(command)
    except Exception as err:
        logger.warning("Screensaver inhibit failed: %s", err)
        return await _run_command(command)

    try:
        return await _run_command(command)
    finally:
        await _release_inhibit(iface, cookie, dbus_fast)


async def _main(command: list[str]) -> int:
    if not command:
        return 2

    return await _inhibit_and_run(command)


def main() -> int:
    return asyncio.run(_main(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
