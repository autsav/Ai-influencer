"""In-memory Meta token hot-swap. Pydantic Settings is immutable; publish + refresh
read from here so a refresh takes effect without restart. Init at lifespan startup."""
import logging

log = logging.getLogger(__name__)

_token: str = ""


def init(token: str) -> None:
    global _token
    _token = token
    log.info("[token_store] initialized")


def get() -> str:
    if not _token:
        raise RuntimeError("token_store not initialized — call token_store.init() at startup")
    return _token


def update(new_token: str) -> None:
    global _token
    _token = new_token
    log.info("[token_store] token hot-swapped")
