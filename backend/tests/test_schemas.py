"""Pure schema checks (no database or Redis required)."""
import pytest
from pydantic import ValidationError

from app.schemas import IngestRequest


def test_valid_batch():
    body = IngestRequest(source="CRM.Events", items=[{"external_id": "a1", "payload": {"value": 12}}])
    assert body.items[0].payload["value"] == 12
    assert body.source == "crm.events"


def test_reject_empty_items():
    with pytest.raises(ValidationError):
        IngestRequest(source="crm", items=[])


def test_reject_invalid_item():
    with pytest.raises(ValidationError):
        IngestRequest(source="crm", items=[{"payload": "not an object"}])


def test_reject_empty_payload():
    with pytest.raises(ValidationError):
        IngestRequest(source="crm", items=[{"payload": {}}])


def test_reject_extra_fields():
    with pytest.raises(ValidationError):
        IngestRequest(source="crm", items=[{"payload": {"ok": True}}], unexpected=True)


def test_reject_unsafe_source_name():
    with pytest.raises(ValidationError):
        IngestRequest(source="crm events", items=[{"payload": {"ok": True}}])
