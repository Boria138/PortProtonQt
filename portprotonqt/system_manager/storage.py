"""Storage manager worker and service."""

import os
import time

from PySide6.QtCore import QThread, Signal

from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.system_manager.common import DbusFastSystemBus, NetworkManagerError, Variant

logger = get_logger(__name__)

class StorageManagerWorker(QThread):
    """Run storage actions outside the UI thread."""

    operation_finished = Signal(str, dict)
    operation_failed = Signal(str, str)

    def __init__(self, operation: str, params: dict | None = None, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.params = params or {}

    def run(self) -> None:
        try:
            service = StorageManagerService()
            payload = service.execute(self.operation, self.params)
        except NetworkManagerError as exc:
            self.operation_failed.emit(self.operation, str(exc))
            return
        except Exception as exc:
            logger.exception("Unexpected storage operation failure: %s", exc)
            self.operation_failed.emit(self.operation, "Unexpected storage error")
            return

        self.operation_finished.emit(self.operation, payload)


class StorageManagerService:
    """Minimal UDisks2 wrapper for removable devices via system D-Bus."""

    UDISKS_SERVICE = "org.freedesktop.UDisks2"
    UDISKS_PATH = "/org/freedesktop/UDisks2"
    OBJECT_MANAGER_INTERFACE = "org.freedesktop.DBus.ObjectManager"
    FILESYSTEM_INTERFACE = "org.freedesktop.UDisks2.Filesystem"
    BLOCK_INTERFACE = "org.freedesktop.UDisks2.Block"
    DRIVE_INTERFACE = "org.freedesktop.UDisks2.Drive"
    PARTITION_INTERFACE = "org.freedesktop.UDisks2.Partition"

    def __init__(self) -> None:
        self.dbus = DbusFastSystemBus()

    def execute(self, operation: str, params: dict) -> dict:
        try:
            if operation == "load":
                return self.list_devices()

            self._run_operation(operation, params)
            time.sleep(1)
            return self.list_devices()
        finally:
            self.dbus.close()

    def _run_operation(self, operation: str, params: dict) -> None:
        if operation == "mount":
            self.mount_device(params.get("device_path", ""))
        elif operation == "unmount":
            self.unmount_device(params.get("device_path", ""))
        else:
            raise NetworkManagerError("Unsupported storage operation")

    def list_devices(self) -> dict:
        objects = self._get_managed_objects()
        devices = self._collect_storage_devices(objects)
        return {
            "available": True,
            "devices": devices,
        }

    def mount_device(self, device_path: str) -> None:
        if not device_path:
            logger.error("Storage operation mount called without device_path")
            return
        objects = self._get_managed_objects()
        device = self._require_device(device_path, objects)
        if device["mounted"]:
            raise NetworkManagerError("The selected device is already mounted")
        self._call_filesystem_method(device["object_path"], "Mount")
        logger.info("Device mounted")

    def unmount_device(self, device_path: str) -> None:
        if not device_path:
            logger.error("Storage operation unmount called without device_path")
            return
        objects = self._get_managed_objects()
        device = self._require_device(device_path, objects)
        if not device["mounted"]:
            raise NetworkManagerError("The selected device is not mounted")
        self._call_filesystem_method(device["object_path"], "Unmount")
        logger.info("Device unmounted")

    def _get_managed_objects(self) -> dict:
        managed_objects = self.dbus.call(
            self.UDISKS_SERVICE,
            self.UDISKS_PATH,
            self.OBJECT_MANAGER_INTERFACE,
            "GetManagedObjects",
        )
        if not isinstance(managed_objects, dict):
            raise NetworkManagerError("Failed to parse storage device list")
        return managed_objects

    def _collect_storage_devices(self, objects: dict) -> list[dict]:
        devices = []
        for object_path, interfaces in objects.items():
            if not self._is_mountable_storage_device(interfaces, objects):
                continue
            devices.append(self._build_storage_device(object_path, interfaces, objects))
        return sorted(devices, key=self._sort_storage_device)

    def _is_mountable_storage_device(self, interfaces: dict, objects: dict) -> bool:
        block = interfaces.get(self.BLOCK_INTERFACE)
        if not block or self.FILESYSTEM_INTERFACE not in interfaces:
            return False
        if self._variant_data(block, "HintIgnore", False):
            return False
        if self._variant_data(block, "IdUsage") != "filesystem":
            return False
        if self._is_critical_mount_point(self._normalize_mount_point(interfaces, include_root=True)):
            return False
        return True

    def _build_storage_device(self, object_path: str, interfaces: dict, objects: dict) -> dict:
        block = interfaces.get(self.BLOCK_INTERFACE, {})
        drive = self._get_drive_interface(interfaces, objects)
        partition = interfaces.get(self.PARTITION_INTERFACE, {})
        mount_point = self._normalize_mount_point(interfaces)
        size_value = self._variant_data(block, "Size", 0)
        used_size = self._get_used_storage_size(mount_point, size_value)
        label = (
            self._variant_data(block, "IdLabel")
            or self._variant_data(partition, "Name")
            or self._variant_data(drive, "Model")
            or self._decode_byte_string(self._variant_data(block, "PreferredDevice", []))
        )
        return {
            "object_path": object_path,
            "path": self._decode_byte_string(self._variant_data(block, "PreferredDevice", [])),
            "label": label,
            "size": self._format_size(size_value if isinstance(size_value, int) else 0),
            "used": self._format_size(used_size) if used_size is not None else "—",
            "fstype": self._variant_data(block, "IdType"),
            "mount_point": mount_point,
            "mounted": bool(mount_point),
            "state": _("Mounted") if mount_point else _("Not mounted"),
        }

    def _get_used_storage_size(self, mount_point: str, size_value) -> int | None:
        if not mount_point:
            return None
        if not isinstance(size_value, int) or size_value <= 0:
            return None
        try:
            fs_stats = os.statvfs(mount_point)
        except OSError as exc:
            logger.debug("Failed to read storage usage for %s: %s", mount_point, exc)
            return None
        free_size = fs_stats.f_bavail * fs_stats.f_frsize
        used_size = max(0, size_value - free_size)
        return min(used_size, size_value)

    def _normalize_mount_point(self, interfaces: dict, include_root: bool = False) -> str:
        filesystem = interfaces.get(self.FILESYSTEM_INTERFACE, {})
        mount_points = self._variant_data(filesystem, "MountPoints", [])
        if not isinstance(mount_points, list):
            return ""
        for mount_point in mount_points:
            decoded_mount_point = self._decode_byte_string(mount_point)
            if decoded_mount_point and (include_root or decoded_mount_point != "/"):
                return decoded_mount_point
        return ""

    def _is_critical_mount_point(self, mount_point: str) -> bool:
        return mount_point in {"/", "/boot", "/boot/efi"}

    def _require_device(self, device_path: str, objects: dict) -> dict:
        for device in self._collect_storage_devices(objects):
            if device["path"] == device_path:
                return device
        raise NetworkManagerError("Storage device not found")

    def _call_filesystem_method(self, object_path: str, method_name: str) -> None:
        self.dbus.call(
            self.UDISKS_SERVICE,
            object_path,
            self.FILESYSTEM_INTERFACE,
            method_name,
            {},
        )

    def _get_drive_interface(self, interfaces: dict, objects: dict) -> dict:
        block = interfaces.get(self.BLOCK_INTERFACE, {})
        drive_path = self._variant_data(block, "Drive", "/")
        if drive_path in ("", "/"):
            return {}
        return objects.get(drive_path, {}).get(self.DRIVE_INTERFACE, {})

    def _variant_data(self, interface: dict, key: str, default=None):
        value = interface.get(key)
        if isinstance(value, Variant):
            return getattr(value, "value", default)
        if not isinstance(value, dict):
            return default
        return value.get("data", default)

    def _decode_byte_string(self, value) -> str:
        if isinstance(value, (bytes, bytearray)):
            byte_values = bytes(value)
            return byte_values.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        if not isinstance(value, list):
            return ""
        byte_values = bytes(item for item in value if isinstance(item, int))
        return byte_values.split(b"\x00", 1)[0].decode("utf-8", errors="replace")

    def _format_size(self, size_bytes: int) -> str:
        if not isinstance(size_bytes, int) or size_bytes <= 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        size = float(size_bytes)
        for unit in units:
            if size < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024
        return "0 B"

    def _sort_storage_device(self, device: dict) -> tuple[int, str, str]:
        return (0 if device["mounted"] else 1, device["label"].lower(), device["path"])

    def _clean_storage_error(self, error_text: str) -> str:
        cleaned = (error_text or "").strip()
        if cleaned:
            return cleaned.splitlines()[-1]
        logger.error("Storage operation failed without detailed error")
        return ""
