"""
Journal Tailer Plugin - Background stream processor for Antigravity WAL.

This plugin provides non-blocking, efficient reading of journal.jsonl
with minimal overhead on the kernel. Perfect for AI agent orchestration
where low-latency journal parsing is critical.
"""

__version__ = "0.1.0"
__author__ = "Antigravity Contributors"

from .tailer import JournalTailer

__all__ = ["JournalTailer"]
