from kit.core.deterministic import deterministic_json

def test_deterministic_json():
    data1 = {"b": 2, "a": 1}
    data2 = {"a": 1, "b": 2}

    j1 = deterministic_json(data1)
    j2 = deterministic_json(data2)

    assert j1 == j2


def test_stable_sort_with_duplicate_uid():
    from kit.core.deterministic import stable_sort_key
    items = [
        {"uid": "A", "importance": 10, "created_at": "1", "id": 2},
        {"uid": "A", "importance": 10, "created_at": "1", "id": 1},
    ]

    sorted_items = sorted(items, key=stable_sort_key)

    assert sorted_items[0]["id"] == 1
