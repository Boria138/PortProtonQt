from typing import TYPE_CHECKING, Any


class InputMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
