"""Unified icon extractor for NE and PE files."""

import struct
import io
import pefile
from PIL import Image
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

RT_ICON = 3
RT_GROUP_ICON = 14
THUMBNAIL_SIZE = 128

class IconExtractorError(Exception):
    """Base exception for icon extraction errors."""

class IconExtractor:
    """Extracts icons from NE and PE files."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._icons = {}  # ID -> bytes
        self._groups = [] # List of group icon data

    def get_icon(self) -> io.BytesIO | None:
        """Extract the best quality icon and return it as image data."""
        try:
            with open(self.file_path, "rb") as f:
                if not self._parse_file(f):
                    return None

            if not self._groups or not self._icons:
                return None

            best_group = self._groups[0]
            data = self._select_best_icon_data(best_group)
            if data is None:
                return None
            return self._icon_data_to_image(data)
        except Exception as e:
            logger.warning("Failed to extract icon from %s: %s", self.file_path, e)
            return None

    def _parse_file(self, f) -> bool:
        """Identify file type and call appropriate parser."""
        f.seek(0)
        if f.read(2) != b"MZ":
            return False
        f.seek(0x3C)
        e_lfanew = struct.unpack("<I", f.read(4))[0]
        f.seek(e_lfanew)
        sig = f.read(2)
        if sig == b"NE":
            logger.debug("Detected NE file")
            return self._parse_ne(f, e_lfanew)
        if sig == b"PE":
            logger.debug("Detected PE file")
            return self._parse_pe()
        return False

    def _parse_ne(self, f, e_lfanew: int) -> bool:
        """Parse NE resource table."""
        f.seek(e_lfanew + 0x24)
        rt_offset = struct.unpack("<H", f.read(2))[0]
        if rt_offset == 0:
            logger.debug("No resource table in NE")
            return False

        f.seek(e_lfanew + rt_offset)
        shift = struct.unpack("<H", f.read(2))[0]
        while True:
            type_id = struct.unpack("<H", f.read(2))[0]
            if type_id == 0:
                break
            count = struct.unpack("<H", f.read(2))[0]
            f.seek(4, 1)
            for _ in range(count):
                off = struct.unpack("<H", f.read(2))[0] << shift
                size = struct.unpack("<H", f.read(2))[0] << shift
                f.seek(2, 1)
                res_id = struct.unpack("<H", f.read(2))[0] & 0x7FFF
                f.seek(4, 1)

                curr = f.tell()
                f.seek(off)
                data = f.read(size)
                t_id = type_id & 0x7FFF
                if t_id == RT_ICON:
                    self._icons[res_id] = data
                elif t_id == RT_GROUP_ICON:
                    self._groups.append(data)
                f.seek(curr)
        return True

    def _parse_pe(self) -> bool:
        """Parse PE resources with pefile."""
        try:
            pe = pefile.PE(name=self.file_path, fast_load=True)
            pe.parse_data_directories(pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"])
        except pefile.PEFormatError as e:
            logger.debug("PE parse failed: %s", e)
            return False

        resource_directory = getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None)
        if resource_directory is None:
            logger.debug("No resource directory in PE")
            return False

        resources = {}
        for resource_entry in reversed(resource_directory.entries):
            resource_key = resource_entry.id if resource_entry.id is not None else resource_entry.struct.Name
            resources[resource_key] = resource_entry

        group_res = resources.get(pefile.RESOURCE_TYPE["RT_GROUP_ICON"])
        icon_res = resources.get(pefile.RESOURCE_TYPE["RT_ICON"])
        if not group_res or not icon_res:
            return False

        self._groups = self._read_group_resources(pe, group_res)
        self._icons = self._read_icon_resources(pe, icon_res)
        return bool(self._groups and self._icons)

    def _read_group_resources(self, pe, group_res):
        """Read RT_GROUP_ICON blobs."""
        groups = []
        for group_entry in group_res.directory.entries:
            data_entry = group_entry.directory.entries[0] if group_entry.struct.DataIsDirectory else group_entry
            rva = data_entry.data.struct.OffsetToData
            groups.append(pe.get_data(rva, data_entry.data.struct.Size))
        return groups

    def _read_icon_resources(self, pe, icon_res):
        """Read RT_ICON blobs keyed by resource ID."""
        icons = {}
        for icon_entry in icon_res.directory.entries:
            data_entry = icon_entry.directory.entries[0] if icon_entry.struct.DataIsDirectory else icon_entry
            rva = data_entry.data.struct.OffsetToData
            resource_id = icon_entry.id if icon_entry.id is not None else icon_entry.struct.Name
            icons[resource_id] = pe.get_data(rva, data_entry.data.struct.Size)
        return icons

    def _select_best_icon_data(self, group_data: bytes) -> bytes | None:
        """Return raw icon bytes for the best entry."""
        if len(group_data) < 6:
            return None

        count = struct.unpack("<H", group_data[4:6])[0]
        best: tuple[int, int, int, int, bytes] | None = None
        for i in range(count):
            ge = group_data[6 + i * 14 : 20 + i * 14]
            if len(ge) != 14:
                continue

            width = ge[0] or 256
            height = ge[1] or 256
            bitcount = struct.unpack("<H", ge[6:8])[0]
            bytes_in_res = struct.unpack("<I", ge[8:12])[0]
            res_id = struct.unpack("<H", ge[12:14])[0]

            data = self._icons.get(res_id)
            if data is None:
                continue

            candidate = (width, height, bitcount, bytes_in_res, data)
            if best is None or candidate[:4] > best[:4]:
                best = candidate

        if best is None:
            return None
        return best[4]

    def _icon_data_to_image(self, data: bytes) -> io.BytesIO | None:
        """Convert raw icon data to a 128x128 PNG stream."""
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            try:
                image = Image.open(io.BytesIO(data))
                image.load()
            except Exception:
                return None
        else:
            image = self._decode_dib_icon(data)
            if image is None:
                return None

        image = image.convert("RGBA")
        if image.size != (THUMBNAIL_SIZE, THUMBNAIL_SIZE):
            image = image.resize((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.Resampling.LANCZOS)

        output = io.BytesIO()
        image.save(output, format="PNG")
        output.seek(0)
        return output

    def _decode_dib_icon(self, data: bytes) -> Image.Image | None:
        """Decode a DIB icon image and apply its transparency mask."""
        if len(data) < 40:
            return None

        header = struct.unpack("<IIIHHIIIIII", data[:40])
        _, width, height, _, bitcount, compression, _, _, _, colors_used, _ = header
        if compression != 0 or width == 0 or height == 0:
            return None

        image_height = height // 2
        palette_size = colors_used or (1 << bitcount if bitcount <= 8 else 0)
        palette_offset = 40
        palette_bytes = palette_size * 4
        pixel_offset = palette_offset + palette_bytes
        row_bits = width * bitcount
        xor_stride = ((row_bits + 31) // 32) * 4
        and_stride = ((width + 31) // 32) * 4
        xor_size = xor_stride * image_height
        and_offset = pixel_offset + xor_size
        if len(data) < and_offset:
            return None

        palette = []
        for index in range(palette_size):
            entry = data[palette_offset + index * 4 : palette_offset + (index + 1) * 4]
            if len(entry) != 4:
                return None
            blue, green, red, _ = entry
            palette.append((red, green, blue))

        image = Image.new("RGBA", (width, image_height))
        for y in range(image_height):
            src_row = image_height - 1 - y
            xor_row = data[pixel_offset + src_row * xor_stride : pixel_offset + (src_row + 1) * xor_stride]
            mask_row = data[and_offset + src_row * and_stride : and_offset + (src_row + 1) * and_stride]
            for x in range(width):
                pixel = self._read_pixel(xor_row, mask_row, x, bitcount, palette)
                if pixel is None:
                    return None
                image.putpixel((x, y), pixel)

        return image

    def _read_pixel(
        self, row: bytes, mask_row: bytes, x: int, bitcount: int, palette: list[tuple[int, int, int]]
    ) -> tuple[int, int, int, int] | None:
        """Read one icon pixel in RGBA."""
        transparent = bool(mask_row[x // 8] & (0x80 >> (x % 8)))
        if bitcount in (1, 2, 4, 8):
            pixels_per_byte = 8 // bitcount
            byte = row[x // pixels_per_byte]
            shift = (pixels_per_byte - 1 - (x % pixels_per_byte)) * bitcount
            index = (byte >> shift) & ((1 << bitcount) - 1)
            if index >= len(palette):
                return None
            red, green, blue = palette[index]
            return red, green, blue, 0 if transparent else 255

        base = x * (bitcount // 8)
        if bitcount == 16:
            value = struct.unpack_from("<H", row, base)[0]
            red = ((value >> 10) & 0x1F) * 255 // 31
            green = ((value >> 5) & 0x1F) * 255 // 31
            blue = (value & 0x1F) * 255 // 31
            return red, green, blue, 0 if transparent else 255
        if bitcount == 24:
            return row[base + 2], row[base + 1], row[base], 0 if transparent else 255
        if bitcount == 32:
            alpha = row[base + 3]
            return row[base + 2], row[base + 1], row[base], 0 if transparent else alpha
        return None
