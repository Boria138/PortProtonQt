"""Bluetooth manager worker and service."""

import re
import threading
import time

from PySide6.QtCore import QThread, Signal
from dbus_fast import DBusError
from dbus_fast.annotations import DBusObjectPath, DBusStr, DBusUInt16, DBusUInt32
from dbus_fast.service import ServiceInterface, method

from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.system_manager.common import (
    DbusFastSystemBus,
    UPOWER_INTERFACE,
    UPOWER_PATH,
    UPOWER_SERVICE,
    NetworkManagerError,
    Variant,
)

logger = get_logger(__name__)

BLUEZ_SERVICE = "org.bluez"
BLUEZ_ROOT_PATH = "/"
BLUEZ_OBJECT_MANAGER_INTERFACE = "org.freedesktop.DBus.ObjectManager"
BLUEZ_PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
BLUEZ_ADAPTER_INTERFACE = "org.bluez.Adapter1"
BLUEZ_DEVICE_INTERFACE = "org.bluez.Device1"
BLUEZ_AGENT_INTERFACE = "org.bluez.Agent1"
BLUEZ_AGENT_MANAGER_INTERFACE = "org.bluez.AgentManager1"
BLUEZ_AGENT_MANAGER_PATH = "/org/bluez"
BLUEZ_AGENT_PATH = "/org/portprotonqt/BluetoothAgent"


class BluezPairingAgent(ServiceInterface):
    """BlueZ Agent1 implementation for interactive pairing."""

    def __init__(self, service: "BluetoothManagerService") -> None:
        super().__init__(BLUEZ_AGENT_INTERFACE)
        self._service = service

    @method()
    def RequestPinCode(self, device: DBusObjectPath) -> DBusStr:
        response = self._service._request_pairing_input(
            _("Bluetooth PIN code"),
            _("Enter the Bluetooth PIN code shown on the device"),
            str(device),
        )
        if not response:
            raise DBusError("org.bluez.Error.Rejected", "Bluetooth PIN entry cancelled")
        return response

    @method()
    def DisplayPinCode(self, _device: DBusObjectPath, _pincode: DBusStr) -> None:
        return None

    @method()
    def RequestPasskey(self, device: DBusObjectPath) -> DBusUInt32:
        response = self._service._request_pairing_input(
            _("Bluetooth passkey"),
            _("Enter the Bluetooth passkey shown on the device"),
            str(device),
        )
        if not response or not response.isdigit():
            raise DBusError("org.bluez.Error.Rejected", "Bluetooth passkey entry cancelled")
        return int(response)

    @method()
    def DisplayPasskey(
        self,
        _device: DBusObjectPath,
        _passkey: DBusUInt32,
        _entered: DBusUInt16,
    ) -> None:
        return None

    @method()
    def RequestConfirmation(self, device: DBusObjectPath, passkey: DBusUInt32) -> None:
        message = _("Confirm the passkey on devices: {0}").format(f"{int(passkey):06d}")
        approved = self._service._request_pairing_confirm(message, str(device))
        if not approved:
            raise DBusError("org.bluez.Error.Rejected", "Bluetooth pairing confirmation rejected")

    @method()
    def RequestAuthorization(self, _device: DBusObjectPath) -> None:
        return None

    @method()
    def AuthorizeService(self, _device: DBusObjectPath, _uuid: DBusStr) -> None:
        return None

    @method()
    def Cancel(self) -> None:
        return None


