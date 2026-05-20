"""Power profile tools for PortProton scripts."""
import argparse
import asyncio
import sys
from typing import Any

from dbus_fast import BusType, Message, Variant
from dbus_fast.aio import MessageBus

from portprotonqt.logger import get_logger


logger = get_logger(__name__)


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
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
ACTIVE_PROFILE = "ActiveProfile"
PROFILES = "Profiles"
DBUS_TIMEOUT = 10


async def _dbus_call(bus: Any, message: Any) -> Any:
    reply = await asyncio.wait_for(bus.call(message), timeout=DBUS_TIMEOUT)
    if reply.message_type.name == "ERROR":
        return None
    return reply.body


async def _get_property(bus: Any, endpoint: Endpoint, name: str) -> Any:
    bus_name, bus_path = endpoint
    body = await _dbus_call(
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


async def _active_profile(bus: Any) -> tuple[Endpoint, str] | None:
    for endpoint in POWER_PROFILE_ENDPOINTS:
        try:
            profile = await _get_property(bus, endpoint, ACTIVE_PROFILE)
        except Exception as error:
            logger.debug("Power profile endpoint unavailable: %s", error)
            continue
        if isinstance(profile, str):
            return endpoint, profile
    return None


async def get_profile() -> str | None:
    """Return active power profile."""
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    active_profile = await _active_profile(bus)
    if not active_profile:
        return None
    return active_profile[1]


async def set_profile(profile: str) -> bool:
    """Set active power profile."""
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    active_profile = await _active_profile(bus)
    if not active_profile:
        return False

    bus_name, bus_path = active_profile[0]
    profiles = await _get_property(bus, active_profile[0], PROFILES)
    if profile not in _profile_names(profiles):
        return False

    body = await _dbus_call(
        bus,
        Message(
            destination=bus_name,
            path=bus_path,
            interface=PROPERTIES_INTERFACE,
            member="Set",
            signature="ssv",
            body=[bus_name, ACTIVE_PROFILE, Variant("s", profile)],
        ),
    )
    return body is not None


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
    """Parse arguments for power profile tools."""
    parser = argparse.ArgumentParser(description="PortProtonQt power profile tools")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("get", help="Print active power profile")

    set_parser = subparsers.add_parser("set", help="Set active power profile")
    set_parser.add_argument("profile", help="Power profile name")
    return parser.parse_args()


async def _main() -> int:
    args = parse_args()
    try:
        if args.command == "get":
            profile = await get_profile()
            if not profile:
                return 1
            print(profile)
            return 0
        if args.command == "set":
            return 0 if await set_profile(args.profile) else 1
    except Exception as error:
        logger.debug("Power profile command failed: %s", error)
        return 1
    return 1


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    sys.exit(main())
