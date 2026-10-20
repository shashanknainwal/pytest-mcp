"""Resolve the command for a third-party server under test."""

import os
import shlex
import shutil

import pytest


def server_argv(env_var: str, default: str) -> list[str]:
    """Command from ``env_var`` (or ``default``), skipping the test if it is not installed."""
    argv = shlex.split(os.environ.get(env_var) or default)
    if shutil.which(argv[0]) is None:
        pytest.skip(f"{argv[0]!r} not found; install the server or set {env_var}")
    return argv
