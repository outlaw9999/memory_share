import threading
import time
from pathlib import Path

from kit.core.kit_cognitive_core import SAMBrain


def test_concurrent_learn_survives_contention(tmp_path: Path) -> None:
    brain = SAMBrain(tmp_path / "chaos.db", root_path=tmp_path)
    brain.render_context = lambda: None  # type: ignore[method-assign]

    errors: list[Exception] = []
    errors_lock = threading.Lock()

    def worker(index: int) -> None:
        try:
            brain.learn(f"entity_{index}", f"memory {index}")
        except Exception as error:  # pragma: no cover - failure path captured in assertion
            with errors_lock:
                errors.append(error)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    with brain._get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count == 20


def test_heavy_recall_stays_responsive(tmp_path: Path) -> None:
    brain = SAMBrain(tmp_path / "load.db", root_path=tmp_path)
    brain.render_context = lambda: None  # type: ignore[method-assign]

    for index in range(250):
        brain.learn(f"load_{index}", f"data {index}")

    start_time = time.perf_counter()
    results = brain.recall(["load_249"], limit=3)
    duration = time.perf_counter() - start_time

    assert duration < 1.0
    assert results
    assert any("data 249" in memory.content for memory in results)


def test_write_storm_survives_50_threads(tmp_path: Path) -> None:
    brain = SAMBrain(tmp_path / "storm.db", root_path=tmp_path)
    brain.render_context = lambda: None  # type: ignore[method-assign]

    errors: list[Exception] = []
    errors_lock = threading.Lock()

    def worker(index: int) -> None:
        try:
            brain.learn(f"storm_{index}", f"payload {index}")
        except Exception as error:  # pragma: no cover - asserted after join
            with errors_lock:
                errors.append(error)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    with brain._get_connection() as conn:
        observation_count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert observation_count == 50


def test_mixed_read_write_load_stays_consistent(tmp_path: Path) -> None:
    brain = SAMBrain(tmp_path / "mixed.db", root_path=tmp_path)
    brain.render_context = lambda: None  # type: ignore[method-assign]

    for index in range(10):
        brain.learn(f"seed_{index}", f"seed memory {index}")

    errors: list[Exception] = []
    errors_lock = threading.Lock()

    def worker(index: int) -> None:
        try:
            if index % 2 == 0:
                brain.learn(f"mixed_{index}", f"write memory {index}")
            else:
                brain.recall([f"seed_{index % 10}"], limit=3)
        except Exception as error:  # pragma: no cover - asserted after join
            with errors_lock:
                errors.append(error)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(40)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    with brain._get_connection() as conn:
        mixed_writes = conn.execute("SELECT COUNT(*) FROM observations WHERE content LIKE 'write memory %'").fetchone()[0]
    assert mixed_writes == 20


def test_duplicate_contention_preserves_node_identity(tmp_path: Path) -> None:
    brain = SAMBrain(tmp_path / "duplicate.db", root_path=tmp_path)
    brain.render_context = lambda: None  # type: ignore[method-assign]

    errors: list[Exception] = []
    errors_lock = threading.Lock()

    def worker() -> None:
        try:
            brain.learn("dup", "same content")
        except Exception as error:  # pragma: no cover - asserted after join
            with errors_lock:
                errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    with brain._get_connection() as conn:
        node_count = conn.execute("SELECT COUNT(*) FROM nodes WHERE uid = 'dup'").fetchone()[0]
        observation_count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert node_count == 1
    assert observation_count == 20
