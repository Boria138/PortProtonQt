"""
Utility module for search optimizations including Trie, hash tables, and fuzzy matching.
"""
from collections.abc import Callable
from typing import Any
from rapidfuzz import fuzz
from threading import Lock
from portprotonqt.logger import get_logger
from PySide6.QtCore import QThread, Signal, QObject

logger = get_logger(__name__)

SEARCH_RESULT_LIMIT = 20
SEARCH_MIN_SCORE = 60.0
MIN_WORD_SEARCH_LENGTH = 3


def build_search_items(
    entries: list[Any],
    name_getter: Callable[[Any], Any],
) -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    for entry in entries:
        raw_name = name_getter(entry)
        name = str(raw_name).lower() if raw_name else ""
        items.append((name, entry))
        for word in name.split():
            if len(word) >= MIN_WORD_SEARCH_LENGTH:
                items.append((word, entry))
    return items


def search_index(
    optimizer: Any,
    search_text: str,
    limit: int = SEARCH_RESULT_LIMIT,
    min_score: float = SEARCH_MIN_SCORE,
) -> list[Any]:
    if len(search_text) < MIN_WORD_SEARCH_LENGTH:
        prefix_results = optimizer.prefix_search(search_text)
        return _unique_search_results([payload for _match_text, payload in prefix_results])

    exact_result = optimizer.exact_search(search_text)
    if exact_result:
        return [exact_result]

    prefix_results = optimizer.prefix_search(search_text)
    if prefix_results:
        return _unique_search_results([payload for _match_text, payload in prefix_results])

    fuzzy_results = optimizer.fuzzy_search(search_text, limit=limit, min_score=min_score)
    return _unique_search_results([payload for _match_text, payload, _score in fuzzy_results])


def _unique_search_results(results: list[Any]) -> list[Any]:
    unique_results: list[Any] = []
    for result in results:
        if result not in unique_results:
            unique_results.append(result)
    return unique_results


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
                score = fuzz.partial_ratio(query_normalized, item_text)
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
            logger.debug("Search completed in %.4f seconds", end_time - start_time)

            self.search_finished.emit(results)
        except Exception as e:
            logger.exception("Search failed: %s", e)
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


    def set_games_data(self, games_data: list):
        """Set the games data to be searched."""
        self.games_data = games_data
        self.worker.set_games_data(games_data)

    def run(self):
        """Run the search operation in the thread."""
        self.worker.execute_search(self.search_text, self.search_type)
