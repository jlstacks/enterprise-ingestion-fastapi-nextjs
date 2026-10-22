from app.services import canonical_request_hash, records_cache_key


class FakeRedis:
    def __init__(self, value):
        self.value = value

    def get(self, key):
        assert key == "ingestion:records:version"
        return self.value


def test_request_hash_is_order_independent():
    first = {"source": "crm", "items": [{"payload": {"b": 2, "a": 1}}]}
    second = {"items": [{"payload": {"a": 1, "b": 2}}], "source": "crm"}
    assert canonical_request_hash(first) == canonical_request_hash(second)


def test_request_hash_changes_with_payload():
    first = {"source": "crm", "items": [{"payload": {"value": 1}}]}
    second = {"source": "crm", "items": [{"payload": {"value": 2}}]}
    assert canonical_request_hash(first) != canonical_request_hash(second)


def test_cache_key_includes_version_and_query_shape():
    assert records_cache_key(FakeRedis("7"), "crm", 20, 40) == 'ingestion:records:v7:["crm",20,40]'
    assert records_cache_key(FakeRedis(None), None, 10, 0) == 'ingestion:records:v0:[null,10,0]'
