"""D-Bus tools for PortProton scripts."""
import argparse
import asyncio
import contextlib
import sys
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, cast

from dbus_fast import BusType, DBusError, Message, Variant
from dbus_fast.aio import MessageBus

from portprotonqt.logger import get_logger


logger = get_logger(__name__)

DBUS_TIMEOUT = 10
NOTIFICATIONS_BUS_NAME = "org.freedesktop.Notifications"
NOTIFICATIONS_BUS_PATH = "/org/freedesktop/Notifications"
DEEPIN_WM_BUS_NAME = "com.deepin.WMSwitcher"
DEEPIN_WM_BUS_PATH = "/com/deepin/WMSwitcher"
SCREENSAVER_BUS_NAME = "org.freedesktop.ScreenSaver"
SCREENSAVER_BUS_PATH = "/org/freedesktop/ScreenSaver"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
ACTIVE_PROFILE = "ActiveProfile"
PROFILES = "Profiles"
Endpoint = tuple[str, str]
POWER_PROFILE_ENDPOINTS: tuple[Endpoint, ...] = (
    (
        "org.freedesktop.UPower.PowerProfiles",
        "/org/freedesktop/UPower/PowerProfiles",
    ),
    (
        "net.hadess.PowerProfiles",
        "/net/hadess/PowerProfiles",
    ),
)


@dataclass(frozen=True)
class NotificationRequest:
    app: str
    icon: str
    title: str
    body: str
    timeout: int


async def dbus_call(awaitable: Awaitable[Any]) -> Any:
    """Run D-Bus awaitable with timeout."""
    return await asyncio.wait_for(awaitable, timeout=DBUS_TIMEOUT)


async def _bus_call(bus: MessageBus, message: Message) -> Any:
    reply = await dbus_call(bus.call(message))
    if reply.message_type.name == "ERROR":
        return None
    return reply.body


async def _session_call(message: Message) -> bool:
    bus = await dbus_call(MessageBus(bus_type=BusType.SESSION).connect())
    try:
        body = await _bus_call(bus, message)
    finally:
        bus.disconnect()
    return body is not None


async def send_notification(request: NotificationRequest) -> bool:
    """Send desktop notification."""
    bus = await dbus_call(MessageBus(bus_type=BusType.SESSION).connect())
    try:
        try:
            return await _send_standard_notification(bus, request)
        except Exception as error:
            logger.warning("Standard notification failed: %s", error)
            return False
    finally:
        bus.disconnect()


async def _send_standard_notification(bus: MessageBus, request: NotificationRequest) -> bool:
    hints = {}
    if request.app == "ru.linux_gaming.PortProtonQt":
        hints["desktop-entry"] = Variant("s", "ru.linux_gaming.PortProtonQt")

    body = await _bus_call(
        bus,
        Message(
            destination=NOTIFICATIONS_BUS_NAME,
            path=NOTIFICATIONS_BUS_PATH,
            interface=NOTIFICATIONS_BUS_NAME,
            member="Notify",
            signature="susssasa{sv}i",
            body=[
                request.app,
                0,
                request.icon,
                request.title,
                request.body,
                [],
                hints,
                request.timeout,
            ],
        ),
    )
    return body is not None


async def request_deepin_wm_switch() -> bool:
    """Request Deepin window manager switch."""
    return await _session_call(
        Message(
            destination=DEEPIN_WM_BUS_NAME,
            path=DEEPIN_WM_BUS_PATH,
            interface=DEEPIN_WM_BUS_NAME,
            member="RequestSwitchWM",
        )
    )


async def request_idle_inhibit(application: str, reason: str) -> tuple[MessageBus, str, Any]:
    """Request idle inhibit through screensaver D-Bus API."""
    bus = await dbus_call(MessageBus(bus_type=BusType.SESSION).connect())
    try:
        kind, payload = await _request_screensaver_inhibit(bus, application, reason)
    except Exception:
        bus.disconnect()
        raise

    return bus, kind, payload


async def _request_screensaver_inhibit(
    bus: MessageBus,
    application: str,
    reason: str,
) -> tuple[str, Any]:
    introspection = await dbus_call(bus.introspect(SCREENSAVER_BUS_NAME, SCREENSAVER_BUS_PATH))
    proxy = bus.get_proxy_object(SCREENSAVER_BUS_NAME, SCREENSAVER_BUS_PATH, introspection)
    iface = cast(Any, proxy.get_interface(SCREENSAVER_BUS_NAME))
    cookie = await dbus_call(iface.call_inhibit(application, reason))
    return "screensaver", (iface, cookie)


