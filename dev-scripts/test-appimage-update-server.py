#!/usr/bin/env python3
"""Run PortProtonQt against a fake AppImage update server."""

import argparse
import http.server
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
APPIMAGE_MAGIC_OFFSET = 8
APPIMAGE_TYPE_2_MAGIC = b"AI\x02"
TEST_APPIMAGE_SIZE_BYTES = 128 * 1024 * 1024
HTTP_COPY_BUFFER_SIZE = 1024 * 1024
OLD_APPIMAGE_FILLER = b"OLD-APPIMAGE-BLOCK\n"
UPDATED_APPIMAGE_FILLER = b"UPDATED-APPIMAGE-BLOCK\n"


class UpdateHandler(http.server.BaseHTTPRequestHandler):
    """Serve fake update metadata and the new AppImage."""

    test_dir = Path()
    server_url = ""
    old_version = "0.1.12"
    new_version = "1.2.0"
    new_appimage_name = "PortProtonQt-1.2.0-x86_64.AppImage"

    def log_message(self, fmt, *args):
        print(f"[server] {fmt % args}")

    def do_GET(self):
        if self.path.endswith(".zsync"):
            self._send_zsync()
        elif self.path.startswith("/download/"):
            self._send_download()
        else:
            self.send_error(404)

    def _send_download(self) -> None:
        filename = self.path.split("/download/", 1)[1]
        path = self.test_dir / filename
        if not path.exists():
            self.send_error(404, f"Not found: {filename}")
            return
        self._send_file(path)

    def _send_zsync(self) -> None:
        filename = self.path.rsplit("/", 1)[-1]
        path = self.test_dir / filename
        if not path.exists():
            self.send_error(404, f"Not found: {filename}")
            return
        self._send_file(path)

    def _send_file(self, path: Path) -> None:
        file_size = path.stat().st_size
        byte_range = self._parse_range(file_size)
        start = 0
        end = file_size - 1
        if byte_range is not None:
            start, end = byte_range
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(path, "rb") as appimage_file:
            appimage_file.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = appimage_file.read(min(HTTP_COPY_BUFFER_SIZE, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _parse_range(self, file_size: int) -> tuple[int, int] | None:
        range_header = self.headers.get("Range", "")
        if not range_header.startswith("bytes="):
            return None

        range_spec = range_header.removeprefix("bytes=").split(",", 1)[0].strip()
        start_text, separator, end_text = range_spec.partition("-")
        if not separator:
            return None
        try:
            if not start_text:
                length = int(end_text)
                return max(file_size - length, 0), file_size - 1
            start = int(start_text)
            end = int(end_text) if end_text else file_size - 1
        except ValueError:
            return None
        if start < 0 or end < start or start >= file_size:
            return None
        return start, min(end, file_size - 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old_version", nargs="?", default="0.1.12")
    parser.add_argument("new_version", nargs="?", default="1.2.0")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--version", default=None,
                        help="Simulate current app version (e.g. --version 0.1.8)")
    return parser.parse_args()


def write_appimage_base(path: Path) -> None:
    true_path = shutil.which("true") or "/usr/bin/true"
    shutil.copyfile(true_path, path)
    path.chmod(0o755)


def update_info(server_url: str, new_appimage_name: str) -> str:
    return f"zsync|{server_url}/{new_appimage_name}.zsync"


def finalize_appimage(path: Path, test_dir: Path, update_info_text: str, filler: bytes) -> None:
    update_info_file = test_dir / f"{path.name}.upd_info"
    update_info_file.write_text(update_info_text, encoding="utf-8")
    subprocess.run(
        ["objcopy", "--add-section", f".upd_info={update_info_file}", str(path)],
        check=True,
    )
    with open(path, "r+b") as appimage_file:
        appimage_file.seek(APPIMAGE_MAGIC_OFFSET)
        appimage_file.write(APPIMAGE_TYPE_2_MAGIC)
        appimage_file.seek(0, os.SEEK_END)
        while appimage_file.tell() < TEST_APPIMAGE_SIZE_BYTES:
            appimage_file.write(
                filler[:TEST_APPIMAGE_SIZE_BYTES - appimage_file.tell()]
            )
    path.chmod(0o755)


def write_zsync(test_dir: Path, server_url: str, new_appimage_name: str) -> None:
    new_appimage = test_dir / new_appimage_name
    zsync_file = test_dir / f"{new_appimage_name}.zsync"
    download_url = f"{server_url}/download/{new_appimage_name}"
    subprocess.run(
        [
            "zsyncmake",
            "-e",
            "-u",
            download_url,
            "-o",
            str(zsync_file),
            "-f",
            new_appimage_name,
            str(new_appimage),
        ],
        check=True,
    )


def start_server(args: argparse.Namespace, test_dir: Path, new_appimage_name: str):
    server = http.server.HTTPServer(("127.0.0.1", args.port), UpdateHandler)
    server_url = f"http://127.0.0.1:{server.server_port}"
    UpdateHandler.test_dir = test_dir
    UpdateHandler.server_url = server_url
    UpdateHandler.old_version = args.old_version
    UpdateHandler.new_version = args.new_version
    UpdateHandler.new_appimage_name = new_appimage_name
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server_url


def python_command() -> str:
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def run_gui(env: dict[str, str]) -> int:
    proc = subprocess.Popen(
        [python_command(), "-m", "portprotonqt.app"],
        cwd=str(REPO_ROOT),
        env=env,
    )
    return proc.wait()


def main() -> None:
    args = parse_args()
    if args.version:
        args.old_version = args.version
    test_dir = Path(tempfile.mkdtemp(prefix="ppqt-appimage-update-"))
    old_appimage = test_dir / f"PortProtonQt-{args.old_version}-x86_64.AppImage"
    new_appimage_name = f"PortProtonQt-{args.new_version}-x86_64.AppImage"
    new_appimage = test_dir / new_appimage_name
    server = None

    try:
        write_appimage_base(old_appimage)
        write_appimage_base(new_appimage)
        server, server_url = start_server(args, test_dir, new_appimage_name)
        update_info_text = update_info(server_url, new_appimage_name)
        finalize_appimage(
            old_appimage,
            test_dir,
            update_info_text,
            OLD_APPIMAGE_FILLER,
        )
        finalize_appimage(
            new_appimage,
            test_dir,
            update_info_text,
            UPDATED_APPIMAGE_FILLER,
        )
        write_zsync(test_dir, server_url, new_appimage_name)

        env = os.environ.copy()
        env["APPIMAGE"] = str(old_appimage)
        env["PORTPROTONQT_VERSION"] = args.old_version

        print("=== AppImage update GUI test ===")
        print(f"Test dir       : {test_dir}")
        print(f"Old AppImage   : {old_appimage}")
        print(f"New AppImage   : {new_appimage}")
        print(f"AppImage size  : {TEST_APPIMAGE_SIZE_BYTES // 1024 // 1024} MiB")
        print(f"HTTP server    : {server_url}")
        print(f"Update info    : {update_info_text}")
        print("")
        print("In GUI: wait for the update dialog, press Update, watch progress.")
        print("After success, old AppImage should be replaced by the new file.")
        print("")

        raise SystemExit(run_gui(env))
    finally:
        if server is not None:
            server.shutdown()
        if args.keep:
            print(f"Keeping test dir: {test_dir}")
        else:
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
