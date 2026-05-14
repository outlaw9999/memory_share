from pathlib import Path
from unittest.mock import patch

from kit.core.dispatcher import classify, dispatch


def test_only_explicit_commands_use_fast_path():
    """Commands outside the routing table must stay on the standard CLI path."""
    assert classify("where") == "direct"
    assert classify("init") == "standard"
    assert classify("learn") == "diagnostic"
    assert classify("unknown-command") == "standard"


def test_dispatch_unknown_command_fails_closed():
    """Unknown dispatch targets must not raise or enter a reasoning path."""
    assert dispatch("unknown-command", None) == 1


def test_fs_direct_uses_current_workspace():
    """Direct filesystem execution should stay on the zero-reasoning fast path."""
    with patch("pathlib.Path.cwd") as cwd_mock, patch("builtins.print"):
        cwd_mock.return_value = Path("E:/DEV/opensource_contrib/memory_share_kit")
        result = dispatch("where", None)

    assert result == 0
