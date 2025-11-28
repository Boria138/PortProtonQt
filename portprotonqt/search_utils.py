"""
Utility module for search optimizations including Trie, hash tables, and fuzzy matching.
"""
import concurrent.futures
import threading
from collections.abc import Callable
from typing import Any
from rapidfuzz import fuzz
from threading import Lock
from portprotonqt.logger import get_logger
from PySide6.QtCore import QThread, QRunnable, Signal, QObject, QTimer
import requests

logger = get_logger(__name__)

class TrieNode:
    """Node in the Trie data structure."""
    def __init__(self):
        self.children = {}
        self.is_end_word = False
        self.payload = None  # Store the original data in leaf nodes

class Trie:
    """Trie data structure for efficient prefix-based searching."""
    def __init__(self):
        self.root = TrieNode()
        self._lock = Lock()  # Thread safety for concurrent access

    def insert(self, key: str, payload: Any):
        """Insert a key with payload into the Trie."""
        with self._lock:
            node = self.root
            for char in key.lower():
                if char not in node.children:
                    node.children[char] = TrieNode()
                node = node.children[char]
            node.is_end_word = True
            node.payload = payload

    def search_prefix(self, prefix: str) -> list[tuple[str, Any]]:
        """Find all entries with the given prefix."""
        with self._lock:
            node = self.root
            for char in prefix.lower():
                if char not in node.children:
                    return []
                node = node.children[char]

            results = []
            self._collect_all(node, prefix.lower(), results)
            return results

    def _collect_all(self, node: TrieNode, current_prefix: str, results: list[tuple[str, Any]]):
        """Collect all entries from the current node."""
        if node.is_end_word:
            results.append((current_prefix, node.payload))

        for char, child_node in node.children.items():
            self._collect_all(child_node, current_prefix + char, results)

class FuzzySearchIndex:
    """Index for fuzzy string matching with rapidfuzz."""
    def __init__(self, items: list[tuple[str, Any]] | None = None):
        self.items: list[tuple[str, Any]] = items or []
        self.normalized_items: list[tuple[str, Any]] = []
        self._lock = Lock()
        self._build_normalized_index()

    def _build_normalized_index(self):
        """Build a normalized index for fuzzy matching."""
        with self._lock:
            self.normalized_items = [(self._normalize(item[0]), item[1]) for item in self.items]

    def _normalize(self, s: str) -> str:
        """Normalize string for fuzzy matching."""
        s = s.lower()
        for ch in ["™", "®"]:
            s = s.replace(ch, "")
        for ch in ["-", ":", ","]:
            s = s.replace(ch, " ")
        s = " ".join(s.split())
        for suffix in ["bin", "app"]:
            if s.endswith(suffix):
                s = s[:-len(suffix)].strip()
        keywords_to_remove = {"ultimate", "edition", "definitive", "complete", "remastered"}
        words = s.split()
        filtered_words = [word for word in words if word not in keywords_to_remove]
        return " ".join(filtered_words)

    def fuzzy_search(self, query: str, limit: int = 5, min_score: float = 60.0) -> list[tuple[str, Any, float]]:
        """Perform fuzzy search using rapidfuzz."""
        with self._lock:
            if not query or not self.normalized_items:
                return []

            query_normalized = self._normalize(query)
            results = []

            for i, (item_text, item_data) in enumerate(self.normalized_items):
                score = fuzz.ratio(query_normalized, item_text)
                if score >= min_score:
                    results.append((self.items[i][0], item_data, score))

            # Sort by score descending
            results.sort(key=lambda x: x[2], reverse=True)
            return results[:limit]

