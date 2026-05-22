import asyncio
import contextlib
import os
import sys
from collections.abc import Awaitable
from typing import Any, cast

from dbus_fast import DBusError, Message, Variant
from dbus_fast.aio import MessageBus

from portprotonqt.logger import get_logger
from portprotonqt.localization import _


logger = get_logger(__name__)

BUS_NAME = "org.freedesktop.ScreenSaver"
BUS_PATH = "/org/freedesktop/ScreenSaver"
PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_BUS_PATH = "/org/freedesktop/portal/desktop"
PORTAL_INTERFACE = "org.freedesktop.portal.Inhibit"
PORTAL_REQUEST_INTERFACE = "org.freedesktop.portal.Request"
PORTAL_IDLE_FLAG = 8
APPLICATION_NAME = "ru.linux_gaming.PortProtonQt"
INHIBIT_REASON = _("Launched")
DBUS_TIMEOUT = 10
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


async def _dbus_call(awaitable: Awaitable[Any]) -> Any:
    return await asyncio.wait_for(awaitable, timeout=DBUS_TIMEOUT)


async def _request_screensaver_inhibit(bus: MessageBus) -> tuple[str, Any]:
    introspection = await _dbus_call(bus.introspect(BUS_NAME, BUS_PATH))
    proxy = bus.get_proxy_object(BUS_NAME, BUS_PATH, introspection)
    iface = cast(Any, proxy.get_interface(BUS_NAME))
    cookie = await _dbus_call(iface.call_inhibit(APPLICATION_NAME, _get_inhibit_reason()))
    return "screensaver", (iface, cookie)


async def _request_portal_inhibit(bus: MessageBus) -> tuple[str, Any]:
    options = {"reason": Variant("s", _get_inhibit_reason())}
    message = Message(
        destination=PORTAL_BUS_NAME,
        path=PORTAL_BUS_PATH,
        interface=PORTAL_INTERFACE,
        member="Inhibit",
        signature="sua{sv}",
        body=["", PORTAL_IDLE_FLAG, options],
    )
    reply = await _dbus_call(bus.call(message))
    return "portal", reply.body[0]


async def _request_inhibit() -> tuple[MessageBus, str, Any]:
    bus = await _dbus_call(MessageBus().connect())
    try:
        try:
            kind, payload = await _request_screensaver_inhibit(bus)
        except Exception as err:
            logger.warning("Screensaver inhibit failed: %s", err)
            kind, payload = await _request_portal_inhibit(bus)
    except Exception:
        bus.disconnect()
        raise

    return bus, kind, payload


async def _release_portal_inhibit(bus: MessageBus, handle: str) -> None:
    message = Message(
        destination=PORTAL_BUS_NAME,
        path=handle,
        interface=PORTAL_REQUEST_INTERFACE,
        member="Close",
    )
    await _dbus_call(bus.call(message))


async def _release_inhibit(bus: MessageBus, kind: str, payload: Any) -> None:
    with contextlib.suppress(DBusError, asyncio.TimeoutError):
        if kind == "screensaver":
            iface, cookie = payload
            await _dbus_call(iface.call_un_inhibit(cookie))
        elif kind == "portal":
            await _release_portal_inhibit(bus, payload)
    bus.disconnect()


async def _inhibit_and_run(command: list[str]) -> int:
    try:
        bus, kind, payload = await _request_inhibit()
    except (ImportError, TimeoutError) as err:
        logger.warning("Screensaver inhibit failed: %s", err)
        return await _run_command(command)
    except Exception as err:
        logger.warning("Screensaver inhibit failed: %s", err)
        return await _run_command(command)

    try:
        return await _run_command(command)
    finally:
        await _release_inhibit(bus, kind, payload)


async def _main(command: list[str]) -> int:
    if not command:
        return 2

    return await _inhibit_and_run(command)


def main() -> int:
    return asyncio.run(_main(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
