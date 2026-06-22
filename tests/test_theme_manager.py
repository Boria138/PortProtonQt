"""Tests for theme_manager: AST injection, parent resolution, and ThemeWrapper."""
import ast
import types
from pathlib import Path
import pytest

from portprotonqt.theme_manager import (
    _get_parent_theme_name,
    _inject_ast_constants,
    _inject_parent_theme_constants,
    _is_valid_theme_name,
    _read_theme_parent_name,
)


# === _is_valid_theme_name ===


class TestIsValidThemeName:
    def test_valid_names(self):
        assert _is_valid_theme_name("standart")
        assert _is_valid_theme_name("classic")
        assert _is_valid_theme_name("my-theme")
        assert _is_valid_theme_name("a")

    def test_empty_string(self):
        assert not _is_valid_theme_name("")

    def test_too_long(self):
        assert not _is_valid_theme_name("x" * 51)

    def test_abs_path(self):
        assert not _is_valid_theme_name("/etc/passwd")

    def test_path_separator(self):
        assert not _is_valid_theme_name("a/b")

    def test_dotdot(self):
        assert not _is_valid_theme_name("..")

    def test_single_dot(self):
        assert not _is_valid_theme_name(".")

    def test_non_string(self):
        assert not _is_valid_theme_name(123)  # type: ignore[arg-type]
        assert not _is_valid_theme_name(None)  # type: ignore[arg-type]


# === _get_parent_theme_name ===


class TestGetParentThemeName:
    def test_standart_returns_none(self):
        assert _get_parent_theme_name("standart") is None

    def test_default_parent_is_standart(self):
        assert _get_parent_theme_name("classic") == "standart"

    def test_explicit_parent(self):
        assert _get_parent_theme_name("classic-light", "standart-light") == "standart-light"

    def test_self_parent_falls_back(self):
        result = _get_parent_theme_name("classic", "classic")
        assert result == "standart"

    def test_invalid_parent_falls_back(self):
        result = _get_parent_theme_name("classic", "/etc/passwd")
        assert result == "standart"


# === _inject_ast_constants ===