async def release_idle_inhibit(bus: MessageBus, kind: str, payload: Any) -> None:
    """Release idle inhibit requested through request_idle_inhibit."""
    with contextlib.suppress(DBusError, asyncio.TimeoutError):
        if kind == "screensaver":
            iface, cookie = payload
            await dbus_call(iface.call_un_inhibit(cookie))
    bus.disconnect()


async def get_power_profile() -> str | None:
    """Return active power profile."""
    bus = await dbus_call(MessageBus(bus_type=BusType.SYSTEM).connect())
    try:
        active_profile = await _active_power_profile(bus)
    finally:
        bus.disconnect()
    if not active_profile:
        return None
    return active_profile[1]


async def set_power_profile(profile: str) -> bool:
    """Set active power profile."""
    bus = await dbus_call(MessageBus(bus_type=BusType.SYSTEM).connect())
    try:
        active_profile = await _active_power_profile(bus)
        if not active_profile:
            return False

        bus_name = active_profile[0][0]
        profiles = await _get_property(bus, active_profile[0], PROFILES)
        if profile not in _profile_names(profiles):
            return False

        body = await _bus_call(
            bus,
            Message(
                destination=bus_name,
                path=active_profile[0][1],
                interface=PROPERTIES_INTERFACE,
                member="Set",
                signature="ssv",
                body=[bus_name, ACTIVE_PROFILE, Variant("s", profile)],
            ),
        )
    finally:
        bus.disconnect()
    return body is not None


async def _get_property(bus: MessageBus, endpoint: Endpoint, name: str) -> Any:
    bus_name, bus_path = endpoint
    body = await _bus_call(
        bus,
        Message(
            destination=bus_name,
            path=bus_path,
            interface=PROPERTIES_INTERFACE,
            member="Get",
            signature="ss",
            body=[bus_name, name],
        ),
    )
    if not body:
        return None
    return _variant_value(body[0])


async def _active_power_profile(bus: MessageBus) -> tuple[Endpoint, str] | None:
    for endpoint in POWER_PROFILE_ENDPOINTS:
        try:
            profile = await _get_property(bus, endpoint, ACTIVE_PROFILE)
        except Exception as error:
            logger.debug("Power profile endpoint unavailable: %s", error)
            continue
        if isinstance(profile, str):
            return endpoint, profile
    return None


def _variant_value(value: Any) -> Any:
    if isinstance(value, Variant):
        return _variant_value(value.value)
    if isinstance(value, dict):
        return {
            _variant_value(key): _variant_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_variant_value(item) for item in value]
    return value


def _profile_names(profiles: Any) -> set[str]:
    if not isinstance(profiles, list):
        return set()

    names = set()
    for profile in profiles:
        if isinstance(profile, dict) and isinstance(profile.get("Profile"), str):
            names.add(profile["Profile"])
    return names


def parse_args() -> argparse.Namespace:
    """Parse D-Bus tool arguments."""
    parser = argparse.ArgumentParser(description="PortProtonQt D-Bus tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    notify_parser = subparsers.add_parser("notify", help="Send notification")
    notify_parser.add_argument("-a", "--app", default="ru.linux_gaming.PortProtonQt")
    notify_parser.add_argument("-i", "--icon", default="")
    notify_parser.add_argument("-t", "--timeout", type=int, default=5000)
    notify_parser.add_argument("title")
    notify_parser.add_argument("body", nargs="?", default="")

    subparsers.add_parser("deepin-switch-wm", help="Request Deepin WM switch")
    return parser.parse_args()


async def _main() -> int:
    args = parse_args()
    try:
        if args.command == "notify":
            request = NotificationRequest(
                args.app,
                args.icon,
                args.title,
                args.body,
                args.timeout,
            )
            return 0 if await send_notification(request) else 1
        if args.command == "deepin-switch-wm":
            return 0 if await request_deepin_wm_switch() else 1
    except Exception as error:
        logger.debug("D-Bus command failed: %s", error)
        return 1
    return 1


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    sys.exit(main())
