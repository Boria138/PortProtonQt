"""Audio manager worker and service."""

import os
import re
import shutil
import subprocess
import time

from PySide6.QtCore import QThread, Signal

from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.system_manager.common import NetworkManagerError

logger = get_logger(__name__)

AUDIO_MAX_VOLUME = 150

class AudioManagerWorker(QThread):
    """Run audio actions outside the UI thread."""

    operation_finished = Signal(str, dict)
    operation_failed = Signal(str, str)

    def __init__(self, operation: str, params: dict | None = None, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.params = params or {}

    def run(self) -> None:
        service = AudioManagerService()
        try:
            payload = service.execute(self.operation, self.params)
        except NetworkManagerError as exc:
            self.operation_failed.emit(self.operation, str(exc))
            return
        except Exception as exc:
            logger.exception("Unexpected audio operation failure: %s", exc)
            self.operation_failed.emit(self.operation, "")
            return

        self.operation_finished.emit(self.operation, payload)


class AudioManagerService:
    """Minimal PulseAudio/PipeWire wrapper via pactl."""

    def __init__(self) -> None:
        self.pactl_path = shutil.which("pactl")

    def execute(self, operation: str, params: dict) -> dict:
        if operation == "load":
            return self.list_audio()

        message = self._run_operation(operation, params)
        if operation == "set_sink_volume":
            return {
                "available": True,
                "message": message,
                "volume_updated": True,
            }
        time.sleep(0.5)
        payload = self.list_audio()
        payload["message"] = message
        return payload

    def _run_operation(self, operation: str, params: dict) -> str:
        if operation == "set_default_sink":
            sink_name = params.get("sink_name", "")
            if not sink_name:
                logger.error("Audio operation set_default_sink called without sink_name")
                return ""
            self._run_pactl(["set-default-sink", sink_name])
            return _("Default output device updated")

        if operation == "set_sink_volume":
            sink_name = params.get("sink_name", "")
            volume = params.get("volume", 0)
            if not sink_name:
                logger.error("Audio operation set_sink_volume called without sink_name")
                return ""
            try:
                volume_value = int(volume)
            except (TypeError, ValueError) as exc:
                raise NetworkManagerError(_("Invalid volume value")) from exc
            volume_value = max(0, min(AUDIO_MAX_VOLUME, volume_value))
            self._run_pactl(["set-sink-volume", sink_name, f"{volume_value}%"])
            return _("Output volume updated")

        if operation == "set_default_source":
            source_name = params.get("source_name", "")
            if not source_name:
                logger.error("Audio operation set_default_source called without source_name")
                return ""
            self._run_pactl(["set-default-source", source_name])
            return _("Default input device updated")

        if operation == "set_card_profile":
            card_name = params.get("card_name", "")
            profile_name = params.get("profile_name", "")
            if not card_name:
                logger.error("Audio operation set_card_profile called without card_name")
                return ""
            if not profile_name:
                logger.error("Audio operation set_card_profile called without profile_name")
                return ""
            self._run_pactl(["set-card-profile", card_name, profile_name])
            return _("Audio profile updated")

        raise NetworkManagerError(_("Unsupported audio operation"))

    def list_audio(self) -> dict:
        if not self.pactl_path:
            return {
                "available": False,
                "status": "pactl is not available",
                "sinks": [],
                "sources": [],
                "cards": [],
                "default_sink": "",
                "default_source": "",
            }

        defaults = self._read_defaults()
        sink_descriptions = self._read_device_descriptions("sinks")
        sink_volumes = self._read_sink_volumes()
        source_descriptions = self._read_device_descriptions("sources")
        sinks = self._read_short_devices("sinks", defaults["sink"], sink_descriptions, sink_volumes)
        sources = self._read_short_devices("sources", defaults["source"], source_descriptions)
        cards = self._read_cards()
        return {
            "available": True,
            "status": "",
            "sinks": sinks,
            "sources": sources,
            "cards": cards,
            "default_sink": defaults["sink"],
            "default_source": defaults["source"],
        }

    def _read_defaults(self) -> dict:
        output = self._run_pactl(["info"])
        default_sink = ""
        default_source = ""
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Default Sink: "):
                default_sink = line.split(": ", 1)[1].strip()
            elif line.startswith("Default Source: "):
                default_source = line.split(": ", 1)[1].strip()
        return {"sink": default_sink, "source": default_source}

    def _read_device_descriptions(self, device_type: str) -> dict[str, str]:
        output = self._run_pactl(["list", device_type])
        descriptions: dict[str, str] = {}
        current_name = ""
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if line.startswith("Name: "):
                current_name = line.split(": ", 1)[1].strip()
                descriptions.setdefault(current_name, current_name)
                continue
            if line.startswith("Description: ") and current_name:
                descriptions[current_name] = line.split(": ", 1)[1].strip()
        return descriptions

    def _read_short_devices(
        self,
        device_type: str,
        default_name: str,
        descriptions: dict[str, str],
        volumes: dict[str, int] | None = None,
    ) -> list[dict]:
        output = self._run_pactl(["list", "short", device_type])
        devices = []
        volume_map = volumes or {}
        for raw_line in output.splitlines():
            if not raw_line.strip():
                continue
            columns = raw_line.split("\t")
            if len(columns) < 2:
                continue
            device_name = columns[1].strip()
            state_text = columns[4].strip() if len(columns) > 4 else _("Unknown")
            raw_description = descriptions.get(device_name, device_name)
            description = self._format_audio_device_description(device_name, raw_description)
            volume_value = volume_map.get(device_name)
            if volume_value is None and device_type == "sinks":
                volume_value = self._read_single_sink_volume(device_name)
            devices.append(
                {
                    "name": device_name,
                    "description": description,
                    "state": state_text,
                    "default": device_name == default_name,
                    "volume": volume_value if volume_value is not None else 0,
                }
            )
        return sorted(devices, key=lambda item: (0 if item["default"] else 1, item["description"].lower()))

    def _read_sink_volumes(self) -> dict[str, int]:
        output = self._run_pactl(["list", "sinks"])
        volumes: dict[str, int] = {}
        current_name = ""
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if line.startswith("Name: "):
                current_name = line.split(": ", 1)[1].strip()
                continue
            if not current_name or not line.startswith("Volume:"):
                continue
            volume_match = re.search(r"(\d+)%", line)
            if not volume_match:
                continue
            try:
                volume_value = int(volume_match.group(1))
            except ValueError:
                continue
            volumes[current_name] = max(0, min(AUDIO_MAX_VOLUME, volume_value))
        return volumes

    def _read_single_sink_volume(self, sink_name: str) -> int | None:
        if not sink_name:
            return None
        output = self._run_pactl(["get-sink-volume", sink_name])
        volume_match = re.search(r"(\d+)%", output)
        if not volume_match:
            return None
        try:
            volume_value = int(volume_match.group(1))
        except ValueError:
            return None
        return max(0, min(AUDIO_MAX_VOLUME, volume_value))

    def _format_audio_device_description(self, device_name: str, raw_description: str) -> str:
        description = (raw_description or "").strip()
        if description and description != device_name:
            return description

        normalized = device_name
        if normalized.startswith("alsa_output."):
            normalized = normalized[len("alsa_output."):]
        elif normalized.startswith("alsa_input."):
            normalized = normalized[len("alsa_input."):]
        elif normalized.startswith("bluez_output."):
            normalized = normalized[len("bluez_output."):]
        elif normalized.startswith("bluez_input."):
            normalized = normalized[len("bluez_input."):]

        normalized = normalized.replace(".monitor", "")
        normalized = normalized.replace(".", " ")
        normalized = normalized.replace("_", " ")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized:
            return device_name

        return normalized.title()

    def _read_cards(self) -> list[dict]:
        output = self._run_pactl(["list", "cards"])
        cards = []
        current_card = None
        in_profiles = False
        for raw_line in output.splitlines():
            line = raw_line.rstrip("\n")
            stripped = line.strip()
            if line.startswith("Card #"):
                current_card = self._flush_audio_card(cards, current_card)
                in_profiles = False
                continue
            if current_card is None:
                current_card = self._create_audio_card()
            if stripped.startswith("Name: "):
                current_card["name"] = stripped.split(": ", 1)[1].strip()
            elif stripped.startswith("Profiles:"):
                in_profiles = True
            elif stripped.startswith("Active Profile: "):
                current_card["active_profile"] = stripped.split(": ", 1)[1].strip()
                in_profiles = False
            elif stripped.startswith("Ports:"):
                in_profiles = False
            elif stripped.startswith("device.description = "):
                current_card["description"] = self._strip_quoted_value(stripped.split("=", 1)[1].strip())
            elif in_profiles and line.startswith("\t\t"):
                self._append_card_profile(current_card, stripped)
        current_card = self._flush_audio_card(cards, current_card)
        return cards

    def _flush_audio_card(self, cards: list[dict], current_card: dict | None) -> dict:
        if current_card and current_card.get("name"):
            if not current_card.get("description"):
                current_card["description"] = current_card["name"]
            cards.append(current_card)
        return self._create_audio_card()

    def _create_audio_card(self) -> dict:
        return {
            "name": "",
            "description": "",
            "active_profile": "",
            "profiles": [],
        }

    def _append_card_profile(self, card: dict, stripped_line: str) -> None:
        if ": " not in stripped_line:
            return
        profile_name, profile_details = stripped_line.split(": ", 1)
        clean_profile_name = profile_name.strip()
        if not clean_profile_name:
            return
        profile_description = profile_details.split(" (", 1)[0].strip()
        profile_available = self._parse_profile_availability(profile_details)
        card["profiles"].append(
            {
                "name": clean_profile_name,
                "description": profile_description or clean_profile_name,
                "available": profile_available,
            }
        )

    def _parse_profile_availability(self, profile_details: str) -> bool:
        available_match = re.search(r"available:\s*([a-zA-Z]+)", profile_details)
        if not available_match:
            return True
        availability = available_match.group(1).lower()
        return availability != "no"

    def _strip_quoted_value(self, value: str) -> str:
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            return value[1:-1]
        return value

    def _run_pactl(self, args: list[str]) -> str:
        if not self.pactl_path:
            raise NetworkManagerError("pactl is not available")
        process_env = os.environ.copy()
        process_env["LC_ALL"] = "C"
        process_env["LANG"] = "C"
        result = subprocess.run(
            [self.pactl_path, *args],
            capture_output=True,
            text=True,
            check=False,
            env=process_env,
        )
        if result.returncode == 0:
            return result.stdout
        error_text = result.stderr.strip() or result.stdout.strip()
        raise NetworkManagerError(self._clean_audio_error(error_text))

    def _clean_audio_error(self, error_text: str) -> str:
        cleaned = (error_text or "").strip()
        if cleaned:
            return cleaned.splitlines()[-1]
        logger.error("Audio operation failed without detailed error")
        return ""
