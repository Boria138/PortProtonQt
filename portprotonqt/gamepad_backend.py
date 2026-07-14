import ctypes
import ctypes.util
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Any

from portprotonqt.logger import get_logger

logger = get_logger(__name__)

SDL_INIT_GAMEPAD = 0x00002000
SDL_GAMEPAD_TYPE_STANDARD = 1
SDL_GAMEPAD_TYPE_XBOX360 = 2
SDL_GAMEPAD_TYPE_XBOXONE = 3
SDL_GAMEPAD_TYPE_PS3 = 4
SDL_GAMEPAD_TYPE_PS4 = 5
SDL_GAMEPAD_TYPE_PS5 = 6
SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO = 7
SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_LEFT = 8
SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_RIGHT = 9
SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_PAIR = 10
SDL_GAMEPAD_TYPE_GAMECUBE = 11
SDL_GAMEPAD_TYPE_STEAM = 12
SDL3_XBOX_LIKE_TYPES = {
    SDL_GAMEPAD_TYPE_STANDARD,
    SDL_GAMEPAD_TYPE_XBOX360,
    SDL_GAMEPAD_TYPE_XBOXONE,
    SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO,
    SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_LEFT,
    SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_RIGHT,
    SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_PAIR,
    SDL_GAMEPAD_TYPE_GAMECUBE,
    SDL_GAMEPAD_TYPE_STEAM,
}
SDL3_PLAYSTATION_TYPES = {
    SDL_GAMEPAD_TYPE_PS3,
    SDL_GAMEPAD_TYPE_PS4,
    SDL_GAMEPAD_TYPE_PS5,
}

SDL_GAMEPAD_BUTTON_SOUTH = 0
SDL_GAMEPAD_BUTTON_EAST = 1
SDL_GAMEPAD_BUTTON_WEST = 2
SDL_GAMEPAD_BUTTON_NORTH = 3
SDL_GAMEPAD_BUTTON_BACK = 4
SDL_GAMEPAD_BUTTON_GUIDE = 5
SDL_GAMEPAD_BUTTON_START = 6
SDL_GAMEPAD_BUTTON_LEFT_SHOULDER = 9
SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER = 10
SDL_GAMEPAD_BUTTON_DPAD_UP = 11
SDL_GAMEPAD_BUTTON_DPAD_DOWN = 12
SDL_GAMEPAD_BUTTON_DPAD_LEFT = 13
SDL_GAMEPAD_BUTTON_DPAD_RIGHT = 14
SDL_GAMEPAD_AXIS_LEFTX = 0
SDL_GAMEPAD_AXIS_LEFTY = 1
SDL_GAMEPAD_AXIS_RIGHTX = 2
SDL_GAMEPAD_AXIS_RIGHTY = 3
SDL_GAMEPAD_AXIS_LEFT_TRIGGER = 4
SDL_GAMEPAD_AXIS_RIGHT_TRIGGER = 5


class GamepadType(Enum):
    XBOX = "Xbox"
    PLAYSTATION = "PlayStation"
    UNKNOWN = "Unknown"


def _get_sdl3_error(sdl: ctypes.CDLL) -> str:
    error = sdl.SDL_GetError()
    if not error:
        return ""
    return error.decode(errors="replace")


def _configure_sdl3_gamepad_api(sdl: ctypes.CDLL) -> None:
    sdl.SDL_InitSubSystem.argtypes = [ctypes.c_uint32]
    sdl.SDL_InitSubSystem.restype = ctypes.c_bool
    sdl.SDL_GetGamepads.argtypes = [ctypes.POINTER(ctypes.c_int)]
    sdl.SDL_GetGamepads.restype = ctypes.POINTER(ctypes.c_uint32)
    sdl.SDL_GetGamepadTypeForID.argtypes = [ctypes.c_uint32]
    sdl.SDL_GetGamepadTypeForID.restype = ctypes.c_int
    sdl.SDL_GetGamepadNameForID.argtypes = [ctypes.c_uint32]
    sdl.SDL_GetGamepadNameForID.restype = ctypes.c_char_p
    sdl.SDL_OpenGamepad.argtypes = [ctypes.c_uint32]
    sdl.SDL_OpenGamepad.restype = ctypes.c_void_p
    sdl.SDL_CloseGamepad.argtypes = [ctypes.c_void_p]
    sdl.SDL_CloseGamepad.restype = None
    sdl.SDL_GamepadConnected.argtypes = [ctypes.c_void_p]
    sdl.SDL_GamepadConnected.restype = ctypes.c_bool
    sdl.SDL_GetGamepadName.argtypes = [ctypes.c_void_p]
    sdl.SDL_GetGamepadName.restype = ctypes.c_char_p
    sdl.SDL_GetGamepadButton.argtypes = [ctypes.c_void_p, ctypes.c_int]
    sdl.SDL_GetGamepadButton.restype = ctypes.c_bool
    sdl.SDL_GetGamepadAxis.argtypes = [ctypes.c_void_p, ctypes.c_int]
    sdl.SDL_GetGamepadAxis.restype = ctypes.c_int16
    sdl.SDL_UpdateGamepads.argtypes = []
    sdl.SDL_UpdateGamepads.restype = None
    sdl.SDL_PumpEvents.argtypes = []
    sdl.SDL_PumpEvents.restype = None
    sdl.SDL_QuitSubSystem.argtypes = [ctypes.c_uint32]
    sdl.SDL_QuitSubSystem.restype = None
    sdl.SDL_GetError.argtypes = []
    sdl.SDL_GetError.restype = ctypes.c_char_p
    sdl.SDL_free.argtypes = [ctypes.c_void_p]
    sdl.SDL_free.restype = None


