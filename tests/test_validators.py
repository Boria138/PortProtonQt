"""Tests for config/validators.py."""
import pytest

from portprotonqt.config.validators import (
    validate_string,
    validate_int,
    validate_bool,
    validate_path,
    validate_url,
    ValidationError,
)


class TestValidateString:
    def test_valid_string(self):
        assert validate_string("hello", "opt") == "hello"

    def test_min_len(self):
        with pytest.raises(ValidationError, match="at least 3"):
            validate_string("ab", "opt", min_len=3)

    def test_max_len(self):
        with pytest.raises(ValidationError, match="must not exceed 5"):
            validate_string("toolong", "opt", max_len=5)

    def test_not_string(self):
        with pytest.raises(ValidationError, match="must be a string"):
            validate_string(123, "opt")  # type: ignore[arg-type]

    def test_empty_string_zero_min(self):
        assert validate_string("", "opt", min_len=0) == ""

    def test_exactly_min_len(self):
        assert validate_string("ab", "opt", min_len=2) == "ab"

    def test_exactly_max_len(self):
        assert validate_string("abcde", "opt", max_len=5) == "abcde"


class TestValidateInt:
    def test_valid_int(self):
        assert validate_int(42, "opt") == 42

    def test_not_int(self):
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_int("42", "opt")  # type: ignore[arg-type]

    def test_below_min(self):
        with pytest.raises(ValidationError, match="at least 10"):
            validate_int(5, "opt", min_val=10)

    def test_above_max(self):
        with pytest.raises(ValidationError, match="must not exceed 100"):
            validate_int(101, "opt", max_val=100)

    def test_exactly_min(self):
        assert validate_int(10, "opt", min_val=10) == 10

    def test_exactly_max(self):
        assert validate_int(100, "opt", max_val=100) == 100

    def test_no_bounds(self):
        assert validate_int(-999, "opt") == -999


class TestValidateBool:
    def test_valid_bool(self):
        assert validate_bool(True, "opt") is True
        assert validate_bool(False, "opt") is False

    def test_not_bool(self):
        with pytest.raises(ValidationError, match="must be a boolean"):
            validate_bool(1, "opt")  # type: ignore[arg-type]

    def test_not_bool_string(self):
        with pytest.raises(ValidationError, match="must be a boolean"):
            validate_bool("true", "opt")  # type: ignore[arg-type]


class TestValidatePath:
    def test_valid_path(self):
        assert validate_path("/some/path", "opt") == "/some/path"

    def test_not_string(self):
        with pytest.raises(ValidationError, match="must be a string path"):
            validate_path(123, "opt")  # type: ignore[arg-type]

    def test_empty_path(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_path("", "opt")

    def test_must_exist_valid(self, tmp_path):
        assert validate_path(str(tmp_path), "opt", must_exist=True) == str(tmp_path)

    def test_must_exist_missing(self, tmp_path):
        with pytest.raises(ValidationError, match="does not exist"):
            validate_path(str(tmp_path / "nope"), "opt", must_exist=True)


class TestValidateUrl:
    def test_valid_url(self):
        assert validate_url("https://example.com", "opt") == "https://example.com"

    def test_allow_empty(self):
        assert validate_url("", "opt", allow_empty=True) == ""

    def test_disallow_empty(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_url("", "opt", allow_empty=False)

    def test_no_protocol(self):
        with pytest.raises(ValidationError, match="valid URL with protocol"):
            validate_url("example.com", "opt", allow_empty=False)

    def test_not_string(self):
        with pytest.raises(ValidationError, match="must be a string URL"):
            validate_url(123, "opt", allow_empty=False)  # type: ignore[arg-type]

    def test_http_url(self):
        assert validate_url("http://example.com", "opt") == "http://example.com"
