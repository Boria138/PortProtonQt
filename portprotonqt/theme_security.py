"""
Theme security module for PortProtonQt.
Provides enhanced security checks for theme files to prevent malicious code execution.
"""
import ast
import os
from portprotonqt.logger import get_logger


logger = get_logger(__name__)


class ThemeSecurityChecker:
    """
    Enhanced security checker for theme files.
    Identifies and blocks various attack vectors in theme Python files.
    """

    # Basic forbidden modules that could allow dangerous operations
    FORBIDDEN_MODULES = {
        # File system operations
        "os", "shutil", "pathlib", "glob", "tempfile", "filecmp", "fileinput",
        "linecache", "io", "mmap", "fnmatch", "difflib",

        # Process and system operations
        "subprocess", "sys", "ctypes", "cffi", "platform", "resource", "signal",
        "multiprocessing", "concurrent", "threading", "asyncio", "select",
        "selectors", "queue", "sched", "contextvars",

        # Network operations
        "socket", "urllib", "urllib2", "urllib.request", "urllib.parse",
        "urllib.error", "urllib.robotparser", "http", "http.client",
        "http.cookies", "http.cookiejar", "ftplib", "telnetlib", "smtplib",
        "poplib", "imaplib", "nntplib", "socketserver", "xmlrpc", "xmlrpc.client",
        "xmlrpc.server", "ipaddress", "webbrowser", "ssl", "uuid",

        # Code execution and dynamic imports
        "code", "codeop", "compileall", "py_compile", "runpy", "zipimport",
        "pkgutil", "pkg_resources", "importlib", "importlib.util",
        "importlib.import_module", "importlib.resources", "importlib.metadata",
        "builtins", "exec", "eval", "__import__", "compile", "execfile",
        "imp", "importlib.machinery", "importlib.abc", "importlib.load_module",
        "importlib.reload", "imp.load_source", "imp.load_compiled", "imp.find_module",
        "imp.get_suffixes", "imp.init_builtin", "imp.init_frozen", "imp.is_builtin",
        "imp.is_frozen", "imp.lock_held", "imp.lock", "imp.reload", "imp.load_module",

        # Data serialization and code execution
        "pickle", "marshal", "shelve", "json", "yaml", "configparser", "binascii", "base64",

        # Databases and storage
        "sqlite3", "dbapi2", "sqlite_web", "dataset", "records", "tinydb",

        # Cryptography and security
        "hashlib", "hmac", "secrets", "crypt", "cryptography",

        # External libraries that could be dangerous
        "requests", "aiohttp", "selenium", "paramiko", "fabric", "docker",
        "boto", "boto3", "pymongo", "pymysql", "psycopg2", "redis", "pika",
        "kafka", "celery", "rq", "playwright", "mechanize", "scrapy",
        "beautifulsoup4", "lxml", "html5lib", "pyautogui",
        "keyboard", "mouse", "pynput", "psutil", "wmi", "pywin32",

        # GUI and UI libraries that could be used for malicious purposes
        "tkinter", "PyQt4", "PyQt5", "PyQt6", "PySide", "PySide2", "PySide6",
        "kivy", "kivymd", "wx", "wxPython", "pygame", "flask", "django",
        "fastapi", "tornado", "bottle", "cherrypy", "falcon", "sanic",


    }

    # Forbidden functions that could allow dangerous operations
    FORBIDDEN_FUNCTIONS = {
        # Code execution
        "exec", "eval", "compile", "execfile", "__import__",

        # Import-related functions that allow dynamic imports
        "importlib.import_module", "importlib.util", "importlib.resources",
        "importlib.metadata", "builtins.__import__", "builtins.eval",
        "builtins.exec", "builtins.compile", "builtins.open",

        # File system operations
        "open", "file", "os.open", "os.fdopen", "io.open", "tempfile.mktemp",
        "tempfile.mkdtemp", "tempfile.NamedTemporaryFile", "tempfile.SpooledTemporaryFile",

        # System operations
        "os.system", "os.popen", "os.spawnl", "os.spawnle", "os.spawnlp",
        "os.spawnlpe", "os.spawnv", "os.spawnve", "os.spawnvp", "os.spawnvpe",
        "os.startfile", "os.execv", "os.execve", "os.execl", "os.execle", "os.execlp",
        "os.execlpe", "subprocess.run", "subprocess.call",
        "subprocess.check_call", "subprocess.check_output", "subprocess.Popen",

        # Network operations
        "socket.socket", "socket.create_connection", "urllib.request.urlopen",
        "urllib.request.Request", "requests.get", "requests.post", "requests.put",
        "requests.delete", "requests.patch", "requests.head", "requests.options",
        "aiohttp.ClientSession", "http.client.HTTPConnection", "http.client.HTTPSConnection",

        # Reflection and introspection that could be dangerous
        "getattr", "setattr", "hasattr", "delattr", "globals", "locals", "vars",
        "dir", "type", "id", "object", "issubclass", "isinstance", "callable",
        "iter", "next", "reversed", "slice", "sorted", "filter", "map", "reduce",

        # Input functions
        "input", "raw_input",

        # Built-in functions that could be dangerous in certain contexts
        "breakpoint", "quit", "exit", "copyright", "credits", "license", "help",

        # Dynamic attribute access that could be dangerous
        "operator.attrgetter", "operator.itemgetter", "operator.methodcaller",

        "apply", "buffer", "coerce", "intern", "long", "unichr",
        "unicode", "xrange", "cmp", "reload", "basestring",
    }

    # Forbidden attributes that could be dangerous
    FORBIDDEN_ATTRIBUTES = {
        # Special methods and attributes that could be used for code execution
        "__class__", "__dict__", "__module__", "__subclasses__", "__bases__",
        "__mro__", "__call__", "__func__", "__self__", "__code__", "__closure__",
        "__globals__", "__name__", "__file__", "__path__", "__package__",
        "__loader__", "__spec__", "__builtins__", "__import__", "__new__",
        "__init__", "__del__", "__repr__", "__str__", "__bytes__", "__format__",
        "__lt__", "__le__", "__eq__", "__ne__", "__gt__", "__ge__", "__hash__",
        "__bool__", "__dir__", "__delattr__", "__getattribute__",
        "__setattr__", "__delete__", "__set__", "__get__", "__set_name__",
        "__prepare__", "__init_subclass__", "__instancecheck__", "__subclasscheck__",
        "__subclasshook__", "__class_getitem__", "__annotations__", "__weakref__",
    }

    def __init__(self):
        self.has_errors = False
        self.errors = []

    def check_theme_safety(self, theme_file: str) -> tuple[bool, list[str]]:
        """
        Enhanced security check for theme files.
        Returns (is_safe, list_of_errors).
        """
        self.has_errors = False
        self.errors = []

        try:
            with open(theme_file, encoding='utf-8') as f:
                content = f.read()

            # Check for syntax errors first
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                self.errors.append(f"Syntax error in file {theme_file}: {e}")
                self.has_errors = True
                return not self.has_errors, self.errors

            # Walk through the AST and check for dangerous patterns
            for node in ast.walk(tree):
                self._check_node_safety(node, theme_file)

        except Exception as e:
            self.errors.append(f"Failed to check theme safety for {theme_file}: {e}")
            self.has_errors = True

        return not self.has_errors, self.errors

    def _check_node_safety(self, node, theme_file: str):
        """Check individual AST nodes for security issues."""
        # Check for forbidden imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                module_name = alias.name
                # Handle from ... import ... cases
                if isinstance(node, ast.ImportFrom) and node.module:
                    module_name = node.module

                # Check if the module is in the forbidden list
                if module_name in self.FORBIDDEN_MODULES:
                    error_msg = f"Forbidden module '{module_name}' found in file {theme_file}"
                    self.errors.append(error_msg)
                    self.has_errors = True
                # Also check submodules (e.g., "os.path" should trigger on "os")
                for forbidden_module in self.FORBIDDEN_MODULES:
                    if module_name.startswith(forbidden_module + "."):
                        error_msg = f"Forbidden submodule '{module_name}' found in file {theme_file}"
                        self.errors.append(error_msg)
                        self.has_errors = True
                        break

        # Check for forbidden function calls
        elif isinstance(node, ast.Call):
            # Check for direct function calls (e.g., eval(), exec())
            if isinstance(node.func, ast.Name):
                if node.func.id in self.FORBIDDEN_FUNCTIONS:
                    error_msg = f"Forbidden function '{node.func.id}' found in file {theme_file}"
                    self.errors.append(error_msg)
                    self.has_errors = True

            # Check for method calls (e.g., os.system(), requests.get())
            elif isinstance(node.func, ast.Attribute):
                # Get the full function path (e.g., "os.system")
                full_func_name = self._get_attribute_path(node.func)
                if full_func_name in self.FORBIDDEN_FUNCTIONS:
                    error_msg = f"Forbidden function '{full_func_name}' found in file {theme_file}"
                    self.errors.append(error_msg)
                    self.has_errors = True
                # Check just the attribute name
                elif node.func.attr in self.FORBIDDEN_FUNCTIONS:
                    error_msg = f"Forbidden method '{node.func.attr}' called in file {theme_file}"
                    self.errors.append(error_msg)
                    self.has_errors = True

        # Check for import expressions that might be used dynamically
        elif isinstance(node, ast.Expr):
            # Check if the expression is a call to an import-related function
            if isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Name):
                    if node.value.func.id in self.FORBIDDEN_FUNCTIONS:
                        error_msg = f"Forbidden function '{node.value.func.id}' found in expression in file {theme_file}"
                        self.errors.append(error_msg)
                        self.has_errors = True
                elif isinstance(node.value.func, ast.Attribute):
                    full_func_name = self._get_attribute_path(node.value.func)
                    if full_func_name in self.FORBIDDEN_FUNCTIONS:
                        error_msg = f"Forbidden function '{full_func_name}' found in expression in file {theme_file}"
                        self.errors.append(error_msg)
                        self.has_errors = True

        # Check for forbidden attributes
        elif isinstance(node, ast.Attribute):
            if node.attr in self.FORBIDDEN_ATTRIBUTES:
                error_msg = f"Forbidden attribute access '{node.attr}' found in file {theme_file}"
                self.errors.append(error_msg)
                self.has_errors = True

        # Check for dangerous expressions (like accessing builtins)
        elif isinstance(node, ast.Name):
            if node.id in self.FORBIDDEN_FUNCTIONS:
                error_msg = f"Forbidden function '{node.id}' found in file {theme_file}"
                self.errors.append(error_msg)
                self.has_errors = True

        # Check for potentially dangerous f-strings that might execute code
        elif isinstance(node, ast.FormattedValue):
            # Check if the format value contains dangerous expressions
            if hasattr(node, 'value'):
                # Recursively check the value for dangerous patterns
                if isinstance(node.value, ast.Call):
                    func_name = self._get_attribute_path(node.value.func)
                    if func_name in self.FORBIDDEN_FUNCTIONS:
                        error_msg = f"Forbidden function '{func_name}' found in f-string in file {theme_file}"
                        self.errors.append(error_msg)
                        self.has_errors = True
                elif isinstance(node.value, ast.Attribute) and node.value.attr in self.FORBIDDEN_ATTRIBUTES:
                    error_msg = f"Forbidden attribute access '{node.value.attr}' found in f-string in file {theme_file}"
                    self.errors.append(error_msg)
                    self.has_errors = True
                elif isinstance(node.value, ast.Name) and node.value.id in self.FORBIDDEN_FUNCTIONS:
                    error_msg = f"Forbidden function '{node.value.id}' found in f-string in file {theme_file}"
                    self.errors.append(error_msg)
                    self.has_errors = True
                # Recursively check nested expressions in f-strings
                elif isinstance(node.value, (ast.BinOp, ast.UnaryOp, ast.BoolOp)):
                    # Check for complex expressions that might contain dangerous operations
                    self._check_node_safety(node.value, theme_file)
                # Check for nested function calls that might be dangerous
                elif isinstance(node.value, ast.Subscript):
                    # Check if we're accessing something potentially dangerous
                    if hasattr(node.value, 'value') and isinstance(node.value.value, ast.Call):
                        func_name = self._get_attribute_path(node.value.value.func)
                        if func_name in self.FORBIDDEN_FUNCTIONS:
                            error_msg = f"Forbidden function '{func_name}' found in f-string subscript in file {theme_file}"
                            self.errors.append(error_msg)
                            self.has_errors = True

        # Check for string concatenation attacks (e.g., "im" + "port", "exec", etc.)
        elif isinstance(node, ast.BinOp):
            # Check for string concatenations that might be used to obfuscate dangerous code
            if isinstance(node.op, ast.Add):  # String concatenation with +
                left_val = self._get_constant_value(node.left)
                right_val = self._get_constant_value(node.right)

                if left_val is not None and right_val is not None:
                    concatenated = str(left_val) + str(right_val)
                    # Check if concatenated string forms a dangerous module/function name
                    if concatenated in self.FORBIDDEN_MODULES or concatenated in self.FORBIDDEN_FUNCTIONS:
                        error_msg = f"Potential string concatenation attack detected: '{concatenated}' in file {theme_file}"
                        self.errors.append(error_msg)
                        self.has_errors = True
                    # Also check if it's a substring of forbidden items
                    for forbidden_module in self.FORBIDDEN_MODULES:
                        if concatenated in forbidden_module or forbidden_module in concatenated:
                            error_msg = f"Potential string concatenation attack detected: '{concatenated}' matches forbidden module '{forbidden_module}' in file {theme_file}"
                            self.errors.append(error_msg)
                            self.has_errors = True
                    for forbidden_func in self.FORBIDDEN_FUNCTIONS:
                        if concatenated in forbidden_func or forbidden_func in concatenated:
                            error_msg = f"Potential string concatenation attack detected: '{concatenated}' matches forbidden function '{forbidden_func}' in file {theme_file}"
                            self.errors.append(error_msg)
                            self.has_errors = True

        # Check for common obfuscation techniques
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ['eval', 'exec']:
                # Check if eval/exec is being called with obfuscated content
                if len(node.args) > 0:
                    first_arg = node.args[0]
                    arg_value = self._get_constant_value(first_arg)
                    if arg_value:
                        # Check if eval/exec argument contains dangerous content
                        for forbidden_func in self.FORBIDDEN_FUNCTIONS:
                            if forbidden_func in str(arg_value):
                                error_msg = f"Potential obfuscated code execution detected: '{forbidden_func}' found in eval/exec argument in file {theme_file}"
                                self.errors.append(error_msg)
                                self.has_errors = True

        # Check for character code arrays (another obfuscation method)
        elif isinstance(node, ast.List) or isinstance(node, ast.Tuple):
            # Check if it's a list of character codes that might be converted to dangerous strings
            if all(isinstance(elt, (ast.Num, ast.Constant)) and isinstance(self._get_constant_value(elt), int) for elt in node.elts):
                # This might be an array of ASCII codes
                try:
                    char_codes = [self._get_constant_value(elt) for elt in node.elts if self._get_constant_value(elt) is not None]
                    # Filter to only include actual integers for character codes
                    int_char_codes = [code for code in char_codes if isinstance(code, int)]
                    if int_char_codes and all(isinstance(code, int) and 32 <= code <= 126 for code in int_char_codes):  # Printable ASCII range
                        decoded_str = ''.join(chr(code) for code in int_char_codes)
                        # Check if decoded string contains dangerous content
                        for forbidden_module in self.FORBIDDEN_MODULES:
                            if forbidden_module in decoded_str:
                                error_msg = f"Potential character code obfuscation detected: '{forbidden_module}' found in decoded array in file {theme_file}"
                                self.errors.append(error_msg)
                                self.has_errors = True
                        for forbidden_func in self.FORBIDDEN_FUNCTIONS:
                            if forbidden_func in decoded_str:
                                error_msg = f"Potential character code obfuscation detected: '{forbidden_func}' found in decoded array in file {theme_file}"
                                self.errors.append(error_msg)
                                self.has_errors = True
                except (ValueError, TypeError, AttributeError):
                    # If conversion fails, continue
                    pass

    def _get_attribute_path(self, attr_node):
        """Extract the full attribute path from an AST node (e.g., 'os.path.join')."""
        if isinstance(attr_node, ast.Name):
            return attr_node.id
        elif isinstance(attr_node, ast.Attribute):
            parent_path = self._get_attribute_path(attr_node.value)
            return f"{parent_path}.{attr_node.attr}"
        return ""

    def _get_constant_value(self, node):
        """Extract the constant value from an AST node if it's a constant."""
        if isinstance(node, ast.Str):  # Python < 3.8
            return node.s
        elif isinstance(node, ast.Constant):  # Python 3.8+
            return node.value
        elif isinstance(node, ast.Num):  # Python < 3.8 for numbers
            return node.n
        elif isinstance(node, ast.Bytes):  # For bytes
            return node.s
        return None


