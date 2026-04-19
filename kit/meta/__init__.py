from kit.api import link, promote

def bump():
    """Meta: Atomic increment of branch version."""
    from kit.api import get_brain
    brain = get_brain()
    # brain._increment_version needs a connection, we can use a transaction
    def _op(conn):
        brain._increment_version(conn)
    return brain._run_write_transaction(_op)

def label(node_uid: str, label_name: str):
    """Meta: Apply a semantic label to a node."""
    from kit.api import get_brain
    brain = get_brain()
    # Custom label logic or just metadata update
    # For now, let's just use metadata
    def _op(conn):
        conn.execute("UPDATE nodes SET metadata = json_set(metadata, '$.label', ?) WHERE uid = ?", (label_name, node_uid))
    return brain._run_write_transaction(_op)

__all__ = ["link", "bump", "promote", "label"]
