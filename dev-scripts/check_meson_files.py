#!/usr/bin/env python3
"""
Pre-commit hook to check if all Python files in the portprotonqt directory are included in meson.build
and to validate proper syntax in meson.build files.

Checks for:
- Missing files in install_data
- Unbalanced brackets: (), [], {}
- Unclosed quotes: ', "
- Missing/extra commas
- Syntax errors with colons, semicolons
- Duplicate entries
- Invalid control structures (if/endif, foreach/endforeach)
- Common typos and formatting issues
"""

import sys
import re
from pathlib import Path
from collections import Counter
from dataclasses import dataclass


@dataclass
class SyntaxError:
    """Represents a syntax error found in a meson file."""
    line_num: int
    message: str
    severity: str = "error"  # error, warning

    def __str__(self):
        prefix = "WARNING" if self.severity == "warning" else "ERROR"
        return f"Line {self.line_num}: [{prefix}] {self.message}"


class MesonLinter:
    """Linter for meson.build files."""

    # Known meson functions
    KNOWN_FUNCTIONS = {
        'project', 'executable', 'library', 'shared_library', 'static_library',
        'install_data', 'install_subdir', 'install_headers', 'install_man',
        'configure_file', 'custom_target', 'run_command', 'find_program',
        'dependency', 'declare_dependency', 'include_directories',
        'subdir', 'subproject', 'import', 'files', 'join_paths',
        'get_option', 'configuration_data', 'vcs_tag', 'environment',
        'generator', 'test', 'benchmark', 'alias_target', 'both_libraries',
        'build_target', 'jar', 'run_target', 'summary', 'message', 'warning', 'error',
        'assert', 'range', 'meson', 'host_machine', 'target_machine', 'build_machine',
    }

    # Known meson methods that can be called on objects
    KNOWN_METHODS = {
        'found', 'get_variable', 'full_path', 'get_path', 'get',
        'set', 'set_quoted', 'has_key', 'keys', 'version', 'name',
        'project_name', 'project_version', 'current_source_dir',
        'current_build_dir', 'source_root', 'build_root', 'add_install_script',
        'add_postconf_script', 'add_dist_script', 'install_dependency_manifest',
        'override_dependency', 'override_find_program', 'is_cross_build',
        'is_unity', 'is_subproject', 'get_compiler', 'backend', 'global_source_root',
        'global_build_root', 'project_source_root', 'project_build_root',
        'find_installation', 'get_id', 'get_linker_id', 'system', 'cpu_family', 'cpu', 'endian',
    }

    # Keywords that must have matching end keywords
    BLOCK_KEYWORDS = {
        'if': 'endif',
        'foreach': 'endforeach',
    }

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.errors: list[SyntaxError] = []
        self.content = ""
        self.lines: list[str] = []

    def lint(self) -> list[SyntaxError]:
        """Run all linting checks and return list of errors."""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.content = f.read()
        self.lines = self.content.split('\n')

        # Run all checks
        self._check_balanced_brackets()
        self._check_quotes()
        self._check_commas()
        self._check_colons()
        self._check_semicolons()
        self._check_control_structures()
        self._check_duplicate_entries()
        self._check_string_concatenation()
        self._check_operator_spacing()
        self._check_trailing_whitespace()
        self._check_empty_function_calls()
        self._check_assignment_syntax()
        self._check_comparison_operators()
        self._check_common_typos()

        return sorted(self.errors, key=lambda e: e.line_num)

    def _is_in_string(self, line: str, pos: int) -> bool:
        """Check if position is inside a string literal."""
        in_single = False
        in_double = False
        i = 0
        while i < pos and i < len(line):
            char = line[i]
            if char == "'" and not in_double:
                in_single = not in_single
            elif char == '"' and not in_single:
                in_double = not in_double
            i += 1
        return in_single or in_double

    def _is_in_comment(self, line: str, pos: int) -> bool:
        """Check if position is inside a comment."""
        comment_pos = -1
        in_single = False
        in_double = False
        for i, char in enumerate(line):
            if char == "'" and not in_double:
                in_single = not in_single
            elif char == '"' and not in_single:
                in_double = not in_double
            elif char == '#' and not in_single and not in_double:
                comment_pos = i
                break
        return comment_pos != -1 and pos >= comment_pos

    def _strip_strings_and_comments(self, line: str) -> str:
        """Remove string literals and comments from line for analysis."""
        result = []
        in_single = False
        in_double = False
        i = 0
        while i < len(line):
            char = line[i]

            # Check for comment start (outside strings)
            if char == '#' and not in_single and not in_double:
                break

            # Handle string delimiters
            if char == "'" and not in_double:
                in_single = not in_single
                result.append(' ')  # Replace with space to preserve positions
            elif char == '"' and not in_single:
                in_double = not in_double
                result.append(' ')
            elif in_single or in_double:
                result.append(' ')  # Replace string content with spaces
            else:
                result.append(char)

            i += 1

        return ''.join(result)

    def _check_balanced_brackets(self):
        """Check for balanced parentheses, square brackets, and curly braces."""
        bracket_pairs = {'(': ')', '[': ']', '{': '}'}
        bracket_names = {'(': 'parenthesis', '[': 'square bracket', '{': 'curly brace'}

        # Track opening brackets with their positions
        stacks = {'(': [], '[': [], '{': []}

        for line_num, line in enumerate(self.lines, 1):
            stripped = self._strip_strings_and_comments(line)

            for i, char in enumerate(stripped):
                if char in '([{':
                    stacks[char].append((line_num, i))
                elif char in ')]}':
                    opener = {'(': ')', '[': ']', '{': '}'}
                    for open_char, close_char in opener.items():
                        if char == close_char:
                            if not stacks[open_char]:
                                self.errors.append(SyntaxError(
                                    line_num,
                                    f"Unmatched closing {bracket_names[open_char]} '{char}'"
                                ))
                            else:
                                stacks[open_char].pop()

        # Check for unclosed brackets
        for open_char, positions in stacks.items():
            for line_num, col in positions:
                self.errors.append(SyntaxError(
                    line_num,
                    f"Unclosed {bracket_names[open_char]} '{open_char}'"
                ))

    def _check_quotes(self):
        """Check for unclosed or mismatched quotes."""
        for line_num, line in enumerate(self.lines, 1):
            # Skip comment-only lines
            stripped = line.strip()
            if stripped.startswith('#'):
                continue

            # Find comment position
            comment_pos = len(line)
            in_single = False
            in_double = False
            for i, char in enumerate(line):
                if char == "'" and not in_double:
                    in_single = not in_single
                elif char == '"' and not in_single:
                    in_double = not in_double
                elif char == '#' and not in_single and not in_double:
                    comment_pos = i
                    break

            # Analyze only the code part (before comment)
            code_part = line[:comment_pos]

            # Count quotes (simplified check)
            single_quotes = 0
            double_quotes = 0
            in_single = False
            in_double = False

            i = 0
            while i < len(code_part):
                char = code_part[i]

                if char == "'" and not in_double:
                    single_quotes += 1
                    in_single = not in_single
                elif char == '"' and not in_single:
                    double_quotes += 1
                    in_double = not in_double

                i += 1

            if single_quotes % 2 != 0:
                self.errors.append(SyntaxError(
                    line_num,
                    "Unclosed single quote (') - odd number of quotes on line"
                ))

            if double_quotes % 2 != 0:
                self.errors.append(SyntaxError(
                    line_num,
                    'Unclosed double quote (") - odd number of quotes on line'
                ))

    def _check_commas(self):
        """Check for missing, extra, or misplaced commas."""
        # Track if we're inside a function call or list
        paren_depth = 0
        bracket_depth = 0

        for line_num, line in enumerate(self.lines, 1):
            stripped = self._strip_strings_and_comments(line)
            line_stripped = stripped.strip()
            original_stripped = line.strip()

            if not line_stripped:
                continue

            # Check for double commas
            if ',,' in line:  # Use original line
                self.errors.append(SyntaxError(
                    line_num,
                    "Double comma ',,'"
                ))

            # Check for comma at start of line (usually wrong)
            # Use original line - meson uses trailing commas on separate lines
            if original_stripped.startswith(',') and not original_stripped.startswith("',") and not original_stripped.startswith('",'):
                self.errors.append(SyntaxError(
                    line_num,
                    "Comma at start of line - likely misplaced or missing from previous line"
                ))

            # Check for space before comma (but not after string/closing bracket)
            # Pattern like `foo ,` is wrong, but `'file.py',` is fine
            # Only flag if there's whitespace directly before comma, not inside quotes
            space_comma_match = re.search(r'([^\s\'"\]\)])\s+,', line)
            if space_comma_match:
                self.errors.append(SyntaxError(
                    line_num,
                    "Space before comma",
                    severity="warning"
                ))

            # Update bracket depth
            for i, char in enumerate(stripped):
                if char == '(':
                    paren_depth += 1
                elif char == ')':
                    paren_depth -= 1
                elif char == '[':
                    bracket_depth += 1
                elif char == ']':
                    bracket_depth -= 1

        # Second pass: check for missing commas between string literals
        self._check_missing_commas_between_strings()

    def _check_missing_commas_between_strings(self):
        """Check for missing commas between consecutive string literals in lists."""
        # Track bracket depth to know when we're in a function call or list
        paren_depth = 0
        bracket_depth = 0

        for line_num, line in enumerate(self.lines, 1):
            stripped = self._strip_strings_and_comments(line)
            original = line.strip()

            # Update bracket depth
            for char in stripped:
                if char == '(':
                    paren_depth += 1
                elif char == ')':
                    paren_depth -= 1
                elif char == '[':
                    bracket_depth += 1
                elif char == ']':
                    bracket_depth -= 1

            # Skip if not inside brackets
            if paren_depth <= 0 and bracket_depth <= 0:
                continue

            # Check if line ends with a string literal WITHOUT trailing comma
            # Pattern: 'something' or "something" at end of line (possibly with comment)
            ends_with_string_no_comma = re.search(r"['\"]([^'\"]*)['\"](?:\s*#.*)?$", original)
            if ends_with_string_no_comma and not re.search(r"['\"],\s*(?:#.*)?$", original):
                # Check next non-empty line
                for next_num in range(line_num, len(self.lines)):
                    next_line = self.lines[next_num].strip()
                    if not next_line or next_line.startswith('#'):
                        continue

                    # If next line starts with a string literal, missing comma!
                    if re.match(r"^['\"]", next_line):
                        self.errors.append(SyntaxError(
                            line_num,
                            f"Missing comma after string literal - next line starts with another string"
                        ))
                    break

    def _check_colons(self):
        """Check for colon syntax errors."""
        for line_num, line in enumerate(self.lines, 1):
            stripped = self._strip_strings_and_comments(line)
            line_stripped = stripped.strip()

            if not line_stripped:
                continue

            # Check for double colons (not valid in meson)
            if '::' in stripped:
                self.errors.append(SyntaxError(
                    line_num,
                    "Double colon '::' - not valid meson syntax"
                ))

            # Check for colon without space after (in keyword arguments)
            # Pattern: word: followed by non-space
            matches = re.finditer(r'(\w+):(\S)', stripped)
            for match in matches:
                # Skip if it's a path separator like '/dir'
                if match.group(2) != ' ':
                    keyword = match.group(1)
                    # Common keyword arguments
                    if keyword in ['install_dir', 'install_mode', 'rename', 'version',
                                   'meson_version', 'license', 'input', 'output',
                                   'configuration', 'exclude_directories', 'exclude_files',
                                   'required', 'native', 'method', 'pkgconfig']:
                        self.errors.append(SyntaxError(
                            line_num,
                            f"Missing space after colon in keyword argument '{keyword}:'",
                            severity="warning"
                        ))

            # Check for space before colon in keyword arguments
            # But exclude foreach syntax: foreach var : list
            if re.search(r'\w\s+:', stripped) and not re.match(r'^\s*foreach\s+', stripped):
                self.errors.append(SyntaxError(
                    line_num,
                    "Space before colon in keyword argument",
                    severity="warning"
                ))

    def _check_semicolons(self):
        """Check for semicolons which are not valid in meson."""
        for line_num, line in enumerate(self.lines, 1):
            stripped = self._strip_strings_and_comments(line)

            if ';' in stripped:
                self.errors.append(SyntaxError(
                    line_num,
                    "Semicolon ';' found - meson does not use semicolons"
                ))

    def _check_control_structures(self):
        """Check if/endif and foreach/endforeach are properly matched."""
        stack = []  # (keyword, line_num)

        for line_num, line in enumerate(self.lines, 1):
            stripped = self._strip_strings_and_comments(line).strip()

            if not stripped:
                continue

            # Check for if statement
            if re.match(r'^if\s+', stripped) or stripped == 'if':
                stack.append(('if', line_num))
            elif stripped == 'else' or re.match(r'^else\s*$', stripped):
                if not stack or stack[-1][0] != 'if':
                    self.errors.append(SyntaxError(
                        line_num,
                        "'else' without matching 'if'"
                    ))
            elif re.match(r'^elif\s+', stripped):
                if not stack or stack[-1][0] != 'if':
                    self.errors.append(SyntaxError(
                        line_num,
                        "'elif' without matching 'if'"
                    ))
            elif stripped == 'endif' or re.match(r'^endif\s*$', stripped):
                if not stack or stack[-1][0] != 'if':
                    self.errors.append(SyntaxError(
                        line_num,
                        "'endif' without matching 'if'"
                    ))
                elif stack:
                    stack.pop()

            # Check for foreach statement
            elif re.match(r'^foreach\s+', stripped):
                stack.append(('foreach', line_num))
            elif stripped == 'endforeach' or re.match(r'^endforeach\s*$', stripped):
                if not stack or stack[-1][0] != 'foreach':
                    self.errors.append(SyntaxError(
                        line_num,
                        "'endforeach' without matching 'foreach'"
                    ))
                elif stack:
                    stack.pop()

        # Check for unclosed blocks
        for keyword, line_num in stack:
            end_keyword = self.BLOCK_KEYWORDS.get(keyword, f'end{keyword}')
            self.errors.append(SyntaxError(
                line_num,
                f"'{keyword}' without matching '{end_keyword}'"
            ))

    def _check_duplicate_entries(self):
        """Check for duplicate file entries in install_data calls."""
        # Find all install_data blocks
        pattern = r'install_data\s*\(((?:[^()]|\((?:[^()]|\([^()]*\))*\))*)\)'
        matches = re.finditer(pattern, self.content, re.DOTALL)

        for match in matches:
            block = match.group(1)
            # Find line number of this block
            start_pos = match.start()
            line_num = self.content[:start_pos].count('\n') + 1

            # Extract all string entries - only standalone file names, not paths
            # Split by newlines and extract file entries
            entries = []
            for entry_match in re.finditer(r"^\s*'([^'/]+\.[a-z]+)'", block, re.MULTILINE):
                entries.append(entry_match.group(1))

            # Find duplicates
            counter = Counter(entries)
            for entry, count in counter.items():
                if count > 1:
                    self.errors.append(SyntaxError(
                        line_num,
                        f"Duplicate entry '{entry}' appears {count} times in install_data",
                        severity="warning"
                    ))

    def _check_string_concatenation(self):
        """Check for incorrect string concatenation."""
        for line_num, line in enumerate(self.lines, 1):
            # Check for + between strings (should use / for paths)
            if re.search(r"'\s*\+\s*'", line):
                self.errors.append(SyntaxError(
                    line_num,
                    "String concatenation with '+' - consider using '/' for paths",
                    severity="warning"
                ))

            # Check for missing operator between strings
            # Pattern: 'string' 'string' without operator
            stripped = self._strip_strings_and_comments(line)
            if re.search(r"'\s+'", line) and "'" in line:
                # More precise check
                in_call = '(' in stripped
                if in_call:
                    # Could be separate arguments - that's ok
                    pass

    def _check_operator_spacing(self):
        """Check for proper spacing around operators."""
        for line_num, line in enumerate(self.lines, 1):
            stripped = self._strip_strings_and_comments(line)

            if not stripped.strip():
                continue

            # Check for missing space around = (but not ==, !=, <=, >=)
            # Pattern: identifier=value without spaces
            if re.search(r'[a-zA-Z_]\w*=[^=]', stripped):
                # But allow keyword arguments with colon
                if not re.search(r'[a-zA-Z_]\w*\s*:', stripped):
                    # Check it's not inside a function call keyword arg
                    if '(' not in stripped or stripped.index('=') < stripped.index('('):
                        pass  # This might be intentional in some contexts

            # Check for == used for assignment (common mistake)
            if re.search(r'^[a-zA-Z_]\w*\s*==\s*[^=]', stripped.strip()):
                self.errors.append(SyntaxError(
                    line_num,
                    "Possible incorrect use of '==' instead of '=' for assignment",
                    severity="warning"
                ))

    def _check_trailing_whitespace(self):
        """Check for trailing whitespace."""
        for line_num, line in enumerate(self.lines, 1):
            if line != line.rstrip():
                self.errors.append(SyntaxError(
                    line_num,
                    "Trailing whitespace",
                    severity="warning"
                ))

    def _check_empty_function_calls(self):
        """Check for potentially erroneous empty function calls."""
        for line_num, line in enumerate(self.lines, 1):
            # Use original line - we want to check if there are actual arguments
            # Skip comment part
            code_line = line.split('#')[0] if '#' in line else line

            # Check for function calls with nothing (not even keyword args)
            # Pattern: function_name() with no arguments where arguments are typically required
            required_arg_functions = ['install_data', 'install_subdir', 'dependency',
                                       'executable', 'library', 'project', 'subdir']
            for func in required_arg_functions:
                if re.search(rf'\b{func}\s*\(\s*\)', code_line):
                    self.errors.append(SyntaxError(
                        line_num,
                        f"'{func}()' called with no arguments - this is likely an error"
                    ))

    def _check_assignment_syntax(self):
        """Check for common assignment syntax errors."""
        for line_num, line in enumerate(self.lines, 1):
            stripped = self._strip_strings_and_comments(line).strip()

            if not stripped:
                continue

            # Check for := (not valid in meson)
            if ':=' in stripped:
                self.errors.append(SyntaxError(
                    line_num,
                    "':=' is not valid meson syntax - use '=' for assignment"
                ))

            # Check for => (not valid in meson)
            if '=>' in stripped:
                self.errors.append(SyntaxError(
                    line_num,
                    "'=>' is not valid meson syntax"
                ))

    def _check_comparison_operators(self):
        """Check for valid comparison operators."""
        for line_num, line in enumerate(self.lines, 1):
            stripped = self._strip_strings_and_comments(line)

            # Check for === (not valid in meson)
            if '===' in stripped:
                self.errors.append(SyntaxError(
                    line_num,
                    "'===' is not valid meson syntax - use '==' for comparison"
                ))

            # Check for !== (not valid in meson)
            if '!==' in stripped:
                self.errors.append(SyntaxError(
                    line_num,
                    "'!==' is not valid meson syntax - use '!=' for comparison"
                ))

            # Check for <> (old not equal syntax)
            if '<>' in stripped:
                self.errors.append(SyntaxError(
                    line_num,
                    "'<>' is not valid meson syntax - use '!=' for not equal"
                ))

    def _check_common_typos(self):
        """Check for common typos in meson keywords and functions."""
        common_typos = {
            'instal_data': 'install_data',
            'install_dataa': 'install_data',
            'instlal_data': 'install_data',
            'install_subdr': 'install_subdir',
            'install_suddir': 'install_subdir',
            'depedency': 'dependency',
            'dependecy': 'dependency',
            'dependancy': 'dependency',
            'excutable': 'executable',
            'executalbe': 'executable',
            'configrue_file': 'configure_file',
            'configure_fiel': 'configure_file',
            'configuartion_data': 'configuration_data',
            'configuration_dataa': 'configuration_data',
            'get_optin': 'get_option',
            'get_optoin': 'get_option',
            'joint_paths': 'join_paths',
            'join_pathss': 'join_paths',
            'forech': 'foreach',
            'foreahc': 'foreach',
            'enforeach': 'endforeach',
            'endforach': 'endforeach',
            'ednif': 'endif',
            'enidif': 'endif',
            'elseif': 'elif',
            'else if': 'elif',
            'porject': 'project',
            'projcet': 'project',
            'mesno': 'meson',
            'meosn': 'meson',
            'vesion': 'version',
            'verison': 'version',
            'licnese': 'license',
            'lisence': 'license',
            'licence': 'license',
        }

        for line_num, line in enumerate(self.lines, 1):
            stripped = self._strip_strings_and_comments(line).lower()

            for typo, correct in common_typos.items():
                if typo in stripped:
                    self.errors.append(SyntaxError(
                        line_num,
                        f"Possible typo '{typo}' - did you mean '{correct}'?"
                    ))