class SearchOptimizer:
    """Main search optimization class combining multiple approaches."""
    def __init__(self):
        self.hash_index: dict[str, Any] = {}
        self.trie_index = Trie()
        self.fuzzy_index = None
        self._lock = Lock()

    def build_indices(self, items: list[tuple[str, Any]]):
        """Build all search indices from items."""
        with self._lock:
            self.hash_index = {item[0].lower(): item[1] for item in items}
            self.trie_index = Trie()
            for key, value in self.hash_index.items():
                self.trie_index.insert(key, value)
            self.fuzzy_index = FuzzySearchIndex(items)

    def exact_search(self, key: str) -> Any | None:
        """Perform exact hash-based lookup."""
        with self._lock:
            return self.hash_index.get(key.lower())

    def prefix_search(self, prefix: str) -> list[tuple[str, Any]]:
        """Perform prefix search using Trie."""
        with self._lock:
            return self.trie_index.search_prefix(prefix)

    def fuzzy_search(self, query: str, limit: int = 5, min_score: float = 60.0) -> list[tuple[str, Any, float]]:
        """Perform fuzzy search."""
        if self.fuzzy_index:
            return self.fuzzy_index.fuzzy_search(query, limit, min_score)
        return []


class RequestRunnable(QRunnable):
    """Runnable for executing HTTP requests in a thread."""

    def __init__(self, method: str, url: str, on_success=None, on_error=None, **kwargs):
        super().__init__()
        self.method = method
        self.url = url
        self.kwargs = kwargs
        self.result = None
        self.error = None
        self.on_success: Callable | None = on_success
        self.on_error: Callable | None = on_error

    def run(self):
        try:
            if self.method.lower() == 'get':
                self.result = requests.get(self.url, **self.kwargs)
            elif self.method.lower() == 'post':
                self.result = requests.post(self.url, **self.kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {self.method}")

            # Execute success callback if provided
            if self.on_success is not None:
                success_callback = self.on_success  # Capture the callback
                def success_handler():
                    if success_callback is not None:  # Re-check to satisfy Pyright
                        success_callback(self.result)
                QTimer.singleShot(0, success_handler)
        except Exception as e:
            self.error = e
            # Execute error callback if provided
            if self.on_error is not None:
                error_callback = self.on_error  # Capture the callback
                captured_error = e  # Capture the exception
                def error_handler():
                    error_callback(captured_error)
                QTimer.singleShot(0, error_handler)


def run_request_in_thread(method: str, url: str, on_success: Callable | None = None, on_error: Callable | None = None, **kwargs):
    """Run HTTP request in a separate thread using Qt's thread system."""
    runnable = RequestRunnable(method, url, on_success=on_success, on_error=on_error, **kwargs)

    # Use QThreadPool to execute the runnable
    from PySide6.QtCore import QThreadPool
    thread_pool = QThreadPool.globalInstance()
    thread_pool.start(runnable)

    return runnable  # Return the runnable to allow for potential cancellation if needed


def run_function_in_thread(func, *args, on_success: Callable | None = None, on_error: Callable | None = None, **kwargs):
    """Run a function in a separate thread."""
    def execute():
        try:
            result = func(*args, **kwargs)
            if on_success:
                on_success(result)
        except Exception as e:
            if on_error:
                on_error(e)

    thread = threading.Thread(target=execute)
    thread.daemon = True
    thread.start()
    return thread


def run_in_thread(func, *args, **kwargs):
    """Run a function in a separate thread."""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(func, *args, **kwargs)
        return future.result()


def run_in_thread_async(func, *args, callback: Callable | None = None, **kwargs):
    """Run a function in a separate thread asynchronously."""
    import threading
    def target():
        try:
            result = func(*args, **kwargs)
            if callback:
                callback(result)
        except Exception as e:
            if callback:
                callback(None)  # or handle error in callback
            logger.error(f"Error in threaded operation: {e}")

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    return thread


# Threaded search implementation using QThread for performance optimization


class ThreadedSearchWorker(QObject):
    """
    A threaded worker for performing search operations without blocking the UI.
    """
    search_started = Signal()
    search_finished = Signal(list)
    search_error = Signal(str)

    def __init__(self):
        super().__init__()
        self.search_optimizer = SearchOptimizer()
        self.games_data = []

    def set_games_data(self, games_data: list):
        """Set the games data to be searched."""
        self.games_data = games_data
        # Build indices from the games data (name, description, etc.)
        items = [(game[0], game) for game in games_data]  # game[0] is the name
        self.search_optimizer.build_indices(items)

    def execute_search(self, search_text: str, search_type: str = "auto"):
        """
        Execute search in a separate thread.

        Args:
            search_text: Text to search for
            search_type: Type of search ("exact", "prefix", "fuzzy", "auto")
        """
        try:
            self.search_started.emit()
            import time
            start_time = time.time()

            results = []

            if search_type == "exact" or (search_type == "auto" and len(search_text) > 2):
                exact_result = self.search_optimizer.exact_search(search_text)
                if exact_result:
                    results = [exact_result]
            elif search_type == "prefix":
                results = self.search_optimizer.prefix_search(search_text)
            elif search_type == "fuzzy" or search_type == "auto":
                results = self.search_optimizer.fuzzy_search(search_text, limit=20, min_score=50.0)
            else:
                # Auto-detect search type based on input
                if len(search_text) < 3:
                    results = self.search_optimizer.prefix_search(search_text)
                else:
                    # Try exact first, then fuzzy
                    exact_result = self.search_optimizer.exact_search(search_text)
                    if exact_result:
                        results = [exact_result]
                    else:
                        results = self.search_optimizer.fuzzy_search(search_text, limit=20, min_score=50.0)

            end_time = time.time()
            print(f"Search completed in {end_time - start_time:.4f} seconds")

            self.search_finished.emit(results)
        except Exception as e:
            self.search_error.emit(str(e))


class ThreadedSearch(QThread):
    """
    QThread implementation for running search operations in the background.
    """
    search_started = Signal()
    search_finished = Signal(list)
    search_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = ThreadedSearchWorker()
        self.search_text = ""
        self.search_type = "auto"
        self.games_data = []

        # Connect worker signals to thread signals
        self.worker.search_started.connect(self.search_started)
        self.worker.search_finished.connect(self.search_finished)
        self.worker.search_error.connect(self.search_error)

    def set_search_params(self, search_text: str, games_data: list, search_type: str = "auto"):
        """Set parameters for the search operation."""
        self.search_text = search_text
        self.games_data = games_data
        self.search_type = search_type

    def set_games_data(self, games_data: list):
        """Set the games data to be searched."""
        self.games_data = games_data
        self.worker.set_games_data(games_data)

    def run(self):
        """Run the search operation in the thread."""
        self.worker.execute_search(self.search_text, self.search_type)


class SearchThreadPool:
    """
    A simple thread pool for managing multiple search operations.
    """
    def __init__(self, max_threads: int = 3):
        self.max_threads = max_threads
        self.active_threads = []
        self.thread_queue = []

    def submit_search(self, search_text: str, games_data: list, search_type: str = "auto",
                     on_start: Callable | None = None, on_finish: Callable | None = None, on_error: Callable | None = None):
        """
        Submit a search operation to the pool.

        Args:
            search_text: Text to search for
            games_data: List of game data tuples to search in
            search_type: Type of search ("exact", "prefix", "fuzzy", "auto")
            on_start: Callback when search starts
            on_finish: Callback when search finishes (receives results)
            on_error: Callback when search errors (receives error message)
        """
        search_thread = ThreadedSearch()
        search_thread.set_search_params(search_text, games_data, search_type)

        # Connect callbacks if provided
        if on_start:
            search_thread.search_started.connect(on_start)
        if on_finish:
            search_thread.search_finished.connect(on_finish)
        if on_error:
            search_thread.search_error.connect(on_error)

        # Start the thread
        search_thread.start()
        self.active_threads.append(search_thread)

        # Clean up finished threads
        self.active_threads = [thread for thread in self.active_threads if thread.isRunning()]

        return search_thread
