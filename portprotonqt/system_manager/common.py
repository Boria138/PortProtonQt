"""Common system integration helpers for network manager services."""

import asyncio
import re
from typing import Any

from dbus_fast import BusType, Variant
from dbus_fast.aio import MessageBus


def _create_variant(signature: str, value: Any) -> Any:
    return Variant(signature, value)

NM_SERVICE = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"
NM_INTERFACE = "org.freedesktop.NetworkManager"
NM_SETTINGS_PATH = "/org/freedesktop/NetworkManager/Settings"
NM_SETTINGS_INTERFACE = "org.freedesktop.NetworkManager.Settings"
NM_SETTINGS_CONNECTION_INTERFACE = "org.freedesktop.NetworkManager.Settings.Connection"
NM_PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
NM_DEVICE_INTERFACE = "org.freedesktop.NetworkManager.Device"
NM_WIRELESS_INTERFACE = "org.freedesktop.NetworkManager.Device.Wireless"
NM_ACTIVE_CONNECTION_INTERFACE = "org.freedesktop.NetworkManager.Connection.Active"
NM_ACCESS_POINT_INTERFACE = "org.freedesktop.NetworkManager.AccessPoint"
NM_WIFI_DEVICE_TYPE = 2
UPOWER_SERVICE = "org.freedesktop.UPower"
UPOWER_PATH = "/org/freedesktop/UPower"
UPOWER_INTERFACE = "org.freedesktop.UPower"
DBUS_PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"

class SystemManagerError(Exception):
    """Base error for system manager operations."""


class NetworkManagerError(SystemManagerError):
    """Raised when NetworkManager D-Bus operations fail."""


class DbusFastSystemBus:
    """Minimal sync wrapper over dbus-fast system bus."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._proxy_cache: dict[tuple[str, str], Any] = {}
        try:
            asyncio.set_event_loop(self._loop)
            self._bus = self._loop.run_until_complete(self._connect())
        except Exception as exc:
            asyncio.set_event_loop(None)
            self._loop.close()
            raise SystemManagerError("Failed to connect to system D-Bus") from exc

    def close(self) -> None:
        try:
            self._bus.disconnect()
        finally:
            asyncio.set_event_loop(None)
            self._loop.close()

    def call(self, service: str, path: str, interface: str, member: str, *args):
        try:
            dbus_interface = self._run(self._get_interface(service, path, interface))
            member_name = self._to_member_name(member)
            method = getattr(dbus_interface, f"call_{member_name}", None)
            if method is None:
                raise SystemManagerError(f"D-Bus method not found: {interface}.{member}")
            result = self._run(method(*args))
            if isinstance(result, tuple) and len(result) == 1:
                return result[0]
            return result
        except SystemManagerError:
            raise
        except Exception as exc:
            raise SystemManagerError(str(exc)) from exc

    def get_property(self, service: str, path: str, interface: str, prop: str):
        value = self.call(
            service,
            path,
            DBUS_PROPERTIES_INTERFACE,
            "Get",
            interface,
            prop,
        )
        return self._unwrap_variant(value)

    def set_property(self, service: str, path: str, interface: str, prop: str, signature: str, value) -> None:
        self.call(
            service,
            path,
            DBUS_PROPERTIES_INTERFACE,
            "Set",
            interface,
            prop,
            _create_variant(signature, value),
        )

    def export_interface(self, path: str, interface: Any) -> None:
        self._bus.export(path, interface)

    def unexport_interface(self, path: str, interface: Any | str | None = None) -> None:
        self._bus.unexport(path, interface)

    def _run(self, coroutine):
        return self._loop.run_until_complete(coroutine)

    async def _connect(self):
        return await MessageBus(bus_type=BusType.SYSTEM).connect()

    async def _get_interface(self, service: str, path: str, interface: str):
        cache_key = (service, path)
        proxy = self._proxy_cache.get(cache_key)
        if proxy is None:
            introspection = await self._bus.introspect(service, path)
            proxy = self._bus.get_proxy_object(service, path, introspection)
            self._proxy_cache[cache_key] = proxy
        return proxy.get_interface(interface)

    def _to_member_name(self, member: str) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "_", member).lower()

    def _unwrap_variant(self, value):
        if isinstance(value, Variant):
            return value.value
        return value
