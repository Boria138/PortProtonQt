"""Network manager worker and service."""

import os
import re
import shutil
import subprocess
import time
import uuid

from PySide6.QtCore import QThread, Signal

from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.system_manager.common import (
    DbusFastSystemBus,
    NM_ACCESS_POINT_INTERFACE,
    NM_ACTIVE_CONNECTION_INTERFACE,
    NM_DEVICE_INTERFACE,
    NM_INTERFACE,
    NM_PATH,
    NM_SERVICE,
    NM_SETTINGS_CONNECTION_INTERFACE,
    NM_SETTINGS_INTERFACE,
    NM_SETTINGS_PATH,
    NM_WIFI_DEVICE_TYPE,
    NM_WIRELESS_INTERFACE,
    NetworkManagerError,
    Variant,
)

logger = get_logger(__name__)

class NetworkManagerWorker(QThread):
    """Run NetworkManager actions outside the UI thread."""

    operation_finished = Signal(str, dict)
    operation_failed = Signal(str, str)

    def __init__(self, operation: str, params: dict | None = None, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.params = params or {}

    def run(self) -> None:
        try:
            service = NetworkManagerService()
            payload = service.execute(self.operation, self.params)
        except NetworkManagerError as exc:
            self.operation_failed.emit(self.operation, str(exc))
            return
        except Exception as exc:
            logger.exception("Unexpected network operation failure: %s", exc)
            self.operation_failed.emit(self.operation, "")
            return

        self.operation_finished.emit(self.operation, payload)


class NetworkManagerService:
    """Minimal NetworkManager D-Bus wrapper based on dbus-fast."""

    def __init__(self) -> None:
        self.dbus = DbusFastSystemBus()
        self.nmcli_path = shutil.which("nmcli")

    def execute(self, operation: str, params: dict) -> dict:
        try:
            if operation == "load":
                return self.list_networks()
            if operation == "get_password":
                payload = {"password": self._get_saved_connection_password(params.get("ssid", ""))}
                return payload

            message = self._run_operation(operation, params)
            if operation in {"connect", "connect_vpn"}:
                time.sleep(2)
            elif operation != "load":
                time.sleep(1)

            payload = self.list_networks()
            payload["message"] = message
            return payload
        finally:
            self.dbus.close()

    def _run_operation(self, operation: str, params: dict) -> str:
        if operation == "scan":
            return self.request_scan()
        if operation == "connect":
            return self.connect_network(params.get("network_path", ""), params.get("password", ""))
        if operation == "disconnect":
            return self.disconnect_network(params.get("network_path", ""))
        if operation == "forget":
            return self.forget_network(params.get("ssid", ""), params.get("network_path", ""))
        if operation == "toggle_wireless":
            return self.set_wireless_enabled(bool(params.get("enabled")))
        if operation == "connect_vpn":
            return self.connect_vpn(params.get("connection_path", ""))
        if operation == "disconnect_vpn":
            return self.disconnect_vpn(params.get("connection_path", ""))
        if operation == "add_vpn":
            return self.add_vpn(params.get("file_path", ""))
        if operation == "delete_vpn":
            return self.delete_vpn(params.get("connection_path", ""))
        if operation == "get_password":
            return self._get_saved_connection_password(params.get("ssid", ""))

        raise NetworkManagerError(_("Unsupported network operation"))

    def list_networks(self) -> dict:
        wireless_enabled = self._extract_bool(
            self._get_property(NM_PATH, NM_INTERFACE, "WirelessEnabled")
        )
        device_path = self._get_wifi_device_path()
        payload = {
            "wireless_enabled": wireless_enabled,
            "device_path": device_path,
            "device_name": "",
            "networks": [],
            "vpns": self._build_vpns(),
            "available": bool(device_path),
        }
        if not device_path:
            return payload

        payload["device_name"] = self._extract_string(
            self._get_property(device_path, NM_DEVICE_INTERFACE, "Interface")
        )
        payload["networks"] = self._build_networks(device_path)
        return payload

    def connect_vpn(self, connection_path: str) -> str:
        if not connection_path:
            logger.error("Network operation connect_vpn called without connection_path")
            return ""
        vpn = self._require_vpn(connection_path)
        if vpn["active"]:
            return _("VPN already connected")
        self._call(
            NM_PATH,
            f"{NM_INTERFACE}.ActivateConnection",
            connection_path,
            "/",
            "/",
        )
        return _("VPN connection started")

    def disconnect_vpn(self, connection_path: str) -> str:
        if not connection_path:
            logger.error("Network operation disconnect_vpn called without connection_path")
            return ""
        vpn = self._require_vpn(connection_path)
        if not vpn["active"]:
            raise NetworkManagerError(_("The selected VPN is not active"))
        active_connections = self._get_active_vpn_connections()
        active_path = active_connections.get(vpn["uuid"], "")
        if not active_path:
            raise NetworkManagerError(_("The selected VPN is not active"))
        self._call(NM_PATH, f"{NM_INTERFACE}.DeactivateConnection", active_path)
        return _("VPN disconnection started")

    def add_vpn(self, file_path: str) -> str:
        if not file_path:
            logger.error("Network operation add_vpn called without file_path")
            return ""
        normalized_path = os.path.normpath(file_path)
        if not os.path.isfile(normalized_path):
            raise NetworkManagerError(_("VPN config file not found"))
        if not normalized_path.lower().endswith((".ovpn", ".conf")):
            raise NetworkManagerError(_("Unsupported VPN config format"))
        if not self.nmcli_path:
            raise NetworkManagerError("nmcli is not available")
        vpn_type = self._detect_vpn_import_type(normalized_path)

        result = subprocess.run(
            [
                self.nmcli_path,
                "connection",
                "import",
                "type",
                vpn_type,
                "file",
                normalized_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            error_text = result.stderr.strip() or result.stdout.strip()
            raise NetworkManagerError(self._clean_error(error_text))
        return _("VPN profile imported")

    def delete_vpn(self, connection_path: str) -> str:
        if not connection_path:
            logger.error("Network operation delete_vpn called without connection_path")
            return ""
        vpn = self._require_vpn(connection_path)
        active_connections = self._get_active_vpn_connections()
        active_path = active_connections.get(vpn["uuid"], "")
        if active_path:
            self._call(NM_PATH, f"{NM_INTERFACE}.DeactivateConnection", active_path)
        self._delete_connection(connection_path)
        return _("VPN profile removed")

    def request_scan(self) -> str:
        device_path = self._require_wifi_device_path()
        self._call(device_path, f"{NM_WIRELESS_INTERFACE}.RequestScan", {})
        return ""

    def connect_network(self, network_path: str, password: str) -> str:
        if not network_path:
            logger.error("Network operation connect called without network_path")
            return ""

        device_path = self._require_wifi_device_path()
        network = self._read_network(network_path)
        saved = self._find_saved_connection(network["ssid"])
        clean_password = password.strip()
        if saved and clean_password and network["secured"]:
            self._delete_connection(saved["path"])
            saved = None

        if saved and not clean_password:
            self._call(
                NM_PATH,
                f"{NM_INTERFACE}.ActivateConnection",
                saved["path"],
                device_path,
                network_path,
            )
            return _("Connection activation started")

        if network["secured"] and not clean_password:
            raise NetworkManagerError(_("Password is required for this network"))

        settings = self._build_connection_settings(
            network["ssid"],
            clean_password,
            network["secured"],
        )
        self._call(
            NM_PATH,
            f"{NM_INTERFACE}.AddAndActivateConnection",
            settings,
            device_path,
            network_path,
        )
        return _("Connection activation started")

    def disconnect_network(self, network_path: str) -> str:
        device_path = self._require_wifi_device_path()
        active_connection = self._extract_first_path(
            self._get_property(device_path, NM_DEVICE_INTERFACE, "ActiveConnection")
        )
        active_ap = self._extract_first_path(
            self._get_property(device_path, NM_WIRELESS_INTERFACE, "ActiveAccessPoint")
        )
        if network_path and active_ap not in ("", "/", network_path):
            raise NetworkManagerError(_("The selected network is not active"))
        if active_connection and active_connection != "/":
            self._call(NM_PATH, f"{NM_INTERFACE}.DeactivateConnection", active_connection)
            return _("Disconnection started")

        self._call(device_path, f"{NM_DEVICE_INTERFACE}.Disconnect")
        return _("Disconnection started")

    def forget_network(self, ssid: str, network_path: str) -> str:
        if not ssid:
            logger.error("Network operation forget called without ssid")
            return ""

        saved = self._find_saved_connection(ssid)
        if not saved:
            raise NetworkManagerError(_("No saved profile found for this network"))

        device_path = self._get_wifi_device_path()
        if device_path:
            self._deactivate_if_selected(device_path, network_path)
        self._delete_connection(saved["path"])
        return _("Network profile removed")

    def set_wireless_enabled(self, enabled: bool) -> str:
        self._set_property(NM_PATH, NM_INTERFACE, "WirelessEnabled", "b", enabled)
        if enabled:
            return _("Wi-Fi enabled")
        return _("Wi-Fi disabled")

    def _build_networks(self, device_path: str) -> list[dict]:
        saved = self._get_saved_connections()
        saved_by_ssid = {item["ssid"]: item for item in saved if item["ssid"]}
        active_ap = self._get_active_access_point(device_path)
        networks = []
        ap_paths = self._extract_paths(
            self._call(device_path, f"{NM_WIRELESS_INTERFACE}.GetAllAccessPoints")
        )
        for ap_path in ap_paths:
            network = self._read_network(ap_path)
            if not network["ssid"]:
                continue

            saved_profile = saved_by_ssid.get(network["ssid"])
            network["saved"] = bool(saved_profile)
            network["saved_path"] = saved_profile["path"] if saved_profile else ""
            network["active"] = ap_path == active_ap
            network["state"] = self._get_network_state(network)
            networks.append(network)

        return sorted(networks, key=self._sort_network)

    def _read_network(self, ap_path: str) -> dict:
        ssid = self._decode_ssid(self._get_property(ap_path, NM_ACCESS_POINT_INTERFACE, "Ssid"))
        flags = self._extract_uint(self._get_property(ap_path, NM_ACCESS_POINT_INTERFACE, "Flags"))
        wpa_flags = self._extract_uint(
            self._get_property(ap_path, NM_ACCESS_POINT_INTERFACE, "WpaFlags")
        )
        rsn_flags = self._extract_uint(
            self._get_property(ap_path, NM_ACCESS_POINT_INTERFACE, "RsnFlags")
        )
        return {
            "path": ap_path,
            "ssid": ssid,
            "strength": self._extract_uint(
                self._get_property(ap_path, NM_ACCESS_POINT_INTERFACE, "Strength")
            ),
            "frequency": self._extract_uint(
                self._get_property(ap_path, NM_ACCESS_POINT_INTERFACE, "Frequency")
            ),
            "secured": bool((flags & 1) or wpa_flags or rsn_flags),
            "security": self._describe_security(flags, wpa_flags, rsn_flags),
        }

    def _get_saved_connections(self) -> list[dict]:
        return self._get_connections_by_type("802-11-wireless")

    def _build_vpns(self) -> list[dict]:
        active_connections = self._get_active_vpn_connections()
        vpns = []
        for connection_type in ("vpn", "wireguard"):
            for connection in self._get_connections_by_type(connection_type):
                connection["active"] = connection["uuid"] in active_connections
                connection["state"] = _("Connected") if connection["active"] else _("Disconnected")
                vpns.append(connection)
        return sorted(vpns, key=self._sort_vpn)

    def _get_connections_by_type(self, connection_type: str) -> list[dict]:
        raw = self._call(NM_SETTINGS_PATH, f"{NM_SETTINGS_INTERFACE}.ListConnections")
        connections = []
        for path in self._extract_paths(raw):
            settings = self._call(path, f"{NM_SETTINGS_CONNECTION_INTERFACE}.GetSettings")
            parsed = self._parse_connection_settings(settings)
            if parsed["type"] != connection_type:
                continue

            parsed["path"] = path
            connections.append(parsed)
        return connections

    def _get_active_vpn_connections(self) -> dict[str, str]:
        raw = self._get_property(NM_PATH, NM_INTERFACE, "ActiveConnections")
        active_connections = {}
        for active_path in self._extract_paths(raw):
            try:
                active_type = self._extract_string(
                    self._get_property(active_path, NM_ACTIVE_CONNECTION_INTERFACE, "Type")
                )
            except NetworkManagerError:
                continue
            if active_type not in {"vpn", "wireguard"}:
                continue
            uuid_value = self._extract_string(
                self._get_property(active_path, NM_ACTIVE_CONNECTION_INTERFACE, "Uuid")
            )
            if uuid_value:
                active_connections[uuid_value] = active_path
        return active_connections

    def _require_vpn(self, connection_path: str) -> dict:
        for vpn in self._build_vpns():
            if vpn["path"] == connection_path:
                return vpn
        raise NetworkManagerError(_("VPN profile not found"))

    def _find_saved_connection(self, ssid: str) -> dict | None:
        for connection in self._get_saved_connections():
            if connection["ssid"] == ssid:
                return connection
        return None

    def _get_saved_connection_password(self, ssid: str) -> str:
        saved = self._find_saved_connection(ssid)
        if not saved:
            return ""
        try:
            raw = self._call(
                saved["path"],
                f"{NM_SETTINGS_CONNECTION_INTERFACE}.GetSecrets",
                "802-11-wireless-security",
            )
            if isinstance(raw, dict):
                group = raw.get("802-11-wireless-security", {})
                psk = self._extract_string(group.get("psk", ""))
            else:
                psk = self._search_group(str(raw), r"'psk': <'([^']*)'>")
            return psk or ""
        except Exception:
            logger.exception("Failed to get saved password for SSID: %s", ssid)
            return ""

    def _get_wifi_device_path(self) -> str:
        raw = self._call(NM_PATH, f"{NM_INTERFACE}.GetAllDevices")
        for path in self._extract_paths(raw):
            device_type = self._extract_uint(
                self._get_property(path, NM_DEVICE_INTERFACE, "DeviceType")
            )
            if device_type == NM_WIFI_DEVICE_TYPE:
                return path
        return ""

    def _require_wifi_device_path(self) -> str:
        device_path = self._get_wifi_device_path()
        if not device_path:
            raise NetworkManagerError(_("Wi-Fi device not found"))
        return device_path

    def _get_active_access_point(self, device_path: str) -> str:
        active_ap = self._extract_first_path(
            self._get_property(device_path, NM_WIRELESS_INTERFACE, "ActiveAccessPoint")
        )
        if active_ap and active_ap != "/":
            return active_ap

        active_connection = self._extract_first_path(
            self._get_property(device_path, NM_DEVICE_INTERFACE, "ActiveConnection")
        )
        if not active_connection or active_connection == "/":
            return ""

        return self._extract_first_path(
            self._get_property(
                active_connection,
                NM_ACTIVE_CONNECTION_INTERFACE,
                "SpecificObject",
            )
        )

    def _deactivate_if_selected(self, device_path: str, network_path: str) -> None:
        active_connection = self._extract_first_path(
            self._get_property(device_path, NM_DEVICE_INTERFACE, "ActiveConnection")
        )
        active_ap = self._get_active_access_point(device_path)
        if network_path and active_ap == network_path and active_connection != "/":
            self._call(NM_PATH, f"{NM_INTERFACE}.DeactivateConnection", active_connection)

    def _delete_connection(self, connection_path: str) -> None:
        self._call(connection_path, f"{NM_SETTINGS_CONNECTION_INTERFACE}.Delete")

    def _build_connection_settings(self, ssid: str, password: str, secured: bool) -> dict:
        connection_uuid = str(uuid.uuid4())
        wireless_settings = {
            "mode": Variant("s", "infrastructure"),
            "ssid": Variant("ay", bytes(ssid.encode("utf-8"))),
        }
        settings = {
            "connection": {
                "id": Variant("s", ssid),
                "type": Variant("s", "802-11-wireless"),
                "uuid": Variant("s", connection_uuid),
                "autoconnect": Variant("b", True),
            },
            "802-11-wireless": wireless_settings,
            "ipv4": {"method": Variant("s", "auto")},
            "ipv6": {"method": Variant("s", "auto")},
        }
        if secured:
            wireless_settings["security"] = Variant("s", "802-11-wireless-security")
            settings["802-11-wireless-security"] = {
                "key-mgmt": Variant("s", "wpa-psk"),
                "psk": Variant("s", password),
            }
        return settings

    def _call(self, object_path: str, method: str, *args):
        interface_name, member = method.rsplit(".", 1)
        try:
            return self.dbus.call(
                NM_SERVICE,
                object_path,
                interface_name,
                member,
                *args,
            )
        except NetworkManagerError as exc:
            raise NetworkManagerError(self._clean_error(str(exc))) from exc

    def _get_property(self, object_path: str, interface: str, prop: str):
        return self.dbus.get_property(
            NM_SERVICE,
            object_path,
            interface,
            prop,
        )

    def _set_property(
        self,
        object_path: str,
        interface: str,
        prop: str,
        signature: str,
        value,
    ) -> None:
        self.dbus.set_property(
            NM_SERVICE,
            object_path,
            interface,
            prop,
            signature,
            value,
        )

    def _parse_connection_settings(self, raw) -> dict:
        if isinstance(raw, dict):
            connection_id = self._extract_string(self._setting_value(raw, "connection", "id"))
            connection_type = self._extract_string(self._setting_value(raw, "connection", "type"))
            ssid = self._decode_ssid(self._setting_value(raw, "802-11-wireless", "ssid"))
            return {
                "id": connection_id,
                "ssid": ssid or connection_id,
                "type": connection_type,
                "uuid": self._extract_string(self._setting_value(raw, "connection", "uuid")),
                "vpn_type": self._extract_vpn_type(raw, connection_type),
            }
        ssid = self._decode_ssid(raw)
        connection_id = self._search_group(raw, r"'id': <'([^']*)'>")
        connection_type = self._search_group(raw, r"'type': <'([^']*)'>")
        return {
            "id": connection_id,
            "ssid": ssid or connection_id,
            "type": connection_type,
            "uuid": self._search_group(raw, r"'uuid': <'([^']*)'>"),
            "vpn_type": self._extract_vpn_type(raw, connection_type),
        }

    def _extract_vpn_type(self, raw, connection_type: str) -> str:
        if connection_type == "wireguard":
            return "WireGuard"
        if connection_type != "vpn":
            return connection_type or "VPN"
        if isinstance(raw, dict):
            service_type = self._extract_string(self._setting_value(raw, "vpn", "service-type"))
        else:
            service_type = self._search_group(raw, r"'service-type': <'([^']*)'>")
        if service_type.endswith(".openvpn"):
            return "OpenVPN"
        if service_type.endswith(".wireguard"):
            return "WireGuard"
        return "VPN"

    def _detect_vpn_import_type(self, config_path: str) -> str:
        suffix = os.path.splitext(config_path)[1].lower()
        if suffix == ".ovpn":
            return "openvpn"

        try:
            with open(config_path, encoding="utf-8", errors="replace") as config_file:
                for line in config_file:
                    token = line.strip().lower()
                    if not token or token.startswith(("#", ";")):
                        continue
                    if token == "[interface]" or token.startswith("[peer]"):
                        return "wireguard"
                    if token.startswith(("client", "remote ", "proto ", "dev ")):
                        return "openvpn"
        except OSError as exc:
            raise NetworkManagerError(_("Failed to read VPN config file")) from exc

        return "wireguard" if suffix == ".conf" else "openvpn"

    def _describe_security(self, flags: int, wpa_flags: int, rsn_flags: int) -> str:
        if not ((flags & 1) or wpa_flags or rsn_flags):
            return _("Open")
        if wpa_flags and rsn_flags:
            return "WPA/WPA2"
        if rsn_flags:
            return "WPA2/WPA3"
        if wpa_flags:
            return "WPA"
        return _("Protected")

    def _get_network_state(self, network: dict) -> str:
        if network["active"]:
            return _("Connected")
        if network["saved"]:
            return _("Saved")
        return _("Available")

    def _sort_network(self, network: dict) -> tuple:
        return (
            0 if network["active"] else 1,
            0 if network["saved"] else 1,
            -network["strength"],
            network["ssid"].lower(),
        )

    def _sort_vpn(self, vpn: dict) -> tuple[int, str]:
        return (0 if vpn["active"] else 1, vpn["id"].lower())

    def _decode_ssid(self, raw) -> str:
        unwrapped = self._unwrap_variant(raw)
        if isinstance(unwrapped, (bytes, bytearray)):
            return bytes(unwrapped).decode("utf-8", errors="replace")
        if isinstance(unwrapped, list):
            byte_values = [value for value in unwrapped if isinstance(value, int)]
            if not byte_values:
                return ""
            return bytes(byte_values).decode("utf-8", errors="replace")
        raw_text = unwrapped if isinstance(unwrapped, str) else str(unwrapped)
        byte_values = re.findall(r"0x([0-9a-fA-F]{2})", raw_text)
        if not byte_values:
            return ""

        ssid_bytes = bytes(int(byte_value, 16) for byte_value in byte_values)
        return ssid_bytes.decode("utf-8", errors="replace")

    def _extract_paths(self, raw) -> list[str]:
        unwrapped = self._unwrap_variant(raw)
        if isinstance(unwrapped, str):
            if unwrapped.startswith("/"):
                return [unwrapped]
            return re.findall(r"'(/[^']+)'", unwrapped)
        if isinstance(unwrapped, (list, tuple)):
            paths = []
            for value in unwrapped:
                path = self._extract_string(value)
                if path.startswith("/"):
                    paths.append(path)
            return paths
        return []

    def _extract_first_path(self, raw) -> str:
        paths = self._extract_paths(raw)
        return paths[0] if paths else ""

    def _extract_string(self, raw) -> str:
        unwrapped = self._unwrap_variant(raw)
        if isinstance(unwrapped, str):
            return unwrapped
        if isinstance(unwrapped, (bytes, bytearray)):
            return bytes(unwrapped).decode("utf-8", errors="replace")
        return self._search_group(str(unwrapped), r"<\'([^']*)\'>")

    def _extract_uint(self, raw) -> int:
        unwrapped = self._unwrap_variant(raw)
        if isinstance(unwrapped, bool):
            return int(unwrapped)
        if isinstance(unwrapped, int):
            return unwrapped
        if isinstance(unwrapped, (bytes, bytearray)) and len(unwrapped) == 1:
            return int(bytes(unwrapped)[0])
        raw_text = str(unwrapped)
        byte_match = re.search(r"byte 0x([0-9a-fA-F]{2})", raw_text)
        if byte_match:
            return int(byte_match.group(1), 16)

        number_match = re.search(r"(?:uint\d+|int\d+)\s+(-?\d+)", raw_text)
        if number_match:
            return int(number_match.group(1))
        return 0

    def _extract_bool(self, raw) -> bool:
        unwrapped = self._unwrap_variant(raw)
        if isinstance(unwrapped, bool):
            return unwrapped
        raw_text = str(unwrapped)
        return "<true>" in raw_text or raw_text.endswith("true)")

    def _setting_value(self, raw: dict, section: str, key: str):
        section_dict = raw.get(section, {})
        if not isinstance(section_dict, dict):
            return ""
        return section_dict.get(key, "")

    def _unwrap_variant(self, value):
        if isinstance(value, Variant):
            return value.value
        return value

    def _search_group(self, raw: str, pattern: str) -> str:
        match = re.search(pattern, raw)
        return match.group(1) if match else ""

    def _clean_error(self, error_text: str) -> str:
        cleaned = error_text.split(":", 1)[-1].strip()
        if cleaned:
            return cleaned
        logger.error("NetworkManager operation failed without detailed error")
        return ""