class BluetoothManagerWorker(QThread):
    """Run Bluetooth actions outside the UI thread."""

    operation_finished = Signal(str, dict)
    operation_failed = Signal(str, str)
    pairing_requested = Signal(dict)

    def __init__(self, operation: str, params: dict | None = None, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.params = params or {}
        self._pairing_event = threading.Event()
        self._pairing_response = ""

    def run(self) -> None:
        try:
            service = BluetoothManagerService(self._request_pairing_response)
            payload = service.execute(self.operation, self.params)
        except NetworkManagerError as exc:
            self.operation_failed.emit(self.operation, str(exc))
            return
        except Exception as exc:
            logger.exception("Unexpected bluetooth operation failure: %s", exc)
            self.operation_failed.emit(self.operation, "")
            return

        if self.isInterruptionRequested():
            return

        self.operation_finished.emit(self.operation, payload)

    def _request_pairing_response(self, request: dict) -> str:
        self._pairing_response = ""
        self._pairing_event.clear()
        self.pairing_requested.emit(request)
        while not self._pairing_event.wait(0.2):
            if self.isInterruptionRequested():
                return ""
        return self._pairing_response

    def submit_pairing_response(self, response: str) -> None:
        self._pairing_response = response
        self._pairing_event.set()

    def requestInterruption(self) -> None:
        """Interrupt worker and unblock pending pairing wait."""
        super().requestInterruption()
        self._pairing_event.set()


class BluetoothManagerService:
    """Bluetooth device management through BlueZ D-Bus API."""

    def __init__(self, request_pairing_response=None) -> None:
        self.dbus = DbusFastSystemBus()
        self.request_pairing_response = request_pairing_response
        self._pairing_agent = BluezPairingAgent(self)
        self._pairing_agent_registered = False

    def execute(self, operation: str, params: dict) -> dict:
        try:
            if operation == "load":
                return self.list_devices()
            if operation == "scan":
                return self.scan_devices()

            self._run_operation(operation, params)
            if operation in {"connect", "disconnect", "forget"}:
                self._sleep_if_needed(2)
            elif operation != "load":
                self._sleep_if_needed(1)

            return self.list_devices()
        finally:
            self._unregister_pairing_agent()
            self.dbus.close()

    def _sleep_if_needed(self, seconds: int) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            time.sleep(0.2)

    def _run_operation(self, operation: str, params: dict) -> None:
        if operation == "toggle_bluetooth":
            self.set_powered(bool(params.get("enabled")))
        elif operation == "connect":
            self.connect_device(params.get("address", ""))
        elif operation == "disconnect":
            self.disconnect_device(params.get("address", ""))
        elif operation == "forget":
            self.forget_device(params.get("address", ""))
        else:
            raise NetworkManagerError("Unsupported Bluetooth operation")

    def list_devices(self, discovered: list[tuple[str, str]] | None = None) -> dict:
        objects = self._get_managed_objects()
        adapter_path = self._get_adapter_path(objects)
        payload = {
            "available": bool(adapter_path),
            "powered": False,
            "adapter_name": "",
            "devices": [],
        }
        if not adapter_path:
            return payload

        adapter_props = self._interface_props(objects, adapter_path, BLUEZ_ADAPTER_INTERFACE)
        payload["powered"] = bool(adapter_props.get("Powered", False))
        payload["adapter_name"] = str(
            adapter_props.get("Alias") or adapter_props.get("Name") or adapter_path.rsplit("/", 1)[-1]
        )
        payload["devices"] = self._build_devices(objects, discovered)
        return payload

    def scan_devices(self) -> dict:
        adapter_path = self._require_adapter_path()
        self._require_powered()
        self._call_bluez(adapter_path, f"{BLUEZ_ADAPTER_INTERFACE}.StartDiscovery")
        try:
            self._sleep_if_needed(8)
        finally:
            try:
                self._call_bluez(adapter_path, f"{BLUEZ_ADAPTER_INTERFACE}.StopDiscovery")
            except NetworkManagerError:
                logger.warning("Failed to stop Bluetooth discovery")
        return self.list_devices()

    def set_powered(self, enabled: bool) -> None:
        adapter_path = self._require_adapter_path()
        self.dbus.set_property(
            BLUEZ_SERVICE,
            adapter_path,
            BLUEZ_ADAPTER_INTERFACE,
            "Powered",
            "b",
            enabled,
        )
        logger.info("Bluetooth %s", "enabled" if enabled else "disabled")

    def connect_device(self, address: str) -> None:
        if not address:
            logger.error("Bluetooth operation connect called without address")
            return
        self._require_powered()
        device = self._require_device(address)
        device_path = str(device["path"])
        if not bool(device.get("paired", False)):
            self._register_pairing_agent()
            try:
                self._call_bluez(device_path, f"{BLUEZ_DEVICE_INTERFACE}.Pair")
            finally:
                self._unregister_pairing_agent()
        self.dbus.set_property(
            BLUEZ_SERVICE,
            device_path,
            BLUEZ_DEVICE_INTERFACE,
            "Trusted",
            "b",
            True,
        )
        self._call_bluez(device_path, f"{BLUEZ_DEVICE_INTERFACE}.Connect")
        logger.info("Bluetooth device connected")

    def _register_pairing_agent(self) -> None:
        if self._pairing_agent_registered:
            return
        self.dbus.export_interface(BLUEZ_AGENT_PATH, self._pairing_agent)
        try:
            self._call_bluez(
                BLUEZ_AGENT_MANAGER_PATH,
                f"{BLUEZ_AGENT_MANAGER_INTERFACE}.RegisterAgent",
                BLUEZ_AGENT_PATH,
                "DisplayYesNo",
            )
        except Exception:
            self.dbus.unexport_interface(BLUEZ_AGENT_PATH)
            raise
        self._pairing_agent_registered = True

    def _unregister_pairing_agent(self) -> None:
        if not self._pairing_agent_registered:
            return
        try:
            self._call_bluez(
                BLUEZ_AGENT_MANAGER_PATH,
                f"{BLUEZ_AGENT_MANAGER_INTERFACE}.UnregisterAgent",
                BLUEZ_AGENT_PATH,
            )
        except NetworkManagerError:
            logger.warning("Failed to unregister Bluetooth pairing agent")
        self.dbus.unexport_interface(BLUEZ_AGENT_PATH)
        self._pairing_agent_registered = False

    def _request_pairing_input(self, title: str, message: str, device_path: str) -> str:
        request = {
            "kind": "input",
            "title": title,
            "message": message,
            "device_path": device_path,
        }
        return self._request_pairing_response(request)

    def _request_pairing_confirm(self, message: str, device_path: str) -> bool:
        request = {
            "kind": "confirm",
            "title": _("Bluetooth pairing"),
            "message": message,
            "device_path": device_path,
        }
        return self._request_pairing_response(request) == "yes"

    def _request_pairing_response(self, request: dict) -> str:
        if self.request_pairing_response is None:
            raise DBusError("org.bluez.Error.Rejected", "Bluetooth pairing requires user confirmation")
        response = self.request_pairing_response(request).strip()
        if request["kind"] == "confirm":
            return "yes" if response == "yes" else "no"
        return response

    def disconnect_device(self, address: str) -> None:
        if not address:
            logger.error("Bluetooth operation disconnect called without address")
            return
        device = self._require_device(address)
        if not bool(device.get("connected", False)):
            raise NetworkManagerError("The selected Bluetooth device is not connected")
        self._call_bluez(str(device["path"]), f"{BLUEZ_DEVICE_INTERFACE}.Disconnect")
        logger.info("Bluetooth device disconnected")

    def forget_device(self, address: str) -> None:
        if not address:
            logger.error("Bluetooth operation forget called without address")
            return
        adapter_path = self._require_adapter_path()
        device = self._require_device(address)
        self._call_bluez(
            adapter_path,
            f"{BLUEZ_ADAPTER_INTERFACE}.RemoveDevice",
            str(device["path"]),
        )
        logger.info("Bluetooth device removed")

    def _get_managed_objects(self) -> dict:
        raw = self._call_bluez(BLUEZ_ROOT_PATH, f"{BLUEZ_OBJECT_MANAGER_INTERFACE}.GetManagedObjects")
        if not isinstance(raw, dict):
            raise NetworkManagerError("Failed to load Bluetooth objects")
        return raw

    def _get_adapter_path(self, objects: dict) -> str:
        for path in sorted(objects):
            interfaces = objects.get(path, {})
            if BLUEZ_ADAPTER_INTERFACE in interfaces:
                return path
        return ""

    def _require_adapter_path(self) -> str:
        adapter_path = self._get_adapter_path(self._get_managed_objects())
        if not adapter_path:
            raise NetworkManagerError("Bluetooth adapter not found")
        return adapter_path

    def _interface_props(self, objects: dict, object_path: str, interface: str) -> dict:
        interfaces = objects.get(object_path, {})
        props = interfaces.get(interface, {})
        if not isinstance(props, dict):
            return {}
        return {key: self._unwrap_variant(value) for key, value in props.items()}

    def _build_devices(self, objects: dict, discovered: list[tuple[str, str]] | None = None) -> list[dict]:
        device_map = {}
        for path, interfaces in objects.items():
            if BLUEZ_DEVICE_INTERFACE not in interfaces:
                continue
            props = self._interface_props(objects, path, BLUEZ_DEVICE_INTERFACE)
            address = str(props.get("Address", "")).upper()
            if not address:
                continue
            device_map[address] = {
                "path": path,
                "address": address,
                "name": str(props.get("Name") or props.get("Alias") or address),
                "paired": bool(props.get("Paired", False)),
                "trusted": bool(props.get("Trusted", False)),
                "connected": bool(props.get("Connected", False)),
                "icon": str(props.get("Icon", "")),
                "address_type": str(props.get("AddressType", "")),
            }

        for address, name in discovered or []:
            key = address.upper()
            if key in device_map and device_map[key].get("name"):
                continue
            device_map[key] = {
                "path": "",
                "address": key,
                "name": name or key,
                "paired": False,
                "trusted": False,
                "connected": False,
                "icon": "",
                "address_type": "",
            }

        battery_levels = self._get_bluetooth_battery_levels()
        devices = []
        for item in device_map.values():
            item["battery"] = battery_levels.get(item["address"], "")
            item["state"] = self._get_bluetooth_state(item)
            devices.append(item)

        devices = self._filter_duplicate_bluetooth_devices(devices)
        return sorted(devices, key=self._sort_bluetooth_device)

    def _require_powered(self) -> None:
        payload = self.list_devices()
        if not payload["powered"]:
            raise NetworkManagerError("Bluetooth is disabled")

    def _require_device(self, address: str) -> dict:
        target = address.upper()
        for device in self.list_devices()["devices"]:
            if str(device["address"]).upper() == target:
                return device
        raise NetworkManagerError("Bluetooth device not found")

    def _get_bluetooth_state(self, device: dict) -> str:
        if bool(device.get("connected", False)):
            return _("Connected")
        if bool(device.get("paired", False)):
            return _("Paired")
        return _("Available")

    def _sort_bluetooth_device(self, device: dict) -> tuple:
        return (
            0 if device["connected"] else 1,
            0 if device["paired"] else 1,
            0 if device["address_type"] == "public" else 1,
            str(device["name"]).lower(),
            str(device["address"]),
        )

    def _filter_duplicate_bluetooth_devices(self, devices: list[dict]) -> list[dict]:
        filtered_devices = []
        devices_by_name = {}
        for device in devices:
            if not device["name"] or device["name"] == device["address"]:
                filtered_devices.append(device)
                continue
            current_device = devices_by_name.get(device["name"])
            if current_device is None:
                devices_by_name[device["name"]] = device
                continue
            if self._compare_bluetooth_device_priority(device, current_device) < 0:
                devices_by_name[device["name"]] = device

        filtered_devices.extend(devices_by_name.values())
        return filtered_devices

    def _compare_bluetooth_device_priority(self, left: dict, right: dict) -> int:
        left_priority = (
            0 if left["connected"] else 1,
            0 if left["paired"] else 1,
            0 if left["trusted"] else 1,
            0 if left["address_type"] == "public" else 1,
        )
        right_priority = (
            0 if right["connected"] else 1,
            0 if right["paired"] else 1,
            0 if right["trusted"] else 1,
            0 if right["address_type"] == "public" else 1,
        )
        if left_priority < right_priority:
            return -1
        if left_priority > right_priority:
            return 1
        return 0

    def _get_bluetooth_battery_levels(self) -> dict[str, str]:
        output = self._call_upower(UPOWER_PATH, f"{UPOWER_INTERFACE}.EnumerateDevices")
        if isinstance(output, str):
            object_paths = re.findall(r"'(/org/freedesktop/UPower/devices/[^']+)'", output)
        elif isinstance(output, (list, tuple)):
            object_paths = [str(item) for item in output if str(item).startswith("/")]
        else:
            object_paths = []
        if not object_paths:
            return {}

        battery_levels = {}
        for object_path in object_paths:
            serial = str(self._call_upower_property(object_path, "Serial")).upper()
            if not serial:
                serial = self._extract_upower_address(
                    str(self._call_upower_property(object_path, "NativePath"))
                )
            percentage = self._call_upower_property(object_path, "Percentage")
            if not serial or not percentage:
                continue
            battery_levels[serial] = f"{int(float(percentage))}%"
        return battery_levels

    def _call_upower(self, object_path: str, method: str, *args):
        interface_name, member = method.rsplit(".", 1)
        try:
            return self.dbus.call(
                UPOWER_SERVICE,
                object_path,
                interface_name,
                member,
                *args,
            )
        except NetworkManagerError:
            return ""

    def _call_upower_property(self, object_path: str, property_name: str) -> str:
        try:
            output = self.dbus.get_property(
                UPOWER_SERVICE,
                object_path,
                "org.freedesktop.UPower.Device",
                property_name,
            )
        except NetworkManagerError:
            return ""
        return self._extract_dbus_property_value(output)

    def _call_bluez(self, object_path: str, method: str, *args):
        interface_name, member = method.rsplit(".", 1)
        try:
            return self.dbus.call(
                BLUEZ_SERVICE,
                object_path,
                interface_name,
                member,
                *args,
            )
        except NetworkManagerError as exc:
            raise NetworkManagerError(self._clean_bluetooth_error(str(exc))) from exc

    def _clean_bluetooth_error(self, error_text: str) -> str:
        cleaned = error_text.split(":", 1)[-1].strip()
        if cleaned:
            return cleaned
        logger.warning("Bluetooth operation failed without detailed error text")
        return ""

    def _extract_upower_address(self, native_path: str) -> str:
        if not native_path:
            return ""
        match = re.search(r"([0-9A-Fa-f]{2}[:_]){5}[0-9A-Fa-f]{2}", native_path)
        if not match:
            return ""
        return match.group(0).replace("_", ":").upper()

    def _extract_dbus_property_value(self, output) -> str:
        if isinstance(output, Variant):
            output = output.value
        if output is None:
            return ""
        if isinstance(output, str):
            return output
        if isinstance(output, (int, float)):
            return str(output)
        return str(output)

    def _unwrap_variant(self, output):
        if isinstance(output, Variant):
            return output.value
        return output
