"""Xorg version detection utilities."""

import ctypes
from ctypes import c_char_p, c_int, c_void_p


def decode_xorg_release(rel: int) -> str:
    """Decode Xorg version from integer format."""
    a = rel // 10_000_000
    b = (rel // 100_000) % 100
    c = (rel // 1_000) % 100
    d = rel % 1_000
    return f"{a}.{b}.{c}.{d}"


def get_xorg_version() -> str:
    """Get Xorg server version via X11 library."""
    lib = ctypes.cdll.LoadLibrary("libX11.so.6")

    lib.XOpenDisplay.argtypes = [c_char_p]
    lib.XOpenDisplay.restype = c_void_p

    lib.XCloseDisplay.argtypes = [c_void_p]
    lib.XCloseDisplay.restype = c_int

    lib.XServerVendor.argtypes = [c_void_p]
    lib.XServerVendor.restype = c_char_p

    lib.XVendorRelease.argtypes = [c_void_p]
    lib.XVendorRelease.restype = c_int

    display_name = __import__("os").environ.get("DISPLAY")
    dpy = lib.XOpenDisplay(display_name.encode() if display_name else None)
    if not dpy:
        raise SystemExit("Failed to open X Display. Check DISPLAY.")

    try:
        release = lib.XVendorRelease(dpy)
        return decode_xorg_release(release)
    finally:
        lib.XCloseDisplay(dpy)
