"""
Journal Tailer Plugin - Background stream processor for Antigravity WAL.

This plugin provides non-blocking, efficient reading of journal.jsonl
with minimal overhead on the kernel.
"""

__version__ = "0.1.0"
__author__ = "Antigravity Contributors"

from .tailer import EventType, JournalEvent, JournalTailer

__all__ = [
    "JournalTailer",
    "EventType",
    "JournalEvent",
]
