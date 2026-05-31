import sys
from pathlib import Path
from typing import Any

DIRECTX_IMPORTS = {
    "ddraw.dll": "DirectDraw",
    "d3d8.dll": "DirectX 8",
    "d3d9.dll": "DirectX 9",
    "d3d10.dll": "DirectX 10",
    "d3d10_1.dll": "DirectX 10",
    "d3d11.dll": "DirectX 11",
    "d3d12.dll": "DirectX 12",
}

DIRECTX_SIGNATURES = {
    "DirectDraw": (b"ddraw.dll", b"DirectDrawCreate"),
    "DirectX 8": (b"d3d8.dll", b"Direct3DCreate8"),
    "DirectX 9": (b"d3d9.dll", b"Direct3DCreate9"),
    "DirectX 10": (b"d3d10.dll", b"D3D10CreateDevice"),
    "DirectX 11": (b"d3d11.dll", b"D3D11CreateDevice"),
    "DirectX 12": (b"d3d12.dll", b"D3D12CreateDevice", b"D3D12Core.dll"),
}

DIRECTX_ORDER = {
    "DirectDraw": 7,
    "DirectX 8": 8,
    "DirectX 9": 9,
    "DirectX 10": 10,
    "DirectX 11": 11,
    "DirectX 12": 12,
}

OPENGL_IMPORTS = {
    "opengl32.dll": "OpenGL",
    "glu32.dll": "OpenGL Utility Library",
}

OPENGL_SIGNATURES = {
    "OpenGL": (
        b"opengl32.dll",
        b"wglCreateContext",
        b"wglGetProcAddress",
        b"glGetString",
        b"OpenGL context",
        b"OpenGL Error",
    ),
    "OpenGL Utility Library": (b"glu32.dll", b"gluPerspective", b"gluLookAt"),
}


def analyze_executable(file_path: str) -> dict[str, Any]:
    """Detect graphics API usage in a Windows executable."""
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    directx = set()
    opengl = set()

    if path.suffix.lower() in {".exe", ".dll"}:
        _add_pe_imports(path, directx, opengl)
    _add_file_signatures(path, directx, opengl)

    return {
        "highest_directx": _highest_directx(list(directx)),
        "uses_opengl": bool(opengl),
    }


def _add_pe_imports(path: Path, directx: set[str], opengl: set[str]) -> None:
    try:
        import pefile
    except ImportError:
        return

    try:
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(
            directories=[
                pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
            ]
        )
        for attr_name in ["DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT"]:
            for entry in getattr(pe, attr_name, []):
                dll = entry.dll.decode("utf-8", errors="ignore").lower()
                if dll in DIRECTX_IMPORTS:
                    directx.add(DIRECTX_IMPORTS[dll])
                elif dll in OPENGL_IMPORTS:
                    opengl.add(OPENGL_IMPORTS[dll])
    except (pefile.PEFormatError, ValueError):
        return


def _add_file_signatures(path: Path, directx: set[str], opengl: set[str]) -> None:
    try:
        with path.open("rb") as f:
            data = f.read(67108864).lower()
    except OSError:
        return

    for name, patterns in DIRECTX_SIGNATURES.items():
        if any(p.lower() in data for p in patterns):
            directx.add(name)

    for name, patterns in OPENGL_SIGNATURES.items():
        if any(p.lower() in data for p in patterns):
            opengl.add(name)


def _highest_directx(directx: list[str]) -> str:
    if not directx:
        return "None"
    return max(directx, key=lambda n: DIRECTX_ORDER[n])


def _main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python3 -m portprotonqt.graphics_detector FILE")
        return 2

    try:
        result = analyze_executable(argv[1])
        print(f"HIGHEST_DX={result['highest_directx']}")
        print(f"USES_OGL={'true' if result['uses_opengl'] else 'false'}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
