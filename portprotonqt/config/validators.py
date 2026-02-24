"""Configuration exceptions and validation utilities."""
import os


class ConfigError(Exception):
    """Base exception for configuration errors."""


class ValidationError(ConfigError):
    """Raised when configuration value validation fails."""

    def __init__(self, message: str, option: str, value):
        super().__init__(message)
        self.option = option
        self.value = value


def validate_string(value: str, option: str, min_len: int = 0, max_len: int = 255) -> str:
    """Validate string configuration value."""
    if not isinstance(value, str):
        raise ValidationError(f"{option} must be a string", option, value)
    if len(value) < min_len:
        raise ValidationError(f"{option} must be at least {min_len} characters", option, value)
    if len(value) > max_len:
        raise ValidationError(f"{option} must not exceed {max_len} characters", option, value)
    return value


def validate_int(value: int, option: str, min_val: int | None = None, max_val: int | None = None) -> int:
    """Validate integer configuration value."""
    if not isinstance(value, int):
        raise ValidationError(f"{option} must be an integer", option, value)
    if min_val is not None and value < min_val:
        raise ValidationError(f"{option} must be at least {min_val}", option, value)
    if max_val is not None and value > max_val:
        raise ValidationError(f"{option} must not exceed {max_val}", option, value)
    return value


def validate_bool(value: bool, option: str) -> bool:
    """Validate boolean configuration value."""
    if not isinstance(value, bool):
        raise ValidationError(f"{option} must be a boolean", option, value)
    return value


def validate_path(value: str, option: str, must_exist: bool = False) -> str:
    """Validate path configuration value."""
    if not isinstance(value, str):
        raise ValidationError(f"{option} must be a string path", option, value)
    if not value:
        raise ValidationError(f"{option} cannot be empty", option, value)
    if must_exist and not os.path.exists(value):
        raise ValidationError(f"{option} path does not exist: {value}", option, value)
    return value


def validate_url(value: str, option: str, allow_empty: bool = True) -> str:
    """Validate URL configuration value."""
    if allow_empty and not value:
        return value
    if not isinstance(value, str):
        raise ValidationError(f"{option} must be a string URL", option, value)
    if not value:
        raise ValidationError(f"{option} cannot be empty", option, value)
    if "://" not in value and value:
        raise ValidationError(f"{option} must be a valid URL with protocol", option, value)
    return value