@lru_cache(maxsize=1)
def _load_sdl3() -> ctypes.CDLL | None:
    library_names = (
        ctypes.util.find_library("SDL3"),
        "libSDL3.so.0",
        "libSDL3.so",
    )
    for library_name in library_names:
        if not library_name:
            continue
        try:
            sdl = ctypes.CDLL(library_name)
            _configure_sdl3_gamepad_api(sdl)
        except (AttributeError, OSError) as e:
            logger.debug("Failed to load SDL3 from %s: %s", library_name, e)
            continue
        if sdl.SDL_InitSubSystem(SDL_INIT_GAMEPAD):
            return sdl
        logger.debug("Failed to initialize SDL3 gamepad subsystem: %s", _get_sdl3_error(sdl))
    return None


def _decode_sdl3_name(name: bytes | None) -> str:
    if not name:
        return ""
    return name.decode(errors="replace")


@dataclass
class SDLGamepad:
    sdl: ctypes.CDLL
    controller: ctypes.c_void_p
    name: str
    path: str
    instance_id: int

    def close(self) -> None:
        try:
            self.sdl.SDL_CloseGamepad(self.controller)
        except (AttributeError, OSError) as e:
            logger.debug("Failed to close SDL gamepad: %s", e)

    def connected(self) -> bool:
        return bool(self.sdl.SDL_GamepadConnected(self.controller))

    def update(self) -> None:
        self.sdl.SDL_UpdateGamepads()

    def get_button(self, button: int) -> int:
        return int(self.sdl.SDL_GetGamepadButton(self.controller, button))

    def get_axis(self, axis: int) -> int:
        return int(self.sdl.SDL_GetGamepadAxis(self.controller, axis))


def find_gamepad() -> SDLGamepad | None:
    sdl = _load_sdl3()
    if sdl is None:
        return None
    sdl.SDL_PumpEvents()
    sdl.SDL_UpdateGamepads()
    count = ctypes.c_int()
    gamepads = sdl.SDL_GetGamepads(ctypes.byref(count))
    if not gamepads:
        return None
    try:
        return _open_first_sdl3_gamepad(sdl, gamepads, count.value)
    finally:
        sdl.SDL_free(gamepads)


def _open_first_sdl3_gamepad(
    sdl: ctypes.CDLL,
    gamepads: Any,
    count: int,
) -> SDLGamepad | None:
    for index in range(count):
        instance_id = int(gamepads[index])
        gamepad = sdl.SDL_OpenGamepad(instance_id)
        if not gamepad:
            logger.debug("Skipping SDL3 gamepad %s: %s", instance_id, _get_sdl3_error(sdl))
            continue
        return SDLGamepad(
            sdl=sdl,
            controller=gamepad,
            name=_decode_sdl3_name(sdl.SDL_GetGamepadName(gamepad)),
            path=f"sdl3-gamepad:{instance_id}",
            instance_id=instance_id,
        )
    return None


def detect_gamepad_type(gamepad: SDLGamepad) -> GamepadType:
    sdl = _load_sdl3()
    if sdl is None:
        return GamepadType.XBOX
    count = ctypes.c_int()
    gamepads = sdl.SDL_GetGamepads(ctypes.byref(count))
    if not gamepads:
        return GamepadType.XBOX
    try:
        gamepad_type = _find_sdl3_gamepad_type(sdl, gamepads, count.value, gamepad.name)
    finally:
        sdl.SDL_free(gamepads)
    return gamepad_type or GamepadType.XBOX


def _find_sdl3_gamepad_type(
    sdl: ctypes.CDLL,
    gamepads: Any,
    count: int,
    target_name: str,
) -> GamepadType | None:
    for index in range(count):
        gamepad_id = gamepads[index]
        sdl_name = _decode_sdl3_name(sdl.SDL_GetGamepadNameForID(gamepad_id))
        if count > 1 and sdl_name.casefold() != target_name.casefold():
            continue
        gamepad_type = _gamepad_type_from_sdl3_value(sdl.SDL_GetGamepadTypeForID(gamepad_id))
        if gamepad_type is not None:
            return gamepad_type
    return None


def _gamepad_type_from_sdl3_value(sdl_type: int) -> GamepadType | None:
    if sdl_type in SDL3_PLAYSTATION_TYPES:
        return GamepadType.PLAYSTATION
    if sdl_type in SDL3_XBOX_LIKE_TYPES:
        return GamepadType.XBOX
    return None


def shutdown() -> None:
    sdl = _load_sdl3()
    if sdl is not None:
        sdl.SDL_QuitSubSystem(SDL_INIT_GAMEPAD)