def get_python_files_from_directory(directory):
    """Get all Python files from a directory (excluding __pycache__ and other non-source files)"""
    python_files = []
    for file_path in Path(directory).iterdir():
        if (file_path.is_file() and
            file_path.suffix == '.py' and
            file_path.name != '__pycache__' and
            not file_path.name.startswith('.') and  # Skip hidden files
            file_path.name != 'meson.build'):       # Exclude meson.build itself
            python_files.append(file_path.name)
    return sorted(python_files)


def get_files_from_meson_build(meson_file_path):
    """Extract file names from all install_* sections in meson.build"""
    with open(meson_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    files = []
    
    # Define all possible install functions that could contain files
    install_functions = [
        'install_data',           # Standard data installation
        'install_sources',        # Source files installation
        'install_subdir',         # Subdirectory installation (doesn't list individual files)
        'install_headers',        # Header files installation
        'install_man',            # Manual pages installation
        'install_symlink',        # Symlinks installation
        'install_emptydir'        # Empty directories installation
    ]
    
    # Process each install function
    for func_name in install_functions:
        # Skip install_subdir since it installs whole directories, not individual files
        if func_name == 'install_subdir':
            continue
            
        # Create regex pattern for this function
        pattern = rf'{func_name}\(\s*((?:[^()]|\((?:[^()]|\([^()]*\))*\))*)\s*\)'
        matches = re.findall(pattern, content, re.DOTALL)

        for match in matches:
            # Extract individual file names (strings between quotes)
            # Looking for common file extensions used in the project
            file_matches = re.findall(r"'([^']*(?:\.py|\.ui|\.qml|\.js|\.css|\.svg|\.json|\.txt|\.md|\.h|\.c|\.cpp|\.hpp|\.xml|\.ini|\.desktop|\.metainfo|\.pot|\.po))'", match)
            files.extend(file_matches)
    
    for match in matches:
        # Extract individual file names (strings between quotes)
        file_matches = re.findall(r"'([^']*(?:\.py|\.ui|\.qml|\.js|\.css|\.svg|\.json|\.txt|\.md))'", match)
        files.extend(file_matches)

    return sorted(set(files))  # Use set to remove duplicates


def check_syntax(repo_root: Path) -> tuple[list[str], list[str]]:
    """Check meson.build syntax and return (errors, warnings)."""
    meson_files_list = list(repo_root.glob("**/meson.build"))

    all_errors = []
    all_warnings = []

    for meson_file in meson_files_list:
        linter = MesonLinter(meson_file)
        errors = linter.lint()

        for error in errors:
            full_msg = f"{meson_file}: {error}"
            if error.severity == "warning":
                all_warnings.append(full_msg)
            else:
                all_errors.append(full_msg)

    return all_errors, all_warnings


def check_files(repo_root: Path) -> list[str]:
    """Check if all Python files are included in meson.build. Return list of missing files."""
    portprotonqt_dir = repo_root / 'portprotonqt'
    portprotonqt_meson = portprotonqt_dir / 'meson.build'

    if not portprotonqt_meson.exists():
        return []

    dir_files = get_python_files_from_directory(portprotonqt_dir)
    meson_files = get_files_from_meson_build(portprotonqt_meson)

    return [f for f in dir_files if f not in meson_files]


def main():
    repo_root = Path(__file__).parent.parent
    exit_code = 0

    # Check syntax
    all_errors, all_warnings = check_syntax(repo_root)

    if all_warnings:
        print("WARNINGS found in meson.build files:")
        for warning in all_warnings:
            print(f"  - {warning}")
        print()

    if all_errors:
        print("ERRORS found in meson.build files:")
        for error in all_errors:
            print(f"  - {error}")
        print("\nPlease fix these syntax errors in the respective meson.build files")
        exit_code = 1

    # Check files inclusion (only if syntax is OK)
    if exit_code == 0:
        missing_files = check_files(repo_root)

        if missing_files:
            print("ERROR: The following files are present in the directory but missing from meson.build:")
            for file in missing_files:
                print(f"  - {file}")
            print("\nPlease add these files to the install_data section in portprotonqt/meson.build")
            exit_code = 1

    # Success message
    if exit_code == 0:
        if all_warnings:
            print("All checks passed (with warnings)")
        else:
            print("All checks passed: syntax is valid and all files are listed")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
