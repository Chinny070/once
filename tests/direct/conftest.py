from pathlib import Path
from typing import Any, Callable

import atexit
import os
import sys
import tempfile

import pytest
from gltest.direct import loader as _gl_loader
from gltest.direct.loader import deploy_contract


# --- Windows-safe patch for gltest.direct.loader._inject_message_to_fd0 -----
# The upstream implementation writes the encoded message to a temp file, dup2s
# it onto fd 0, then immediately tries os.unlink(path). On Windows the file is
# still open through stdin, so unlink raises PermissionError [WinError 32] and
# every direct-mode test aborts before reaching contract logic. On POSIX the
# unlink succeeds because the OS defers deletion until the handle closes.
#
# Replacement writes the same bytes, performs the same dup2, but defers cleanup
# of the temp file to interpreter shutdown. Behaviour is identical on Linux and
# fixed on Windows; no semantics of the direct VM are altered.
_PENDING_TEMP_FILES: list[str] = []


@atexit.register
def _cleanup_pending_temp_files() -> None:
    for path in _PENDING_TEMP_FILES:
        try:
            os.unlink(path)
        except OSError:
            pass


def _inject_message_to_fd0_safe(vm) -> None:
    try:
        from genlayer.py import calldata
        from genlayer.py.types import Address
    except ImportError:
        return

    sender_addr = vm.sender
    if isinstance(sender_addr, bytes):
        sender_addr = Address(sender_addr)

    contract_addr = vm._contract_address
    if isinstance(contract_addr, bytes):
        contract_addr = Address(contract_addr)

    origin_addr = vm.origin
    if isinstance(origin_addr, bytes):
        origin_addr = Address(origin_addr)

    message_data = {
        "contract_address": contract_addr,
        "sender_address": sender_addr,
        "origin_address": origin_addr,
        "stack": [],
        "value": vm._value,
        "datetime": vm._datetime,
        "is_init": False,
        "chain_id": vm._chain_id,
        "entry_kind": 0,
        "entry_data": b"",
        "entry_stage_data": None,
    }

    encoded = calldata.encode(message_data)

    fd, path = tempfile.mkstemp(prefix="gltest-msg-", suffix=".bin")
    try:
        os.write(fd, encoded)
        os.lseek(fd, 0, os.SEEK_SET)
        original_stdin = os.dup(0)
        vm._original_stdin_fd = original_stdin
        os.dup2(fd, 0)
    finally:
        os.close(fd)
        if sys.platform.startswith("win"):
            _PENDING_TEMP_FILES.append(path)
        else:
            try:
                os.unlink(path)
            except OSError:
                _PENDING_TEMP_FILES.append(path)


_gl_loader._inject_message_to_fd0 = _inject_message_to_fd0_safe


@pytest.fixture
def direct_deploy(direct_vm) -> Callable[..., Any]:
    def _deploy(contract_path: str, *args: Any, **kwargs: Any) -> Any:
        path = Path(contract_path)
        if not path.is_absolute():
            path = (Path.cwd() / contract_path).resolve()
        return deploy_contract(path, direct_vm, *args, **kwargs)
    return _deploy


@pytest.fixture(autouse=True)
def _refresh_transaction_datetime(direct_vm):
    direct_vm.check_pickling = True
    original_refresh = direct_vm._refresh_gl_message

    def refresh_with_datetime():
        original_refresh()
        gl = sys.modules.get("genlayer.gl")
        if gl is not None and isinstance(getattr(gl, "message_raw", None), dict):
            gl.message_raw["datetime"] = direct_vm._datetime

    direct_vm._refresh_gl_message = refresh_with_datetime
    direct_vm._refresh_gl_message()
    yield