class TestInjectAstConstants:
    def _make_module(self) -> types.ModuleType:
        mod = types.ModuleType("test_module")
        return mod

    def test_injects_string_constants(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('font_family = "Play"\nfont_size = "16px"\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert mod.font_family == "Play"
        assert mod.font_size == "16px"

    def test_injects_numeric_constants(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('width = 150\nheight_ratio = 2.25\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert mod.width == 150
        assert mod.height_ratio == 2.25

    def test_injects_tuple_constants(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('margins = (10, 7, 15, 10)\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert mod.margins == (10, 7, 15, 10)

    def test_injects_list_constants(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('items = [1, 2, 3]\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert mod.items == [1, 2, 3]

    def test_injects_dict_constants(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('config = {"key": "value", "count": 42}\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert mod.config == {"key": "value", "count": 42}

    def test_injects_nested_dict(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('data = [{"position": 0, "color": "#fff"}]\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert mod.data == [{"position": 0, "color": "#fff"}]

    def test_skips_private_names(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('_private = "hidden"\npublic = "visible"\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert not hasattr(mod, "_private")
        assert mod.public == "visible"

    def test_skips_callables(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('def foo(): pass\nresult = "ok"\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert not hasattr(mod, "foo")
        assert mod.result == "ok"

    def test_skips_fstring_assignments(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('border_none = "0px solid"\nSTYLE = f"border: {border_none};"\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert mod.border_none == "0px solid"
        assert not hasattr(mod, "STYLE")

    def test_does_not_overwrite_existing(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('color = "new"\n')
        mod = self._make_module()
        mod.__dict__["color"] = "original"
        _inject_ast_constants(str(src), mod)
        assert mod.color == "original"

    def test_dict_with_variable_refs_skipped(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('accent = "#409EFF"\nanim = {"fill_color": accent}\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert mod.accent == "#409EFF"
        assert not hasattr(mod, "anim")

    def test_syntax_error_does_not_crash(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('this is not valid python {{{\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)

    def test_missing_file_does_not_crash(self):
        mod = self._make_module()
        _inject_ast_constants("/nonexistent/file.py", mod)

    def test_skips_import_statements(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('import os\nfrom pathlib import Path\nvalue = "ok"\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert mod.value == "ok"

    def test_skips_class_definitions(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('class MyClass: pass\nvalue = "ok"\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert not hasattr(mod, "MyClass")
        assert mod.value == "ok"

    def test_skips_function_definitions(self, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text('def helper(): return 1\nvalue = "ok"\n')
        mod = self._make_module()
        _inject_ast_constants(str(src), mod)
        assert not hasattr(mod, "helper")
        assert mod.value == "ok"


# === _inject_parent_theme_constants ===


class TestInjectParentThemeConstants:
    def _make_child_theme(self, tmp_path: Path, name: str, parent: str, styles_content: str):
        """Create a child theme folder with styles.py."""
        theme_dir = tmp_path / "themes" / name
        theme_dir.mkdir(parents=True)
        (theme_dir / "styles.py").write_text(
            f'THEME_INHERITS = "{parent}"\n{styles_content}'
        )
        return theme_dir

    def _make_parent_theme(self, tmp_path: Path, name: str, styles_content: str):
        """Create a parent theme folder with styles.py (no styles/ subdir)."""
        theme_dir = tmp_path / "themes" / name
        theme_dir.mkdir(parents=True)
        (theme_dir / "styles.py").write_text(styles_content)
        return theme_dir

    def _patch_dirs(self, monkeypatch, tmp_path: Path):
        monkeypatch.setattr(
            "portprotonqt.theme_manager.THEMES_DIRS",
            [str(tmp_path / "themes_custom"), str(tmp_path / "themes")],
        )

    def test_inherits_simple_constants_from_styles(self, tmp_path: Path, monkeypatch):
        self._patch_dirs(monkeypatch, tmp_path)
        self._make_parent_theme(
            tmp_path, "parent1",
            'border_none = "0px solid"\ncolor_transparent = "transparent"\n'
        )
        self._make_child_theme(tmp_path, "child1", "parent1", 'my_color = "red"\n')

        mod = types.ModuleType("child1")
        mod.__dict__["my_color"] = "red"
        _inject_parent_theme_constants(mod, "")

        assert mod.__dict__["border_none"] == "0px solid"
        assert mod.__dict__["color_transparent"] == "transparent"
        assert mod.__dict__["my_color"] == "red"

    def test_inherits_dict_constants(self, tmp_path: Path, monkeypatch):
        self._patch_dirs(monkeypatch, tmp_path)
        self._make_parent_theme(
            tmp_path, "parent2",
            'CARD = {"width": 200, "height": 300}\n'
        )
        self._make_child_theme(tmp_path, "child2", "parent2", '')

        mod = types.ModuleType("child2")
        _inject_parent_theme_constants(mod, "")

        assert mod.CARD == {"width": 200, "height": 300}

    def test_constants_py_used_when_exists(self, tmp_path: Path, monkeypatch):
        self._patch_dirs(monkeypatch, tmp_path)
        theme_dir = tmp_path / "themes" / "parent3"
        styles_dir = theme_dir / "styles"
        styles_dir.mkdir(parents=True)
        (styles_dir / "constants.py").write_text('from_const = "constants"\n')
        (theme_dir / "styles.py").write_text('from_styles = "styles"\n')
        self._make_child_theme(tmp_path, "child3", "parent3", '')

        mod = types.ModuleType("child3")
        _inject_parent_theme_constants(mod, "")

        assert mod.from_const == "constants"
        assert mod.from_styles == "styles"

    def test_does_not_inject_submodule_styles(self, tmp_path: Path, monkeypatch):
        self._patch_dirs(monkeypatch, tmp_path)
        theme_dir = tmp_path / "themes" / "parent4"
        styles_dir = theme_dir / "styles"
        styles_dir.mkdir(parents=True)
        (styles_dir / "constants.py").write_text('const_val = "from_constants"\n')
        (styles_dir / "base.py").write_text('base_val = "from_base"\n')
        (theme_dir / "styles.py").write_text('')
        self._make_child_theme(tmp_path, "child4", "parent4", '')

        mod = types.ModuleType("child4")
        _inject_parent_theme_constants(mod, "")

        assert mod.const_val == "from_constants"
        assert not hasattr(mod, "base_val")

    def test_no_parent_does_nothing(self, tmp_path: Path, monkeypatch):
        self._patch_dirs(monkeypatch, tmp_path)
        self._make_child_theme(tmp_path, "orphan", "standart", '')

        mod = types.ModuleType("orphan")
        _inject_parent_theme_constants(mod, "")
        assert not hasattr(mod, "any_key")


# === _read_theme_parent_name ===


class TestReadThemeParentName:
    def test_reads_theme_inherits(self, tmp_path: Path, monkeypatch):
        theme_dir = tmp_path / "themes" / "mytheme"
        theme_dir.mkdir(parents=True)
        (theme_dir / "styles.py").write_text('THEME_INHERITS = "standart"\n')

        monkeypatch.setattr(
            "portprotonqt.theme_manager._find_theme_folder",
            lambda name: str(theme_dir) if name == "mytheme" else None,
        )
        assert _read_theme_parent_name("mytheme") == "standart"

    def test_no_theme_inherits_returns_standart(self, tmp_path: Path, monkeypatch):
        theme_dir = tmp_path / "themes" / "bare"
        theme_dir.mkdir(parents=True)
        (theme_dir / "styles.py").write_text('color = "red"\n')

        monkeypatch.setattr(
            "portprotonqt.theme_manager._find_theme_folder",
            lambda name: str(theme_dir) if name == "bare" else None,
        )
        assert _read_theme_parent_name("bare") == "standart"

    def test_missing_folder_falls_back(self, monkeypatch):
        monkeypatch.setattr(
            "portprotonqt.theme_manager._find_theme_folder",
            lambda name: None,
        )
        assert _read_theme_parent_name("nonexistent") == "standart"


# === Integration: classic/classic-light themes have required styles ===


class TestThemeStylesIntegrity:
    """Verify that classic and classic-light define all styles that
    were lost during the theme rewrite."""

    def test_classic_has_required_styles(self):
        theme_path = Path(__file__).parent.parent / "portprotonqt" / "themes" / "classic" / "styles.py"
        content = theme_path.read_text(encoding="utf-8")

        required_styles = [
            "NAV_BUTTON_STYLE",
            "COMBOBOX_STYLE",
            "SETTINGS_TABLE_COMBOBOX_STYLE",
            "LINE_EDIT_STYLE",
            "ADDGAME_INPUT_STYLE",
            "TAB_STYLE",
            "HINT_BAR_STYLE",
            "QGROUP_BOX_STYLE",
            "WINETRICKS_TABBLE_STYLE",
            "SETTINGS_TITLE_STYLE",
            "ACTION_BUTTON_STYLE",
            "ACTION_BUTTON_ACTIVE_STYLE",
            "LIBRARY_WIDGET_STYLE",
            "GAME_CARD_WINDOW_STYLE",
            "PLAY_BUTTON_STYLE",
            "ADDGAME_BACK_BUTTON_STYLE",
            "LIBRARY_CONTROLS_BUTTON_STYLE",
            "LIBRARY_FILTER_COMBOBOX_STYLE",
            "SEARCH_EDIT_STYLE",
            "THEME_STORE_SCROLL_STYLE",
            "THEME_STORE_CARD_STYLE",
            "THEME_STORE_CARD_TITLE_STYLE",
            "THEME_STORE_CARD_META_STYLE",
            "THEME_STORE_DETAIL_TITLE_STYLE",
            "THEME_STORE_DESCRIPTION_STYLE",
            "THEME_STORE_PREVIEW_STYLE",
        ]
        for style_name in required_styles:
            assert f"{style_name}" in content, f"classic/styles.py missing {style_name}"

    def test_classic_light_has_required_styles(self):
        theme_path = Path(__file__).parent.parent / "portprotonqt" / "themes" / "classic-light" / "styles.py"
        content = theme_path.read_text(encoding="utf-8")

        required_styles = [
            "NAV_BUTTON_STYLE",
            "COMBOBOX_STYLE",
            "LINE_EDIT_STYLE",
            "ADDGAME_INPUT_STYLE",
            "TAB_STYLE",
            "QGROUP_BOX_STYLE",
            "SETTINGS_TITLE_STYLE",
            "ACTION_BUTTON_STYLE",
            "ACTION_BUTTON_ACTIVE_STYLE",
        ]
        for style_name in required_styles:
            assert f"{style_name}" in content, f"classic-light/styles.py missing {style_name}"

    def test_classic_game_card_animation_has_glow_keys(self):
        theme_path = Path(__file__).parent.parent / "portprotonqt" / "themes" / "classic" / "styles.py"
        content = theme_path.read_text(encoding="utf-8")
        assert '"glow_base_alpha"' in content
        assert '"glow_pulse_alpha"' in content

    def test_classic_light_game_card_animation_has_glow_keys(self):
        theme_path = Path(__file__).parent.parent / "portprotonqt" / "themes" / "classic-light" / "styles.py"
        content = theme_path.read_text(encoding="utf-8")
        assert '"glow_base_alpha"' in content
        assert '"glow_pulse_alpha"' in content

    def test_classic_styles_use_fstrings_not_hardcoded(self):
        """Classic QSS style constants should be f-strings, not plain strings
        (except HINT_BAR_STYLE and %-formatted styles for icon paths)."""
        theme_path = Path(__file__).parent.parent / "portprotonqt" / "themes" / "classic" / "styles.py"
        content = theme_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        plain_style_count = 0
        fstring_style_count = 0
        percent_style_count = 0
        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if not target.id.endswith("_STYLE"):
                    continue
                if isinstance(node.value, ast.JoinedStr):
                    fstring_style_count += 1
                elif isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Mod):
                    percent_style_count += 1
                elif isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    plain_style_count += 1

        assert fstring_style_count > 10, "Classic should use f-strings for most styles"
        assert plain_style_count <= 1, f"Classic has {plain_style_count} plain string styles"
        assert percent_style_count <= 3, f"Classic has {percent_style_count} %-formatted styles"

    def test_classic_light_styles_use_fstrings_not_hardcoded(self):
        """Classic-light QSS style constants should be f-strings, not plain strings
        (except %-formatted styles for icon paths)."""
        theme_path = Path(__file__).parent.parent / "portprotonqt" / "themes" / "classic-light" / "styles.py"
        content = theme_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        plain_style_count = 0
        fstring_style_count = 0
        percent_style_count = 0
        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if not target.id.endswith("_STYLE"):
                    continue
                if isinstance(node.value, ast.JoinedStr):
                    fstring_style_count += 1
                elif isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Mod):
                    percent_style_count += 1
                elif isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    plain_style_count += 1

        assert fstring_style_count > 10, "Classic-light should use f-strings for most styles"
        assert plain_style_count == 0, f"Classic-light has {plain_style_count} plain string styles"
        assert percent_style_count <= 3, f"Classic-light has {percent_style_count} %-formatted styles"

    def test_classic_theme_inherits_standart(self):
        theme_path = Path(__file__).parent.parent / "portprotonqt" / "themes" / "classic" / "styles.py"
        content = theme_path.read_text(encoding="utf-8")
        assert 'THEME_INHERITS = "standart"' in content

    def test_classic_light_theme_inherits_standart_light(self):
        theme_path = Path(__file__).parent.parent / "portprotonqt" / "themes" / "classic-light" / "styles.py"
        content = theme_path.read_text(encoding="utf-8")
        assert 'THEME_INHERITS = "standart-light"' in content


# === Integration: all theme .py files are valid Python ===


class TestThemeFilesParse:
    """All themes must be valid, parseable Python files."""

    _themes_dir = Path(__file__).parent.parent / "portprotonqt" / "themes"

    @pytest.mark.parametrize(
        "theme_file",
        sorted(p for p in _themes_dir.glob("*/styles.py")),
    )
    def test_styles_py_parses(self, theme_file: Path):
        source = theme_file.read_text(encoding="utf-8")
        ast.parse(source, filename=str(theme_file))

    @pytest.mark.parametrize(
        "constants_file",
        sorted(_themes_dir.glob("*/styles/constants.py")),
    )
    def test_constants_py_parses(self, constants_file: Path):
        source = constants_file.read_text(encoding="utf-8")
        ast.parse(source, filename=str(constants_file))
