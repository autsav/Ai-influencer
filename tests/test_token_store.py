import pytest

from aeloria.auth import token_store


def test_get_before_init_raises():
    token_store._token = ""  # reset
    with pytest.raises(RuntimeError):
        token_store.get()


def test_init_then_get():
    token_store._token = ""
    token_store.init("abc")
    assert token_store.get() == "abc"


def test_update_hot_swaps():
    token_store.init("abc")
    token_store.update("xyz")
    assert token_store.get() == "xyz"