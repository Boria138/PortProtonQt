"""Wine metadata loader for PortProtonQt."""

import os
import tempfile

import orjson
import requests
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from portprotonqt.downloader import Downloader
from portprotonqt.logger import get_logger

logger = get_logger(__name__)


def get_cpu_level():
    """
    Determine CPU level based on feature flags.

    Returns:
        int: CPU level (0-4) based on supported instruction sets
    """
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                if line.startswith('flags'):
                    flags = set(line.split(':')[1].strip().split())
                    break
            else:
                logger.warning("Could not find flags in /proc/cpuinfo, defaulting to CPU level 4")
                return 4
    except FileNotFoundError:
        logger.warning("Could not read /proc/cpuinfo, defaulting to CPU level 4")
        return 4

    level1_required = {'lm', 'cmov', 'cx8', 'fpu', 'fxsr', 'mmx', 'syscall', 'sse2'}
    if not level1_required.issubset(flags):
        return 0

    level2_required = {'cx16', 'lahf_lm', 'popcnt', 'sse4_1', 'sse4_2', 'ssse3'}
    if not level2_required.issubset(flags):
        return 1

    level3_required = {'avx', 'avx2', 'bmi1', 'bmi2', 'f16c', 'fma', 'abm', 'movbe', 'xsave'}
    if not level3_required.issubset(flags):
        return 2

    level4_required = {'avx512f', 'avx512bw', 'avx512cd', 'avx512dq', 'avx512vl'}
    if level4_required.issubset(flags):
        return 4

    return 3


class WineLoadingThread(QThread):
    """Thread for loading wine metadata in the background."""

    loading_complete = Signal(object)
    loading_error = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.downloader = Downloader(max_workers=1)

    def run(self):
        try:
            json_url = "https://git.linux-gaming.ru/Boria138/PortProton-Wine-Metadata/raw/branch/main/wine_metadata.json"

            with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
                temp_path = tmp.name

            try:
                session = requests.Session()
                response = session.get(json_url, stream=True, timeout=30)
                response.raise_for_status()

                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                with open(temp_path, 'rb') as f:
                    metadata = orjson.loads(f.read())

                logger.info(f"Successfully loaded JSON metadata with {len(metadata)} entries")
                self.loading_complete.emit(metadata)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            self.loading_error.emit(str(e))
