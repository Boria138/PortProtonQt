"""Bluetooth manager worker and service."""

import os
import re
import select
import shutil
import subprocess
import threading
import time

from PySide6.QtCore import QThread, Signal

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
    """Minimal bluetoothctl wrapper for adapter and device management."""

    def __init__(self, request_pairing_response=None) -> None:
        self.bluetoothctl_path = shutil.which("bluetoothctl")
        if not self.bluetoothctl_path:
            raise NetworkManagerError("bluetoothctl is not available")
        self.dbus: DbusFastSystemBus | None = None
        self.request_pairing_response = request_pairing_response

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
            if self.dbus is not None:
                self.dbus.close()
                self.dbus = None

    def _sleep_if_needed(self, seconds: int) -> None:
        """Sleep in small increments to allow thread interruption."""
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
            raise NetworkManagerError(_("Unsupported Bluetooth operation"))

    def list_devices(self, discovered: list[tuple[str, str]] | None = None) -> dict:
        show_output = self._run_commands(["show"])
        list_output = self._run_commands(["list"])
        has_controller = bool(re.search(r"Controller\s+[0-9A-F:]{17}\b", list_output))
        available = "No default controller available" not in show_output and has_controller
        payload = {
            "available": available,
            "powered": False,
            "adapter_name": "",
            "devices": [],
        }
        if not available:
            return payload

        payload["powered"] = self._extract_bluetooth_bool(show_output, "Powered")
        payload["adapter_name"] = self._extract_bluetooth_value(show_output, "Name")
        payload["devices"] = self._build_devices(discovered)
        return payload

    def scan_devices(self) -> dict:
        self._require_adapter()
        self._require_powered()
        discovered = self._scan_nearby_devices()
        return self.list_devices(discovered)

    def set_powered(self, enabled: bool) -> None:
        self._require_adapter()
        state = "on" if enabled else "off"
        output = self._run_commands([f"power {state}"])
        if "Failed" in output:
            raise NetworkManagerError(self._extract_bluetooth_error(output))
        logger.info("Bluetooth %s", "enabled" if enabled else "disabled")

    def connect_device(self, address: str) -> None:
        if not address:
            logger.error("Bluetooth operation connect called without address")
            return
        device = self._require_device(address)
        self._require_powered()
        if not device["paired"]:
            try:
                self._pair_device(address)
            except NetworkManagerError as exc:
                device = self._resolve_paired_device(device)
                if not device["paired"]:
                    raise exc
        else:
            device = self._resolve_paired_device(device)

        target_address = device["address"]
        # Trust device before connecting
        self._run_commands([f"trust {target_address}"])
        output = self._run_commands([f"connect {target_address}"])
        if "Connection successful" in output:
            logger.info("Bluetooth device connected")
            return
        if device["connected"]:
            logger.info("Bluetooth device already connected")
            return
        raise NetworkManagerError(self._extract_bluetooth_error(output))

    def disconnect_device(self, address: str) -> None:
        if not address:
            logger.error("Bluetooth operation disconnect called without address")
            return
        device = self._require_device(address)
        if not device["connected"]:
            raise NetworkManagerError(_("The selected Bluetooth device is not connected"))
        output = self._run_commands([f"disconnect {address}"])
        if "Successful disconnected" in output or "disconnect successful" in output.lower():
            logger.info("Bluetooth device disconnected")
            return
        if "Failed" in output:
            raise NetworkManagerError(self._extract_bluetooth_error(output))
        logger.info("Bluetooth device disconnected")

    def forget_device(self, address: str) -> None:
        if not address:
            logger.error("Bluetooth operation forget called without address")
            return
        self._require_device(address)
        output = self._run_commands([f"remove {address}"])
        if "Device has been removed" in output:
            logger.info("Bluetooth device removed")
            return
        raise NetworkManagerError(self._extract_bluetooth_error(output))

    def _build_devices(self, discovered: list[tuple[str, str]] | None = None) -> list[dict]:
        device_map = dict(self._list_known_devices())
        for address, name in discovered or []:
            if address not in device_map or not device_map[address]:
                device_map[address] = name

        battery_levels = self._get_bluetooth_battery_levels()
        devices = []
        for address, name in device_map.items():
            info_output = self._run_commands([f"info {address}"])
            devices.append(
                {
                    "address": address,
                    "name": name or address,
                    "paired": self._extract_bluetooth_bool(info_output, "Paired"),
                    "trusted": self._extract_bluetooth_bool(info_output, "Trusted"),
                    "connected": self._extract_bluetooth_bool(info_output, "Connected"),
                    "icon": self._extract_bluetooth_value(info_output, "Icon"),
                    "address_type": self._extract_bluetooth_address_type(info_output),
                    "battery": battery_levels.get(address.upper(), ""),
                    "state": self._get_bluetooth_state(info_output),
                }
            )
        devices = self._filter_duplicate_bluetooth_devices(devices)
        return sorted(devices, key=self._sort_bluetooth_device)

    def _scan_nearby_devices(self) -> list[tuple[str, str]]:
        bluetoothctl_path = self.bluetoothctl_path
        if bluetoothctl_path is None:
            raise NetworkManagerError("bluetoothctl is not available")
        process = subprocess.Popen(
            [bluetoothctl_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        try:
            self._write_process_command(process, "scan on")
            # Sleep in increments to allow interruption
            for _counter in range(50):  # 10 seconds total
                time.sleep(0.2)
                if process.poll() is not None:
                    break
            session_output = self._finish_bluetooth_scan(process)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
        return list(self._parse_bluetooth_devices(session_output).items())

    def _finish_bluetooth_scan(self, process: subprocess.Popen) -> str:
        if process.stdin is None:
            raise NetworkManagerError(_("Bluetooth control channel is unavailable"))

        process.stdin.write("devices\n")
        process.stdin.write("scan off\n")
        process.stdin.write("quit\n")
        process.stdin.flush()
        try:
            stdout, _stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            stdout, _stderr = process.communicate()
            raise NetworkManagerError(_("Bluetooth scan timed out")) from exc
        return self._strip_ansi(stdout or "")

    def _parse_bluetooth_devices(self, output: str) -> dict[str, str]:
        devices = {}
        for line in output.splitlines():
            match = re.search(r"Device\s+([0-9A-F:]{17})\s+(.+)$", line.strip())
            if match:
                devices[match.group(1)] = match.group(2).strip()
        return devices

    def _list_known_devices(self) -> list[tuple[str, str]]:
        output = self._run_commands(["devices"])
        devices = []
        for line in output.splitlines():
            match = re.match(r"Device\s+([0-9A-F:]{17})\s+(.+)$", line.strip())
            if match:
                devices.append((match.group(1), match.group(2).strip()))
        return devices

    def _require_adapter(self) -> None:
        payload = self.list_devices()
        if not payload["available"]:
            raise NetworkManagerError(_("Bluetooth adapter not found"))

    def _require_powered(self) -> None:
        payload = self.list_devices()
        if not payload["powered"]:
            raise NetworkManagerError(_("Bluetooth is disabled"))

    def _require_device(self, address: str) -> dict:
        for device in self.list_devices()["devices"]:
            if device["address"] == address:
                return device
        raise NetworkManagerError(_("Bluetooth device not found"))

    def _resolve_paired_device(self, device: dict) -> dict:
        devices = self.list_devices()["devices"]
        preferred_device = device
        for candidate in devices:
            if candidate["address"] == device["address"]:
                preferred_device = candidate
                continue
            if candidate["name"] != device["name"]:
                continue
            if not (candidate["paired"] or candidate["trusted"] or candidate["connected"]):
                continue
            if self._compare_bluetooth_device_priority(candidate, preferred_device) < 0:
                preferred_device = candidate
        return preferred_device

    def _pair_device(self, address: str) -> None:
        output = self._run_pairing_session(address)
        if "Pairing successful" in output:
            # Trust and connect after successful pairing
            self._run_commands([f"trust {address}"])
            self._sleep_if_needed(1)
            connect_output = self._run_commands([f"connect {address}"])
            if "Connection successful" in connect_output:
                logger.info("Auto-connected to %s after pairing", address)
            # Wait before returning so UI can refresh device state
            self._sleep_if_needed(2)
            return
        raise NetworkManagerError(self._extract_bluetooth_error(output))

    def _start_pairing_process(self, address: str) -> subprocess.Popen:
        bluetoothctl_path = self.bluetoothctl_path
        if bluetoothctl_path is None:
            raise NetworkManagerError("bluetoothctl is not available")
        process = subprocess.Popen(
            [bluetoothctl_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self._write_process_command(process, "agent DisplayYesNo")
        self._write_process_command(process, "default-agent")
        self._write_process_command(process, f"pair {address}")
        return process

    def _read_pairing_chunk(self, process: subprocess.Popen) -> str:
        if process.stdout is None:
            raise NetworkManagerError(_("Bluetooth output channel is unavailable"))
        ready, _write_ready, _error_ready = select.select([process.stdout], [], [], 0.2)
        if not ready:
            return ""
        chunk = os.read(process.stdout.fileno(), 4096).decode("utf-8", errors="replace")
        return self._strip_ansi(chunk)

    def _process_pairing_output(self, output_text: str, last_request: str, process: subprocess.Popen) -> tuple[str, str]:
        parsed_lines = self._extract_pairing_lines(output_text)
        if parsed_lines:
            output_text = "\n".join(parsed_lines)
        request = self._parse_pairing_output(output_text, last_request)
        if request is None:
            return output_text, last_request
        last_request = request["message"]
        response = self._get_pairing_response(request)
        self._write_process_command(process, response)
        # Clear output after sending response to avoid re-parsing old messages
        return "", last_request

    def _pairing_finished(self, output_text: str) -> bool:
        if "Pairing successful" in output_text:
            return True
        return any(
            text in output_text
            for text in ["Failed to pair", "AuthenticationFailed", "AuthenticationCanceled"]
        )

    def _run_pairing_session(self, address: str) -> str:
        process = self._start_pairing_process(address)
        output_text = ""
        last_request = ""
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                chunk = self._read_pairing_chunk(process)
                if not chunk:
                    if process.poll() is None:
                        continue
                    break
                output_text += chunk
                output_text, last_request = self._process_pairing_output(
                    output_text,
                    last_request,
                    process,
                )
                if self._pairing_finished(output_text):
                    break
        finally:
            try:
                self._write_process_command(process, "quit")
            except (NetworkManagerError, OSError):
                pass
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        return output_text

    def _extract_pairing_lines(self, output: str) -> list[str]:
        lines = []
        for raw_line in output.splitlines():
            cleaned_line = raw_line.strip()
            if cleaned_line:
                lines.append(cleaned_line)
        return lines

    def _get_pairing_response(self, request: dict) -> str:
        if self.request_pairing_response is None:
            raise NetworkManagerError(_("Bluetooth pairing requires user confirmation"))
        response = self.request_pairing_response(request).strip()
        if request["kind"] == "confirm":
            return "yes" if response == "yes" else "no"
        if not response:
            raise NetworkManagerError(_("Bluetooth pairing cancelled"))
        return response

    def _parse_pairing_output(self, output: str, last_request: str) -> dict | None:
        # Handle "Confirm passkey 123456 (yes/no):" from DisplayYesNo agent
        passkey_match = re.search(r"Confirm passkey\s+(\d+)", output)
        if passkey_match:
            request = {
                "kind": "confirm",
                "title": _("Bluetooth pairing"),
                "message": _("Confirm the passkey on the device: {0}").format(passkey_match.group(1)),
            }
            return None if request["message"] == last_request else request

        # Handle "Passkey: 123456" from agent
        passkey_display_match = re.search(r"Passkey:\s*(\d+)", output)
        if passkey_display_match:
            request = {
                "kind": "confirm",
                "title": _("Bluetooth pairing"),
                "message": _("Confirm the passkey on the phone: {0}").format(
                    passkey_display_match.group(1)
                ),
            }
            return None if request["message"] == last_request else request

        # Handle "Request confirmation" prompt
        if "Request confirmation" in output:
            request = {
                "kind": "confirm",
                "title": _("Bluetooth pairing"),
                "message": _("Confirm pairing on the device?"),
            }
            return None if request["message"] == last_request else request

        if "Authorize service" in output:
            request = {
                "kind": "confirm",
                "title": _("Bluetooth authorization"),
                "message": _("Authorize the Bluetooth service on the device?"),
            }
            return None if request["message"] == last_request else request

        if "Enter PIN code" in output or "Request PIN code" in output:
            request = {
                "kind": "input",
                "title": _("Bluetooth PIN code"),
                "message": _("Enter the Bluetooth PIN code shown on the device"),
            }
            return None if request["message"] == last_request else request

        if "Enter passkey" in output or "Request passkey" in output:
            request = {
                "kind": "input",
                "title": _("Bluetooth passkey"),
                "message": _("Enter the Bluetooth passkey shown on the device"),
            }
            return None if request["message"] == last_request else request
        return None

    def _run_commands(self, commands: list[str]) -> str:
        bluetoothctl_path = self.bluetoothctl_path
        if bluetoothctl_path is None:
            raise NetworkManagerError("bluetoothctl is not available")
        try:
            process = subprocess.run(
                [bluetoothctl_path],
                input="\n".join([*commands, "quit"]) + "\n",
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except subprocess.TimeoutExpired as exc:
            raise NetworkManagerError(_("Bluetooth command timed out")) from exc
        output = self._strip_ansi((process.stdout or "") + (process.stderr or ""))
        if process.returncode != 0 and output.strip():
            raise NetworkManagerError(self._extract_bluetooth_error(output))
        return output

    def _write_process_command(self, process: subprocess.Popen, command: str) -> None:
        if process.stdin is None:
            raise NetworkManagerError(_("Bluetooth control channel is unavailable"))
        payload = f"{command}\n"
        try:
            process.stdin.write(payload)
        except TypeError:
            process.stdin.write(payload.encode("utf-8"))
        process.stdin.flush()

    def _extract_bluetooth_value(self, output: str, key: str) -> str:
        match = re.search(rf"{re.escape(key)}:\s*(.+)$", output, re.MULTILINE)
        return match.group(1).strip() if match else ""

    def _extract_bluetooth_address_type(self, output: str) -> str:
        match = re.search(r"Device\s+[0-9A-F:]{17}\s+\(([^)]+)\)", output)
        return match.group(1).strip() if match else ""

    def _extract_bluetooth_bool(self, output: str, key: str) -> bool:
        value = self._extract_bluetooth_value(output, key).lower()
        return value == "yes"

    def _get_bluetooth_state(self, output: str) -> str:
        if self._extract_bluetooth_bool(output, "Connected"):
            return _("Connected")
        if self._extract_bluetooth_bool(output, "Paired"):
            return _("Paired")
        return _("Available")

    def _sort_bluetooth_device(self, device: dict) -> tuple:
        return (
            0 if device["connected"] else 1,
            0 if device["paired"] else 1,
            0 if device["address_type"] == "public" else 1,
            device["name"].lower(),
            device["address"],
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

    def _extract_bluetooth_error(self, output: str) -> str:
        for line in reversed(output.splitlines()):
            cleaned_line = line.strip()
            if cleaned_line.startswith("Failed") or "not available" in cleaned_line.lower():
                return cleaned_line
        cleaned_output = output.strip()
        if cleaned_output:
            return cleaned_output.splitlines()[-1].strip()
        logger.error("Bluetooth operation failed without detailed error")
        return ""

    def _strip_ansi(self, text: str) -> str:
        return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)

    def _get_bluetooth_battery_levels(self) -> dict[str, str]:
        if self.dbus is None:
            try:
                self.dbus = DbusFastSystemBus()
            except NetworkManagerError:
                return {}

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
        if self.dbus is None:
            return ""
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
        if self.dbus is None:
            return ""
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
