import json
import time
import atexit
from pathlib import Path

class ReplayTracer:
    def __init__(self):
        self.commands = []
        self.signals = []
        self.calls = []
        self._exported = False
        atexit.register(self.export)

    def log_command(self, cmd_data):
        self.commands.append(cmd_data)

    def log_call(self, call_data):
        self.calls.append(call_data)

    def log_signal(self, sig_data):
        self.signals.append(sig_data)

    def export_safe(self):
        return {
            "commands": self.commands,
            "calls": self.calls,
            "signals": self.signals
        }

    def export(self):
        if self._exported:
            return
        self._exported = True
        try:
            with open("runtime_call_graph.json", "w", encoding="utf-8") as f:
                json.dump(self.export_safe(), f, indent=2)
        except Exception:
            with open("runtime_call_graph.partial.json", "w", encoding="utf-8") as f:
                json.dump(self.export_safe(), f, indent=2)

tracer = ReplayTracer()

def traced(name):
    def wrapper(fn):
        if getattr(fn, "__is_traced__", False):
            return fn

        def inner(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                tracer.log_call({
                    "node": name,
                    "status": "success",
                    "latency_ms": (time.perf_counter() - start) * 1000
                })
                return result
            except Exception as e:
                tracer.log_call({
                    "node": name,
                    "status": "error",
                    "latency_ms": (time.perf_counter() - start) * 1000,
                    "error": str(e)
                })
                raise

        inner.__is_traced__ = True
        return inner
    return wrapper
