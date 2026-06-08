import os
import hashlib
import shutil
import stat
import subprocess
import tempfile
import shlex
from typing import BinaryIO
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

SYNC_HEADER = b'\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00'
SYNC_HEADER_MDF = b'\x80\xc0\x80\x80\x80\x80\x80\xc0\x80\x80\x80\x80'
ISO_9660_SIG = b'\x01\x43\x44\x30\x30\x31\x01\x00'
DISC_BLOCK_SIZES = (2048, 2336, 2352, 2368, 2448)
SVCD_SUB_HEADERS = (
    b"\x00\x00\x08\x00\x00\x00\x08\x00",
    b"\x00\x00\x09\x00\x00\x00\x09\x00",
    b"\x00\x00\x88\x00\x00\x00\x88\x00",
    b"\x00\x00\x89\x00\x00\x00\x89\x00",
)
UDF_SIGNATURES = (b"BEA01", b"BOOT2", b"CD001", b"CDW02", b"NSR02", b"NSR03", b"TEA01")
CONVERTIBLE_DISC_EXTENSIONS = (".mdf", ".nrg")


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

    def _is_svcd_sub_header(self, header: bytes) -> bool:
        """Return True if header matches known SVCD subheader bytes."""
        return header[:8] in SVCD_SUB_HEADERS

    def _calculate_disc_layout(self, source: BinaryIO) -> tuple[int, int]:
        """Return pregap and block size using the iat detection rules."""
        source.seek(0, os.SEEK_END)
        image_size = source.tell()
        cd_id_start = -1
        cd_id_end = 0
        header_size = 0

        for offset in range(32768, image_size):
            source.seek(offset)
            header = source.read(12)
            if header == SYNC_HEADER:
                header_size = self._add_header_size(header_size, 16)
                continue
            if self._is_svcd_sub_header(header):
                header_size = self._add_header_size(header_size, 8)
                continue
            if header[:5] in UDF_SIGNATURES:
                if cd_id_start < 0:
                    cd_id_start = offset
                else:
                    cd_id_end = offset
                    break

        if cd_id_start < 0 or cd_id_end <= cd_id_start:
            return self._detect_sector_layout(source)

        block_size = self._calculate_block_size(cd_id_end - cd_id_start)
        pregap = cd_id_start - (block_size * 16) - header_size - 1
        return max(pregap, 0), block_size

    def _add_header_size(self, header_size: int, value: int) -> int:
        """Add a detected header size once, matching iat's mixed header logic."""
        if header_size in (value, 24):
            return header_size
        return header_size + value

    def _calculate_block_size(self, block_delta: int) -> int:
        """Return closest iat-supported block size for descriptor spacing."""
        for block_size in DISC_BLOCK_SIZES[:-1]:
            if block_delta % block_size == 0:
                return block_size
        return DISC_BLOCK_SIZES[-1]

    def _detect_sector_layout(self, source: BinaryIO) -> tuple[int, int]:
        """Fallback sector layout detection for images without two descriptors."""
        source.seek(0)
        h0 = source.read(12)
        source.seek(2352)
        h2352 = source.read(12)
        if h0 == SYNC_HEADER and h2352 == SYNC_HEADER_MDF:
            return 0, 2448
        if h0 == SYNC_HEADER:
            return 0, 2352
        return 0, 2352

    def _write_sync_sector_data(self, target: BinaryIO, sector: bytes) -> None:
        """Write ISO user data from a sector with a sync header."""
        mode = sector[15]
        if mode == 0:
            target.write(sector[16:2352])
        elif mode == 1:
            target.write(sector[16:2064])
        elif mode == 2:
            self._write_mode_two_sector_data(target, sector)
        else:
            raise ValueError(f"Unknown MDF sector mode {mode}")

    def _write_mode_two_sector_data(self, target: BinaryIO, sector: bytes) -> None:
        """Write ISO user data from a Mode 2 sector."""
        sub_header = sector[16:24]
        if sub_header[:4] != sub_header[4:8]:
            target.write(sector[16:2352])
            return
        if sub_header[2] & 0x20:
            target.write(sector[24:2348])
            return
        target.write(sector[24:2072])

    def _write_headerless_sector_data(self, target: BinaryIO, sector: bytes) -> bool:
        """Write ISO user data from a 2336-byte headerless sector."""
        sub_header = sector[:8]
        if sub_header[:4] != sub_header[4:8]:
            return False
        if self._is_svcd_sub_header(sub_header):
            target.write(sector[8:2332])
        else:
            target.write(sector[8:2056])
        return True

    def _write_iso_from_mdf(self, mdf_path: str, iso_path: str) -> None:
        """Convert MDF to ISO using iat-compatible sector extraction."""
        with open(mdf_path, "rb") as source, open(iso_path, "wb") as target:
            pregap, block_size = self._calculate_disc_layout(source)
            image_size = os.path.getsize(mdf_path)
            source.seek(pregap)
            sector_index = pregap
            while sector_index < image_size:
                sector = source.read(block_size)
                if not sector:
                    return
                if len(sector) != block_size:
                    raise ValueError(f"Truncated MDF sector at {sector_index}")
                if sector.startswith(SYNC_HEADER):
                    self._write_sync_sector_data(target, sector)
                elif block_size == 2336 and not self._write_headerless_sector_data(target, sector):
                    sector_index += 1
                    source.seek(sector_index)
                    continue
                elif block_size == 2048:
                    target.write(sector)
                else:
                    sector_index += 1
                    source.seek(sector_index)
                    continue
                sector_index += block_size

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

        if normalized_mdf.lower().endswith(".mdf"):
            mdf_sources = self._get_mdf_sources(normalized_mdf)
        else:
            mdf_sources = [normalized_mdf]
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
        if normalized_iso.lower().endswith(CONVERTIBLE_DISC_EXTENSIONS):
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
