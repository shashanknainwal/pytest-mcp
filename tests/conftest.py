import socket
import sys
from pathlib import Path

import pytest

SERVERS = Path(__file__).parent / "servers"
CALCULATOR = SERVERS / "calculator.py"
SLOPPY = SERVERS / "sloppy.py"
PYTHON = sys.executable


@pytest.fixture
def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
