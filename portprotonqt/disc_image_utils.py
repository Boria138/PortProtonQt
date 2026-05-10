import os
import hashlib
import shutil
import stat
import subprocess
import tempfile
import shlex
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

SYNC_HEADER = b'\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00'
SYNC_HEADER_MDF = b'\x80\xc0\x80\x80\x80\x80\x80\xc0\x80\x80\x80\x80'
ISO_9660_SIG = b'\x01\x43\x44\x30\x30\x31\x01\x00'


class DiscImageManager:
    """Manager for disc image (ISO, MDF) conversion and extraction."""

    def __init__(self):
        self._iso_rw_paths: dict[str, str] = {}
        self._mdf_iso_paths: dict[str, str] = {}

    def _get_iso_rw_root(self, iso_path: str) -> str:
        """Return writable runtime path for ISO content."""
        runtime_dir = tempfile.gettempdir()
        normalized_iso = os.path.abspath(os.path.expanduser(iso_path))
        digest = hashlib.sha1(normalized_iso.encode("utf-8")).hexdigest()[:16]
        return os.path.join(runtime_dir, "PortProtonQt", "iso_rw", digest)

    def _get_mdf_iso_path(self, mdf_path: str) -> str:
        """Return temporary ISO path converted from MDF."""
        runtime_dir = tempfile.gettempdir()
        normalized_mdf = os.path.abspath(os.path.expanduser(mdf_path))
        digest = hashlib.sha1(normalized_mdf.encode("utf-8")).hexdigest()[:16]
        return os.path.join(runtime_dir, "PortProtonQt", "mdf_iso", f"{digest}.iso")

    def _get_7zip_binary(self) -> str | None:
        """Return preferred 7-Zip binary path."""
        seven_zip = shutil.which("7zz")
        if seven_zip:
            return seven_zip
        return shutil.which("7z")

    def _is_iso9660_file(self, file_path: str) -> bool:
        """Check if a file has an ISO 9660 volume descriptor."""
        try:
            with open(file_path, "rb") as file:
                file.seek(32768)
                return file.read(8) == ISO_9660_SIG
        except OSError as e:
            logger.error("Failed to read ISO 9660 signature for %s: %s", file_path, e)
            return False

    def _write_iso_from_mdf(self, mdf_path: str, iso_path: str) -> None:
        """Convert MDF to ISO using logic from test.py or legacy fallback."""
        with open(mdf_path, "rb") as source:
            source.seek(0)
            h0 = source.read(12)
            source.seek(2352)
            h2352 = source.read(12)

            if h0 == SYNC_HEADER:
                if h2352 == SYNC_HEADER_MDF:
                    sector_size = 2448
                elif h2352 == SYNC_HEADER:
                    sector_size = 2352
                else:
                    raise ValueError(f"Unknown SYNC format for {mdf_path}")

                source.seek(0, os.SEEK_END)
                num_sectors = source.tell() // sector_size
                source.seek(0)
                with open(iso_path, "wb") as target:
                    for _ in range(num_sectors):
                        sector_start = source.tell()
                        header = source.read(16)
                        if len(header) < 16:
                            break
                        mode = header[15]
                        data_offset = 24 if mode == 2 else 16
                        source.seek(sector_start + data_offset)
                        data = source.read(2048)
                        if len(data) < 2048:
                            break
                        target.write(data)
                        source.seek(sector_start + sector_size)
                return

        # Legacy fallback
        with open(mdf_path, "rb") as source, open(iso_path, "wb") as target:
            sector_index = 0
            while True:
                sector = source.read(2352)
                if not sector:
                    return
                if len(sector) != 2352:
                    raise ValueError(f"Truncated MDF sector at {sector_index}")
                mode = sector[15]
                if mode == 1:
                    target.write(sector[16:2064])
                elif mode == 2:
                    target.write(sector[24:2072])
                else:
                    raise ValueError(f"Unknown MDF sector mode {mode} at {sector_index}")
                sector_index += 1

    def _convert_mdf_to_iso(self, mdf_path: str) -> str | None:
        """Convert raw 2352-byte sector MDF to temporary ISO."""
        normalized_mdf = os.path.abspath(os.path.expanduser(mdf_path))
        if self._is_iso9660_file(normalized_mdf):
            return normalized_mdf

        iso_path = self._mdf_iso_paths.get(normalized_mdf, self._get_mdf_iso_path(normalized_mdf))
        stamp_path = f"{iso_path}.source_stamp"
        try:
            source_stamp = f"{os.path.getsize(normalized_mdf)}:{int(os.path.getmtime(normalized_mdf))}"
        except OSError as e:
            logger.error("Failed to read MDF metadata for %s: %s", normalized_mdf, e)
            return None

        if os.path.isfile(iso_path) and os.path.isfile(stamp_path):
            try:
                with open(stamp_path, encoding="utf-8") as file:
                    if file.read().strip() == source_stamp:
                        self._mdf_iso_paths[normalized_mdf] = iso_path
                        return iso_path
            except OSError:
                pass

        os.makedirs(os.path.dirname(iso_path), exist_ok=True)
        tmp_path = f"{iso_path}.tmp"
        try:
            self._write_iso_from_mdf(normalized_mdf, tmp_path)
            os.replace(tmp_path, iso_path)
            with open(stamp_path, "w", encoding="utf-8") as file:
                file.write(source_stamp)
        except (OSError, ValueError) as e:
            logger.error("Failed to convert MDF to ISO %s: %s", normalized_mdf, e)
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            return None

        self._mdf_iso_paths[normalized_mdf] = iso_path
        return iso_path

    def _get_mdf_sources(self, mdf_path: str) -> list[str]:
        """Return all MDF discs from the selected image directory."""
        normalized_mdf = os.path.abspath(os.path.expanduser(mdf_path))
        source_dir = os.path.dirname(normalized_mdf)
        try:
            sources = [
                os.path.join(source_dir, name)
                for name in os.listdir(source_dir)
                if name.lower().endswith(".mdf") and os.path.isfile(os.path.join(source_dir, name))
            ]
        except OSError as e:
            logger.error("Failed to list MDF directory %s: %s", source_dir, e)
            return [normalized_mdf]
        sources.sort(key=lambda path: os.path.basename(path).casefold())
        return sources or [normalized_mdf]

    def _get_disc_source_stamp(self, source_paths: list[str]) -> str | None:
        """Return metadata stamp for extracted disc image sources."""
        stamps = []
        for source_path in source_paths:
            try:
                stamps.append(f"{source_path}:{os.path.getsize(source_path)}:{int(os.path.getmtime(source_path))}")
            except OSError as e:
                logger.error("Failed to read disc image metadata for %s: %s", source_path, e)
                return None
        return "\n".join(stamps)

    def _ensure_writable_tree(self, root_dir: str):
        """Ensure user-write permissions for all files and directories in tree."""
        if not os.path.isdir(root_dir):
            return
        for current_root, dir_names, file_names in os.walk(root_dir, topdown=False):
            for name in file_names:
                path = os.path.join(current_root, name)
                try:
                    mode = os.stat(path, follow_symlinks=False).st_mode
                    os.chmod(path, mode | stat.S_IWUSR, follow_symlinks=False)
                except OSError:
                    continue
            for name in dir_names:
                path = os.path.join(current_root, name)
                try:
                    mode = os.stat(path, follow_symlinks=False).st_mode
                    os.chmod(path, mode | stat.S_IWUSR | stat.S_IXUSR, follow_symlinks=False)
                except OSError:
                    continue

    def _clear_disc_runtime_dir(self, rw_root: str) -> None:
        self._ensure_writable_tree(rw_root)
        for entry in os.scandir(rw_root):
            if entry.name == ".iso_source_stamp":
                continue
            if entry.is_dir(follow_symlinks=False):
                shutil.rmtree(entry.path)
            else:
                os.remove(entry.path)

    def _extract_iso_to_rw(self, seven_zip_binary: str, iso_path: str, rw_root: str, overwrite_mode: str) -> None:
        subprocess.run(
            [seven_zip_binary, "x", iso_path, f"-o{rw_root}", "-y", overwrite_mode],
            capture_output=True,
            text=True,
            check=True
        )

    def _sync_mdf_set_to_rw(self, mdf_path: str) -> str | None:
        """Extract all MDF discs from one directory to a shared runtime path."""
        normalized_mdf = os.path.abspath(os.path.expanduser(mdf_path))
        rw_root = self._iso_rw_paths.get(normalized_mdf, self._get_iso_rw_root(normalized_mdf))
        os.makedirs(rw_root, exist_ok=True)
        stamp_path = os.path.join(rw_root, ".iso_source_stamp")
        seven_zip_binary = self._get_7zip_binary()
        if not seven_zip_binary:
            logger.error("7zz or 7z is required to extract MDF set %s", mdf_path)
            return None

        mdf_sources = self._get_mdf_sources(normalized_mdf)
        source_stamp = self._get_disc_source_stamp(mdf_sources)
        if not source_stamp:
            return None

        old_stamp = ""
        if os.path.isfile(stamp_path):
            try:
                with open(stamp_path, encoding="utf-8") as file:
                    old_stamp = file.read().strip()
            except OSError:
                old_stamp = ""
        if old_stamp == source_stamp:
            self._iso_rw_paths[normalized_mdf] = rw_root
            return rw_root

        iso_sources = []
        for source_path in mdf_sources:
            iso_source = self._convert_mdf_to_iso(source_path)
            if not iso_source:
                return None
            iso_sources.append(iso_source)
        try:
            self._clear_disc_runtime_dir(rw_root)
            for iso_source in iso_sources:
                self._extract_iso_to_rw(seven_zip_binary, iso_source, rw_root, "-aos")
            with open(stamp_path, "w", encoding="utf-8") as file:
                file.write(source_stamp)
        except (subprocess.CalledProcessError, OSError) as e:
            logger.error("Failed to sync MDF set to RW path %s: %s", rw_root, e)
            return None

        self._iso_rw_paths[normalized_mdf] = rw_root
        return rw_root

    def sync_iso_to_rw(self, iso_path: str) -> str | None:
        """Extract disc image content to writable runtime directory if source changed."""
        normalized_iso = os.path.abspath(os.path.expanduser(iso_path))
        if normalized_iso.lower().endswith(".mdf"):
            return self._sync_mdf_set_to_rw(normalized_iso)
        rw_root = self._iso_rw_paths.get(normalized_iso, self._get_iso_rw_root(normalized_iso))
        os.makedirs(rw_root, exist_ok=True)
        stamp_path = os.path.join(rw_root, ".iso_source_stamp")
        seven_zip_binary = self._get_7zip_binary()
        if not seven_zip_binary:
            logger.error("7zz or 7z is required to extract ISO %s", iso_path)
            return None

        try:
            source_stamp = f"{os.path.getsize(normalized_iso)}:{int(os.path.getmtime(normalized_iso))}"
        except OSError as e:
            logger.error("Failed to read ISO metadata for %s: %s", normalized_iso, e)
            return None

        old_stamp = ""
        if os.path.isfile(stamp_path):
            try:
                with open(stamp_path, encoding="utf-8") as file:
                    old_stamp = file.read().strip()
            except OSError:
                old_stamp = ""

        if old_stamp != source_stamp:
            try:
                self._clear_disc_runtime_dir(rw_root)
                self._extract_iso_to_rw(seven_zip_binary, normalized_iso, rw_root, "-aoa")
                with open(stamp_path, "w", encoding="utf-8") as file:
                    file.write(source_stamp)
            except (subprocess.CalledProcessError, OSError) as e:
                logger.error("Failed to sync ISO content to RW path %s: %s", rw_root, e)
                return None

        self._iso_rw_paths[normalized_iso] = rw_root
        return rw_root

    def cleanup_iso_rw_paths(self):
        """Remove temporary writable ISO copies created during this session."""
        for rw_root in set(self._iso_rw_paths.values()):
            if not os.path.isdir(rw_root):
                continue
            try:
                self._ensure_writable_tree(rw_root)
                shutil.rmtree(rw_root)
            except OSError as e:
                logger.warning("Failed to cleanup ISO runtime directory %s: %s", rw_root, e)
        self._iso_rw_paths.clear()
        self.cleanup_mdf_iso_paths()
        self._cleanup_empty_iso_runtime_dirs()
        self._cleanup_empty_mdf_runtime_dirs()

    def cleanup_mdf_iso_paths(self) -> None:
        """Remove temporary ISO files converted from MDF."""
        for iso_path in set(self._mdf_iso_paths.values()):
            for path in (iso_path, f"{iso_path}.source_stamp"):
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError as e:
                    logger.warning("Failed to cleanup MDF ISO file %s: %s", path, e)
        self._mdf_iso_paths.clear()

    def _cleanup_empty_iso_runtime_dirs(self):
        """Remove empty ISO runtime parent directories."""
        base_dir = os.path.join(tempfile.gettempdir(), "PortProtonQt", "iso_rw")
        portproton_tmp_dir = os.path.dirname(base_dir)
        for path in (base_dir, portproton_tmp_dir):
            try:
                os.rmdir(path)
            except OSError:
                continue

    def _cleanup_empty_mdf_runtime_dirs(self) -> None:
        """Remove empty MDF conversion parent directories."""
        base_dir = os.path.join(tempfile.gettempdir(), "PortProtonQt", "mdf_iso")
        portproton_tmp_dir = os.path.dirname(base_dir)
        for path in (base_dir, portproton_tmp_dir):
            try:
                os.rmdir(path)
            except OSError:
                continue

    def _parse_autorun_open_executable(self, autorun_path: str) -> str | None:
        """Parse executable path from [autorun] open= in autorun.inf."""
        in_autorun_section = False
        encodings = ("utf-8", "cp1251", "latin-1")
        for encoding in encodings:
            try:
                with open(autorun_path, encoding=encoding) as file:
                    for raw_line in file:
                        line = raw_line.strip()
                        if not line or line.startswith(("#", ";")):
                            continue
                        if line.startswith("[") and line.endswith("]"):
                            section_name = line[1:-1].strip().lower()
                            in_autorun_section = section_name == "autorun"
                            continue
                        if not in_autorun_section or "=" not in line:
                            continue
                        key, value = line.split("=", 1)
                        if key.strip().lower() != "open":
                            continue
                        parsed_value = value.strip().strip('"').strip("'")
                        if parsed_value:
                            return parsed_value
                return None
            except UnicodeDecodeError:
                continue
            except OSError as e:
                logger.warning("Failed reading autorun.inf: %s", e)
                return None
        return None

    def _find_autorun_file(self, root_dir: str) -> str | None:
        """Find autorun.inf in extracted ISO content without case sensitivity."""
        for current_root, _dir_names, files in os.walk(root_dir):
            for file_name in files:
                if file_name.lower() == "autorun.inf":
                    return os.path.join(current_root, file_name)
        return None

    def _find_setup_executable(self, root_dir: str) -> str | None:
        """Find setup.exe in extracted disc content without case sensitivity."""
        for current_root, _dir_names, files in os.walk(root_dir):
            for file_name in files:
                if file_name.lower() == "setup.exe":
                    return os.path.join(current_root, file_name)
        return None

    def _resolve_iso_relative_path(self, root_dir: str, relative_path: str) -> str | None:
        """Resolve path inside root_dir without case sensitivity."""
        normalized = relative_path.replace("\\", "/").lstrip("/").split("/")
        current_path = root_dir
        for part in normalized:
            if not part or part == ".":
                continue
            if part == "..":
                return None
            try:
                entries = os.listdir(current_path)
            except OSError:
                return None
            match = next((name for name in entries if name.lower() == part.lower()), None)
            if not match:
                return None
            current_path = os.path.join(current_path, match)
        return current_path

    def resolve_iso_launch_parts(self, iso_path: str) -> list[str] | None:
        """Resolve executable and launch arguments from disc image autorun.inf."""
        rw_root = self.sync_iso_to_rw(iso_path)
        if not rw_root:
            return None

        autorun_path = self._find_autorun_file(rw_root)
        if not autorun_path:
            setup_path = self._find_setup_executable(rw_root)
            if setup_path:
                return [setup_path]
            return None

        open_entry = self._parse_autorun_open_executable(autorun_path)
        if not open_entry:
            setup_path = self._find_setup_executable(rw_root)
            if setup_path:
                return [setup_path]
            return None

        open_command_parts = shlex.split(open_entry, posix=False)
        if not open_command_parts:
            return None

        candidate_path = self._resolve_iso_relative_path(rw_root, open_command_parts[0])
        if not candidate_path or not os.path.isfile(candidate_path):
            return None
        return [candidate_path] + open_command_parts[1:]

    def resolve_iso_executable(self, iso_path: str) -> str | None:
        """Resolve executable for disc image by reading [autorun] open= in autorun.inf."""
        launch_parts = self.resolve_iso_launch_parts(iso_path)
        if not launch_parts:
            return None
        return launch_parts[0]