def check_theme_safety(theme_file: str) -> bool:
    """
    Convenience function to check theme safety.
    Returns True if the theme is safe, False otherwise.
    """
    checker = ThemeSecurityChecker()
    is_safe, errors = checker.check_theme_safety(theme_file)

    for error in errors:
        logger.error(error)

    return is_safe


def is_safe_image_file(file_path: str) -> bool:
    """
    Check if an image file is safe to load by verifying its extension and basic file properties.
    This helps prevent loading malicious files that might be disguised as images.
    """

    # Check file extension first
    safe_extensions = {'.png', '.jpg', '.jpeg', '.svg', '.bmp', '.gif', '.webp', '.ico'}
    _, ext = os.path.splitext(file_path.lower())

    if ext not in safe_extensions:
        logger.warning(f"Unsafe image file extension for {file_path}: {ext}")
        return False

    # Check file size (prevent loading extremely large files)
    try:
        file_size = os.path.getsize(file_path)
        # Limit to 50MB to prevent memory exhaustion attacks
        if file_size > 50 * 1024 * 1024:  # 50MB
            logger.warning(f"Image file too large ({file_size} bytes): {file_path}")
            return False
    except OSError:
        logger.error(f"Could not get file size for {file_path}")
        return False

    # For security, we can also check the file's magic bytes (first few bytes)
    # to ensure it's actually an image file and not a disguised executable
    try:
        with open(file_path, 'rb') as f:
            header = f.read(32)  # Read first 32 bytes

        # Check for common image file signatures (magic bytes)
        if ext == '.png':
            # PNG signature: 89 50 4E 47 0D 0A 1A 0A
            if not header.startswith(b'\x89PNG\r\n\x1a\n'):
                logger.warning(f"File {file_path} does not have PNG signature")
                return False
        elif ext in ['.jpg', '.jpeg']:
            # JPEG signature: FF D8 FF
            if not header.startswith(b'\xff\xd8\xff'):
                logger.warning(f"File {file_path} does not have JPEG signature")
                return False
        elif ext == '.gif':
            # GIF signature: 47 49 46 38 (GIF8)
            if not header.startswith(b'GIF8'):
                logger.warning(f"File {file_path} does not have GIF signature")
                return False
        elif ext == '.bmp':
            # BMP signature: 42 4D (BM)
            if not header.startswith(b'BM'):
                logger.warning(f"File {file_path} does not have BMP signature")
                return False
        # SVG is text-based, so we just check if it contains XML-like structure
        elif ext == '.svg':
            try:
                header_str = header.decode('utf-8', errors='ignore')
                # Basic check for SVG XML structure
                if not ('<svg' in header_str or '<?xml' in header_str):
                    logger.warning(f"File {file_path} does not appear to be a valid SVG")
                    return False
            except UnicodeDecodeError:
                logger.warning(f"SVG file {file_path} contains invalid UTF-8")
                return False
    except Exception as e:
        logger.error(f"Error checking image file signature for {file_path}: {e}")
        return False

    return True
