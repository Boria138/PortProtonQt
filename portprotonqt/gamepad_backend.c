#include <SDL3/SDL.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>

typedef struct {
    SDL_Gamepad *gamepad;
    SDL_JoystickID instance_id;
    int sdl_type;
} PortProtonGamepad;

static PortProtonGamepad *open_gamepad(SDL_JoystickID instance_id)
{
    SDL_Gamepad *gamepad = SDL_OpenGamepad(instance_id);
    if (gamepad == NULL) {
        return NULL;
    }
    PortProtonGamepad *result = malloc(sizeof(*result));
    if (result == NULL) {
        SDL_CloseGamepad(gamepad);
        SDL_SetError("Failed to allocate gamepad handle");
        return NULL;
    }
    result->gamepad = gamepad;
    result->instance_id = instance_id;
    result->sdl_type = SDL_GetGamepadTypeForID(instance_id);
    return result;
}

PortProtonGamepad *portproton_gamepad_find(void)
{
    SDL_ClearError();
    if (!SDL_InitSubSystem(SDL_INIT_GAMEPAD)) {
        return NULL;
    }
    SDL_PumpEvents();
    SDL_UpdateGamepads();
    int count = 0;
    SDL_JoystickID *gamepads = SDL_GetGamepads(&count);
    if (gamepads == NULL) {
        return NULL;
    }
    if (count == 0) {
        SDL_free(gamepads);
        SDL_ClearError();
        return NULL;
    }
    PortProtonGamepad *result = NULL;
    for (int index = 0; index < count && result == NULL; index++) {
        result = open_gamepad(gamepads[index]);
    }
    SDL_free(gamepads);
    return result;
}

const char *portproton_gamepad_get_error(void)
{
    const char *error = SDL_GetError();
    return error != NULL ? error : "";
}

void portproton_gamepad_close(PortProtonGamepad *gamepad)
{
    if (gamepad == NULL) {
        return;
    }
    if (gamepad->gamepad != NULL) {
        SDL_CloseGamepad(gamepad->gamepad);
    }
    free(gamepad);
}

bool portproton_gamepad_connected(const PortProtonGamepad *gamepad)
{
    return gamepad != NULL && gamepad->gamepad != NULL &&
           SDL_GamepadConnected(gamepad->gamepad);
}

void portproton_gamepad_update(void)
{
    SDL_UpdateGamepads();
}

int portproton_gamepad_get_button(const PortProtonGamepad *gamepad, int button)
{
    if (gamepad == NULL || gamepad->gamepad == NULL) {
        return 0;
    }
    return SDL_GetGamepadButton(gamepad->gamepad, button);
}

int16_t portproton_gamepad_get_axis(const PortProtonGamepad *gamepad, int axis)
{
    if (gamepad == NULL || gamepad->gamepad == NULL) {
        return 0;
    }
    return SDL_GetGamepadAxis(gamepad->gamepad, axis);
}

const char *portproton_gamepad_get_name(const PortProtonGamepad *gamepad)
{
    if (gamepad == NULL || gamepad->gamepad == NULL) {
        return "";
    }
    const char *name = SDL_GetGamepadName(gamepad->gamepad);
    return name != NULL ? name : "";
}

uint32_t portproton_gamepad_get_instance_id(const PortProtonGamepad *gamepad)
{
    return gamepad != NULL ? gamepad->instance_id : 0;
}

int portproton_gamepad_get_type(const PortProtonGamepad *gamepad)
{
    return gamepad != NULL ? gamepad->sdl_type : 0;
}

void portproton_gamepad_shutdown(void)
{
    SDL_QuitSubSystem(SDL_INIT_GAMEPAD);
}
