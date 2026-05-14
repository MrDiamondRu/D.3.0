from __future__ import annotations

from threading import local

_state = local()


def set_current_user(user) -> None:
    _state.user = user


def get_current_user():
    return getattr(_state, "user", None)
